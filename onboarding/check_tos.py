#!/usr/bin/env python3
"""HAWK オンボーディング予定のうち、利用規約の同意（Web申込）が未取得の会社を洗い出す。

運用ルール: 利用規約の同意＝Web申込フォームの送信が済んでいない会社は、
オンボーディングで広告アカウントのつなぎ込みができない。日程だけ先に確定して
同意依頼を送り忘れると当日に何もできないので、予定と申込記録を突き合わせて
未取得をアラートとして出す。

  予定   : カレンダー(primary)の今日から N 日のうち、タイトルに
           オンボ / ボーディング / つなぎ込み / 繋ぎ込み を含む社外予定
  申込記録: 【HAWK】Web申込リスト の「申込リスト」タブ（会社名=C列 / メール=E,F列）

判定（迷ったらアラート側に倒す。取得済みと誤判定するのが一番まずい）:
  ✅ 取得済み … 社名を正規化して完全一致、または先方参加者のメールドメインが申込者と一致
  ⚠️ 要確認   … 社名の部分一致しかない（別会社の可能性）
  🚨 未取得   … どれにも当たらない

読み取り専用。メール送信・シート書き込みはしない。

使い方:
  python3 onboarding/check_tos.py              # 今日から30日
  python3 onboarding/check_tos.py --days 14
  python3 onboarding/check_tos.py --quiet      # アラートが無ければ何も出さない

終了コード: 0=アラートなし / 1=未取得・要確認あり / 2=取得失敗
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import unicodedata

ACCOUNT = os.environ.get("GOG_ACCOUNT", "yuki.katayama@fout.jp")
APPLY_SHEET = "1VuZS0aUUG5_r7gIttrofpdAWDY0JRQRUSf2n7p6oJmo"  # 【HAWK】Web申込リスト
APPLY_RANGE = "申込リスト!A1:W"
JST = dt.timezone(dt.timedelta(hours=9))

ONBOARD_RE = re.compile(r"オンボ|ボーディング|つなぎ込|繋ぎ込|ツナギコミ", re.I)
# 社内の準備・仮押さえはオンボーディング本体ではない
INTERNAL_RE = re.compile(r"^\s*\[作業\]|社内|仮/|仮押さえ|候補|事前")
OWN_DOMAINS = {"fout.jp", "gmail.com", "group.calendar.google.com", "resource.calendar.google.com"}
LEGAL = ["株式会社", "有限会社", "合同会社", "(株)", "㈱", "(有)", "㈲"]


def gog(*args):
    out = subprocess.run(
        ["gog", "--account", ACCOUNT, "-j", *args],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError(f"gog {' '.join(args[:3])} failed: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def key(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s+", "", s)
    for lg in LEGAL:
        s = s.replace(unicodedata.normalize("NFKC", lg), "")
    s = re.sub(r"様$", "", s)
    return re.sub(r"[-_.,・'’]", "", s).lower()


def company_names(summary, description):
    """予定タイトル（と説明文の見出し）から先方社名の候補を取る。"""
    names = []
    pats = [
        r"確定[_＿](.+?)様",              # [オンライン社外] 確定_viviON様_HAWKオンボーディング
        r"\]\s*(.+?)\s+-\s+HAWK",         # [オンライン社外] gaaboo - HAWKオンボーディング（つなぎ込み）
        r"([^\s_＿\]】/／]+?)様",          # 〇〇様_HAWK…
    ]
    for p in pats:
        m = re.search(p, summary)
        if m:
            names.append(m.group(1))
    m = re.search(r"【(?:株式会社)?\s*(.+?)様", re.sub(r"<[^>]+>", "", description or ""))
    if m:
        names.append(m.group(1))
    return [n for n in dict.fromkeys(n.strip() for n in names) if key(n)]


def domains(emails):
    out = set()
    for e in emails:
        for part in re.split(r"[,\s]+", e or ""):
            if "@" in part:
                out.add(part.rsplit("@", 1)[1].lower())
    return out - OWN_DOMAINS


def load_applications():
    d = gog("sheets", "get", APPLY_SHEET, APPLY_RANGE)
    rows = d.get("values", d) if isinstance(d, dict) else d
    apps = []
    for r in rows[1:]:
        r = list(r) + [""] * 6
        if not r[2]:
            continue
        apps.append({
            "date": r[0], "no": r[1], "company": r[2],
            "key": key(r[2]), "domains": domains([r[4], r[5]]),
        })
    return apps


def load_events(days):
    today = dt.datetime.now(JST).date()
    d = gog("calendar", "events", "--from", today.isoformat(),
            "--to", (today + dt.timedelta(days=days)).isoformat(),
            "--max", "250", "--all-pages")
    evs = []
    for e in d.get("events", []):
        s = e.get("summary") or ""
        if not ONBOARD_RE.search(s) or INTERNAL_RE.search(s):
            continue
        if e.get("status") == "cancelled":
            continue
        start = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date")
        evs.append({
            "summary": s, "start": start,
            "names": company_names(s, e.get("description")),
            "domains": domains(a.get("email") for a in e.get("attendees", [])),
        })
    return evs


def judge(ev, apps):
    keys = [key(n) for n in ev["names"]]
    for a in apps:
        if a["key"] in keys or (ev["domains"] & a["domains"]):
            return "ok", a
    for a in apps:
        if any(k and (k in a["key"] or a["key"] in k) for k in keys):
            return "maybe", a
    return "missing", None


def fmt_start(s):
    try:
        t = dt.datetime.fromisoformat(s).astimezone(JST)
        return t.strftime("%m/%d(") + "月火水木金土日"[t.weekday()] + t.strftime(") %H:%M")
    except (TypeError, ValueError):
        return s or "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    try:
        apps = load_applications()
        evs = load_events(args.days)
    except Exception as e:  # noqa: BLE001 — 取得失敗は「確認できなかった」として呼び出し側に返す
        print(f"[tos-check] 取得失敗: {e}", file=sys.stderr)
        return 2

    alerts, oks = [], []
    for ev in sorted(evs, key=lambda x: x["start"] or ""):
        st, a = judge(ev, apps)
        name = ev["names"][0] if ev["names"] else "(社名不明)"
        when = fmt_start(ev["start"])
        if st == "ok":
            oks.append(f"✅ {when} {name} … 規約同意済み（{a['date'][:10]} 申込 {a['no']}）")
        elif st == "maybe":
            alerts.append(f"⚠️ {when} {name} … 要確認: 申込リストに似た社名「{a['company']}」のみ。同一社か確認")
        else:
            alerts.append(f"🚨 {when} {name} … 利用規約の同意が未取得。当日までに同意依頼メールを送る")

    if args.quiet and not alerts:
        return 0
    print(f"## オンボーディング前の利用規約チェック（今日から{args.days}日）")
    if not evs:
        print("対象のオンボーディング予定はありません。")
    for line in alerts + oks:
        print(line)
    if alerts:
        print("\n→ 同意依頼の文面は .claude/skills/onboarding-tos-gate/SKILL.md のテンプレを使う。")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
