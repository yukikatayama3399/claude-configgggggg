#!/bin/bash
# mac_junk_report.sh — Mac の「ゴミ・カス」がどこに何 GB あるかを測る（読み取り専用。何も消さない）
#
#   bash mac_junk_report.sh
#
# 出すもの:
#   1. よくある溜まり場ごとの容量（キャッシュ・ログ・ゴミ箱・ダウンロード・iPhone バックアップ等）
#   2. ~/Library/Caches / Application Support / Containers の大きい順 上位
#   3. 2026-11-02 に削除したアプリの残りデータ
#   4. ホーム内の 1GB 超のファイル
# 数分かかることがある。権限で読めない所は飛ばす。

set -u

# KB を見やすい単位に
human() { awk '{ kb=$1; $1=""; sub(/^ /,"");
  if (kb>=1048576) printf "%7.1f GB  %s\n", kb/1048576, $0;
  else if (kb>=1024) printf "%7.0f MB  %s\n", kb/1024, $0;
  else printf "%7d KB  %s\n", kb, $0 }'; }

size_of() {
  local p="$1"
  [ -e "$p" ] || return 0
  printf '%s %s\n' "$(du -sk "$p" 2>/dev/null | cut -f1)" "$p"
}

top_in() {
  local dir="$1" n="$2"
  [ -d "$dir" ] || return 0
  echo "== $(echo "$dir" | sed "s#^$HOME#~#") の大きい順 上位 ${n}"
  du -sk "$dir"/* "$dir"/.[!.]* 2>/dev/null | sort -rn | head -n "$n" | human | sed "s#$HOME#~#"
}

echo "== 1. よくある溜まり場"
{
  size_of "$HOME/Library/Caches"
  size_of "$HOME/Library/Logs"
  size_of "$HOME/.Trash"
  size_of "$HOME/Downloads"
  size_of "$HOME/Desktop"
  size_of "$HOME/Movies"
  size_of "$HOME/Library/Application Support/MobileSync/Backup"
  size_of "$HOME/Library/Developer"
  size_of "$HOME/Library/Containers/com.apple.mail/Data/Library/Mail Downloads"
  size_of "$HOME/Library/Mail"
  size_of "$HOME/Library/Messages/Attachments"
  size_of "$HOME/.npm"
  size_of "$HOME/.cache"
  size_of "$HOME/.ollama"
  size_of "$HOME/.docker"
  size_of "$HOME/Library/Containers/com.docker.docker"
  size_of "$HOME/Dropbox"
  size_of "$HOME/Library/Application Support"
  size_of "$HOME/Library/Containers"
  size_of "$HOME/Library/Group Containers"
  size_of /Library/Caches
  size_of /private/var/log
  command -v brew >/dev/null 2>&1 && size_of "$(brew --cache 2>/dev/null)"
} | sort -rn | human | sed "s#$HOME#~#"
echo

top_in "$HOME/Library/Caches" 15; echo
top_in "$HOME/Library/Application Support" 15; echo
top_in "$HOME/Library/Containers" 10; echo
top_in "$HOME/Library/Group Containers" 8; echo

echo "== 3. 削除したアプリの残りデータ"
PAT='dropbox|capcut|filmora|wondershare|vrew|goodnotes|kindle|net\.sourceforge\.skim|skim|firefox|mozilla|fellou|sidekick|pushplaylabs|proton|logi|lghub|steermouse|iterm|moomoo|outlook|com\.microsoft\.teams|teams2|skype|twitter|1password|agilebits|shadowrocket|pdfelement|omnidisk|highfive|fatline|clipy|phoneclean|hyperswitch|adwords|unarchiver|macwinzipper|notion web'
for d in "$HOME/Library/Application Support" "$HOME/Library/Caches" "$HOME/Library/Containers" \
         "$HOME/Library/Group Containers" "$HOME/Library/Preferences" "$HOME/Library/Logs" \
         "$HOME/Library/HTTPStorages" "$HOME/Library/WebKit" "$HOME/Library/Saved Application State"; do
  [ -d "$d" ] || continue
  ls -1 "$d" 2>/dev/null | grep -iE "$PAT" | while IFS= read -r n; do size_of "$d/$n"; done
done | sort -rn | human | sed "s#$HOME#~#"
echo

echo "== 4. ホーム内の 1GB 超のファイル（Google Drive / iCloud 等のクラウド同期フォルダは除く）"
find "$HOME" -xdev \( -path "$HOME/Library/CloudStorage" -o -path "$HOME/Library/Mobile Documents" \) -prune \
  -o -type f -size +1G -exec du -sk {} + 2>/dev/null \
  | sort -rn | head -n 25 | human | sed "s#$HOME#~#"
echo
echo "== 空き容量"
df -h / | tail -1
