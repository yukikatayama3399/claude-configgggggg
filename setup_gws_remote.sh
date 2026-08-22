#!/usr/bin/env bash
# ============================================================
# setup_gws_remote.sh
# Google 公式の Google Workspace CLI (gws) をクラウド環境で使えるようにする
#
# 認証は「新しく取らない」。既に gog が持っている refresh token を
# authorized_user 形式の credentials.json に組み直して gws に渡す。
# これにより CLAUDE.md の「認証は会社 Mac 1台でしかやらない」を守ったまま
# gws が使える(gws auth login をクラウドで叩く必要がない)。
#
# 前提: setup_gog_remote.sh と同じ3つの環境変数
#   GOG_CREDENTIALS_B64   … credentials.json (client_id/client_secret) の base64
#   GOG_TOKEN_EXPORT_B64  … `gog auth tokens export` 出力の base64
#   GOG_KEYRING_PASSWORD  … 暗号化ファイル keyring のパスワード
#
# 使い方: bash setup_gws_remote.sh
# 冪等: 何度実行してもOK
# ============================================================
set -euo pipefail

GWS_VERSION="0.22.5"              # npm の @googleworkspace/cli のバージョン
NPM_PREFIX="$HOME/.local"         # gws のインストール先(bin/ に入る)
BIN_DIR="$NPM_PREFIX/bin"
CONFIG_DIR="$HOME/.config/gws"
CRED_FILE="$CONFIG_DIR/credentials.json"

log()  { echo "==> $*"; }
fail() { echo "!! $*" >&2; exit 1; }

# ---- 0. 環境変数チェック ----
for v in GOG_CREDENTIALS_B64 GOG_TOKEN_EXPORT_B64; do
  [ -n "${!v:-}" ] || fail "環境変数 $v が未設定。Claude Code の環境変数設定を確認して。"
done
log "環境変数: OK"

# ---- 1. gws のインストール ----
# npm パッケージは薄いラッパで、postinstall が OS 別のバイナリを取ってくる。
if command -v gws >/dev/null 2>&1 && [ "$(gws --version 2>/dev/null | head -1)" = "gws $GWS_VERSION" ]; then
  log "gws は既にインストール済み: $(gws --version | head -1)"
else
  log "gws v${GWS_VERSION} をインストール中 (npm)..."
  mkdir -p "$NPM_PREFIX"
  npm install --prefix "$NPM_PREFIX" -g "@googleworkspace/cli@${GWS_VERSION}" >/dev/null \
    || fail "npm install に失敗。ネットワーク(npm registry)へ到達できるか確認して。"
  log "インストール完了: $BIN_DIR/gws"
fi

# PATH を通す(このシェル + 永続化)
case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) export PATH="$BIN_DIR:$PATH"
     if [ -f "$HOME/.bashrc" ] && ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc"; then
       echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
     fi ;;
esac
gws --version >/dev/null 2>&1 || fail "gws が実行できない"

# ---- 2. credentials.json の用意 ----
# 優先順:
#   (a) GWS_CREDENTIALS_B64 があればそれを使う
#       (会社 Mac で `gws auth export --unmasked` した結果を配った場合)
#   (b) 無ければ gog の client + refresh token から authorized_user 形式を組む
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

if [ -n "${GWS_CREDENTIALS_B64:-}" ]; then
  printf '%s' "$GWS_CREDENTIALS_B64" | base64 -d > "$CRED_FILE"
  head -c 1 "$CRED_FILE" | grep -q '{' \
    || fail "GWS_CREDENTIALS_B64 のdecode結果がJSONに見えへん。値を確認して。"
  log "credentials: GWS_CREDENTIALS_B64 から復元"
else
  python3 - "$CRED_FILE" <<'PY' || fail "gog のトークンから credentials.json を組めなかった"
import base64, json, os, sys

out_path = sys.argv[1]

def load_b64_json(var):
    raw = os.environ.get(var, "")
    if not raw:
        sys.exit(f"!! 環境変数 {var} が空")
    try:
        return json.loads(base64.b64decode(raw))
    except Exception as e:
        sys.exit(f"!! {var} をJSONとして読めない: {e}")

def find_key(obj, names):
    """ネストした dict/list から names のどれかのキーの値(文字列)を最初に1つ返す。"""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k in names and isinstance(v, str) and v:
                    return v
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(x for x in cur if isinstance(x, (dict, list)))
    return None

# client_id / client_secret は gog の credentials.json (Desktop app の JSON) から。
# {"installed": {...}} / {"web": {...}} / フラットのいずれでも拾えるようにする。
creds = load_b64_json("GOG_CREDENTIALS_B64")
client_id     = find_key(creds, {"client_id", "clientId"})
client_secret = find_key(creds, {"client_secret", "clientSecret"})
if not client_id or not client_secret:
    sys.exit("!! GOG_CREDENTIALS_B64 から client_id / client_secret を取り出せない")

# refresh token は gog の token export から。gog の版によって入れ物が変わりうるので
# キー名の候補を広めに取り、見つからなければ "1//" 始まりの文字列を探す。
tok = load_b64_json("GOG_TOKEN_EXPORT_B64")
refresh = find_key(tok, {"refresh_token", "refreshToken", "RefreshToken"})
if not refresh:
    stack, found = [tok], None
    while stack and not found:
        cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, str) and cur.startswith("1//"):
            found = cur
    refresh = found
if not refresh:
    sys.exit("!! GOG_TOKEN_EXPORT_B64 から refresh token を取り出せない"
             "(gog のバージョンで export 形式が変わった可能性)")

fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump({
        "type": "authorized_user",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh,
    }, f)
PY
  log "credentials: gog の refresh token から生成(新規認証なし)"
fi
chmod 600 "$CRED_FILE"

export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE="$CRED_FILE"
# クラウドには OS キーチェーンが無いので keyring はファイルバックエンドにしておく
export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file

# ---- 3. 検証(読み取り専用) ----
log "疎通確認 (drive.files.list, 1件だけ):"
if gws drive files list --params '{"pageSize":1,"fields":"files(id)"}' >/dev/null 2>/tmp/gws_check.err; then
  log "✅ セットアップ完了。例: gws calendar events list --params '{\"calendarId\":\"primary\"}'"
else
  echo ""
  echo "⚠️  gws の疎通に失敗:"
  sed 's/^/    /' /tmp/gws_check.err >&2
  echo "   ・invalid_grant → refresh token 失効。「正」の Mac で bash sync_gog_token.sh --reauth"
  echo "   ・not enabled   → OAuth プロジェクトで該当 API が無効(CLAUDE.md の有効化手順)"
  exit 1
fi
