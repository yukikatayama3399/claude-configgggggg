#!/usr/bin/env bash
# ============================================================
# setup_gws_remote.sh
# Google 公式の Google Workspace CLI (gws) を使えるようにする
#
# 認証は「新しく取らない」。既に gog が持っている refresh token を
# authorized_user 形式の credentials.json に組み直して gws に渡す。
# これにより CLAUDE.md の「認証は会社 Mac 1台でしかやらない」を守ったまま
# gws が使える(gws auth login をどこでも叩く必要がない)。
#
# 認証情報の入手元は3つ。上から順に探す:
#   1. GWS_CREDENTIALS_B64        … gws 独自の認証を配っている場合
#   2. GOG_CREDENTIALS_B64 + GOG_TOKEN_EXPORT_B64  … クラウド(web)セッション
#   3. ローカルの gog 本体          … 会社 Mac など、gog が認証済みの端末
#
# client_secret が上のどこにも無い場合(gog が keyring に退避している)は、
# Cloud Console の OAuth クライアント JSON を渡す:
#   GWS_CLIENT_SECRET_JSON=<パス>       … ローカル実行時
#   GWS_CLIENT_SECRET_JSON_B64=<base64> … クラウドの環境変数に入れる場合
#
# 使い方:
#   bash setup_gws_remote.sh                       # 既定 @fout.jp
#   GWS_ACCOUNT=other@example.com bash setup_gws_remote.sh
# 冪等: 何度実行してもOK
# ============================================================
set -euo pipefail

GWS_VERSION="0.22.5"              # npm の @googleworkspace/cli のバージョン
NPM_PREFIX="$HOME/.local"         # gws のインストール先(bin/ に入る)
BIN_DIR="$NPM_PREFIX/bin"
CONFIG_DIR="$HOME/.config/gws"
CRED_FILE="$CONFIG_DIR/credentials.json"
ACCOUNT="${GWS_ACCOUNT:-${GOG_ACCOUNT:-yuki.katayama@fout.jp}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILDER="$SCRIPT_DIR/gws_credentials_from_gog.py"

log()  { echo "==> $*"; }
fail() { echo "!! $*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || fail "python3 が無い"
[ -f "$BUILDER" ] || fail "$BUILDER が無い(リポジトリのクローン内で実行して)"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# base64 -d は GNU と BSD(macOS) で挙動が違うので python3 で decode する。
b64_env_to_file() {  # $1=環境変数名 $2=出力先
  python3 - "$1" "$2" <<'PY'
import base64, os, sys
name, out = sys.argv[1], sys.argv[2]
raw = os.environ.get(name, "")
if not raw:
    sys.exit(f"!! 環境変数 {name} が空")
try:
    data = base64.b64decode(raw)
except Exception as e:
    sys.exit(f"!! {name} を base64 として読めない: {e}")
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "wb") as f:
    f.write(data)
PY
}

# sync_gog_token.sh が書き出した .env の 1 行(KEY=base64)を decode する。
# クラウドへ配った値には、gog が keyring に退避する前の client_secret が
# 残っていることがあるため、Mac 側の候補として使える。
b64_line_to_file() {  # $1=envファイル $2=変数名 $3=出力先
  python3 - "$1" "$2" "$3" <<'PYLINE'
import base64, os, sys
src, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
val = None
with open(src) as f:
    for line in f:
        line = line.strip()
        if line.startswith(name + "="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
if not val:
    sys.exit(1)
try:
    data = base64.b64decode(val)
except Exception:
    sys.exit(1)
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "wb") as f:
    f.write(data)
PYLINE
}

# ---- 1. gws のインストール ----
# npm パッケージは薄いラッパで、postinstall が OS 別のバイナリを取ってくる。
if command -v gws >/dev/null 2>&1 && [ "$(gws --version 2>/dev/null | head -1)" = "gws $GWS_VERSION" ]; then
  log "gws は既にインストール済み: $(gws --version | head -1)"
