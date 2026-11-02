#!/bin/bash
# mac_junk_clean.sh — キャッシュと削除済みアプリの残りデータを消す（MacBook-Air-3 / 2026-11-02 の計測結果から作成）
#
#   bash mac_junk_clean.sh             # ドライラン（消す対象と容量を表示するだけ）
#   bash mac_junk_clean.sh --apply     # 削除（ゴミ箱を経由せず完全に消す。元に戻せない）
#   bash mac_junk_clean.sh --inspect   # 大物（Claude / Google / OneDrive / Ollama 等）の内訳を表示するだけ
#
# 消すのは「作り直されるキャッシュ」と「本体を削除済みのアプリのデータ」だけ。
# 名前を 1 つずつ指定している（パターン一致で macOS 本体の login 系を巻き込まないため）。
# 残しているアプリ（Office / OneDrive / Zoom / Slack / LINE / WeChat / Claude 等）のデータには触らない。
# 1Password 7 の保管庫（Group Containers/2BUA8C4S2C.com.agilebits）も念のため残す。

set -u

L="$HOME/Library"

# Chrome を終了してから消すもの
CHROME_CACHE=(
  "$L/Caches/Google/Chrome"
)

# 作り直されるキャッシュ・更新ファイルの残り
CACHES=(
  "$L/Caches/now.typeless.desktop.ShipIt"
  "$L/Caches/typeless-updater"
  "$L/Caches/com.todesktop.24062654z2002es.ShipIt"
  "$L/Caches/@circlebackdesktop-updater"
  "$L/Caches/pip"
  "$L/Caches/com.openai.chat"
)

