#!/bin/bash
# mac_login_quiet.sh — ログイン時に勝手に立ち上がるアプリを止める（アプリ自体は消さない）
#
#   bash mac_login_quiet.sh            # ドライラン（何をするか表示するだけ）
#   bash mac_login_quiet.sh --apply    # 実行
#   bash mac_login_quiet.sh --undo     # 元に戻す
#
# やること:
#   1. LOGIN_ITEMS をログイン項目から外す（アプリは残る。手で開けば普通に使える）
#   2. QUIT_APPS を「ログイン直後 60 秒以内に macOS の復元で立ち上がったら終了させる」
#      LaunchAgent を入れる。
#      macOS の「再ログイン時にウインドウを再度開く」は残したまま（Chrome 等は今まで通り
#      復元される）、指定アプリだけを閉じる。macOS にアプリ単位で復元を外す設定が無いための策。
#      注意: ログイン後 60 秒以内に自分で開いた対象アプリも閉じられる。

set -u

LOGIN_ITEMS=("Clipy")
QUIT_APPS=("Microsoft Excel" "Microsoft Word" "Microsoft PowerPoint" "zoom.us")
WINDOW_SEC=60

LABEL="local.quit-restored-apps"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
WORKER="$HOME/.local/bin/quit_restored_apps.sh"
STATE_DIR="$HOME/.config/mac_login_quiet"
STATE="$STATE_DIR/removed_login_items.tsv"
UID_NUM=$(id -u)

MODE=dry
case "${1:-}" in
  ""|--dry-run) MODE=dry ;;
  --apply) MODE=apply ;;
  --undo)  MODE=undo ;;
  -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
  *) echo "不明な引数: $1（--help 参照）" >&2; exit 1 ;;
esac

[ "$(uname)" = Darwin ] || { echo "macOS 専用です。" >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { echo "sudo なしで実行してください。" >&2; exit 1; }

se() { osascript -e "tell application \"System Events\" to $1" 2>/dev/null; }

# ------------------------------------------------------------------ undo
if [ "$MODE" = undo ]; then
  if [ -f "$AGENT" ]; then
    launchctl bootout "gui/$UID_NUM" "$AGENT" 2>/dev/null
    rm -f "$AGENT" "$WORKER"
    echo "自動終了の LaunchAgent を外した"
  fi
  if [ -f "$STATE" ]; then
    while IFS=$'\t' read -r name path; do
      [ -n "$path" ] || continue
      se "make login item at end with properties {path:\"$path\", hidden:false}" >/dev/null \
        && echo "ログイン項目に戻した: $name" || echo "!! 戻せなかった: $name ($path)"
    done < "$STATE"
    rm -f "$STATE"
  fi
  echo "完了。"
  exit 0
fi

# ------------------------------------------------------------------ dry / apply
[ "$MODE" = dry ] && echo "【ドライラン】何も変更しません。実行するには --apply を付けてください。"

echo "== 1. ログイン項目から外す"
for name in "${LOGIN_ITEMS[@]}"; do
  if [ "$(se "exists login item \"$name\"")" != true ]; then
    echo "  （$name はログイン項目に無い）"
    continue
  fi
  echo "  外す: $name"
  [ "$MODE" = apply ] || continue
  path=$(se "get path of login item \"$name\"")
  if se "delete login item \"$name\"" >/dev/null; then
    mkdir -p "$STATE_DIR"
    printf '%s\t%s\n' "$name" "$path" >> "$STATE"
  else
    echo "  !! 失敗: $name（システム設定 → 一般 → ログイン項目 から手で外してください）"
  fi
done

echo "== 2. 復元で立ち上がったら閉じるアプリ（ログイン後 ${WINDOW_SEC} 秒間）"
for a in "${QUIT_APPS[@]}"; do echo "  $a"; done
echo "  → $AGENT"

if [ "$MODE" = apply ]; then
  mkdir -p "$(dirname "$WORKER")" "$(dirname "$AGENT")"
  {
    echo '#!/bin/bash'
    echo '# mac_login_quiet.sh が生成。ログイン直後に復元された指定アプリを終了する。'
    printf 'APPS=('; printf '"%s" ' "${QUIT_APPS[@]}"; echo ')'
    echo "END=\$((SECONDS + $WINDOW_SEC))"
    cat <<'EOS'
while [ "$SECONDS" -lt "$END" ]; do
  for a in "${APPS[@]}"; do
    # プロセス名は 16 文字で切れる（Microsoft PowerPoint 等）のでパスで探す
    pat="/$a.app/Contents/MacOS/"
    pgrep -qf "$pat" || continue
    # まず通常の終了。権限が無い等で失敗したら SIGTERM
    if ! osascript -e "tell application \"$a\" to quit" >/dev/null 2>&1; then
      pkill -TERM -f "$pat"
    fi
    echo "$(date '+%F %T') quit: $a"
  done
  sleep 2
done
EOS
  } > "$WORKER"
  chmod +x "$WORKER"

  cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$WORKER</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/$LABEL.log</string>
  <key>StandardErrorPath</key><string>/tmp/$LABEL.log</string>
</dict>
</plist>
EOF
  plutil -lint "$AGENT" >/dev/null || { echo "!! plist が不正です: $AGENT" >&2; exit 1; }
  # 登録だけ。RunAtLoad で今すぐ走ると開いている Excel 等が閉じるので、今回は起動させない
  launchctl enable "gui/$UID_NUM/$LABEL" 2>/dev/null
  echo
  echo "完了。次回ログインから有効になります（今開いているアプリは閉じません）。"
  echo "動作ログ: /tmp/$LABEL.log"
  echo "元に戻す: bash $0 --undo"
fi