else
  command -v npm >/dev/null 2>&1 || fail "npm が無い。Node.js を入れるか、別の方法で gws を入れて。"
  log "gws v${GWS_VERSION} をインストール中 (npm)..."
  mkdir -p "$NPM_PREFIX"
  npm install --prefix "$NPM_PREFIX" -g "@googleworkspace/cli@${GWS_VERSION}" >/dev/null \
    || fail "npm install に失敗。ネットワーク(npm registry)へ到達できるか確認して。"
  log "インストール完了: $BIN_DIR/gws"
fi

# PATH を通す(このシェル + 使っているシェルの rc)
case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) export PATH="$BIN_DIR:$PATH"
     PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
     for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
       [ -f "$rc" ] || continue
       grep -qF "$PATH_LINE" "$rc" || echo "$PATH_LINE" >> "$rc"
     done ;;
esac
gws --version >/dev/null 2>&1 || fail "gws が実行できない"

# ---- 2. credentials.json の用意 ----
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# Cloud Console から落とした OAuth クライアント JSON を base64 で配る経路。
# gog が client_secret を keyring に退避していて、配った GOG_CREDENTIALS_B64 にも
# 入っていない場合の逃げ道。クラウドの環境変数に入れておけば恒久的に効く。
if [ -n "${GWS_CLIENT_SECRET_JSON_B64:-}" ] && [ -z "${GWS_CLIENT_SECRET_JSON:-}" ]; then
  b64_env_to_file GWS_CLIENT_SECRET_JSON_B64 "$WORK_DIR/client_secret.json" || exit 1
  GWS_CLIENT_SECRET_JSON="$WORK_DIR/client_secret.json"
  log "client 情報の候補: GWS_CLIENT_SECRET_JSON_B64 を使用"
fi

if [ -n "${GWS_CREDENTIALS_B64:-}" ]; then
  # (1) gws 独自の認証を配っている場合(通常は使わない)
  b64_env_to_file GWS_CREDENTIALS_B64 "$CRED_FILE" || fail "GWS_CREDENTIALS_B64 の展開に失敗"
  python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$CRED_FILE" \
    || fail "GWS_CREDENTIALS_B64 のdecode結果がJSONに見えへん。値を確認して。"
  log "credentials: GWS_CREDENTIALS_B64 から復元"

elif [ -n "${GOG_CREDENTIALS_B64:-}" ] && [ -n "${GOG_TOKEN_EXPORT_B64:-}" ]; then
  # (2) クラウドセッション: setup_gog_remote.sh と同じ環境変数を使う
  b64_env_to_file GOG_CREDENTIALS_B64  "$WORK_DIR/gog_credentials.json" || exit 1
  b64_env_to_file GOG_TOKEN_EXPORT_B64 "$WORK_DIR/gog_token.json"       || exit 1
  python3 "$BUILDER" --account "$ACCOUNT" --token "$WORK_DIR/gog_token.json" \
      --out "$CRED_FILE" --verbose \
      ${GWS_CLIENT_SECRET_JSON:+"$GWS_CLIENT_SECRET_JSON"} \
      "$WORK_DIR/gog_credentials.json" \
    || fail "gog の環境変数から credentials.json を組めなかった"
  log "credentials: gog の環境変数から生成($ACCOUNT / 新規認証なし)"

