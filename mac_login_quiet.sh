#!/bin/bash
# mac_login_quiet.sh — ログイン時に勝手に立ち上がるアプリを止める（アプリ自体は消さない）
#
#   bash mac_login_quiet.sh            # ドライラン（何をするか表示するだけ）
#   bash mac_login_quiet.sh --apply    # 実行（途中で Mac のパスワードを聞かれる）
#   bash mac_login_quiet.sh --status   # 復元リストの中身と動作ログを見る
#   bash mac_login_quiet.sh --undo     # 元に戻す
#
# やること:
#   1. LOGIN_ITEMS をログイン項目から外す（アプリは残る）
#   2. 復元リストから NO_RELAUNCH を消す LaunchDaemon を入れる  ← 本命
#      macOS はログアウト時に「次回ログインで開き直すアプリ一覧」を
#      ~/Library/Preferences/ByHost/com.apple.loginwindow.<UUID>.plist の
#      TALAppsToRelaunchAtLogin に書く。書かれた直後にこのデーモンが指定アプリだけ消すので、
#      次のログインで Office / Zoom は一瞬も起動しない。Chrome 等は今まで通り復元される。
#      ログアウト後も動き続ける必要があるので、ユーザーの LaunchAgent ではなく root のデーモン。
#   3. 保険: それでも立ち上がった場合はログイン後 60 秒以内に終了させる LaunchAgent
#      （FileVault の再起動直後など、2 が間に合わなかった時用）

set -u

LOGIN_ITEMS=("Clipy")
# 復元させないアプリ: "バンドルID|アプリ名"
NO_RELAUNCH=(
  "com.microsoft.Excel|Microsoft Excel"
  "com.microsoft.Word|Microsoft Word"
  "com.microsoft.Powerpoint|Microsoft PowerPoint"
  "us.zoom.xos|zoom.us"
)
WINDOW_SEC=60

ME=$(id -un)
UID_NUM=$(id -u)
STATE_DIR="$HOME/.config/mac_login_quiet"
STATE="$STATE_DIR/removed_login_items.tsv"

D_LABEL="local.strip-relaunch-list"
D_PLIST="/Library/LaunchDaemons/$D_LABEL.plist"
D_SCRIPT="/usr/local/sbin/strip_relaunch_list.sh"
D_LOG="/var/log/$D_LABEL.log"

A_LABEL="local.quit-restored-apps"
A_PLIST="$HOME/Library/LaunchAgents/$A_LABEL.plist"
A_SCRIPT="$HOME/.local/bin/quit_restored_apps.sh"
A_LOG="/tmp/$A_LABEL.log"

BYHOST_DIR="$HOME/Library/Preferences/ByHost"

MODE=dry
case "${1:-}" in
  ""|--dry-run) MODE=dry ;;
  --apply)  MODE=apply ;;
  --status) MODE=status ;;
  --undo)   MODE=undo ;;
  -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
  *) echo "不明な引数: $1（--help 参照）" >&2; exit 1 ;;
esac

