#!/bin/bash
# ============================================================
# 定期実行(Routine)セッション用のブートストラップ。
#
# Routine のセッションにはこのリポジトリがクローンされておらず、
# SessionStart フック(.claude/hooks/session-start.sh)も走らない。
# そのため「リポジトリの〇〇を実行」「gog で〇〇」と書いた Routine は
# gog もスクリプトも無い状態で起動し、何もできずに終わっていた（2026-09-25 棚卸し）。
#
# Routine のプロンプト冒頭で、リポジトリを clone してからこれを実行する
# （手順は routines/README.md の「冒頭ブロック」）。
#   - gog / gws をセットアップ（SessionStart フックと同じ処理）
#   - 以降の Bash 呼び出しで読み込む環境ファイル ~/.routine_env を書き出す
# 冪等なので何回叩いてもよい。認証情報はこのファイルには一切書かない。
# ============================================================
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

export CLAUDE_CODE_REMOTE=true
export CLAUDE_PROJECT_DIR="$REPO"

for v in GOG_CREDENTIALS_B64 GOG_TOKEN_EXPORT_B64 GOG_KEYRING_PASSWORD; do
  if [ -z "${!v:-}" ]; then
    echo "[bootstrap] 環境変数 $v が未設定。Routine の環境(Default)の環境変数を確認すること" >&2
    exit 1
  fi
done

bash "$REPO/.claude/hooks/session-start.sh"

ENV_FILE="$HOME/.routine_env"
cat > "$ENV_FILE" <<EOF
export PATH="\$HOME/bin:\$HOME/.local/bin:\$PATH"
export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE="\$HOME/.config/gws/credentials.json"
export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file
export GOG_KEYRING_BACKEND=file
export REPO="$REPO"
EOF

# shellcheck disable=SC1090
source "$ENV_FILE"

ok=1
if gog auth doctor --check --no-input >/dev/null 2>&1; then
  echo "[bootstrap] gog: OK"
else
  echo "[bootstrap] gog: NG（gog auth doctor --check --no-input でエラーを確認）" >&2
  ok=0
fi
if command -v gws >/dev/null 2>&1; then
  echo "[bootstrap] gws: OK"
else
  echo "[bootstrap] gws: NG" >&2
  ok=0
fi

echo "[bootstrap] REPO=$REPO"
echo "[bootstrap] 以降の Bash 呼び出しは毎回先頭で: source ~/.routine_env && cd \"\$REPO\""
[ "$ok" = 1 ]
