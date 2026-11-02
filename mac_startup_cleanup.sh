#!/bin/bash
# mac_startup_cleanup.sh — 使っていないアプリと常駐の残骸を片付ける（MacBook-Air-3 用の一覧）
#
# 使い方（sudo は付けない。必要な所だけスクリプトが sudo を求める）:
#   bash mac_startup_cleanup.sh               # ドライラン: 何を退避するか表示するだけ
#   bash mac_startup_cleanup.sh --apply       # 実行
#   bash mac_startup_cleanup.sh --list-apps   # インストール済みアプリを最終使用日の古い順に一覧
#   bash mac_startup_cleanup.sh --restore ~/startup_cleanup_backup/<日時>   # 元に戻す
#
# 削除はしない。全部 ~/startup_cleanup_backup/<日時>/files/<元のパス> に退避するので、
# --restore で元の場所に戻せる。様子を見て問題なければ、そのフォルダをゴミ箱へ。
# アプリ本体だけを動かすので、各アプリのデータ（~/Dropbox、1Password の保管庫、
# ~/Library 配下の設定など）はそのまま残る。
#
# 残すもの（2026-11-02 決定）: Excel / Word / PowerPoint / OneDrive / Zoom とその更新ツール、
#   Google Docs/Sheets/Slides のショートカット、Bitwarden、UCSS、Apple 純正、連絡系アプリ、
#   Trend Micro・Avast、Google 日本語入力、Karabiner、DisplayLink、Brother、SwitchResX

set -u

# ---- 退避するアプリ（存在するものだけ処理）
REMOVE_APPS=(
  # 前から不要
  "$HOME/Applications/Clipy.app"
  "$HOME/Applications/HighfiveApp.app"
  "$HOME/Applications/PhoneClean.app"
  # Microsoft（Excel / Word / PowerPoint / OneDrive は残す）
  "/Applications/Microsoft Outlook.app"
  "/Applications/Microsoft Teams.app"
  # 古い・サービス終了・代替あり
  "/Applications/Utilities/QuickTime Player 7.app"
  "/Applications/Utilities/Adobe AIR Uninstaller.app"
  "/Applications/Utilities/Adobe AIR Application Installer.app"
  "/Applications/Utilities/LogiMgr Uninstaller.app"
  "/Applications/Skype.app"
  "/Applications/Twitter.app"
  "/Applications/HyperSwitch.app"
  "/Applications/Google AdWords Editor.app"
  "/Applications/MacWinZipper.app"
  "/Applications/The Unarchiver.app"
  "/Applications/OmniDiskSweeper_容量整理.app"
  "/Applications/PDFelementPro6.app"
  "/Applications/Shadowrocket.app"
  "/Applications/1Password 7.app"
  # 動画編集
  "/Applications/CapCut 2.app"
  "/Applications/Wondershare Filmora Mac.app"
  "/Applications/Vrew.app"
  # メモ・読書
  "/Applications/Goodnotes.app"
  "/Applications/Amazon Kindle.app"
  "/Applications/Skim.app"
  # ストレージ
  "/Applications/Dropbox.app"
  # ブラウザ・VPN
  "/Applications/Firefox.app"
  "/Applications/Fellou.app"
  "/Applications/Sidekick.app"
  "/Applications/ProtonVPN.app"
  "/Applications/Notion Web Clipper.app"
  # マウス系
  "/Applications/Logi Options.app"
  "/Applications/lghub.app"
  "/Applications/Utilities/SteerMouse.app"
  # その他
  "/Applications/iTerm.app"
  "/Applications/moomoo.app"
)

# ---- 退避する常駐ジョブ（アプリ本体が無い残骸・上のアプリ付属の updater）
#      上のアプリの中を指している LaunchAgent / LaunchDaemon は、この一覧に無くても自動で拾う
REMOVE_JOBS=(
  /Library/LaunchDaemons/com.microsoft.teams.TeamsUpdaterDaemon.plist
  /Library/LaunchDaemons/com.oracle.java.Helper-Tool.plist
  /Library/LaunchAgents/com.oracle.java.Java-Updater.plist
  /Library/LaunchDaemons/com.west2online.ClashXPro.ProxyConfigHelper.plist
  /Library/LaunchDaemons/org.macosforge.xquartz.privileged_startx.plist
  /Library/LaunchAgents/org.macosforge.xquartz.startx.plist
  /Library/LaunchDaemons/jp.co.canon.MasterInstaller.plist
  "$HOME/Library/LaunchAgents/com.fatline.HighfiveApp.ota.plist"
)

# ---- その他の残骸（アプリ本体が既に無いもの）
REMOVE_PATHS=(
  "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin"
  /Library/PreferencePanes/JavaControlPanel.prefPane
  "/Library/Application Support/Oracle/Java"
  /opt/X11
)