[ "$(uname)" = Darwin ] || { echo "macOS 専用です。" >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { echo "sudo なしで実行してください（必要な所だけパスワードを聞きます）。" >&2; exit 1; }

se() { osascript -e "tell application \"System Events\" to $1" 2>/dev/null; }

# ------------------------------------------------------------------ status
if [ "$MODE" = status ]; then
  echo "== 前回ログアウト時に保存された復元リスト"
  defaults -currentHost read com.apple.loginwindow TALAppsToRelaunchAtLogin 2>/dev/null \
    | grep -E 'BundleID' || echo "  （空、または無し）"
  echo "== 復元リスト掃除デーモンのログ ($D_LOG)"
  tail -n 20 "$D_LOG" 2>/dev/null || echo "  （まだ無し）"
  echo "== 保険の自動終了ログ ($A_LOG)"
  tail -n 20 "$A_LOG" 2>/dev/null || echo "  （まだ無し = 保険は発動していない）"
  exit 0
fi

# ------------------------------------------------------------------ undo
if [ "$MODE" = undo ]; then
  sudo -v || exit 1
  if [ -f "$D_PLIST" ] || [ -f "$D_SCRIPT" ]; then
    sudo launchctl bootout system "$D_PLIST" 2>/dev/null
    sudo rm -f "$D_PLIST" "$D_SCRIPT"
    echo "復元リスト掃除デーモンを外した"
  fi
  if [ -f "$A_PLIST" ]; then
    launchctl bootout "gui/$UID_NUM" "$A_PLIST" 2>/dev/null
    rm -f "$A_PLIST" "$A_SCRIPT"
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
if [ "$MODE" = apply ]; then
  sudo -v || exit 1
else
  echo "【ドライラン】何も変更しません。実行するには --apply を付けてください。"
fi

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

echo "== 2. 次回ログインで復元させないアプリ（それ以外は今まで通り復元）"
IDS=""; NAMES=()
for e in "${NO_RELAUNCH[@]}"; do
  IDS="$IDS ${e%%|*}"; NAMES+=("${e#*|}")
  echo "  ${e#*|}  (${e%%|*})"
done
echo "  → $D_PLIST（root で常駐。ログアウト後も動く）"
echo "== 3. 保険: それでも立ち上がったらログイン後 ${WINDOW_SEC} 秒以内に終了"
echo "  → $A_PLIST"

[ "$MODE" = apply ] || exit 0

# ---- 2. 復元リスト掃除デーモン（root 所有・ユーザーが書き換えられない場所に置く）
TMP=$(mktemp)
{
  echo '#!/bin/bash'
  echo '# mac_login_quiet.sh が生成。ログアウト時に保存された復元リストから指定アプリを消す。'
  echo "USER_NAME=\"$ME\""
  echo "BYHOST=\"$BYHOST_DIR\""
  echo "IDS=\" $(echo "$IDS" | tr '[:upper:]' '[:lower:]') \""
  cat <<'EOS'
PB=/usr/libexec/PlistBuddy
for f in "$BYHOST"/com.apple.loginwindow.*.plist; do
  [ -f "$f" ] || continue
  # 編集はユーザー権限で行う（root で書くと所有者が変わり、次回 macOS が書けなくなる）
  n=$(sudo -u "$USER_NAME" $PB -c "Print :TALAppsToRelaunchAtLogin" "$f" 2>/dev/null | grep -c 'BundleID')
  i=$((n - 1))
  while [ "$i" -ge 0 ]; do
    id=$(sudo -u "$USER_NAME" $PB -c "Print :TALAppsToRelaunchAtLogin:$i:BundleID" "$f" 2>/dev/null)
    lid=$(echo "$id" | tr '[:upper:]' '[:lower:]')
    case "$IDS" in
      *" $lid "*)
        sudo -u "$USER_NAME" $PB -c "Delete :TALAppsToRelaunchAtLogin:$i" "$f" \
          && echo "$(date '+%F %T') 復元リストから除外: $id" ;;
    esac
    i=$((i - 1))
  done
done
exit 0
EOS
} > "$TMP"
sudo mkdir -p "$(dirname "$D_SCRIPT")"
sudo install -o root -g wheel -m 755 "$TMP" "$D_SCRIPT" || { echo "!! 配置失敗: $D_SCRIPT" >&2; exit 1; }
rm -f "$TMP"

TMP=$(mktemp)
cat > "$TMP" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$D_LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$D_SCRIPT</string></array>
  <key>WatchPaths</key>
  <array><string>$BYHOST_DIR</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$D_LOG</string>
  <key>StandardErrorPath</key><string>$D_LOG</string>
</dict>
</plist>
EOF
plutil -lint "$TMP" >/dev/null || { echo "!! plist が不正" >&2; exit 1; }
sudo launchctl bootout system "$D_PLIST" 2>/dev/null
sudo install -o root -g wheel -m 644 "$TMP" "$D_PLIST" || { echo "!! 配置失敗: $D_PLIST" >&2; exit 1; }
rm -f "$TMP"
sudo launchctl bootstrap system "$D_PLIST" || { echo "!! デーモン起動失敗: $D_LABEL" >&2; exit 1; }
echo "  デーモン起動: $D_LABEL"

# ---- 3. 保険の自動終了 LaunchAgent
mkdir -p "$(dirname "$A_SCRIPT")" "$(dirname "$A_PLIST")"
{
  echo '#!/bin/bash'
  echo '# mac_login_quiet.sh が生成。復元リスト掃除が間に合わず起動した指定アプリを終了する保険。'
  printf 'APPS=('; printf '"%s" ' "${NAMES[@]}"; echo ')'
  echo "END=\$((SECONDS + $WINDOW_SEC))"
  cat <<'EOS'
while [ "$SECONDS" -lt "$END" ]; do
  for a in "${APPS[@]}"; do
    # プロセス名は 16 文字で切れる（Microsoft PowerPoint 等）のでパスで探す
    pat="/$a.app/Contents/MacOS/"
    pgrep -qf "$pat" || continue
    if ! osascript -e "tell application \"$a\" to quit" >/dev/null 2>&1; then
      pkill -TERM -f "$pat"
    fi
    echo "$(date '+%F %T') quit: $a"
  done
  sleep 2
done
EOS
} > "$A_SCRIPT"
chmod +x "$A_SCRIPT"
cat > "$A_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$A_LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$A_SCRIPT</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$A_LOG</string>
  <key>StandardErrorPath</key><string>$A_LOG</string>
</dict>
</plist>
EOF
# 今は読み込まない（今開いている Excel 等を閉じないため）。次回ログインから有効

echo
echo "完了。次のログアウト → ログインから効きます（今開いているアプリはそのまま）。"
echo "確認: bash $0 --status"
echo "元に戻す: bash $0 --undo"
