#!/usr/bin/env bash
#
# 週次報告 Doc の find-or-create（upsert）ヘルパー。
#
# 目的:
#   週次報告ドラフトの自動生成が「毎回 Doc を新規作成する」と、
#   事前に人手で書き込んだ申し送り（■ 0. 先行メモ）が捨てられてしまう。
#   このスクリプトで「同名の Doc があればそれを使う／無ければ作る」に寄せる。
#
# 使い方:
#   ./weekly_report_doc.sh 2026-08-14               # docId を出力（無ければ作る）
#   ./weekly_report_doc.sh 2026-08-14 --no-create   # docId を出力（無ければ exit 3）
#   ./weekly_report_doc.sh 2026-08-14 --carryover   # 既存 Doc の「■ 0. 先行メモ」だけ出力
#   ./weekly_report_doc.sh 2026-08-14 --reset-body  # ヘッダと■0を残して以降を削除し、挿入位置を出力
#
# 日付は「その週の金曜日」を YYYY-MM-DD で渡す（既存 Doc の命名規則に合わせる）。
#
# 推奨フロー（■0 のハイパーリンクを壊さない）:
#   ID=$(./weekly_report_doc.sh "$D")
#   IDX=$(./weekly_report_doc.sh "$D" --reset-body)   # ■1 以降だけ消す
#   gog --account ... docs insert "$ID" -f draft.txt --index "$IDX"
# docs clear は使わないこと。docs cat はリンクを落とすので、
# 「cat して作り直す」と ■0 のリンクが平文に戻る。
#
set -euo pipefail

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"
# 11_週次mtg用報告メモ / Yuki
PARENT_FOLDER="${WEEKLY_REPORT_FOLDER:-1F70c4D3EuWR14kefYyKCiEw4Wy9Jzvvk}"
CARRYOVER_HEADING="■ 0. 先行メモ"

usage() {
  sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

DATE="${1:-}"
MODE="${2:-ensure}"
[[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || usage

NAME="週次報告_${DATE}_片山"

find_doc() {
  gog --account "$ACCOUNT" drive search "name = '${NAME}' and trashed = false" \
    --raw-query -j 2>/dev/null \
    | python3 -c '
import sys, json
try:
    files = json.load(sys.stdin).get("files", [])
except Exception:
    files = []
docs = [f for f in files if f.get("mimeType") == "application/vnd.google-apps.document"]
print(docs[0]["id"] if docs else "")
'
}

DOC_ID="$(find_doc)"

case "$MODE" in
  --carryover)
    # 既存 Doc から「■ 0. 先行メモ」ブロックを抜き出す。
    # 次の区切り線（─────）＋見出し（■ 1. 〜）の直前までを1ブロックとみなす。
    [[ -n "$DOC_ID" ]] || exit 0
    gog --account "$ACCOUNT" docs cat "$DOC_ID" 2>/dev/null \
      | python3 -c '
import sys, re
heading = """'"$CARRYOVER_HEADING"'"""
lines = sys.stdin.read().splitlines()
start = next((i for i, l in enumerate(lines) if l.startswith(heading)), None)
if start is None:
    sys.exit(0)
# 見出しの直前の区切り線から取り込む
if start > 0 and lines[start - 1].startswith("─"):
    start -= 1
end = len(lines)
for i in range(start + 2, len(lines)):
    if re.match(r"^■ [1-9]", lines[i]):
        # 見出しの直前の区切り線は次セクションのものなので手前で切る
        end = i - 1 if i > 0 and lines[i - 1].startswith("─") else i
        break
print("\n".join(lines[start:end]).rstrip())
'
    ;;
  --no-create)
    [[ -n "$DOC_ID" ]] || exit 3
    echo "$DOC_ID"
    ;;
  --reset-body)
    # ヘッダと「■ 0. 先行メモ」は残し、「■ 1.」以降を削除する。
    # 削除後、生成本文を挿入すべきインデックスを標準出力に出す。
    [[ -n "$DOC_ID" ]] || { echo "Doc が見つかりません: $NAME" >&2; exit 3; }
    START="$(gog --account "$ACCOUNT" docs raw "$DOC_ID" 2>/dev/null | python3 -c '
import sys, json, re
doc = json.load(sys.stdin)
paras = []
for e in doc["body"]["content"]:
    p = e.get("paragraph")
    if not p:
        continue
    txt = "".join(r.get("textRun", {}).get("content", "") for r in p["elements"])
    paras.append((e["startIndex"], e["endIndex"], txt))
idx = next((i for i, (_, _, t) in enumerate(paras) if re.match(r"^■ 1[.．]", t)), None)
if idx is None:
    print("")           # ■1 が無い＝新規同然。呼び出し側で末尾追記に倒す
    sys.exit(0)
if idx > 0 and paras[idx - 1][2].startswith("─"):
    idx -= 1            # 直前の区切り線ごと消す
print(f"{paras[idx][0]} {paras[-1][1]}")
')"
    if [[ -z "$START" ]]; then
      # 本文がまだ無い Doc。末尾に追記させる。
      gog --account "$ACCOUNT" docs raw "$DOC_ID" 2>/dev/null \
        | python3 -c 'import sys, json; print(json.load(sys.stdin)["body"]["content"][-1]["endIndex"] - 1)'
      exit 0
    fi
    read -r S E <<<"$START"
    # 本文末尾の改行は消せないので end-1 まで
    gog --account "$ACCOUNT" docs delete "$DOC_ID" --start "$S" --end "$((E - 1))" -y >/dev/null
    echo "$S"
    ;;
  ensure)
    if [[ -z "$DOC_ID" ]]; then
      DOC_ID="$(gog --account "$ACCOUNT" docs create "$NAME" --parent "$PARENT_FOLDER" -j 2>/dev/null \
        | python3 -c 'import sys, json; print(json.load(sys.stdin).get("id", ""))')"
      [[ -n "$DOC_ID" ]] || { echo "docs create に失敗しました: $NAME" >&2; exit 1; }
    fi
    echo "$DOC_ID"
    ;;
  *)
    usage
    ;;
esac
