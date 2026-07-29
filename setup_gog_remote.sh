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

# credentials.json が gog auth credentials set に食わせられる形か検証する。
# 罠が2つあって、どちらも「JSONとしては妥当なので通ってしまう」タイプ:
#   1) Mac の gog は既定で client_secret を keyring に入れ、credentials.json 側は
#      client_id だけになる (gog auth credentials list の SECRET_KEYRING=true)。
#   2) gog が書く credentials.json はフラット形 {"client_id":...} だが、
#      gog auth credentials set が受け付けるのは Cloud Console 版の
#      {"installed":{...}} / {"web":{...}} だけ。自分が書いた形を戻せない。
# どちらも後段で初めて落ちるので、ここで先に弾く。
check_credentials_json() {
  local f="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$f" <<'PY'
import json, sys

try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception as exc:
    sys.exit("JSONとして読めない: %s" % exc)

problems = []

inner = None
for key in ("installed", "web"):
    section = data.get(key) if isinstance(data, dict) else None
    if isinstance(section, dict):
        inner = section
        break

if inner is None:
    problems.append("installed / web のラッパーが無い"
                    "(gog auth credentials set が受け付けない形式)")
    inner = data if isinstance(data, dict) else {}

missing = [k for k in ("client_id", "client_secret")
           if not str(inner.get(k) or "").strip()]
if missing:
    problems.append("次のキーが空 or 欠落: %s" % ", ".join(missing))

if problems:
    sys.exit("; ".join(problems))
PY
  else
    # python3 が無い環境向けのフォールバック。
    # 開き引用符の直後に空白以外の文字が1つ以上あることを要求して、
    # "" や "   " を空扱いで弾く。
    grep -qE '"(installed|web)"[[:space:]]*:' "$f" \
      && grep -qE '"client_id"[[:space:]]*:[[:space:]]*"[[:space:]]*[^[:space:]"]' "$f" \
      && grep -qE '"client_secret"[[:space:]]*:[[:space:]]*"[[:space:]]*[^[:space:]"]' "$f"
  fi
}

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

if ! CRED_ERR="$(check_credentials_json "$CONFIG_DIR/credentials.json" 2>&1)"; then
  [ -n "$CRED_ERR" ] && echo "   詳細: $CRED_ERR" >&2
  cat >&2 <<'EOS'
!! GOG_CREDENTIALS_B64 の中身が gog に登録できる形になってない。

   よくある原因: Mac 側の gog の credentials.json を base64 した。
   あのファイルは元の client JSON ではなく gog が書いた別物で、二重にダメ:
     - client_secret が入っていない (既定で keyring 側に保存される。
       確認は gog auth credentials list → SECRET_KEYRING が true)
     - installed/web ラッパーの無いフラット形式で、
       gog auth credentials set 自体が受け付けない

   対処: Google Cloud Console → APIとサービス → 認証情報 →
   OAuth 2.0 クライアントID から JSON をダウンロードし直して、
   そのファイル(installed 形式)をそのまま base64 する:
     openssl base64 -A -in ~/Downloads/client_secret_XXXX.json | pbcopy
   → GOG_CREDENTIALS_B64 を更新して再実行。
EOS
  exit 1
fi
log "credentials.json 復元: $CONFIG_DIR/credentials.json (client_id/client_secret あり)"

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
