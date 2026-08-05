#!/usr/bin/env bash
# ============================================================
# restore_gog_local.sh — Mac(ローカル)側で実行する
#
# 目的: クラウドで生きているトークンを Mac に「移し替える」。
#
# sync_gog_token.sh の逆方向。
#   sync_gog_token.sh   : Mac  → クラウド/CI へ配る
#   restore_gog_local.sh: 3つの値 → Mac の gog へ戻す   ← これ
#
# 使いどころ:
#   クラウドの Routine は動いているのに、Mac の cron ルーティンだけ
#   invalid_grant で Google 系が全部スキップされている、という状態。
#   クラウド側が正しいので、認証しなおさずコピーで直す。
#
# 重要: このスクリプトは `gog auth add` を叩かない。
#       CLAUDE.md の「認証は1台でしかやらない」ルールを壊さない。
#
# 使い方:
#   1) 3つの値を環境変数にセットしてから実行する
#        export GOG_CREDENTIALS_B64=...
#        export GOG_TOKEN_EXPORT_B64=...
#        export GOG_KEYRING_PASSWORD=...
#        bash restore_gog_local.sh
#   2) または sync_gog_token.sh が書き出した .env を渡す
#        bash restore_gog_local.sh ~/.gog_sync/gog_env_YYYYmmdd_HHMMSS.env
#
# 冪等: 何度実行してもOK
# ============================================================
set -euo pipefail

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"

# setup_gog_remote.sh / sync_gog_token.sh と必ず揃える。
# ずれているとトークン形式が合わず import が壊れる。
GOG_VERSION_EXPECTED="0.19.0"

# 疎通確認に使う読み取り専用のシート(ヨミ管理)。中身は変更しない。
VERIFY_SHEET_ID="${GOG_VERIFY_SHEET_ID:-1iyhwVNhN_HJNdIBL_pREhrhBdQu2it5ktFOYq-DDm_w}"

log()  { echo "==> $*"; }
fail() { echo "!! $*" >&2; exit 1; }

# ---- 0. .env ファイルが渡されたら読む ----
if [ "$#" -gt 0 ]; then
  ENV_FILE="$1"
  [ -f "$ENV_FILE" ] || fail "ファイルが無い: $ENV_FILE"
  log "値をファイルから読む: $ENV_FILE"
  # コメント行を除いて KEY=VALUE だけを拾う
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

for v in GOG_CREDENTIALS_B64 GOG_TOKEN_EXPORT_B64; do
  [ -n "${!v:-}" ] || fail "環境変数 $v が未設定。Claude Code on the web の環境変数か ~/.gog_sync/*.env から取る。"
done
log "credentials / token の2値: OK"

# GOG_KEYRING_PASSWORD は「暗号化ファイル keyring」を使う環境(クラウド/CI)でだけ必須。
# Mac は既定で macOS キーチェーンを使うので無くても復旧できる。
if [ -n "${GOG_KEYRING_PASSWORD:-}" ]; then
  log "GOG_KEYRING_PASSWORD: セット済み"
else
  log "GOG_KEYRING_PASSWORD: 未設定。macOS キーチェーンを使う想定で続行する"
  log "  (doctor が keyring.backend = file と出る環境では必須。その場合は中断されるので設定して再実行)"
fi

# ---- 1. gog のバージョン一致チェック ----
command -v gog >/dev/null 2>&1 || fail "gog が見つからない。先に gog をインストールして。"
GOG_VERSION_ACTUAL="$(gog --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
if [ "$GOG_VERSION_ACTUAL" != "$GOG_VERSION_EXPECTED" ]; then
  echo "!! gog のバージョン不一致" >&2
  echo "   この Mac    : ${GOG_VERSION_ACTUAL:-不明}" >&2
  echo "   配布元想定  : ${GOG_VERSION_EXPECTED}" >&2
  echo "   揃えてから実行して。(クラウド側は setup_gog_remote.sh の GOG_VERSION)" >&2
  exit 1
fi
log "gog v${GOG_VERSION_ACTUAL}: 配布元と一致"

# ---- 2. 既存トークンのバックアップ ----
# 上書きに失敗しても元に戻せるようにしておく。
BACKUP_DIR="${HOME}/.gog_sync/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
if gog auth tokens export --out "${BACKUP_DIR}/tokens_before.json" --overwrite >/dev/null 2>&1; then
  chmod 600 "${BACKUP_DIR}/tokens_before.json"
  log "既存トークンを退避: ${BACKUP_DIR}/tokens_before.json"
else
  log "既存トークンの退避はスキップ(読めるトークンが無い。失効済みなら想定どおり)"
fi

# ---- 3. credentials.json の復元 ----
# keyring バックエンドはこの Mac の設定のままにする(勝手に file へ倒さない)。
CONFIG_DIR="${HOME}/.config/gogcli"
mkdir -p "$CONFIG_DIR"
echo "$GOG_CREDENTIALS_B64" | base64 -d > "${CONFIG_DIR}/credentials.json"
head -c 1 "${CONFIG_DIR}/credentials.json" | grep -q '{' \
  || fail "credentials.json のdecode結果がJSONに見えない。B64値を確認して。"
chmod 600 "${CONFIG_DIR}/credentials.json"
log "credentials.json 復元: ${CONFIG_DIR}/credentials.json"

gog auth credentials set "${CONFIG_DIR}/credentials.json" --no-input \
  || fail "credentials.json の登録に失敗"
log "credentials.json を gog に登録: OK"

# ---- 4. トークンのインポート ----
TOKEN_TMP="$(mktemp)"
trap 'rm -f "$TOKEN_TMP"' EXIT
echo "$GOG_TOKEN_EXPORT_B64" | base64 -d > "$TOKEN_TMP"
gog auth tokens import "$TOKEN_TMP" --no-input --force \
  || fail "トークンのインポート失敗。配布元で再export して3つの値を焼き直す必要があるかも。"
rm -f "$TOKEN_TMP"
log "トークンインポート: OK"

# ---- 5. 検証(doctor だけでなく実APIも叩く) ----
log "アカウント一覧:"
gog auth list --no-input || true

log "auth doctor:"
gog auth doctor --check --no-input || {
  echo "" >&2
  echo "⚠️  doctor がエラー。配布元(クラウド)の値が古い可能性がある。" >&2
  echo "   会社 Mac で: bash sync_gog_token.sh --reauth  → 3つの値を配り直す。" >&2
  exit 1
}

log "実API疎通(Sheets 読み取り):"
if gog --account "$ACCOUNT" sheets get "$VERIFY_SHEET_ID" "A1:B2"; then
  log "✅ 復旧完了。cron のルーティンは次回発火から Google 系が動く。"
else
  fail "doctor は通ったが実APIが弾かれた。スコープ不足かAPI無効化を疑う(CLAUDE.md 参照)。"
fi

# ---- 6. cron から見えるかの注意 ----
cat <<'EOF'

------------------------------------------------------------
最後に必ず確認すること:

cron は login shell の環境変数を引き継がない。
ターミナルで動いても、cron 実行時に GOG_KEYRING_PASSWORD が
見えていないと同じように失敗する(keyring を開けない)。

  bash diagnose_mac_routines.sh

を実行して「cron から見える環境変数」の項目を確認する。
------------------------------------------------------------
EOF
