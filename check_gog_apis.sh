#!/usr/bin/env bash
# ============================================================
# check_gog_apis.sh — gog が各 Google API に到達できるかを一括確認
#
# 読み取り専用。ファイルの作成・変更・削除は一切しない。
# いつ実行しても安全なので「gog 壊れてない?」の一次切り分けに使う。
#
# 使い方:
#   bash check_gog_apis.sh
#   bash check_gog_apis.sh --account other@example.com
#
# 終了コード: 0 = 全項目OK / 1 = 1つ以上NG
# ============================================================
set -uo pipefail   # -e は付けない(1項目失敗しても最後まで検査したいため)

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"
if [ "${1:-}" = "--account" ] && [ -n "${2:-}" ]; then
  ACCOUNT="$2"
fi

GOG="$(command -v gog || echo "$HOME/bin/gog")"
[ -x "$GOG" ] || { echo "!! gog が見つからない: $GOG"; exit 1; }

FAILED=0
RESULTS=""

# 1コマンド実行して成否だけ記録する。
# 失敗時は API 無効化などの原因が分かる先頭行を控える。
check() {
  local label="$1"; shift
  local out
  if out="$("$@" 2>&1)"; then
    RESULTS+="OK   ${label}"$'\n'
  else
    FAILED=1
    local reason
    reason="$(printf '%s' "$out" | grep -v '^$' | head -1 | cut -c1-100)"
    RESULTS+="NG   ${label}  … ${reason}"$'\n'
  fi
}

echo "gog: $("$GOG" --version 2>/dev/null | head -1)"
echo "アカウント: $ACCOUNT"
echo ""

# ---- 認証そのもの ----
check "auth (refresh token)" "$GOG" auth doctor --check --no-input

# ---- 一覧系コマンドがある API はそれで確認 ----
check "Drive"    "$GOG" --account "$ACCOUNT" drive ls --max 1
check "Gmail"    "$GOG" --account "$ACCOUNT" gmail labels list
check "Calendar" "$GOG" --account "$ACCOUNT" calendar list

# ---- 一覧系が無い API は存在しない ID を投げて判定 ----
# 注意: `<サービス> --help` はローカル処理で必ず成功するため検査にならない。
# API が無効なら "not enabled"、有効なら 404/notFound が返る。
# この差で「プロジェクト側で API が有効か」を読み取り専用のまま判定できる。
# (Slides は実際にここが無効で壊れていた実績があるので必ず検査する)
BOGUS_ID="0000000000000000000000000000000000000000000"
api_check() {
  local label="$1"; shift
  local out
  out="$("$@" "$BOGUS_ID" 2>&1)"
  if printf '%s' "$out" | grep -qi 'not enabled'; then
    FAILED=1
    RESULTS+="NG   ${label}  … API がプロジェクトで無効(CLAUDE.md の有効化手順を参照)"$'\n'
  elif printf '%s' "$out" | grep -qiE 'not ?found|404|invalid|badRequest'; then
    RESULTS+="OK   ${label}"$'\n'
  else
    # 想定外の応答は判定を保留し、そのまま見せる(誤ってOKにしない)。
    FAILED=1
    RESULTS+="??   ${label}  … 判定不能: $(printf '%s' "$out" | grep -v '^$' | head -1 | cut -c1-80)"$'\n'
  fi
}

api_check "Sheets" "$GOG" --account "$ACCOUNT" sheets metadata
api_check "Docs"   "$GOG" --account "$ACCOUNT" docs cat
api_check "Slides" "$GOG" --account "$ACCOUNT" slides raw

printf '%s' "$RESULTS"
echo ""
if [ "$FAILED" = "0" ]; then
  echo "✅ 全項目OK"
  exit 0
else
  echo "❌ NG あり。"
  echo "   ・'not enabled' → OAuth プロジェクトで当該 API を有効化(CLAUDE.md 参照)"
  echo "   ・auth が NG    → 「正」の Mac で bash sync_gog_token.sh --reauth"
  exit 1
fi
