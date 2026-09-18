#!/usr/bin/env bash
# 「仮」のオンボーディング予定を、前日 18:00 JST に自動削除する。
#
# ルール（2026-09-18 片山決定）:
#   杉浦さん(sugiura@fout.jp)が参加者に入っているオンボーディングの仮予定は、
#   どんな理由でも「確定していなければ」前日 18:00 に削除する。
#   対象は 片山(yuki.katayama@fout.jp) が作った予定のうち、未確定のものだけ。
#
# 「未確定」の判定（全部満たしたものだけ削除。迷ったら削除しない）:
#   1. creator/organizer が片山本人（他人が作った予定は絶対に触らない）
#   2. 参加者に sugiura@fout.jp が入っている
#   3. タイトルに「仮」を含む（例: `[仮] HAWKオンボーディング候補（…）` / `[作業] 仮/〇〇_…候補日`）
#      → 確定したらタイトルから「仮」を外す運用。これが「確定」の合図。
#   4. タイトルに「確定」を含まない（念のための二重ガード）
#   5. 繰り返し予定のインスタンスではない（定例会などを誤って消さない）
#   6. status が cancelled ではない
#
# 対象日は既定で「翌日(JST)」。18:00 JST に回すと「前日18時に翌日分を削除」になる。
#
# 使い方:
#   bash calendar/delete_tentative_onboarding.sh                 # 翌日分を削除
#   bash calendar/delete_tentative_onboarding.sh --dry-run       # 消す対象を表示するだけ
#   bash calendar/delete_tentative_onboarding.sh --date 2026-09-28 --dry-run
#   bash calendar/delete_tentative_onboarding.sh --send-updates all   # 参加者に取消メールを送る
#
# 出力: 1行1件 `DELETE|DRY-RUN <開始時刻> <タイトル> (<eventId>)` と末尾のサマリ。
# 終了コード: 0=正常（0件含む）, 1=削除失敗あり, 2=引数/前提エラー
set -euo pipefail

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"
PARTNER="${ONBOARDING_PARTNER:-sugiura@fout.jp}"
CALENDAR="${ONBOARDING_CALENDAR:-primary}"
MARKER='仮'
CONFIRMED_MARKER='確定'
SEND_UPDATES="${ONBOARDING_SEND_UPDATES:-none}"   # all | externalOnly | none
DRY_RUN=0
DATE=""

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--dry-run)    DRY_RUN=1; shift ;;
    --date)          DATE="$2"; shift 2 ;;
    --account)       ACCOUNT="$2"; shift 2 ;;
    --partner)       PARTNER="$2"; shift 2 ;;
    --send-updates)  SEND_UPDATES="$2"; shift 2 ;;
    -h|--help)       sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

command -v gog >/dev/null 2>&1 || { echo "gog が見つからない。先に bash setup_gog_remote.sh を実行" >&2; exit 2; }

# 対象日（JST）。既定は翌日。
if [ -z "$DATE" ]; then
  DATE=$(TZ=Asia/Tokyo date -d 'tomorrow' +%Y-%m-%d)
fi
case "$DATE" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
  *) echo "--date は YYYY-MM-DD 形式: $DATE" >&2; exit 2 ;;
esac
FROM="${DATE}T00:00:00+09:00"
TO="${DATE}T23:59:59+09:00"

echo "対象日: ${DATE} (JST) / カレンダー: ${CALENDAR} / 作成者: ${ACCOUNT} / 参加者条件: ${PARTNER} / 未確定マーカー: ${MARKER}"
[ "$DRY_RUN" -eq 1 ] && echo "(dry-run: 削除は実行しない)"

# 対象日の予定を全件取得し、条件に合うものだけ TSV で出す: id \t start \t summary
# ページングは自前で回す（gog の --all-pages は JSON 出力だと初回ページしか返さないことがある）。
CANDIDATES=$(ACCOUNT="$ACCOUNT" PARTNER="$PARTNER" MARKER="$MARKER" CONFIRMED="$CONFIRMED_MARKER" \
             CALENDAR="$CALENDAR" FROM="$FROM" TO="$TO" python3 -c '
import os, sys, json, subprocess
acct = os.environ["ACCOUNT"].lower()
partner = os.environ["PARTNER"].lower()
marker = os.environ["MARKER"]
confirmed = os.environ["CONFIRMED"]

items, token = [], None
for _ in range(50):                                # 無限ループ防止
    cmd = ["gog", "--account", os.environ["ACCOUNT"], "-j", "calendar", "events", os.environ["CALENDAR"],
           "--from", os.environ["FROM"], "--to", os.environ["TO"], "--max", "250"]
    if token:
        cmd += ["--page", token]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write("gog calendar events failed: " + out.stderr.strip()[:500] + "\n")
        sys.exit(2)
    raw = out.stdout.strip()
    d = json.loads(raw) if raw else {}
    items += d.get("events") or d.get("items") or []
    token = d.get("nextPageToken")
    if not token:
        break

for e in items:
    if e.get("status") == "cancelled":
        continue
    if e.get("recurringEventId"):
        continue                                   # 定例などの繰り返しは対象外
    creator = (e.get("creator") or {}).get("email", "").lower()
    organizer = (e.get("organizer") or {}).get("email", "").lower()
    if creator != acct or organizer != acct:
        continue                                   # 片山が作った予定のみ
    attendees = [a.get("email", "").lower() for a in e.get("attendees") or []]
    if partner not in attendees:
        continue                                   # 杉浦さんが入っている予定のみ
    summary = e.get("summary") or ""
    if marker not in summary or confirmed in summary:
        continue                                   # 「仮」が無い／「確定」がある = 確定扱い
    start = e.get("start") or {}
    start_s = start.get("dateTime") or start.get("date") or ""
    print("\t".join([e["id"], start_s, summary.replace("\t", " ")]))
') || { echo "予定の取得に失敗したため中止（削除は行っていない）" >&2; exit 2; }

if [ -z "$CANDIDATES" ]; then
  echo "対象なし（${DATE} に未確定のオンボーディング仮予定はありません）"
  exit 0
fi

deleted=0; failed=0
while IFS=$'\t' read -r id start summary; do
  [ -n "$id" ] || continue
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "DRY-RUN ${start} ${summary} (${id})"
    deleted=$((deleted+1))
    continue
  fi
  if gog --account "$ACCOUNT" calendar delete "$CALENDAR" "$id" \
        --send-updates "$SEND_UPDATES" -y --no-input >/dev/null 2>&1; then
    echo "DELETE ${start} ${summary} (${id})"
    deleted=$((deleted+1))
  else
    echo "FAILED ${start} ${summary} (${id})" >&2
    failed=$((failed+1))
  fi
done <<< "$CANDIDATES"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "サマリ: ${DATE} の削除対象 ${deleted} 件（dry-run・未実行）"
else
  echo "サマリ: ${DATE} の未確定オンボーディング仮予定を ${deleted} 件削除、失敗 ${failed} 件"
fi
[ "$failed" -eq 0 ]
