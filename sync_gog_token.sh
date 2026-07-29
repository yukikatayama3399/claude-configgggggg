#!/usr/bin/env bash
# ============================================================
# sync_gog_token.sh  —  Mac(ローカル)側で実行する
#
# 目的: gog の認証を「1台だけ」で行い、その結果を全環境へ配る。
#
# 運用ルール(重要):
#   認証する端末を1台に固定する = この台を「正」とする。
#   他の端末やクラウドでは絶対に `gog auth add` を叩かない。
#   必ずこのスクリプトが出力した3つの値をコピーして使う。
#
# 使い方:
#   bash sync_gog_token.sh              # 既存トークンをそのまま書き出す(安全)
#   bash sync_gog_token.sh --reauth     # 認証しなおしてから書き出す
#   bash sync_gog_token.sh --print      # 値を標準出力にも出す(画面共有時は注意)
#   bash sync_gog_token.sh --gh-secrets # GitHub Secrets にも push する
# ============================================================
set -euo pipefail

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"
REPO="${GOG_GH_REPO:-yukikatayama3399/claude-configgggggg}"

# クラウド側(setup_gog_remote.sh)と必ず揃える。片方だけ上げると import が壊れる。
GOG_VERSION_EXPECTED="0.19.0"

# 再認証時に要求するスコープ。減らすと既存の権限が失われるので、
# 現在の付与内容をそのまま維持している。安易に削らないこと。
SERVICES="ads,analytics,appscript,calendar,chat,classroom,contacts,docs,drive,driveactivity,drivelabels,forms,gmail,meet,people,photos,searchconsole,sheets,sites,slides,tasks,youtube"

OUT_DIR="${HOME}/.gog_sync"
OUT_FILE="${OUT_DIR}/gog_env_$(date +%Y%m%d_%H%M%S).env"

DO_REAUTH=0
DO_PRINT=0
DO_GH=0
for arg in "$@"; do
  case "$arg" in
    --reauth)     DO_REAUTH=1 ;;
    --print)      DO_PRINT=1 ;;
    --gh-secrets) DO_GH=1 ;;
    -h|--help)    sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "!! 不明な引数: $arg" >&2; exit 1 ;;
  esac
done

log()  { echo "==> $*"; }
fail() { echo "!! $*" >&2; exit 1; }

# ---- 0. 前提チェック ----
command -v gog >/dev/null 2>&1 || fail "gog が見つからない。先に gog をインストールして。"

GOG_VERSION_ACTUAL="$(gog --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
if [ "$GOG_VERSION_ACTUAL" != "$GOG_VERSION_EXPECTED" ]; then
  echo "!! gog のバージョン不一致" >&2
  echo "   この Mac      : ${GOG_VERSION_ACTUAL:-不明}" >&2
  echo "   クラウド想定  : ${GOG_VERSION_EXPECTED}" >&2
  echo "   トークン形式が変わっている可能性がある。両方を揃えてから実行して。" >&2
  echo "   (クラウド側は setup_gog_remote.sh の GOG_VERSION と bin/ の tarball)" >&2
  exit 1
fi
log "gog v${GOG_VERSION_ACTUAL}: クラウド側と一致"

# keyring パスワードは全環境で同一でなければトークンを復号できない。
if [ -z "${GOG_KEYRING_PASSWORD:-}" ]; then
  echo "!! GOG_KEYRING_PASSWORD が未設定。" >&2
  echo "   これは全環境(この Mac / クラウド / CI)で同一の値でなければならない。" >&2
  echo "   既にクラウドで動いている値をこのシェルに export してから再実行して。" >&2
  exit 1
fi
log "GOG_KEYRING_PASSWORD: セット済み"

# ---- 1. 再認証(任意・対話が必要) ----
if [ "$DO_REAUTH" = "1" ]; then
  log "再認証する: $ACCOUNT"
  echo "    ブラウザが開くので、$ACCOUNT でログインして同意すること。"
  echo "    別アカウントで同意すると別人のトークンが入るので注意。"
  gog auth add "$ACCOUNT" --services "$SERVICES" \
    || fail "認証に失敗した。トークンは書き換えていないので、既存の値はそのまま使える。"
  log "再認証: OK"
