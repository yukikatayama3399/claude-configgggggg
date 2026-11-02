#!/bin/bash
# mac_startup_cleanup.sh — Mac の起動時に立ち上がる不要アプリ・常駐ヘルパーを片付ける
#
# 使い方（sudo は付けない。必要な所だけスクリプトが sudo を求める）:
#   bash mac_startup_cleanup.sh               # ドライラン: 何を退避するか表示するだけ
#   bash mac_startup_cleanup.sh --apply       # 実行
#   bash mac_startup_cleanup.sh --list-apps   # インストール済みアプリを最終使用日の古い順に一覧
#   bash mac_startup_cleanup.sh --restore ~/startup_cleanup_backup/<日時>   # 元に戻す
#
# 削除はしない。全部 ~/startup_cleanup_backup/<日時>/files/<元のパス> に退避するので、
# --restore で元の場所に戻せる。様子を見て問題なければ、そのフォルダをゴミ箱へ。
#
# 対象（存在するものだけ処理する。無ければ何もしない）:
#   - Clipy（ログイン項目＋アプリ）
#   - Microsoft Excel / Word / PowerPoint
#       Outlook / OneNote / Defender 等が残っていなければ AutoUpdate とライセンスヘルパーも
#   - Zoom（アプリ＋常駐 Daemon＋updater）
#   - Oracle Java の更新ヘルパー・ブラウザプラグイン・設定パネル（JDK 本体は触らない）
#   - ClashX Pro / XQuartz / Canon MasterInstaller / HighfiveApp
#
# 触らないもの: Trend Micro・Avast（セキュリティ）、Google 日本語入力、Karabiner、
#   Google / OneDrive / Teams の updater、DisplayLink、Brother、SwitchResX、Logi

set -u

MODE=dry
RESTORE_DIR=""
case "${1:-}" in
  ""|--dry-run) MODE=dry ;;
  --apply)      MODE=apply ;;
  --list-apps)  MODE=list ;;
  --restore)    MODE=restore; RESTORE_DIR="${2:-}" ;;
  -h|--help)    sed -n '2,25p' "$0"; exit 0 ;;
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
  local p="$1"
  [ -e "$p" ] || [ -L "$p" ] || return 0
  FOUND=$((FOUND + 1))
  echo "  退避: $p"
  [ "$MODE" = apply ] || return 0
  mkdir -p "$BACKUP/files$(dirname "$p")"
  if as_owner "$p" mv "$p" "$BACKUP/files$p"; then
    printf 'FILE\t%s\n' "$p" >> "$MANIFEST"
  else
    fail "$p"
  fi
}

# launchd ジョブを止めて plist と PrivilegedHelperTools の実体を退避
remove_job() {
  local plist="$1" prog
  [ -e "$plist" ] || return 0
  prog=$(plutil -extract Program raw -o - "$plist" 2>/dev/null \
      || plutil -extract ProgramArguments.0 raw -o - "$plist" 2>/dev/null)
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

quit_app() {
  [ "$MODE" = apply ] || return 0
  osascript -e "tell application \"$1\" to quit" >/dev/null 2>&1 || true
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

echo "== Clipy"
quit_app Clipy
remove_login_item Clipy
stash /Applications/Clipy.app

echo "== Microsoft Excel / Word / PowerPoint"
for a in "Microsoft Excel" "Microsoft Word" "Microsoft PowerPoint"; do
  quit_app "$a"
  stash "/Applications/$a.app"
done
KEEP_MS=""
for a in "Microsoft Outlook" "Microsoft OneNote" "Microsoft Defender" "Microsoft Remote Desktop" "Windows App"; do
  [ -d "/Applications/$a.app" ] && KEEP_MS="$KEEP_MS $a,"
done
if [ -z "$KEEP_MS" ]; then
  remove_job /Library/LaunchAgents/com.microsoft.update.agent.plist
  remove_job /Library/LaunchDaemons/com.microsoft.autoupdate.helper.plist
  stash "/Library/Application Support/Microsoft/MAU2.0"
  remove_job /Library/LaunchDaemons/com.microsoft.office.licensingV2.helper.plist
else
  echo "  （${KEEP_MS%,} が残っているので AutoUpdate とライセンスヘルパーは残す）"
fi

echo "== Zoom"
quit_app zoom.us
stash /Applications/zoom.us.app
remove_job /Library/LaunchDaemons/us.zoom.ZoomDaemon.plist
remove_job /Library/LaunchAgents/us.zoom.updater.plist
remove_job /Library/LaunchAgents/us.zoom.updater.login.check.plist
stash "/Library/Internet Plug-Ins/ZoomUsPlugIn.plugin"

echo "== Oracle Java（更新ヘルパー・プラグイン。JDK 本体は残す）"
remove_job /Library/LaunchDaemons/com.oracle.java.Helper-Tool.plist
remove_job /Library/LaunchAgents/com.oracle.java.Java-Updater.plist
stash "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin"
stash /Library/PreferencePanes/JavaControlPanel.prefPane
stash "/Library/Application Support/Oracle/Java"

echo "== ClashX Pro"
quit_app "ClashX Pro"
remove_job /Library/LaunchDaemons/com.west2online.ClashXPro.ProxyConfigHelper.plist
stash "/Applications/ClashX Pro.app"

echo "== XQuartz"
remove_job /Library/LaunchDaemons/org.macosforge.xquartz.privileged_startx.plist
remove_job /Library/LaunchAgents/org.macosforge.xquartz.startx.plist
stash /Applications/Utilities/XQuartz.app
stash /opt/X11

echo "== Canon MasterInstaller"
remove_job /Library/LaunchDaemons/jp.co.canon.MasterInstaller.plist

echo "== HighfiveApp"
quit_app HighfiveApp
remove_job "$HOME/Library/LaunchAgents/com.fatline.HighfiveApp.ota.plist"
stash "$HOME/Applications/HighfiveApp.app"

echo
echo "対象: ${FOUND} 件"

# ClashX がシステムのプロキシを 127.0.0.1 に向けたまま残っていると通信できなくなる
if scutil --proxy 2>/dev/null | grep -qE 'Proxy : 127\.0\.0\.1'; then
  echo "⚠ システムのプロキシが 127.0.0.1 に向いています（ClashX の残り設定の可能性）。"
  echo "  システム設定 → ネットワーク → 使用中の回線 → 詳細 → プロキシ を全部オフにしてください。"
fi

if [ "$MODE" = apply ]; then
  if [ -n "$FAILED" ]; then
    echo
    echo "退避できなかったもの:"
    printf '%s' "$FAILED"
    echo "  アプリが 'Operation not permitted' の場合は、Finder でゴミ箱へドラッグするか、"
    echo "  システム設定 → プライバシーとセキュリティ → アプリの管理 でターミナルを許可して再実行。"
  fi
  echo
  echo "退避先: $BACKUP"
  echo "元に戻す: bash $0 --restore $BACKUP"
  echo "再起動して問題なければ、退避フォルダはゴミ箱へ入れてOK。"
fi
