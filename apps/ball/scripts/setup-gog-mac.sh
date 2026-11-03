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

# KEY=VALUE を読む。コピーのときに値の途中で改行が入っても、次の KEY= の行までを1つの値としてつなげる。
# 空白・改行・引用符は取り除く（base64 とパスワードに空白は入らない）。
read_val() {
  awk -v key="$1" '
    /^[[:space:]]*[A-Z_][A-Z0-9_]*[[:space:]]*=/ { cur = $0; sub(/[[:space:]]*=.*/, "", cur); gsub(/[[:space:]]/, "", cur)
      if (cur == key) { on = 1; v = $0; sub(/^[^=]*=/, "", v); out = out v; next } else { on = 0 } }
    on { out = out $0 }
    END { gsub(/[[:space:]"\047]/, "", out); printf "%s", out }' "$ENV_FILE"
}
# base64 で使わない文字（見えない記号・全角文字など）を取り除き、末尾の = が欠けていたら補う
clean_b64() { local s; s="$(printf '%s' "$1" | LC_ALL=C tr -cd 'A-Za-z0-9+/=')"; s="${s%%=*}"; while [ $(( ${#s} % 4 )) -ne 0 ]; do s="$s="; done; printf '%s' "$s"; }
fp() { printf '%s' "$1" | shasum -a 256 | cut -c1-8; }
CRED="$(clean_b64 "$(read_val GOG_CREDENTIALS_B64)")"
TOKEN="$(clean_b64 "$(read_val GOG_TOKEN_EXPORT_B64)")"
PASS="$(read_val GOG_KEYRING_PASSWORD)"
# 指紋（ハッシュの先頭8文字）。元の値は復元できない。クラウドで動いている値と同じかの確認用
log "読み取った長さ: ${#CRED} / ${#TOKEN} / ${#PASS}（正しくは 412 / 4336 / 29）"
log "指紋: $(fp "$CRED") / $(fp "$TOKEN") / $(fp "$PASS")（正しくは 737668b8 / 58ebf73d / eb4adaa9。値を作り直した後は変わります）"
[ -n "$CRED" ]  || fail "GOG_CREDENTIALS_B64 が空です"
[ -n "$TOKEN" ] || fail "GOG_TOKEN_EXPORT_B64 が空です"
[ -n "$PASS" ]  || fail "GOG_KEYRING_PASSWORD が空です"
[ "$(fp "$CRED")" = "737668b8" ]  || echo "!! GOG_CREDENTIALS_B64 がクラウドの値と一致しません。貼り直してください" >&2
[ "$(fp "$TOKEN")" = "58ebf73d" ] || echo "!! GOG_TOKEN_EXPORT_B64 がクラウドの値と一致しません。貼り直してください" >&2
[ "$(fp "$PASS")" = "eb4adaa9" ]  || echo "!! GOG_KEYRING_PASSWORD がクラウドの値と一致しません。貼り直してください" >&2

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
