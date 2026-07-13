#!/usr/bin/env bash
# ============================================================
# setup_gog_remote.sh
# Claude Code クラウド環境で gog (gogcli) を使えるようにする
# 前提: 以下3つの環境変数がセッションに登録済みであること
#   GOG_CREDENTIALS_B64   … credentials.json (client_id) の base64
#   GOG_TOKEN_EXPORT_B64  … `gog auth tokens export` 出力の base64
#   GOG_KEYRING_PASSWORD  … 暗号化ファイルkeyringのパスワード
# 使い方: bash setup_gog_remote.sh
# 冪等: 何度実行してもOK
# ============================================================
set -euo pipefail

GOG_VERSION="0.19.0"   # ローカル(Mac)側と揃える。上げるときは両方同時に
BIN_DIR="$HOME/bin"
CONFIG_DIR="$HOME/.config/gogcli"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo "==> $*"; }
fail() { echo "!! $*" >&2; exit 1; }

# ---- 0. 環境変数チェック ----
for v in GOG_CREDENTIALS_B64 GOG_TOKEN_EXPORT_B64 GOG_KEYRING_PASSWORD; do
  [ -n "${!v:-}" ] || fail "環境変数 $v が未設定。Claude Code の環境変数設定を確認して。"
done
log "環境変数3つ: OK"

# ---- 1. gog バイナリのインストール ----
if command -v gog >/dev/null 2>&1; then
  log "gog は既にインストール済み: $(gog --version)"
else
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64)  GOARCH="amd64" ;;
    aarch64|arm64) GOARCH="arm64" ;;
    *) fail "未対応アーキテクチャ: $ARCH" ;;
  esac
  TARBALL="gogcli_${GOG_VERSION}_linux_${GOARCH}.tar.gz"
  LOCAL_TARBALL="${SCRIPT_DIR}/bin/${TARBALL}"
  TMPDIR_DL="$(mktemp -d)"
  if [ -f "$LOCAL_TARBALL" ]; then
    log "同梱の gog v${GOG_VERSION} (${GOARCH}) を使用: $LOCAL_TARBALL"
    cp "$LOCAL_TARBALL" "${TMPDIR_DL}/${TARBALL}"
  else
    URL="https://github.com/openclaw/gogcli/releases/download/v${GOG_VERSION}/${TARBALL}"
    log "gog v${GOG_VERSION} (${GOARCH}) をダウンロード中..."
    curl -fsSL -o "${TMPDIR_DL}/${TARBALL}" "$URL" || fail "ダウンロード失敗: $URL"
  fi
  tar -xzf "${TMPDIR_DL}/${TARBALL}" -C "$TMPDIR_DL"
  mkdir -p "$BIN_DIR"
  install -m 0755 "${TMPDIR_DL}/gog" "$BIN_DIR/gog"
  rm -rf "$TMPDIR_DL"
  log "インストール完了: $BIN_DIR/gog"
fi

# PATH に $HOME/bin がなければ通す(このシェル + 永続化)
case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) export PATH="$BIN_DIR:$PATH"
     if [ -f "$HOME/.bashrc" ] && ! grep -q 'export PATH="$HOME/bin:$PATH"' "$HOME/.bashrc"; then
       echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
     fi ;;
esac
gog --version >/dev/null || fail "gog が実行できない"

# ---- 2. keyring をファイルバックエンドに設定 ----
# クラウドLinuxにはOSキーチェーンがないので暗号化ファイルkeyringを使う。
# パスワードは GOG_KEYRING_PASSWORD から自動で拾われる。
export GOG_KEYRING_BACKEND=file
gog auth keyring file --no-input >/dev/null 2>&1 || true
log "keyring: file バックエンドに設定"

# ---- 3. credentials.json の復元 ----
mkdir -p "$CONFIG_DIR"
echo "$GOG_CREDENTIALS_B64" | base64 -d > "$CONFIG_DIR/credentials.json"
head -c 1 "$CONFIG_DIR/credentials.json" | grep -q '{' \
  || fail "credentials.json のdecode結果がJSONに見えへん。B64値を確認して。"
chmod 600 "$CONFIG_DIR/credentials.json"
log "credentials.json 復元: $CONFIG_DIR/credentials.json"

gog auth credentials set "$CONFIG_DIR/credentials.json" --no-input \
  || fail "credentials.json の登録(gog auth credentials set)に失敗"
log "credentials.json を gog に登録: OK"

# ---- 4. トークンのインポート ----
TOKEN_TMP="$(mktemp)"
trap 'rm -f "$TOKEN_TMP"' EXIT
echo "$GOG_TOKEN_EXPORT_B64" | base64 -d > "$TOKEN_TMP"
gog auth tokens import "$TOKEN_TMP" --no-input --force \
  || fail "トークンのインポート失敗。ローカルで再export(gog auth tokens export)して環境変数を焼き直す必要があるかも。"
rm -f "$TOKEN_TMP"
log "トークンインポート: OK"

# ---- 5. 検証 ----
log "アカウント一覧:"
gog auth list --no-input || true
log "auth doctor で健全性チェック:"
if gog auth doctor --check --no-input; then
  log "✅ セットアップ完了。例: gog --account yuki.katayama@fout.jp --readonly calendar events --today"
else
  echo ""
  echo "⚠️  doctor がエラーを報告。上のメッセージを確認して。"
  echo "   refresh token 失効なら、Mac側で:"
  echo "     gog auth tokens export --out /tmp/gog_tokens.json"
  echo "     openssl base64 -A -in /tmp/gog_tokens.json | pbcopy && rm /tmp/gog_tokens.json"
  echo "   → GOG_TOKEN_EXPORT_B64 を更新して再実行。"
  exit 1
fi