# 2026-11-02 に本体を削除したアプリの残りデータ
LEFTOVERS=(
  # Goodnotes
  "$L/Containers/com.goodnotesapp.x"
  "$L/Containers/com.goodnotesapp.x.WidgetExtension"
  "$L/Group Containers/group.com.goodnotesapp.open-in-action-extension"
  "$L/Group Containers/group.com.goodnotesapp.nexushelper"
  "$L/Group Containers/group.com.goodnotesapp.goodnotes"
  # Wondershare（Filmora / PDFelement / Recoverit）
  "$L/Application Support/com.wondershare.Installer"
  "$L/Application Support/Wondershare Filmora Mac"
  "$L/Application Support/WonderShare AI Stylizer"
  "$L/Application Support/wondershare"
  "$L/Application Support/com.wondershare.PDFelement6.Professional"
  "$L/Application Support/com.wondershare.recoverit"
  "$L/WebKit/com.wondershare.Installer"
  "$L/WebKit/com.wondershare.filmoramacos"
  "$L/WebKit/com.wondershare.recoverit"
  "$L/HTTPStorages/com.wondershare.Installer"
  "$L/HTTPStorages/com.wondershare.recoverit"
  "$L/HTTPStorages/com.wondershare.ossmgr"
  "$L/HTTPStorages/com.wondershare.filmoramacos.binarycookies"
  "$L/Logs/Wondershare"
  "$L/Saved Application State/com.wondershare.filmoramacos.savedState"
  "$L/Saved Application State/com.wondershare.Installer.savedState"
  # Vrew
  "$L/Application Support/vrew"
  "$L/Saved Application State/com.voyagerx.vrew.savedState"
  # Microsoft Teams / Outlook（Office 共通の UBF8T346G9.Office は残す）
  "$L/Containers/com.microsoft.teams2"
  "$L/Containers/com.microsoft.teams2.respawn"
  "$L/Containers/com.microsoft.teams2.notificationcenter"
  "$L/Containers/com.microsoft.teams2.launcher"
  "$L/Containers/com.microsoft.teams2.widgetextension"
  "$L/Group Containers/UBF8T346G9.com.microsoft.teams"
  "$L/WebKit/com.microsoft.teams"
  "$L/HTTPStorages/com.microsoft.teams.binarycookies"
  "$L/Saved Application State/com.microsoft.teams.savedState"
  "$L/Containers/com.microsoft.Outlook"
  "$L/Containers/com.microsoft.outlook.profilemanager"
  "$L/Containers/com.microsoft.Outlook.CalendarWidget"
  # ブラウザ（Fellou / Firefox / Sidekick）
  "$L/Application Support/Fellou"
  "$L/Logs/Fellou"
  "$L/Saved Application State/com.fellou.ai.savedState"
  "$L/Application Support/Firefox"
  "$L/Application Support/Mozilla"
  "$L/Caches/Firefox"
  "$L/Caches/Mozilla"
  "$L/WebKit/org.mozilla.firefox"
  "$L/Application Support/Sidekick"
  "$L/Caches/Sidekick"
  # Dropbox（~/Dropbox の中身は別扱い）
  "$L/Application Support/Dropbox"
  "$L/Containers/com.getdropbox.dropbox.garcon"
  "$L/Containers/com.getdropbox.dropbox.fileprovider"
  "$L/Containers/com.getdropbox.dropbox.TransferExtension"
  "$L/Containers/com.dropbox.alternatenotificationservice"
  "$L/Group Containers/com.getdropbox.dropbox.garcon"
  "$L/Group Containers/com.dropbox.client.crashpad"
  "$L/Group Containers/G7HH3F8CAK.com.getdropbox.dropbox.sync"
  "$L/HTTPStorages/com.dropbox.DropboxMacUpdate"
  # その他
  "$L/Application Support/com.imobie.PhoneClean"
  "$L/Application Support/LGHUB"
  "$L/Application Support/Logitech"
  "$L/HTTPStorages/com.logi.ghub.installer"
  "$L/Saved Application State/com.logi.ghub.ui.savedState"
  "$L/Application Support/com.clipy-app.Clipy"
  "$L/Application Support/Clipy"
  "$L/Caches/com.clipy-app.Clipy"
  "$L/HTTPStorages/com.clipy-app.Clipy"
  "$L/HTTPStorages/com.clipy-app.Clipy.binarycookies"
  "$L/Application Support/iTerm"
  "$L/HTTPStorages/com.googlecode.iterm2"
  "$L/HTTPStorages/com.googlecode.iterm2.binarycookies"
  "$L/HTTPStorages/com.skype.skype"
  "$L/Saved Application State/com.skype.skype.savedState"
  "$L/Logs/Skype Helper (Renderer)"
  "$L/Application Support/HyperSwitch"
  "$L/Containers/ch.protonvpn.mac"
  "$L/Group Containers/J6S6Q257EK.group.ch.protonvpn.mac"
  "$L/Containers/cx.c3.theunarchiver"
  "$L/Containers/com.liguangming.Shadowrocket.Shortcuts"
  "$L/Group Containers/group.com.liguangming.Shadowrocket"
  "$L/Containers/com.amazon.Lassen.SendToKindleExtension"
  "$L/Group Containers/group.com.moomoo.mm.StockQuoteWidgetMoo"
  # Java（本体は削除済み）
  "$L/Application Support/Java"
  # 本体が既に無いアプリ（--inspect で「アプリ: 見つからない」を確認済み）
  "$L/Application Support/Dia"
  "$L/Application Support/LarkInternational"
  "$L/Application Support/Microsoft Edge"
  "$L/Application Support/com.openai.atlas"
  "$L/Application Support/Adobe"
)

MODE=dry
case "${1:-}" in
  ""|--dry-run) MODE=dry ;;
  --apply)   MODE=apply ;;
  --inspect) MODE=inspect ;;
  -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
  *) echo "不明な引数: $1（--help 参照）" >&2; exit 1 ;;