MODE=dry
RESTORE_DIR=""
case "${1:-}" in
  ""|--dry-run) MODE=dry ;;
  --apply)      MODE=apply ;;
  --list-apps)  MODE=list ;;
  --restore)    MODE=restore; RESTORE_DIR="${2:-}" ;;
  -h|--help)    sed -n '2,19p' "$0"; exit 0 ;;
  *) echo "不明な引数: $1（--help 参照）" >&2; exit 1 ;;
esac

if [ "$(uname)" != "Darwin" ]; then
  echo "macOS 専用です。" >&2; exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
  echo "sudo を付けずに実行してください（必要な所だけ sudo を求めます）。" >&2; exit 1
fi

UID_NUM=$(id -u)
BACKUP="$HOME/startup_cleanup_backup/$(date +%Y%m%d-%H%M%S)"
MANIFEST="$BACKUP/manifest.tsv"
FOUND=0
FREED_KB=0
FAILED=""

# $HOME 配下でなければ sudo を付けて実行
as_owner() {
  local p="$1"; shift
  case "$p" in
    "$HOME"/*) "$@" ;;
    *) sudo "$@" ;;
  esac
}

fail() { FAILED="${FAILED}  - $1"$'\n'; echo "    !! 失敗: $1"; }

# ---------------------------------------------------------------- --list-apps
if [ "$MODE" = list ]; then
  echo "最終使用日  サイズ  アプリ  （古い順。'未使用' は記録なし）"
  for app in /Applications/*.app /Applications/Utilities/*.app "$HOME"/Applications/*.app; do
    [ -d "$app" ] || continue
    used=$(mdls -raw -name kMDItemLastUsedDate "$app" 2>/dev/null)
    case "$used" in ""|"(null)") used="0000-00-00(未使用)" ;; *) used="${used%% *}" ;; esac
    size=$(du -sh "$app" 2>/dev/null | cut -f1)
    printf '%s\t%s\t%s\n' "$used" "$size" "${app#/Applications/}"
  done | sort
  exit 0
fi

# ---------------------------------------------------------------- --restore
if [ "$MODE" = restore ]; then
  [ -n "$RESTORE_DIR" ] && [ -f "$RESTORE_DIR/manifest.tsv" ] || {
    echo "manifest.tsv のある退避フォルダを指定してください: --restore ~/startup_cleanup_backup/<日時>" >&2
    ls -d "$HOME"/startup_cleanup_backup/*/ 2>/dev/null
    exit 1
  }
  sudo -v || exit 1
  while IFS=$'\t' read -r kind a b; do
    case "$kind" in
      FILE)
        src="$RESTORE_DIR/files$a"
        if [ -e "$a" ]; then echo "  skip（既にある）: $a"; continue; fi
        [ -e "$src" ] || { echo "  skip（退避物なし）: $a"; continue; }
        as_owner "$a" mkdir -p "$(dirname "$a")"
        if as_owner "$a" mv "$src" "$a"; then
          echo "  戻した: $a"
          case "$a" in
            /Library/LaunchDaemons/*.plist) sudo launchctl bootstrap system "$a" 2>/dev/null ;;
            */LaunchAgents/*.plist) launchctl bootstrap "gui/$UID_NUM" "$a" 2>/dev/null ;;
          esac
        else
          fail "$a"
        fi
        ;;
      LOGIN)
        osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$b\", hidden:false}" >/dev/null \
          && echo "  ログイン項目に戻した: $a" || fail "ログイン項目 $a"
        ;;
    esac
  done < "$RESTORE_DIR/manifest.tsv"
  [ -n "$FAILED" ] && { echo; echo "戻せなかったもの:"; printf '%s' "$FAILED"; }
  echo "完了。"
  exit 0
fi

# ---------------------------------------------------------------- dry-run / apply
if [ "$MODE" = apply ]; then
  echo "退避先: $BACKUP"
  sudo -v || exit 1
  mkdir -p "$BACKUP/files"
  : > "$MANIFEST"
else
  echo "【ドライラン】何も変更しません。実行するには --apply を付けてください。"
fi

# ファイル／フォルダを退避フォルダへ移動
stash() {
  local p="$1" kb
  [ -e "$p" ] || [ -L "$p" ] || return 0
  FOUND=$((FOUND + 1))
  kb=$(du -sk "$p" 2>/dev/null | cut -f1)
  FREED_KB=$((FREED_KB + ${kb:-0}))
  echo "  退避: $p"
  [ "$MODE" = apply ] || return 0
  mkdir -p "$BACKUP/files$(dirname "$p")"
  if as_owner "$p" mv "$p" "$BACKUP/files$p"; then
    printf 'FILE\t%s\n' "$p" >> "$MANIFEST"
  else
    fail "$p"
  fi
}

job_program() {
  plutil -extract Program raw -o - "$1" 2>/dev/null \
    || plutil -extract ProgramArguments.0 raw -o - "$1" 2>/dev/null
}

# launchd ジョブを止めて plist と PrivilegedHelperTools の実体を退避
remove_job() {
  local plist="$1" prog
  [ -e "$plist" ] || return 0
  prog=$(job_program "$plist")
  if [ "$MODE" = apply ]; then
    case "$plist" in
      /Library/LaunchDaemons/*) sudo launchctl bootout system "$plist" 2>/dev/null ;;
      *)                        launchctl bootout "gui/$UID_NUM" "$plist" 2>/dev/null ;;
    esac
  fi
  stash "$plist"
  case "$prog" in
    /Library/PrivilegedHelperTools/*) stash "$prog" ;;
  esac
}

# 起動中のときだけ、バンドル ID 指定で終了させる。
# 名前で tell すると、ファイル名とアプリ名が違う場合に「〜はどこですか？」ダイアログで止まる。
quit_app() {
  local app="$1" bid
  [ "$MODE" = apply ] || return 0
  pgrep -qf "$app/Contents/MacOS/" || return 0
  bid=$(defaults read "$app/Contents/Info" CFBundleIdentifier 2>/dev/null)
  if [ -n "$bid" ]; then
    osascript -e "with timeout of 15 seconds" -e "tell application id \"$bid\" to quit" -e "end timeout" >/dev/null 2>&1
  fi
  sleep 1
  pgrep -qf "$app/Contents/MacOS/" && pkill -TERM -f "$app/Contents/MacOS/"
  return 0
}

remove_login_item() {
  local name="$1" path
  [ "$(osascript -e "tell application \"System Events\" to exists login item \"$name\"" 2>/dev/null)" = true ] || return 0
  FOUND=$((FOUND + 1))
  echo "  ログイン項目から外す: $name"
  [ "$MODE" = apply ] || return 0
  path=$(osascript -e "tell application \"System Events\" to get path of login item \"$name\"" 2>/dev/null)
  if osascript -e "tell application \"System Events\" to delete login item \"$name\"" >/dev/null; then
    printf 'LOGIN\t%s\t%s\n' "$name" "$path" >> "$MANIFEST"
  else
    fail "ログイン項目 $name"
  fi
}

echo "== 1. 常駐ジョブ（アプリ付属の updater・残骸）"
for j in "${REMOVE_JOBS[@]}"; do remove_job "$j"; done
# 退避するアプリの中を指している LaunchAgent / LaunchDaemon も止める
for plist in /Library/LaunchAgents/*.plist /Library/LaunchDaemons/*.plist "$HOME"/Library/LaunchAgents/*.plist; do
  [ -e "$plist" ] || continue
  prog=$(job_program "$plist")
  [ -n "$prog" ] || continue
  for app in "${REMOVE_APPS[@]}"; do
    case "$prog" in "$app"/*) remove_job "$plist"; break ;; esac
  done
done

echo "== 2. アプリ"
for app in "${REMOVE_APPS[@]}"; do
  [ -e "$app" ] || continue
  name=$(basename "$app" .app)
  quit_app "$app"
  remove_login_item "$name"
  stash "$app"
done

echo "== 3. その他の残骸"
for p in "${REMOVE_PATHS[@]}"; do stash "$p"; done

echo
echo "対象: ${FOUND} 件 / 空く容量: 約 $((FREED_KB / 1024 / 1024)) GB（退避フォルダを空にした後）"

# ClashX がシステムのプロキシを 127.0.0.1 に向けたまま残っていると通信できなくなる
if scutil --proxy 2>/dev/null | grep -qE 'Proxy : 127\.0\.0\.1'; then
  echo "⚠ システムのプロキシが 127.0.0.1 に向いています（ClashX / Shadowrocket の残り設定の可能性）。"
  echo "  システム設定 → ネットワーク → 使用中の回線 → 詳細 → プロキシ を全部オフにしてください。"
fi

if [ "$MODE" = apply ]; then
  if [ -n "$FAILED" ]; then
    echo
    echo "退避できなかったもの:"
    printf '%s' "$FAILED"
    echo "  'Operation not permitted' の場合は、システム設定 → プライバシーとセキュリティ →"
    echo "  アプリの管理（とフルディスクアクセス）でターミナルを許可して、もう一度 --apply。"
    echo "  または Finder でそのアプリをゴミ箱へドラッグ。"
  fi
  echo
  echo "退避先: $BACKUP"
  echo "元に戻す: bash $0 --restore $BACKUP"
  echo "数日使って問題なければ、退避フォルダをゴミ箱へ入れて空にすると容量が空きます。"
fi
