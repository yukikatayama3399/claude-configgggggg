#!/usr/bin/env python3
# ============================================================
# メール追いかけリスト（返信待ち／要返信）を作る
#
#   python3 gmail/followup_report.py --days 60
#
# 「送ったのに返ってきていない」「相手から返ってきたのに返していない」
# スレッドだけを抜き出す。一斉送信（同じ件名が大量にあるもの）と
# 自動通知は除外するので、人力で追う価値があるものだけが残る。
#
# 前提: gog と gws がセットアップ済み（SessionStart フックが自動で行う）。
#   - スレッド一覧の取得は gog gmail search
#   - スレッド内の宛先/差出人の取得は gws gmail users threads get
# 読み取り専用。送信も下書き作成も一切しない。
# ============================================================
import argparse
import datetime
import email.utils
import json
import subprocess
import sys

ME = "yuki.katayama@fout.jp"
# 自社ドメイン。相手先の判定から除く
INTERNAL_DOMAINS = {"fout.jp"}
# 件名に含まれていたら自動通知とみなして捨てる
NOISE_SUBJECT_MARKERS = (
    "予約が完了しました:",
    "Delivery Status Notification",
    "Undeliverable:",
    "招待:",
    "更新された招待:",
    "キャンセルされた予定:",
    "unsubscribe",
)
# ラベルにこれが付いていたら捨てる
NOISE_LABELS = {"TRASH", "SPAM", "DRAFT", "ゴミ箱", "メルマガ・通知", "カレンダー通知"}


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"failed: {' '.join(cmd)}\n{p.stderr[:500]}")
    return p.stdout


def fetch_sent_threads(account, days, max_pages):
    """gog gmail search をページ送りして、送信を含むスレッドの一覧を集める。"""
    threads, token = {}, None
    for i in range(max_pages):
        cmd = ["gog", "-a", account, "-j", "gmail", "search",
               f"in:sent -in:chats newer_than:{days}d", "--max", "100"]
        if token:
            cmd += ["--page", token]
        try:
            data = json.loads(run(cmd) or "{}")
        except (RuntimeError, json.JSONDecodeError) as e:
            print(f"[warn] page {i + 1} を取得できず打ち切り: {e}", file=sys.stderr)
            break
        page = data.get("threads") or []
        for t in page:
            threads[t["id"]] = t
        print(f"[info] page {i + 1}: {len(page)} 件 (累計 {len(threads)})", file=sys.stderr)
        token = data.get("nextPageToken")
        if not token or not page:
            break
    return list(threads.values())


def is_noise(t, bulk_subjects):
    subject = t.get("subject") or ""
    if not subject.strip() or subject.strip().lower() == "test":
        return True
    if subject in bulk_subjects:
        return True
    if any(m.lower() in subject.lower() for m in NOISE_SUBJECT_MARKERS):
        return True
    if NOISE_LABELS & set(t.get("labels") or []):
        return True
    return False


def fetch_thread_detail(account, tid):
    params = json.dumps({
        "userId": "me", "id": tid, "format": "metadata",
        "metadataHeaders": ["To", "From", "Cc", "Subject", "Date"],
    }, ensure_ascii=False)
    return json.loads(run(["gws", "gmail", "users", "threads", "get", "--params", params]))


