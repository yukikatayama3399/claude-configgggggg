#!/usr/bin/env bash
# ============================================================
# inventory_mac_routines.sh — Mac ローカルの scheduled-tasks を棚卸しする
#
# 読み取りのみ。何も変更しない。
#
# 出したいもの:
#   ・定義が何個あって、それぞれ何のファイルを持っているか
#   ・cron に登録されているか（登録が無い＝Claude Code 側のスケジューラ頼み）
#   ・~/.claude/logs にログがあるか（このルーティン群は Claude Code 内部の
#     スケジューラで動くため基本残らない。無くても停止の根拠にはならない）
#   ・gog を --account 無しで呼んでいないか（既定アカウントが個人 Gmail のため事故る）
#   ・クラウドの Routine と名前が重複していないか（二重実行の検出）
#
# 使い方: bash inventory_mac_routines.sh
#         bash inventory_mac_routines.sh > /tmp/inventory.txt   # 貼り付け用
# ============================================================
set -uo pipefail

TASKS_DIR="${HOME}/.claude/scheduled-tasks"
LOG_DIR="${HOME}/.claude/logs"

# クラウド側で enabled になっている Routine 名（2026-08-05 の list_triggers 実データ）。
# Mac 側と名前が当たると二重実行の疑いがある。
CLOUD_ROUTINES="hawk-url-index-original-refresh
daily-calendar-free-sweep"

echo "=============================================="
echo "Mac ローカル scheduled-tasks 棚卸し"
echo "  日時: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  対象: $TASKS_DIR"
echo "=============================================="

[ -d "$TASKS_DIR" ] || { echo "定義ディレクトリが無い: $TASKS_DIR"; exit 1; }

CRON="$(crontab -l 2>/dev/null || true)"

# ---- 一覧 ----
printf '\n%-42s %-6s %-8s %-12s %s\n' "タスク名" "cron" "gog" "最終ログ" "備考"
printf '%s\n' "----------------------------------------------------------------------------------------------------"

TOTAL=0; IN_CRON=0; NO_LOG=0; GOG_BARE=0

for entry in "$TASKS_DIR"/*; do
  [ -e "$entry" ] || continue
  name="$(basename "$entry")"
  name="${name%.md}"
  TOTAL=$((TOTAL+1))

  # cron に名前が出てくるか
  if printf '%s' "$CRON" | grep -q -- "$name"; then
    cron_mark="あり"; IN_CRON=$((IN_CRON+1))
  else
    cron_mark="—"
  fi

  # gog の呼び出し。--account / -a のどちらも無い行があるか
  gog_mark="—"
  if grep -rq --include='SKILL.md' --include='*.sh' 'gog ' "$entry" 2>/dev/null; then
    # アカウント指定は --account / -a の両方。-a はバッククォート直後にも現れるので
    # 直前がスペースであることを前提にしない。
    if grep -rq --include='SKILL.md' --include='*.sh' -E -- '--account|[^-[:alnum:]]-a[ =]' "$entry" 2>/dev/null; then
      gog_mark="ok"
    else
      gog_mark="要確認"; GOG_BARE=$((GOG_BARE+1))
    fi
  fi

  # 最終ログ。ログが無い＝一度も走っていない可能性
  logf="$(ls -t "$LOG_DIR/$name"*.log 2>/dev/null | head -1)"
  if [ -n "$logf" ]; then
    last="$(date -r "$logf" '+%m-%d %H:%M' 2>/dev/null || echo '?')"
  else
    last="-"; NO_LOG=$((NO_LOG+1))
  fi

  # クラウドの Routine と名前が当たるか
  note=""
  if printf '%s\n' "$CLOUD_ROUTINES" | grep -qx -- "$name"; then
    note="クラウドにも同名Routineあり(二重実行の疑い)"
  fi

  printf '%-42s %-6s %-8s %-12s %s\n' "$name" "$cron_mark" "$gog_mark" "$last" "$note"
done

echo ""
echo "=============================================="
echo "集計"
echo "=============================================="
echo "  定義の総数            : $TOTAL"
echo "  crontab に出てくるもの : $IN_CRON"
echo "  ~/.claude/logs にログ無し : $NO_LOG"
echo "  gog を素で呼ぶ疑い     : $GOG_BARE"
echo ""
echo "  注: このルーティン群は crontab ではなく Claude Code 内部のスケジューラで"
echo "      発火する(Claude Code 起動中のみ)。ログは ~/.claude/logs に残らないため、"
echo "      「-」は停止の根拠にならない。実際の発火は Slack DM 等で確認すること。"

# ---- gog を --account 無しで呼んでいる箇所の実物 ----
echo ""
echo "=============================================="
echo "gog を --account 無しで呼んでいる行（実物）"
echo "=============================================="
echo "  既定アカウントは個人 Gmail なので、ここに出る行は 403 になりうる。"
echo "  SKILL.md と *.sh のみを見る(LEARNINGS.md は過去ログなので対象外)。"
echo ""
grep -rn --include='SKILL.md' --include='*.sh' 'gog ' "$TASKS_DIR" 2>/dev/null \
  | grep -v -E -- '--account|[^-[:alnum:]]-a[ =]' \
  | sed "s|$TASKS_DIR/||" | head -40 \
  || echo "  (該当なし)"

# ---- ログの新しい順 ----
echo ""
echo "=============================================="
echo "ログの更新が新しい順（実際に動いているもの）"
echo "=============================================="
if [ -d "$LOG_DIR" ]; then
  ls -lt "$LOG_DIR"/*.log 2>/dev/null | head -20 | awk '{print "  "$6" "$7" "$8"  "$9}' \
    || echo "  (ログなし)"
else
  echo "  ログディレクトリが無い: $LOG_DIR"
fi

echo ""
echo "=============================================="
echo "crontab の中身"
echo "=============================================="
printf '%s\n' "${CRON:-  (空)}" | sed 's/^/  /'
