#!/usr/bin/env bash
# ============================================================
# audit_gog_routines.sh — ルーティン定義に潜む gog の地雷を洗い出す
#
# 読み取り専用。ファイルは一切変更しない。
#
# 探すもの:
#   [A] --account を書いていない gog コマンド
#       → 既定アカウント（gmail スコープのみ）で実行され 403 forbidden になる。
#         2026-08-05 に判明した「16日間のトークン失効誤報」の真因。
#   [B] gog auth add / gog auth login を復旧手順として案内している箇所
#       → auth add は --services 既定が user なので 22 スコープが最小構成に潰れる。
#         auth login はそもそも存在しないサブコマンド（正しくは auth manage）。
#   [C] 認証系の失敗を「失効」と断定している箇所
#       → 403 forbidden や keyring エラーまで失効に丸めると誤報になる。
#
# 使い方:
#   bash audit_gog_routines.sh
#   bash audit_gog_routines.sh ~/some/other/dir
#
# 終了コード: 0 = 指摘なし / 1 = 1件以上の指摘あり
# ============================================================
set -uo pipefail

DIR="${1:-$HOME/.claude/scheduled-tasks}"
[ -d "$DIR" ] || { echo "!! ディレクトリが無い: $DIR"; exit 1; }

echo "監査対象: $DIR"
echo ""

FOUND=0
A_HITS=0; B_HITS=0; C_HITS=0

# 対象ファイルを集める（.md 直置きとサブディレクトリの両方に対応）
FILES="$(find "$DIR" -type f \( -name '*.md' -o -name '*.sh' \) 2>/dev/null | sort)"
[ -n "$FILES" ] || { echo "対象ファイルが見つからない"; exit 1; }

echo "=============================================="
echo "[A] --account を書いていない gog コマンド"
echo "=============================================="
while IFS= read -r f; do
  # gog を呼んでいる行のうち、--account も -a も付いていないものを拾う。
  # コメント行・説明文中の言及も出るが、消すより見せたほうが安全。
  hits="$(grep -nE '(^|[^a-zA-Z0-9_-])gog[[:space:]]' "$f" 2>/dev/null \
          | grep -vE -- '--account|[[:space:]]-a[[:space:]]' \
          | grep -vE 'gog[[:space:]]+(auth|--version|--help)')"
  if [ -n "$hits" ]; then
    echo ""
    echo "--- ${f#$DIR/}"
    printf '%s\n' "$hits" | sed 's/^/    /'
    A_HITS=$((A_HITS+1)); FOUND=1
  fi
done <<< "$FILES"
[ "$A_HITS" -eq 0 ] && echo "  指摘なし"

echo ""
echo "=============================================="
echo "[B] 危険な復旧手順の案内（gog auth add / login）"
echo "=============================================="
while IFS= read -r f; do
  hits="$(grep -nE 'gog[[:space:]]+auth[[:space:]]+(add|login)' "$f" 2>/dev/null)"
  if [ -n "$hits" ]; then
    echo ""
    echo "--- ${f#$DIR/}"
    printf '%s\n' "$hits" | sed 's/^/    /'
    B_HITS=$((B_HITS+1)); FOUND=1
  fi
done <<< "$FILES"
[ "$B_HITS" -eq 0 ] && echo "  指摘なし"

echo ""
echo "=============================================="
echo "[C] 認証エラーを「失効」と断定している箇所"
echo "=============================================="
while IFS= read -r f; do
  hits="$(grep -nE '失効|invalid_grant|再認証' "$f" 2>/dev/null)"
  if [ -n "$hits" ]; then
    echo ""
    echo "--- ${f#$DIR/}"
    printf '%s\n' "$hits" | sed 's/^/    /'
    C_HITS=$((C_HITS+1)); FOUND=1
  fi
done <<< "$FILES"
[ "$C_HITS" -eq 0 ] && echo "  指摘なし"

echo ""
echo "=============================================="
echo "まとめ: [A] ${A_HITS}ファイル / [B] ${B_HITS}ファイル / [C] ${C_HITS}ファイル"
echo "=============================================="
echo ""
echo "直し方:"
echo "  [A] gog の呼び出しを gog --account yuki.katayama@fout.jp <サブコマンド> に直す。"
echo "      グローバルフラグはサブコマンドの前に置く（後ろだと unknown flag）。"
echo "  [B] 復旧手順の案内を削除する。正しい復旧は sync_gog_token.sh 経由のみ。"
echo "  [C] 失効と断定する前に bash diagnose_gog.sh の判定を使う。"
echo "      403 forbidden は権限不足であって失効ではない。"

exit "$FOUND"
