#!/bin/bash
# ============================================================
# SessionStart hook: gog (gogcli) をセッション開始時に自動セットアップ
# クラウド環境(Claude Code on the web)は毎セッション初期化されるため、
# 毎回 setup_gog_remote.sh を手打ちする代わりにこのフックで自動化する。
# 認証情報はこのファイルには一切書かない。セッション環境変数
# (GOG_CREDENTIALS_B64 / GOG_TOKEN_EXPORT_B64 / GOG_KEYRING_PASSWORD) から取得する。
# ============================================================
set -uo pipefail

# ローカル(Mac等)では何もしない。クラウド(remote)環境でだけ動かす。
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# gog セットアップ(冪等)。失敗してもセッション自体はブロックしない。
if bash "$CLAUDE_PROJECT_DIR/setup_gog_remote.sh"; then
  echo "[session-start] gog setup: OK"
else
  echo "[session-start] gog setup: FAILED (環境変数未設定 or refresh token失効の可能性。setup_gog_remote.sh を手動実行してエラー確認を)" >&2
fi

# gog を $HOME/bin に入れているので、セッション全体で PATH を通す。
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export PATH="$HOME/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi

exit 0
