#!/usr/bin/env bash
# 議事録（Gemini自動メモ等）に手で追記した「共有事項メモ」を横断的に拾い上げる。
#
# 仕組み:
#   自動生成議事録に人間が追記した行のうち、マーカー（既定: 【共有】）で始まる行を
#   「週報で全体共有する特別な事項」として扱い、直近 N 日に更新された Doc から集める。
#
# 出力: Markdown（標準出力）。週報下書きにそのまま貼れる形。
#   ■ <Doc名> (<最終更新日>)
#   ・<マーカーを除いた本文>
#   出典: <DocのURL>
#
# 読み取り専用。Doc への書き込みは一切しない（書き込みは呼び出し側=週報ルーティンが行う）。
#
# 使い方:
#   bash weekly/collect_shared_notes.sh                # 直近8日・マーカー【共有】
#   bash weekly/collect_shared_notes.sh --days 14
#   bash weekly/collect_shared_notes.sh --marker '★共有'
set -euo pipefail

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"
DAYS=8
MARKER='【共有】'

while [ $# -gt 0 ]; do
  case "$1" in
    --days)    DAYS="$2"; shift 2 ;;
    --marker)  MARKER="$2"; shift 2 ;;
    --account) ACCOUNT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

CUTOFF=$(date -u -d "${DAYS} days ago" +%Y-%m-%dT%H:%M:%SZ)

# 候補 Doc を2系統で探して union する。
#  a) 本文にマーカーを含む Doc（fullText 検索。追記直後は索引が遅れることがある）
#  b) 直近更新の自動生成議事録（本文に 'Gemini' を含む: Gemini メモは末尾定型文で必ず引っかかる）
# title contains は CJK で効かないため使わない（既存 Routine と同じ理由）。
q_common="mimeType = 'application/vnd.google-apps.document' and trashed = false and modifiedTime > '${CUTOFF}'"
search() {
  gog --account "$ACCOUNT" -j drive search "$1" 2>/dev/null \
    | python3 -c 'import sys,json
d=json.load(sys.stdin)
for f in d.get("files",[]):
    print("\t".join([f["id"], f.get("modifiedTime",""), f.get("name","")]))'
}

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
{
  search "fullText contains '${MARKER}' and ${q_common}" || true
  search "fullText contains 'Gemini' and ${q_common}"    || true
} | sort -u -t$'\t' -k1,1 > "$TMP"

found=0
while IFS=$'\t' read -r id mtime name; do
  [ -n "$id" ] || continue
  body=$(gog --account "$ACCOUNT" docs cat "$id" 2>/dev/null) || continue
  hits=$(printf '%s\n' "$body" | MARKER="$MARKER" python3 -c '
import os, sys
m = os.environ["MARKER"]
for line in sys.stdin:
    if m in line:
        # マーカー以降を項目化（行頭以外にマーカーがある行も以降だけ拾う）
        print("・" + line.split(m, 1)[1].strip(" 　\n"))
' || true)
  [ -n "$hits" ] || continue
  found=1
  echo "■ ${name} (更新: ${mtime%%T*})"
  printf '%s\n' "$hits"
  echo "出典: https://docs.google.com/document/d/${id}/edit"
  echo
done < "$TMP"

if [ "$found" -eq 0 ]; then
  echo "（直近${DAYS}日の議事録に ${MARKER} 付きの追記はありません）"
fi