else
  log "再認証はスキップ(既存トークンを書き出すだけ)。やり直すなら --reauth"
fi

# ---- 2. 健全性チェック(壊れた値を配らないため) ----
log "auth doctor:"
gog auth doctor --check --no-input \
  || fail "doctor が異常を報告。この状態の値を配ると全環境が壊れるので中断する。"

# ---- 3. 3つの値を生成 ----
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

CRED_PATH="$(gog auth status -j 2>/dev/null \
  | grep -o '"credentials_path"[[:space:]]*:[[:space:]]*"[^"]*"' \
  | sed 's/.*:[[:space:]]*"//; s/"$//')"
[ -n "$CRED_PATH" ] && [ -f "$CRED_PATH" ] \
  || fail "credentials.json の場所が特定できない: ${CRED_PATH:-(空)}"
log "credentials.json: $CRED_PATH"

TOKEN_TMP="$(mktemp)"
trap 'rm -f "$TOKEN_TMP"' EXIT
# mktemp が既にファイルを作っているので --overwrite が必須。
gog auth tokens export --out "$TOKEN_TMP" --overwrite >/dev/null \
  || fail "gog auth tokens export に失敗"

CREDENTIALS_B64="$(openssl base64 -A -in "$CRED_PATH")"
TOKEN_B64="$(openssl base64 -A -in "$TOKEN_TMP")"
rm -f "$TOKEN_TMP"

umask 077
cat > "$OUT_FILE" <<EOF
# gog 認証値 — $(date '+%Y-%m-%d %H:%M:%S') / $(hostname) で生成
# この端末を「正」として運用する。他の端末で gog auth add を叩かないこと。
GOG_CREDENTIALS_B64=${CREDENTIALS_B64}
GOG_TOKEN_EXPORT_B64=${TOKEN_B64}
GOG_KEYRING_PASSWORD=${GOG_KEYRING_PASSWORD}
EOF
chmod 600 "$OUT_FILE"

log "書き出し完了: $OUT_FILE (chmod 600)"
echo "    GOG_CREDENTIALS_B64  : ${#CREDENTIALS_B64} 文字"
echo "    GOG_TOKEN_EXPORT_B64 : ${#TOKEN_B64} 文字"
echo "    GOG_KEYRING_PASSWORD : ${#GOG_KEYRING_PASSWORD} 文字"

# ---- 4. 任意: GitHub Secrets へ push ----
if [ "$DO_GH" = "1" ]; then
  command -v gh >/dev/null 2>&1 || fail "gh CLI が無いので --gh-secrets は使えない"
  log "GitHub Secrets に push: $REPO"
  printf '%s' "$CREDENTIALS_B64"        | gh secret set GOG_CREDENTIALS_B64   --repo "$REPO"
  printf '%s' "$TOKEN_B64"              | gh secret set GOG_TOKEN_EXPORT_B64  --repo "$REPO"
  printf '%s' "$GOG_KEYRING_PASSWORD"   | gh secret set GOG_KEYRING_PASSWORD  --repo "$REPO"
  log "GitHub Secrets: OK"
fi

# ---- 5. 次にやること ----
cat <<EOF

------------------------------------------------------------
次の手順:

1. Claude Code on the web の環境変数を更新する
   (GitHub Secrets とは別物。web UI の環境設定側にも同じ3つが必要)
   値は $OUT_FILE から取る。

2. クラウドで新しいセッションを開き、SessionStart フックの出力が
   "status ok" になることを確認する。

3. 確認できたら、この一時ファイルを消す:
     rm $OUT_FILE

注意: このファイルには実トークンが入っている。
      出力先は \$HOME/.gog_sync でリポジトリ外だが、
      中身をリポジトリに貼り付けたりコミットしないこと。
------------------------------------------------------------
EOF

if [ "$DO_PRINT" = "1" ]; then
  echo ""
  echo "=== 値(--print 指定) ==="
  cat "$OUT_FILE"
fi