elif command -v gog >/dev/null 2>&1; then
  # (3) ローカルの gog から直接もらう(会社 Mac など)
  # gog が管理している credentials.json は client_secret が抜かれていることが
  # あるので、候補を複数渡して「両方揃っているファイル」を選ばせる。
  CRED_PATH="$(gog auth status -j 2>/dev/null \
    | grep -o '"credentials_path"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | sed 's/.*:[[:space:]]*"//; s/"$//')"
  # mktemp -d の中に作るので --overwrite は不要だが、再実行に備えて付けておく。
  gog auth tokens export "$ACCOUNT" --out "$WORK_DIR/gog_token.json" --overwrite >/dev/null \
    || fail "gog auth tokens export に失敗($ACCOUNT)。gog auth list で確認して。"

  # 候補集め。set -e 下では `[ test ] && cmd` を文の最後に置くと
  # テストが偽になった時点でスクリプトが落ちるので if で書く。
  CLIENT_SOURCES=()
  add_source() {  # 実在するファイルだけ、重複なしで足す
    local p="$1" existing
    [ -f "$p" ] || return 0
    for existing in ${CLIENT_SOURCES+"${CLIENT_SOURCES[@]}"}; do
      if [ "$existing" = "$p" ]; then return 0; fi
    done
    CLIENT_SOURCES+=("$p")
  }
  # 明示指定(Cloud Console から落とした OAuth クライアントの JSON)が最優先。
  # 存在しないパスを渡されたら黙って無視せずここで止める。
  if [ -n "${GWS_CLIENT_SECRET_JSON:-}" ]; then
    if [ -f "$GWS_CLIENT_SECRET_JSON" ]; then
      add_source "$GWS_CLIENT_SECRET_JSON"
    else
      fail "GWS_CLIENT_SECRET_JSON のファイルが無い: $GWS_CLIENT_SECRET_JSON"
    fi
  fi
  # sync_gog_token.sh が過去に書き出した値(新しい順)。gog が keyring へ
  # 退避する前の client_secret が残っていることがある。
  i=0
  for envf in $(ls -t "$HOME"/.gog_sync/gog_env_*.env 2>/dev/null || true); do
    i=$((i + 1))
    if b64_line_to_file "$envf" GOG_CREDENTIALS_B64 "$WORK_DIR/sync_${i}.json" 2>/dev/null; then
      add_source "$WORK_DIR/sync_${i}.json"
    fi
  done
  if [ -n "$CRED_PATH" ]; then
    add_source "$CRED_PATH"
  fi
  add_source "$HOME/.config/gogcli/credentials.json"
  add_source "$HOME/Library/Application Support/gogcli/credentials.json"
  python3 "$BUILDER" --account "$ACCOUNT" --token "$WORK_DIR/gog_token.json" \
      --out "$CRED_FILE" --verbose ${CLIENT_SOURCES+"${CLIENT_SOURCES[@]}"} \
    || fail "ローカルの gog から credentials.json を組めなかった"
  log "credentials: ローカルの gog から生成($ACCOUNT / 新規認証なし)"

else
  fail "認証情報が見つからない。
   クラウドなら GOG_CREDENTIALS_B64 / GOG_TOKEN_EXPORT_B64 を設定して。
   ローカルなら gog を入れて認証済みにして(認証は会社 Mac だけ。CLAUDE.md 参照)。"
fi
chmod 600 "$CRED_FILE"

export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE="$CRED_FILE"
# クラウドには OS キーチェーンが無いので keyring はファイルバックエンドにしておく
export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file

# ---- 3. 検証(読み取り専用) ----
log "疎通確認 (drive.files.list, 1件だけ):"
ERR_LOG="$WORK_DIR/gws_check.err"
if gws drive files list --params '{"pageSize":1,"fields":"files(id)"}' >/dev/null 2>"$ERR_LOG"; then
  log "✅ セットアップ完了。例: gws calendar events list --params '{\"calendarId\":\"primary\"}'"
else
  echo ""
  echo "⚠️  gws の疎通に失敗:"
  sed 's/^/    /' "$ERR_LOG" >&2
  echo "   ・invalid_grant → refresh token 失効。「正」の Mac で bash sync_gog_token.sh --reauth"
  echo "   ・invalid_client → client_id/secret の出所がトークンと合っていない"
  echo "   ・not enabled   → OAuth プロジェクトで該当 API が無効(CLAUDE.md の有効化手順)"
  exit 1
fi
