#!/bin/bash
# ============================================================
# UserPromptSubmit hook: オンボーディングの話が出たら「利用規約の同意が先」を割り込ませる
#
# HAWK は利用規約の同意（Web申込フォームの送信）が済まないと、オンボーディングで
# 広告アカウントをつなぎ込めない。日程だけ確定して同意依頼を忘れる人的ミスを防ぐため、
# プロンプトにオンボーディング系の語が含まれたら:
#   1) ルール（同意が先・未取得なら冒頭でアラート）を Claude の文脈に注入し
#   2) gog が使える環境なら onboarding/check_tos.py の結果も一緒に渡す
# 判定に失敗してもプロンプト自体は止めない（exit 0）。
# ============================================================
set -uo pipefail

input=$(cat)
prompt=$(printf '%s' "$input" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("prompt",""))
except Exception: pass')

if ! printf '%s' "$prompt" | grep -qiE 'オンボ|ボーディング|つなぎ込|繋ぎ込|ツナギコミ|onboard|トライアル|キックオフ'; then
  exit 0
fi

check=""
if command -v gog >/dev/null 2>&1; then
  check=$(cd "$CLAUDE_PROJECT_DIR" && timeout 40 python3 onboarding/check_tos.py --days 30 2>&1)
fi
[ -n "$check" ] || check="(自動チェック未実行。python3 onboarding/check_tos.py で確認すること)"

CHECK="$check" python3 -c '
import json, os
ctx = """【HAWK ルール: オンボーディングは利用規約の同意が先】
利用規約の同意（Web申込フォームの送信＝【HAWK】Web申込リストに記載）が無い会社は、
オンボーディングで広告アカウントのつなぎ込みができない。この依頼に関わる会社について:
- 同意が未取得（🚨）/要確認（⚠️）なら、回答の冒頭で必ずアラートを出す
- 日程調整・確定・御礼メールを書く場合も、未取得なら同意依頼（シルバー／月次、2週間以内の解約で0円）を必ず盛り込む
- 手順と文面テンプレは .claude/skills/onboarding-tos-gate/SKILL.md

現時点の自動チェック結果:
""" + os.environ["CHECK"]
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}, ensure_ascii=False))
'
exit 0