def header(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def counterparts(msgs):
    """スレッドに出てくる社外アドレスを集める（自動送信元は除く）。"""
    found = set()
    for m in msgs:
        for field in ("From", "To", "Cc"):
            for _, addr in email.utils.getaddresses([header(m, field)]):
                if "@" not in addr:
                    continue
                domain = addr.split("@")[1].lower()
                if domain in INTERNAL_DOMAINS or domain.endswith("googlemail.com"):
                    continue
                found.add(addr.lower())
    return sorted(found)


def is_ours(msg):
    """差出人が自社（自分または社内の同席者）かどうか。"""
    for _, addr in email.utils.getaddresses([header(msg, "From")]):
        if "@" in addr and addr.split("@")[1].lower() in INTERNAL_DOMAINS:
            return True
    return False


def classify(msgs):
    """誰にボールがあるかを判定する。社内の誰かが返していれば自社側の返信として扱う。"""
    if any("mailer-daemon" in header(m, "From").lower()
           or "Delivery Status Notification" in header(m, "Subject")
           or header(m, "Subject").startswith("Undeliverable:") for m in msgs):
        return "配信不能"
    if not any(not is_ours(m) for m in msgs):
        return "未返信"
    return "返信待ち" if is_ours(msgs[-1]) else "要返信"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default=ME)
    ap.add_argument("--days", type=int, default=60, help="遡る日数")
    ap.add_argument("--min-age", type=int, default=3,
                    help="最終やり取りからこの日数以上経ったものだけ出す")
    ap.add_argument("--bulk-threshold", type=int, default=10,
                    help="同じ件名がこの件数以上あれば一斉送信とみなして除外")
    ap.add_argument("--max-pages", type=int, default=12)
    ap.add_argument("--json", action="store_true", help="Markdown ではなく JSON で出す")
    args = ap.parse_args()

    threads = fetch_sent_threads(args.account, args.days, args.max_pages)
    if not threads:
        print("対象スレッドが取得できませんでした。", file=sys.stderr)
        return 1

    subject_counts = {}
    for t in threads:
        s = t.get("subject") or ""
        subject_counts[s] = subject_counts.get(s, 0) + 1
    bulk_subjects = {s for s, n in subject_counts.items() if n >= args.bulk_threshold}
    print(f"[info] 一斉送信として除外する件名: {len(bulk_subjects)} 種", file=sys.stderr)

    today = datetime.datetime.now(datetime.timezone.utc)
    rows = []
    survivors = [t for t in threads if not is_noise(t, bulk_subjects)]
    print(f"[info] 個別やり取りの候補: {len(survivors)} 件。詳細を取得します", file=sys.stderr)

    for t in survivors:
        try:
            detail = fetch_thread_detail(args.account, t["id"])
        except RuntimeError as e:
            print(f"[warn] {t['id']} の詳細取得に失敗: {e}", file=sys.stderr)
            continue
        msgs = sorted(detail.get("messages") or [], key=lambda m: int(m["internalDate"]))
        if not msgs:
            continue
        parties = counterparts(msgs)
        if not parties:
            continue  # 自分宛だけのメモ・自動レポートなど
        last = msgs[-1]
        last_dt = datetime.datetime.fromtimestamp(int(last["internalDate"]) / 1000,
                                                 datetime.timezone.utc)
        age = (today - last_dt).days
        if age < args.min_age:
            continue
        inbound = [m for m in msgs if not is_ours(m)]
        last_in = None
        if inbound:
            last_in = datetime.datetime.fromtimestamp(
                int(inbound[-1]["internalDate"]) / 1000, datetime.timezone.utc)
        rows.append({
            "state": classify(msgs),
            "age_days": age,
            "last": last_dt.strftime("%Y-%m-%d"),
            "last_inbound": last_in.strftime("%Y-%m-%d") if last_in else "",
            "messages": len(msgs),
            "domains": sorted({p.split("@")[1] for p in parties}),
            "counterparts": parties,
            "subject": header(msgs[0], "Subject"),
            "snippet": (last.get("snippet") or "")[:120],
            "thread_id": t["id"],
            "url": f"https://mail.google.com/mail/u/0/#all/{t['id']}",
        })

    order = {"要返信": 0, "配信不能": 1, "未返信": 2, "返信待ち": 3}
    rows.sort(key=lambda r: (order.get(r["state"], 9), -r["age_days"]))

    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0

    print(f"# メール追いかけリスト（{datetime.date.today()} 時点 / 直近{args.days}日）\n")
    print(f"対象 {len(rows)} 件（要返信 "
          f"{sum(1 for r in rows if r['state'] == '要返信')} / 配信不能 "
          f"{sum(1 for r in rows if r['state'] == '配信不能')} / 未返信 "
          f"{sum(1 for r in rows if r['state'] == '未返信')} / 返信待ち "
          f"{sum(1 for r in rows if r['state'] == '返信待ち')}）\n")
    print("| 状態 | 経過 | 相手 | 件名 | 最終 | 通数 | Gmail |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['state']} | {r['age_days']}日 | {','.join(r['domains'])} "
              f"| {r['subject'][:40]} | {r['last']} | {r['messages']} "
              f"| [開く]({r['url']}) |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
