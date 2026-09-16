#!/usr/bin/env bash
# PreToolUse(Bash) ガード。
#
# 運用ルール（2026-09-16 決定）: 作業は基本的に許可なく進める（dontAsk）が、
# 「メール送信」と「Slack 投稿」だけは必ず人の確認を挟む。
#
# permissions.ask は MCP ツール名では効くが、gog / gws / curl を Bash から
# 叩く経路は素通りしてしまう。CLAUDE.md の方針上 Google Workspace 操作は
# gog が主経路なので、実際にメールが飛ぶのはむしろこちら。ここで拾う。
set -uo pipefail

cmd="$(jq -r '.tool_input.command // ""' 2>/dev/null)"
[ -n "$cmd" ] || exit 0

if printf '%s' "$cmd" | grep -Eqi \
  -e 'gmail[[:space:]]+(users[[:space:]]+)?(messages[[:space:]]+)?send' \
  -e 'gmail[[:space:]]+\+send' \
  -e 'gmail[[:space:]]+drafts[[:space:]]+send' \
  -e 'gmail[[:space:]]+users[[:space:]]+drafts[[:space:]]+send' \
  -e 'chat\.postMessage' \
  -e 'chat\.scheduleMessage' \
  -e 'hooks\.slack\.com' ; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"メール送信 / Slack 投稿は自動実行せず必ず確認する運用（.claude/hooks/guard-send.sh）"}}
JSON
fi
exit 0
