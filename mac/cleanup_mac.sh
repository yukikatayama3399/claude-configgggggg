#!/usr/bin/env bash
# ============================================================
# mac/cleanup_mac.sh — 消してよいものを消してディスクを空ける（既定はドライラン）
#
# 引数なしで実行すると「何をどれだけ消すか」を出すだけで削除はしない。
# 実際に消すのは --apply を付けたときだけ。
#
# 使い方:
#   bash mac/cleanup_mac.sh                            # ドライラン（既定・安全）
#   bash mac/cleanup_mac.sh --apply                    # safe だけ削除
#   bash mac/cleanup_mac.sh --apply --include-careful  # careful も削除
#   bash mac/cleanup_mac.sh --apply --snapshots        # TimeMachine ローカルスナップショットも削除
#   bash mac/cleanup_mac.sh --apply --yes              # 確認プロンプトを出さない
#
# 対象の定義は mac/_targets.sh。class の意味もそこに書いてある。
#   safe    … 消して問題ないキャッシュ（既定の削除対象）
#   careful … 再ダウンロード/再ビルドが必要になる（--include-careful でのみ）
#   report  … このスクリプトは絶対に消さない
#
# 安全弁:
#   - $HOME 配下でないパスは削除しない
#   - $HOME そのもの / / などの危険なパスは削除しない
#   - Homebrew / Docker は rm ではなく公式のクリーンアップコマンドを案内する
# ============================================================
set -uo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "!! このスクリプトは macOS 専用（今は $(uname -s) で動いている）"
  echo "   お使いの Mac のターミナルで実行すること。"
  exit 1
fi

APPLY=0
INCLUDE_CAREFUL=0
SNAPSHOTS=0
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --include-careful) INCLUDE_CAREFUL=1 ;;
    --snapshots) SNAPSHOTS=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "!! 不明な引数: $arg（--help で使い方）"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=mac/_targets.sh
. "$SCRIPT_DIR/_targets.sh"

human_kb() {
  awk -v kb="$1" 'BEGIN{
    if (kb >= 1048576) printf "%.1f GB", kb/1048576;
    else if (kb >= 1024) printf "%.1f MB", kb/1024;
    else printf "%d KB", kb;
  }'
}

