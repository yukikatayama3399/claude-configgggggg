#!/usr/bin/env bash
# ============================================================
# install_sns_event_radar.sh — sns-event-radar を Mac に配置する
#
# 他のルーティンと同じ <名前>/SKILL.md のディレクトリ形式で、
# iCloud（マスター）と ~/.claude/scheduled-tasks（実行用）の両方に置く。
#
# 2026-08-07: 最初はベタ置きの .md を案内してしまい、形式違いで登録されず
# 2日間まったく発火しなかった。その再発防止として手順をスクリプト化した。
#
# 使い方:
#   bash patches/install_sns_event_radar.sh
#
# 既存があれば .bak-<日時> に退避してから上書きする。
# ============================================================
set -euo pipefail

NAME="sns-event-radar"
SRC="$(cd "$(dirname "$0")/.." && pwd)/routines/$NAME"
ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Claude/scheduled-tasks"
LOCAL="$HOME/.claude/scheduled-tasks"
STAMP="$(date +%Y%m%d%H%M%S)"

[ -d "$SRC" ] || { echo "!! 配置元が無い: $SRC"; exit 1; }
[ -f "$SRC/SKILL.md" ] || { echo "!! SKILL.md が無い: $SRC"; exit 1; }

install_to() {
  local dest_root="$1" label="$2"
  if [ ! -d "$dest_root" ]; then
    echo "-- $label: 親ディレクトリが無いのでスキップ ($dest_root)"
    return
  fi
  local dest="$dest_root/$NAME"
  if [ -d "$dest" ]; then
    mv "$dest" "$dest.bak-$STAMP"
    echo "-- $label: 既存を退避 → $dest.bak-$STAMP"
  fi
  cp -R "$SRC" "$dest"
  echo "OK $label: $dest"
}

install_to "$ICLOUD" "iCloud(マスター)"
install_to "$LOCAL"  "ローカル(実行用)"

echo ""
echo "=== 確認 ==="
for root in "$ICLOUD" "$LOCAL"; do
  [ -d "$root/$NAME" ] && ls "$root/$NAME" | sed "s|^|  $root/$NAME/|"
done

echo ""
echo "=== 次にやること ==="
echo "1. Claude Code に登録を依頼する:"
echo "   「sns-event-radar を cron 0 8 * * *（Asia/Tokyo）のルーティンとして登録して」"
echo "2. 登録後、初回だけ手動実行して権限承認を通す"
echo "   （WebFetch / Slack MCP / Bash(gog)。飛ばすと無人実行時に権限待ちで止まる）"
echo "3. 翌朝 8:00 に DM が届けば完了"
