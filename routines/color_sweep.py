#!/usr/bin/env python3
"""カレンダー色分けスイープ（作業 / 対面 / meet / デフォルト の4バケツ）。

判定は決定論。変更するのは colorId だけで、タイトル・時間・出席者・公開範囲・
availability には一切触れない。--apply を付けない限り読み取りのみ。

既知の制約1: gog v0.19.0 も Google Calendar MCP も「色を既定色に戻す」ことができない
（gog は --event-color= を exit 0 のまま黙って無視し、MCP は空 colorId を拒否する）。
そのため「デフォルト」バケツは *色を付けない* と定義し、既に色が付いている場合は
触らずに要手動クリアとして報告する。

既知の制約2: 対面かオンラインかを機械的に判別する材料がカレンダーに無い（2026-08-22 実測）。
  - 会議室を押さえていてもオンライン: [オンライン社外] Regal core は TELECUBE ブース、
    [オンライン 社外] サイバーバズ加賀美さんは Lumpy Gravy 会議室から接続している
  - Meet リンクがあっても対面: 【週次】HAWK定例会、来社勉強会（サイバーバズ様）
つまり location / 会議室リソース / hangoutLink はどれも判定に使えない。
唯一の確かな手がかりはタイトル先頭の [主タグ] で、これは命名ルーティンが付ける。
タグが無い予定は「相手がいれば対面」に倒し、推定であることを必ず報告する。
"""
import argparse, json, re, subprocess, sys

ACC = "yuki.katayama@fout.jp"
DAYS = 14

# バケツ -> colorId。None = 色を付けない（既定色のまま）
COLOR = {"作業": "8", "meet": "6", "対面": "3", "デフォルト": None}

PRIVATE_RE = re.compile(
    r"私用|病院|通院|歯医者|処方箋|薬局|会食|ランチ|昼食|飲み会|呑み|ジム|キックボクシング|"
    r"美容|散髪|保育|休暇|有給", re.I)

# タイトル先頭の主タグ -> バケツ。タグがあれば実体推定より優先する。
TAG_BUCKET = {
    "作業": "作業",
    "private": "デフォルト",
    "オンライン社外": "meet", "オンライン社内": "meet", "オンライン": "meet",
    "往訪": "対面", "来訪": "対面", "社内": "対面", "社外": "対面",
}


def gog(*args, check=True):
    r = subprocess.run(["gog", "--account", ACC, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"gog {' '.join(args)} failed: {(r.stderr or r.stdout)[:300]}")
    return r


def fetch():
    r = gog("calendar", "events", "--from", "today", "--days", str(DAYS), "--all-pages", "-j")
    return json.loads(r.stdout)["events"]


def main_tag(summary):
    m = re.match(r"\s*[\[［]([^\]］]+)[\]］]", summary or "")
    if not m:
        return None
    head = m.group(1).split("/")[0].split("／")[0]
    return re.sub(r"\s+", "", head)


def classify(e):
    """(バケツ, 理由) を返す。対象外なら (None, 理由)。"""
    summary = e.get("summary", "") or ""

    if e.get("eventType", "default") != "default":
        return None, f"eventType={e.get('eventType')}"
    if e.get("workingLocationProperties"):
        return None, "勤務場所イベント"
    if e.get("status") == "cancelled":
        return None, "キャンセル済み"
    if not e.get("start", {}).get("dateTime"):
        return None, "終日予定"

    tag = main_tag(summary)
    humans = [a for a in e.get("attendees", []) if not a.get("resource") and not a.get("self")]

    # タグがあればそれが唯一の確かな手がかり。必ず優先する。
    if tag:
        b = TAG_BUCKET.get(tag) or TAG_BUCKET.get(tag.lower())
        return (b, f"タグ[{tag}]") if b else (None, f"未知のタグ[{tag}]")

    if PRIVATE_RE.search(summary):
        return "デフォルト", "私用キーワード"

    # 対面とオンラインは機械的に区別できない（下の「判定材料が無い」参照）。
    # 相手がいる予定は対面に倒す。オンラインなら命名ルーティンが [オンライン*] を付ける。
    if humans:
        return "対面", f"推定・他{len(humans)}名"
    return "作業", "推定・出席者なし"


def build_plan(events):
    plan, skip, guessed, stray = [], [], [], []
    seen_series = set()

    for e in events:
        summary = e.get("summary", "") or ""
        when = (e.get("start", {}).get("dateTime") or e.get("start", {}).get("date") or "")[:16]
        bucket, why = classify(e)

        if bucket is None:
            skip.append((when, summary, why))
            continue

        want, cur = COLOR[bucket], e.get("colorId")

        # デフォルトバケツ: 色は付けない。既に色があるなら手で消すしかないので報告だけ。
        if want is None:
            if cur:
                stray.append((when, summary, cur))
            continue

        if cur == want:
            continue

        target_id, scope = e["id"], "単発"
        if e.get("recurringEventId"):
            target_id, scope = e["recurringEventId"], "シリーズ"
            if target_id in seen_series:
                continue
            seen_series.add(target_id)

        item = {"when": when, "summary": summary, "bucket": bucket, "why": why,
                "cur": cur, "want": want, "id": target_id, "scope": scope}
        plan.append(item)
        if why.startswith("推定"):
            guessed.append(item)

    return plan, skip, guessed, stray


def apply(plan):
    ok, fail = [], []
    for p in plan:
        r = gog("calendar", "update", "primary", p["id"],
                f"--event-color={p['want']}", "--no-input", check=False)
        (ok if r.returncode == 0 else fail).append(p)
        if r.returncode != 0:
            p["error"] = (r.stderr or r.stdout).strip()[:200]
    return ok, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="実際に色を書き込む")
    a = ap.parse_args()

    events = fetch()
    plan, skip, guessed, stray = build_plan(events)

    print(f"取得 {len(events)}件 / 変更対象 {len(plan)}件 / 対象外 {len(skip)}件")

    if not a.apply:
        for p in plan:
            print(f"  DRY {p['when']} →{p['bucket']} {p['cur'] or '-'}→{p['want']} "
                  f"({p['why']}) {p['summary'][:40]}")
        return 0

    ok, fail = apply(plan)

    # 書いたら必ず読み返して検証する（gog が黙って無視する系のバグを検出するため）
    after = {e.get("recurringEventId") or e["id"]: e.get("colorId") for e in fetch()}
    unverified = [p for p in ok if after.get(p["id"]) != p["want"]]

    print(f"適用 {len(ok)}件 / 失敗 {len(fail)}件 / 反映されなかった {len(unverified)}件")
    for p in ok:
        print(f"  OK   {p['when']} →{p['bucket']} {p['cur'] or '-'}→{p['want']} {p['summary'][:40]}")
    for p in fail:
        print(f"  FAIL {p['when']} {p['summary'][:40]} :: {p.get('error','')}")
    for p in unverified:
        print(f"  未反映 {p['when']} {p['summary'][:40]}（要確認）")
    if guessed:
        print(f"\n推定で決めた {len(guessed)}件（タグが無いので実体から判定）:")
        for p in guessed:
            print(f"  ? {p['when']} →{p['bucket']} ({p['why']}) {p['summary'][:40]}")
    if stray:
        print(f"\n私用なのに色が残っている {len(stray)}件（APIで解除できないため手動クリア）:")
        for when, summary, cur in stray:
            print(f"  ! {when} 色{cur} {summary[:40]}")

    return 1 if (fail or unverified) else 0


if __name__ == "__main__":
    sys.exit(main())