# パスが削除して安全かを判定する。安全弁なので条件は厳しめにしている。
is_safe_path() {
  local p="$1"
  case "$p" in
    "" ) return 1 ;;
    "$HOME" | "$HOME/" ) return 1 ;;    # ホームそのもの
    "/" | "/*" ) return 1 ;;
    "$HOME"/*) : ;;                     # ホーム配下のみ許可
    *) return 1 ;;
  esac
  # .. を含むパスは弾く（定義ファイルの書き間違い対策）
  case "$p" in *".."*) return 1 ;; esac
  # 短すぎるパスは弾く
  [ "${#p}" -gt $(( ${#HOME} + 3 )) ] || return 1
  return 0
}

# ------------------------------------------------------------
# 候補を集めてサイズを測る
# ------------------------------------------------------------
echo "対象を調べている（du で1つずつ測るので少し待つ）..."

PLAN=""       # kb|class|mode|label|path
total=0
skipped=""

while IFS='|' read -r class mode label path; do
  case "$class" in ''|'#'*) continue ;; esac
  [ -n "${path:-}" ] || continue
  [ "$class" = "report" ] && continue          # report は触らない
  [ "$class" = "careful" ] && [ "$INCLUDE_CAREFUL" -eq 0 ] && continue
  [ -e "$path" ] || continue

  if ! is_safe_path "$path"; then
    skipped="${skipped}    - ${path}（\$HOME 配下でない等の理由で対象外）"$'\n'
    continue
  fi

  kb="$(du -sk "$path" 2>/dev/null | awk '{print $1+0}')"
  [ "${kb:-0}" -gt 0 ] || continue

  PLAN="${PLAN}${kb}|${class}|${mode}|${label}|${path}"$'\n'
  total=$(( total + kb ))
done < <(emit_targets)

# TimeMachine のローカルスナップショット（rm では消せないので tmutil を使う）
SNAP_LIST=""
if [ "$SNAPSHOTS" -eq 1 ] && command -v tmutil >/dev/null 2>&1; then
  SNAP_LIST="$(tmutil listlocalsnapshots / 2>/dev/null | sed -n 's/^com\.apple\.TimeMachine\.\(.*\)\.local$/\1/p')"
fi

# ------------------------------------------------------------
# 計画を表示
# ------------------------------------------------------------
echo
if [ -z "$PLAN" ]; then
  echo "削除対象は見つからなかった。"
else
  if [ "$APPLY" -eq 1 ]; then
    echo "== 以下を削除する"
  else
    echo "== ドライラン: 以下を削除する予定（今回は消さない）"
  fi
  printf '\n  %10s  %-8s %s\n' "SIZE" "CLASS" "対象"
  printf '  %10s  %-8s %s\n' "----------" "--------" "----"
  printf '%s' "$PLAN" | sort -t'|' -k1,1rn | while IFS='|' read -r kb class mode label path; do
    printf '  %10s  %-8s %s\n' "$(human_kb "$kb")" "$class" "$label"
    printf '  %10s  %-8s   %s (%s)\n' "" "" "$path" "$mode"
  done
  echo
  echo "  空く見込み: $(human_kb "$total")"
fi

if [ -n "$skipped" ]; then
  echo
  echo "  安全弁で除外したパス:"
  printf '%s' "$skipped"
fi

if [ -n "$SNAP_LIST" ]; then
  echo
  echo "  TimeMachine ローカルスナップショット（削除対象）:"
  printf '%s\n' "$SNAP_LIST" | sed 's/^/    - /'
fi

# Homebrew / Docker は rm ではなく専用コマンドが正しいので案内だけ出す
echo
echo "== 手で叩くと更に空くもの（このスクリプトは実行しない）"
if command -v brew >/dev/null 2>&1; then
  echo "  brew cleanup -s --prune=all      # 古いバージョンとダウンロードキャッシュを整理"
fi
if command -v docker >/dev/null 2>&1; then
  echo "  docker system prune -a --volumes # 未使用イメージ/コンテナ/ボリュームを削除（要注意）"
fi
echo "  xcrun simctl delete unavailable  # 使えないシミュレータを削除（Xcode がある場合）"

if [ "$INCLUDE_CAREFUL" -eq 0 ]; then
  echo
  echo "  ※ careful 分類（Homebrew キャッシュ、Gradle/Maven、Playwright 等）は今回除外。"
  echo "     含めるには --include-careful を付ける。"
fi

# ------------------------------------------------------------
# ドライランならここで終わり
# ------------------------------------------------------------
if [ "$APPLY" -eq 0 ]; then
  echo
  echo "実際に消すには --apply を付けて実行する:"
  echo "  bash mac/cleanup_mac.sh --apply"
  exit 0
fi

if [ -z "$PLAN" ] && [ -z "$SNAP_LIST" ]; then
  exit 0
fi

# ------------------------------------------------------------
# 確認して削除
# ------------------------------------------------------------
if [ "$ASSUME_YES" -eq 0 ]; then
  echo
  printf '本当に削除する? [y/N] '
  read -r reply
  case "$reply" in
    y|Y|yes|YES) : ;;
    *) echo "中止した。何も消していない。"; exit 0 ;;
  esac
fi

echo
freed=0
failed=0

while IFS='|' read -r kb class mode label path; do
  [ -n "${path:-}" ] || continue
  # 削除の直前にもう一度安全弁を通す
  if ! is_safe_path "$path"; then
    echo "  skip: $path（安全弁）"
    continue
  fi
  [ -e "$path" ] || continue

  case "$mode" in
    contents)
      # 親ディレクトリは残して中身だけ消す。ドットファイルも対象にするため find を使う。
      if find "$path" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null; then
        echo "  ✅ 空にした: $label ($(human_kb "$kb"))"
        freed=$(( freed + kb ))
      else
        # 使用中のファイルなどは消えないことがある。致命的ではないので続行する。
        echo "  △ 一部消せなかった: $label（アプリが使用中の可能性。アプリを終了して再実行）"
        failed=$(( failed + 1 ))
      fi
      ;;
    whole)
      if rm -rf "$path" 2>/dev/null; then
        echo "  ✅ 削除した: $label ($(human_kb "$kb"))"
        freed=$(( freed + kb ))
      else
        echo "  △ 消せなかった: $label"
        failed=$(( failed + 1 ))
      fi
      ;;
    *)
      echo "  skip: $label（未知の mode: $mode）"
      ;;
  esac
done < <(printf '%s' "$PLAN")

if [ -n "$SNAP_LIST" ]; then
  while IFS= read -r snap; do
    [ -n "$snap" ] || continue
    if tmutil deletelocalsnapshots "$snap" >/dev/null 2>&1; then
      echo "  ✅ スナップショット削除: $snap"
    else
      echo "  △ スナップショット削除に失敗: $snap（sudo が必要な場合あり）"
      failed=$(( failed + 1 ))
    fi
  done <<< "$SNAP_LIST"
fi

echo
echo "== 結果"
echo "  空けた容量（見込み）: $(human_kb "$freed")"
[ "$failed" -gt 0 ] && echo "  消しきれなかった項目: ${failed} 件（該当アプリを終了して再実行すると消える）"
echo
df -h / | sed 's/^/  /'