esac
[ "$(uname)" = Darwin ] || { echo "macOS 専用です。" >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { echo "sudo なしで実行してください。" >&2; exit 1; }

human() { awk '{ kb=$1; $1=""; sub(/^ /,"");
  if (kb>=1048576) printf "%7.1f GB  %s\n", kb/1048576, $0;
  else if (kb>=1024) printf "%7.0f MB  %s\n", kb/1024, $0;
  else printf "%7d KB  %s\n", kb, $0 }'; }

# ---------------------------------------------------------------- inspect
if [ "$MODE" = inspect ]; then
  for d in "$L/Application Support/Claude" "$L/Application Support/Claude/vm_bundles" "$L/Application Support/Google" \
           "$L/Application Support/Google/Chrome" "$L/Application Support/Google/Chrome/Default" \
           "$L/Group Containers/UBF8T346G9.OneDriveSyncClientSuite" "$L/Containers/com.microsoft.OneDrive-mac" \
           "$L/Application Support/ChatWork" "$HOME/.ollama/models" "$HOME/Dropbox"; do
    [ -d "$d" ] || continue
    echo "== $(echo "$d" | sed "s#^$HOME#~#") の内訳 上位 8"
    du -sk "$d"/* "$d"/.[!.]* 2>/dev/null | sort -rn | head -n 8 | human | sed "s#$d/##"
    echo
  done
  echo "== 本体が見当たらないかもしれないアプリのデータ（アプリの有無）"
  for pair in "Dia|Dia" "LarkInternational|Lark" "Microsoft Edge|Edge" "com.openai.atlas|Atlas" "Adobe|Adobe"; do
    name=${pair%%|*}; kw=${pair#*|}
    sz=$(du -sk "$L/Application Support/$name" 2>/dev/null | cut -f1)
    [ -n "$sz" ] || continue
    app=$(ls -1 /Applications "$HOME/Applications" 2>/dev/null | grep -i "$kw" | grep '\.app$' | head -1)
    printf '%s\t%s\n' "$sz" "$name  →  アプリ: ${app:-見つからない}" | human
  done
  exit 0
fi

# ---------------------------------------------------------------- dry / apply
[ "$MODE" = dry ] && echo "【ドライラン】何も消しません。消すには --apply を付けてください（元に戻せません）。"

TOTAL=0
FAILED=""
purge() {
  local p="$1" kb
  [ -e "$p" ] || [ -L "$p" ] || return 0
  kb=$(du -sk "$p" 2>/dev/null | cut -f1); kb=${kb:-0}
  TOTAL=$((TOTAL + kb))
  printf '%s %s\n' "$kb" "$p" | human | sed "s#$HOME#~#"
  [ "$MODE" = apply ] || return 0
  rm -rf "$p" 2>/dev/null
  if [ -e "$p" ]; then
    # インストーラが root で作ったファイルは sudo で消す（Containers は sudo でも無理。フルディスクアクセスが要る）
    case "$p" in
      */Containers/*) ;;
      *) sudo rm -rf "$p" 2>/dev/null ;;
    esac
  fi
  [ -e "$p" ] && FAILED="${FAILED}  - ${p}"$'\n'
  return 0
}

# アプリが起動中なら飛ばす（起動中にキャッシュを消すと不具合の元）
app_running() {
  if pgrep -xq "$1"; then
    echo "  $1 が起動中なのでスキップ。$1 を終了（⌘Q）してからもう一度実行してください。"
    return 0
  fi
  return 1
}

echo "== 1. Chrome のキャッシュ"
if ! app_running "Google Chrome"; then
  for p in "${CHROME_CACHE[@]}"; do purge "$p"; done
  # 各プロファイルの Service Worker キャッシュ（サイトが作り直す。ログイン状態・履歴には影響しない）
  for prof in "$L/Application Support/Google/Chrome/"*/; do
    purge "${prof}Service Worker/CacheStorage"
    purge "${prof}Service Worker/ScriptCache"
    purge "${prof}GPUCache"
  done
fi

echo "== 2. 更新ファイルの残り・キャッシュ"
for p in "${CACHES[@]}"; do purge "$p"; done

echo "== 3. 削除したアプリの残りデータ"
for p in "${LEFTOVERS[@]}"; do purge "$p"; done

echo "== 4. 使い続けるアプリのキャッシュ（作り直される）"
if ! app_running "Claude"; then
  purge "$L/Application Support/Claude/Cache"
  purge "$L/Application Support/Claude/Code Cache"
  purge "$L/Application Support/Claude/GPUCache"
fi
if ! app_running "Chatwork"; then
  # Partitions 直下はアカウントごとのセッション。ログイン情報は残してキャッシュだけ消す
  for part in "$L/Application Support/ChatWork/Partitions/"*/; do
    purge "${part}Cache"
    purge "${part}Code Cache"
    purge "${part}GPUCache"
    purge "${part}Service Worker/CacheStorage"
    purge "${part}Service Worker/ScriptCache"
  done
fi

echo
echo "合計: 約 $((TOTAL / 1024)) MB"
if [ "$MODE" = apply ]; then
  if [ -n "$FAILED" ]; then
    echo
    echo "消せなかったもの（権限で拒否）:"
    printf '%s' "$FAILED" | sed "s#$HOME#~#"
    echo "  システム設定 → プライバシーとセキュリティ → フルディスクアクセス でターミナルをオンにし、"
    echo "  ターミナルを再起動してからもう一度 --apply してください。"
  fi
  df -h / | tail -1
fi
