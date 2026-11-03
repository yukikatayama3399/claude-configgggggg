#!/usr/bin/env bash
# ============================================================
# BALL 専用の gog を、個人 Mac に用意する（新しい認証はしない）
#
# クラウドで動いている3つの値を ~/.ball/gog.env に書いておき、
# それを BALL 専用の場所（~/.ball/gog）に取り込む。
# この Mac に元から入っている gog の設定には触らない。
# `gog auth add` は叩かない（「認証は会社 Mac の1台だけ」のルールどおり）。
#
# ~/.ball/gog.env の中身（3行。値はクラウド環境の環境変数からコピー）:
#   GOG_CREDENTIALS_B64=...
#   GOG_TOKEN_EXPORT_B64=...
#   GOG_KEYRING_PASSWORD=...
#
# 使い方: bash scripts/setup-gog-mac.sh
# ============================================================
set -euo pipefail

ENV_FILE="${BALL_GOG_ENV:-$HOME/.ball/gog.env}"
export GOG_HOME="${BALL_GOG_HOME:-$HOME/.ball/gog}"
ACCOUNT="${BALL_GOG_ACCOUNT:-yuki.katayama@fout.jp}"

log()  { echo "==> $*"; }
fail() { echo "!! $*" >&2; exit 1; }

command -v gog >/dev/null 2>&1 || fail "gog が見つかりません。"
[ -f "$ENV_FILE" ] || fail "$ENV_FILE がありません。先に3つの値を書いてください（README 参照）。"
chmod 600 "$ENV_FILE"

# KEY=VALUE を読む（前後の空白・引用符は外す）
read_val() { grep -E "^[[:space:]]*$1[[:space:]]*=" "$ENV_FILE" | tail -1 | sed -E "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//; s/^[\"']//; s/[\"'][[:space:]]*$//" | tr -d '\r'; }
CRED="$(read_val GOG_CREDENTIALS_B64)"
TOKEN="$(read_val GOG_TOKEN_EXPORT_B64)"
PASS="$(read_val GOG_KEYRING_PASSWORD)"
[ -n "$CRED" ]  || fail "GOG_CREDENTIALS_B64 が空です"
[ -n "$TOKEN" ] || fail "GOG_TOKEN_EXPORT_B64 が空です"
[ -n "$PASS" ]  || fail "GOG_KEYRING_PASSWORD が空です"

export GOG_KEYRING_BACKEND=file
export GOG_KEYRING_PASSWORD="$PASS"
mkdir -p "$GOG_HOME"; chmod 700 "$GOG_HOME"
log "BALL 専用の gog の置き場所: $GOG_HOME"

gog auth keyring file --no-input >/dev/null 2>&1 || true

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
printf '%s' "$CRED"  | base64 --decode > "$TMP/credentials.json" || fail "GOG_CREDENTIALS_B64 を読めません（コピーが欠けていないか確認）"
head -c 1 "$TMP/credentials.json" | grep -q '{' || fail "GOG_CREDENTIALS_B64 の中身が JSON に見えません"
printf '%s' "$TOKEN" | base64 --decode > "$TMP/token.json" || fail "GOG_TOKEN_EXPORT_B64 を読めません"

gog auth credentials set "$TMP/credentials.json" --no-input >/dev/null || fail "credentials の登録に失敗"
log "credentials: OK"
gog auth tokens import "$TMP/token.json" --no-input --force >/dev/null || fail "トークンの取り込みに失敗"
log "トークン: OK"

if gog --account "$ACCOUNT" --gmail-no-send --no-input -j gmail search "in:inbox" --max 1 >/dev/null 2>&1; then
  log "✅ Gmail を読めました。BALL を起動し直すか、下の帯の「Gmail」を押してください。"
else
  fail "まだ Gmail を読めません。値のコピーが正しいか確認してください。"
fi
