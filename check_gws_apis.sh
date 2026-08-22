#!/usr/bin/env bash
# ============================================================
# check_gws_apis.sh — gws (Google Workspace CLI) の疎通を一括確認
#
# 読み取り専用。ファイルの作成・変更・削除は一切しない。
# いつ実行しても安全なので「gws 壊れてない?」の一次切り分けに使う。
# (gog 側の同等スクリプトは check_gog_apis.sh)
#
# 使い方:
#   bash check_gws_apis.sh
#
# 終了コード: 0 = 全項目OK / 1 = 1つ以上NG
# ============================================================
set -uo pipefail   # -e は付けない(1項目失敗しても最後まで検査したいため)

GWS="$(command -v gws || echo "$HOME/.local/bin/gws")"
[ -x "$GWS" ] || { echo "!! gws が見つからない: $GWS  → bash setup_gws_remote.sh"; exit 1; }

# 明示指定が無ければ setup_gws_remote.sh が置いた credentials を使う
if [ -z "${GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE:-}" ] && [ -f "$HOME/.config/gws/credentials.json" ]; then
  export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE="$HOME/.config/gws/credentials.json"
fi

FAILED=0
RESULTS=""

# 1コマンド実行して成否だけ記録する。失敗時は原因が分かる行を控える。
check() {
  local label="$1"; shift
  local out
  if out="$("$@" 2>&1)"; then
    RESULTS+="OK   ${label}"$'\n'
  else
    FAILED=1
    local reason
    reason="$(printf '%s' "$out" | grep -iE '"message"|error' | head -1 | cut -c1-120)"
    RESULTS+="NG   ${label}  … ${reason}"$'\n'
  fi
}

echo "gws: $("$GWS" --version 2>/dev/null | head -1)"
echo "credentials: ${GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE:-(env/暗号化ストアを使用)}"
echo ""

# ---- 認証そのもの ----
# auth status は token_valid で判定する(コマンド自体は失敗しないため)
AUTH_JSON="$("$GWS" auth status 2>&1)"
if printf '%s' "$AUTH_JSON" | grep -q '"token_valid": true'; then
  RESULTS+="OK   auth (token refresh)"$'\n'
  EMAIL="$(printf '%s' "$AUTH_JSON" | grep -o '"email": *"[^"]*"' | head -1 | cut -d'"' -f4)"
  [ -n "$EMAIL" ] && echo "アカウント: $EMAIL" && echo ""
else
  FAILED=1
  RESULTS+="NG   auth (token refresh)  … $(printf '%s' "$AUTH_JSON" | grep -o '"token_error": *"[^"]*"' | cut -d'"' -f4)"$'\n'
fi

# ---- 一覧系コマンドがある API はそれで確認 ----
check "Drive"    "$GWS" drive files list        --params '{"pageSize":1,"fields":"files(id)"}'
check "Gmail"    "$GWS" gmail users labels list --params '{"userId":"me"}'
check "Calendar" "$GWS" calendar calendarList list --params '{"maxResults":1}'

# ---- 一覧系が無い API は存在しない ID を投げて判定 ----
# API が無効なら "not enabled"、有効なら 404/notFound が返る。
# この差で「プロジェクト側で API が有効か」を読み取り専用のまま判定できる。
BOGUS_ID="0000000000000000000000000000000000000000000"
api_check() {
  local label="$1"; local svc="$2"; local res="$3"; local key="$4"
  local out
  out="$("$GWS" "$svc" "$res" get --params "{\"$key\":\"$BOGUS_ID\"}" 2>&1)"
  if printf '%s' "$out" | grep -qi 'not enabled\|has not been used'; then
    FAILED=1
    RESULTS+="NG   ${label}  … API がプロジェクトで無効(CLAUDE.md の有効化手順を参照)"$'\n'
  elif printf '%s' "$out" | grep -qiE 'not ?found|404|invalid|badRequest|400'; then
    RESULTS+="OK   ${label}"$'\n'
  else
    # 想定外の応答は判定を保留し、そのまま見せる(誤ってOKにしない)。
    FAILED=1
    RESULTS+="??   ${label}  … 判定不能: $(printf '%s' "$out" | grep -v '^$' | head -1 | cut -c1-80)"$'\n'
  fi
}

api_check "Sheets" sheets spreadsheets  spreadsheetId
api_check "Docs"   docs   documents     documentId
api_check "Slides" slides presentations presentationId

printf '%s' "$RESULTS"
echo ""
if [ "$FAILED" = "0" ]; then
  echo "✅ 全項目OK"
  exit 0
else
  echo "❌ NG あり。"
  echo "   ・'not enabled'  → OAuth プロジェクトで当該 API を有効化(CLAUDE.md 参照)"
  echo "   ・auth が NG     → 「正」の Mac で bash sync_gog_token.sh --reauth"
  echo "                       (gws の認証は gog のトークンを流用しているため)"
  echo "   ・credentials 無 → bash setup_gws_remote.sh"
  exit 1
fi
