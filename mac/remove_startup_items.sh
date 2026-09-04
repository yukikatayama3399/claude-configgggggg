#!/usr/bin/env bash
# ============================================================
# mac/remove_startup_items.sh — 不要な常駐（LaunchAgents / LaunchDaemons）を外す
#
# 既定はドライラン。--apply を付けたときだけ実行する。
#
# 【消さずに「退避」する】
#   plist は削除ではなく ~/mac-startup-backup/<日時>/ へ移動する。
#   同じ場所に restore.sh を書き出すので、後悔したら
#       bash ~/mac-startup-backup/<日時>/restore.sh
#   で全部元に戻せる（戻したあと再起動すれば再び常駐する）。
#
# 使い方:
#   bash mac/remove_startup_items.sh                  # 何を外すか見るだけ
#   bash mac/remove_startup_items.sh --apply          # 実行（sudo パスワードを聞かれる）
#   bash mac/remove_startup_items.sh --apply --yes    # 確認プロンプト無し
#   bash mac/remove_startup_items.sh --list-untouched # 触らない候補も見る
#
# 【Avast は別扱い】
#   Avast はカーネル拡張とネットワークフィルタを入れるので、plist だけ
#   外すと中途半端に残る。**Avast 自身のアンインストーラを使うこと。**
#   それでも plist を外したい場合だけ --include-avast を付ける。
#
# 【アプリ本体は消さない】
#   このスクリプトは「起動時の常駐」を止めるだけ。アプリは残る。
#   そのため Adobe CC / G HUB / Zoom は、次にアプリを起動すると
#   自分の常駐を再登録する。恒久的に消すならアプリ自体を削除する。
# ============================================================
set -uo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "!! このスクリプトは macOS 専用（今は $(uname -s) で動いている）"
  echo "   お使いの Mac のターミナルで実行すること。"
  exit 1
fi

APPLY=0
ASSUME_YES=0
INCLUDE_AVAST=0
LIST_UNTOUCHED=0

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    --include-avast) INCLUDE_AVAST=1 ;;
    --list-untouched) LIST_UNTOUCHED=1 ;;
    -h|--help) sed -n '2,33p' "$0"; exit 0 ;;
    *) echo "!! 不明な引数: $arg（--help で使い方）"; exit 1 ;;
  esac
done

# ------------------------------------------------------------
# 外す対象。scope|group|ファイル名|説明
#   scope … user   = ~/Library/LaunchAgents   (sudo 不要)
#           agent  = /Library/LaunchAgents    (sudo 必要)
#           daemon = /Library/LaunchDaemons   (sudo 必要)
#   group … normal = 既定で外す / avast = --include-avast の時だけ
# ------------------------------------------------------------
targets() {
  cat <<'EOF'
user|normal|com.imobie.silentcleanserver.plist|iMobie のクリーナー常駐
user|normal|jp.co.canon.Inkjet_Extended_Survey_Agent.plist|Canon の利用調査エージェント
user|normal|com.snap.AssistantService.plist|Snapchat の常駐
user|normal|com.spotify.webhelper.plist|Spotify の常駐ヘルパー
user|normal|com.dropbox.DropboxMacUpdate.agent.plist|Dropbox のアップデータ（本体は未稼働）
user|normal|com.adobe.GC.Invoker-1.0.plist|Adobe Genuine Software の常駐(1/9)
agent|normal|com.adobe.GC.Invoker-1.0.plist|Adobe Genuine Software の常駐(2/9)
agent|normal|com.adobe.AdobeCreativeCloud.plist|Adobe Creative Cloud 本体の常駐(3/9)
agent|normal|com.adobe.ccxprocess.plist|Adobe CCX Process(4/9)
agent|normal|com.adobe.ARMDCHelper.cc24aef4a1b90ed56a725c38014c95072f92651fb65e1bf9c8e43c37a23d420d.plist|Adobe Reader の更新ヘルパー(5/9)
daemon|normal|com.adobe.ARMDC.Communicator.plist|Adobe Reader 更新の通信役(6/9)
daemon|normal|com.adobe.ARMDC.SMJobBlessHelper.plist|Adobe Reader 更新の特権ヘルパー(7/9)
daemon|normal|com.adobe.acc.installer.v2.plist|Adobe CC インストーラのヘルパー(8/9)
daemon|normal|com.adobe.agsservice.plist|Adobe Genuine Software サービス(9/9)
agent|normal|com.logi.ghub.plist|Logitech G HUB
agent|normal|com.logitech.manager.daemon.plist|Logitech Manager
daemon|normal|com.logi.ghub.updater.plist|Logitech G HUB のアップデータ
agent|normal|us.zoom.updater.login.check.plist|Zoom アップデータ（ログイン時チェック）
agent|normal|us.zoom.updater.plist|Zoom アップデータ
daemon|normal|com.starstechnologies.updater.plist|Stars Technologies のアップデータ
daemon|normal|com.oracle.java.Helper-Tool.plist|Java の特権ヘルパー
daemon|normal|com.edb.launchd.postgresql-9.6.plist|PostgreSQL 9.6 の自動起動（2021年サポート終了）
agent|avast|com.avast.userinit.plist|Avast のログイン時初期化
daemon|avast|com.avast.init.plist|Avast の本体デーモン
daemon|avast|com.avast.update.plist|Avast のアップデータ
EOF
}

# 判断が要るので触らないもの。--list-untouched で表示するだけ。
untouched() {
  cat <<'EOF'
com.google.inputmethod.Japanese.*|Google 日本語入力。使用中なので残す
com.microsoft.OneDrive*Updater*|OneDrive のアップデータ。OneDrive を使うなら残す
com.microsoft.office.licensingV2.helper|Office のライセンス認証。外すと Office が動かなくなる
com.microsoft.autoupdate.helper|Microsoft AutoUpdate。Office の更新に必要
com.microsoft.SyncReporter / update.agent|Microsoft の同期レポート・更新。要否は用途次第
com.microsoft.teams.TeamsUpdaterDaemon|Teams のアップデータ。Teams を使うなら残す
com.google.keystone.* / GoogleUpdater.*|Chrome の自動更新。外すと Chrome が更新されなくなる
com.west2online.ClashXPro.ProxyConfigHelper|ClashX Pro（プロキシ）。通信設定に関わるので自己判断
com.displaylink.usbnivolistener|DisplayLink。外部ディスプレイを使うなら残す
fr.madrau.switchresx.helper|SwitchResX（解像度変更）。使っているなら残す
com.brother.LOGINserver|Brother プリンタ。印刷に使うなら残す
com.fatline.HighfiveApp.ota|Highfive の更新。表の対象外なので保留
ai.memory.sync / claude.backup|片山さん自身が入れたもの。残す
EOF
}

dir_for_scope() {
  case "$1" in
    user)   printf '%s' "$HOME/Library/LaunchAgents" ;;
    agent)  printf '%s' "/Library/LaunchAgents" ;;
    daemon) printf '%s' "/Library/LaunchDaemons" ;;
    *)      printf '%s' "" ;;
  esac
}

# plist の Label を読む。読めなければファイル名から推測する。
label_of() {
  local f="$1" base
  base="$(basename "$f" .plist)"
  if [ -f "$f" ] && [ -x /usr/libexec/PlistBuddy ]; then
    /usr/libexec/PlistBuddy -c 'Print :Label' "$f" 2>/dev/null || printf '%s' "$base"
  else
    printf '%s' "$base"
  fi
}

# ------------------------------------------------------------
# 計画を作る
# ------------------------------------------------------------
PLAN=""
skipped_avast=0
missing=0

while IFS='|' read -r scope group file desc; do
  case "$scope" in ''|'#'*) continue ;; esac
  if [ "$group" = "avast" ] && [ "$INCLUDE_AVAST" -eq 0 ]; then
    skipped_avast=$(( skipped_avast + 1 ))
    continue
  fi
  d="$(dir_for_scope "$scope")"
  [ -n "$d" ] || continue
  path="$d/$file"
  # -e はリンク先を追うので、壊れたシンボリックリンクだと偽になる。
  # ディレクトリには残っているので -L も見る（launchd は読めないが掃除の対象）。
  if [ ! -e "$path" ] && [ ! -L "$path" ]; then
    missing=$(( missing + 1 ))
    continue
  fi
  PLAN="${PLAN}${scope}|${path}|${desc}"$'\n'
done < <(targets)

echo "== 外す常駐の一覧"
if [ -z "$PLAN" ]; then
  echo "  対象が1つも見つからなかった（既に外し済み？）"
else
  n=0
  while IFS='|' read -r scope path desc; do
    [ -n "${path:-}" ] || continue
    n=$(( n + 1 ))
    printf '  %2d. %-8s %s\n' "$n" "$scope" "$desc"
    printf '      %s\n' "$path"
  done < <(printf '%s' "$PLAN")
  echo
  echo "  合計 ${n} 件"
fi

[ "$missing" -gt 0 ] && echo "  （${missing} 件は既に存在しないので対象外）"

if [ "$skipped_avast" -eq 1 ] || [ "$skipped_avast" -gt 1 ]; then
  echo
  echo "  ⚠️  Avast の ${skipped_avast} 件は含めていない。"
  echo "     Avast はカーネル拡張とネットワークフィルタを入れるので、plist だけ"
  echo "     外すと中途半端に残る。**Avast 自身のアンインストーラで消すこと。**"
  echo "     手順: /Applications/Avast.app を開く → メニューバーの Avast →"
  echo "           「Avast をアンインストール」（または Finder で Avast.app を"
  echo "           ゴミ箱に入れると案内が出る）"
  echo "     それでも plist だけ外したいなら --include-avast を付ける。"
fi

if [ "$LIST_UNTOUCHED" -eq 1 ]; then
  echo
  echo "== 判断が要るので触らないもの"
  untouched | while IFS='|' read -r name why; do
    printf '  - %-46s %s\n' "$name" "$why"
  done
fi

echo
echo "== 注意"
echo "  ・アプリ本体は消さない。Adobe CC / G HUB / Zoom は次にアプリを起動すると"
echo "    自分の常駐を再登録する。恒久的に止めるならアプリ自体を削除する。"
echo "  ・PostgreSQL 9.6 は自動起動を止めるだけで、データベースの中身"
echo "    (/Library/PostgreSQL) は触らない。"
echo "  ・plist は削除ではなく退避する。restore.sh で全部元に戻せる。"

if [ -z "$PLAN" ]; then
  exit 0
fi

if [ "$APPLY" -eq 0 ]; then
  echo
  echo "ドライランなので何も変更していない。実行するには:"
  echo "  bash mac/remove_startup_items.sh --apply"
  exit 0
fi

# ------------------------------------------------------------
# 実行
# ------------------------------------------------------------
if [ "$ASSUME_YES" -eq 0 ]; then
  echo
  printf '上記を外す? （退避なので後で戻せる） [y/N] '
  read -r reply
  case "$reply" in
    y|Y|yes|YES) : ;;
    *) echo "中止した。何も変更していない。"; exit 0 ;;
  esac
fi

BACKUP_DIR="$HOME/mac-startup-backup/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR" || { echo "!! 退避先を作れなかった: $BACKUP_DIR"; exit 1; }

RESTORE="$BACKUP_DIR/restore.sh"
{
  echo '#!/usr/bin/env bash'
  echo '# remove_startup_items.sh が外した常駐を元の場所へ戻す。'
  echo '# 戻したあと再起動すれば、また起動時に常駐する。'
  echo 'set -uo pipefail'
  echo 'echo "退避した plist を元の場所へ戻す（sudo パスワードを聞かれる）"'
} > "$RESTORE"

# /Library 配下が対象に含まれるときだけ sudo を要求する。
# ホーム配下だけなら権限昇格は不要なので聞かない。
if printf '%s' "$PLAN" | grep -qv '^user|'; then
  echo
  echo "/Library 配下の操作に sudo が必要。パスワードを聞かれたら入力する。"
  sudo -v || { echo "!! sudo が使えないので中止した。何も変更していない。"; exit 1; }
fi

done_n=0
fail_n=0

while IFS='|' read -r scope path desc; do
  [ -n "${path:-}" ] || continue
  { [ -e "$path" ] || [ -L "$path" ]; } || continue

  label="$(label_of "$path")"
  base="$(basename "$path")"
  dest_dir="$BACKUP_DIR/$scope"
  mkdir -p "$dest_dir"
  dest="$dest_dir/$base"

  # まず動いているものを停止する。停止しないとファイルを消しても再起動まで生き残る。
  case "$scope" in
    user|agent) launchctl bootout "gui/$(id -u)/$label" >/dev/null 2>&1 ;;
    daemon)     sudo launchctl bootout "system/$label"  >/dev/null 2>&1 ;;
  esac

  # 次に plist を退避する（削除ではない）
  moved=0
  case "$scope" in
    user)  mv "$path" "$dest" 2>/dev/null && moved=1 ;;
    *)     sudo mv "$path" "$dest" 2>/dev/null && moved=1 ;;
  esac

  if [ "$moved" -eq 1 ]; then
    echo "  ✅ 外した: $desc"
    done_n=$(( done_n + 1 ))
    # 戻し方を restore.sh に記録する
    if [ "$scope" = "user" ]; then
      printf 'mv %q %q && echo "  戻した: %s"\n' "$dest" "$path" "$base" >> "$RESTORE"
    else
      printf 'sudo mv %q %q && echo "  戻した: %s"\n' "$dest" "$path" "$base" >> "$RESTORE"
    fi
  else
    echo "  △ 外せなかった: $desc"
    echo "     $path"
    fail_n=$(( fail_n + 1 ))
  fi
done < <(printf '%s' "$PLAN")

echo 'echo "戻し終わった。再起動すると再び常駐する。"' >> "$RESTORE"
chmod +x "$RESTORE"

echo
echo "== 結果"
echo "  外した: ${done_n} 件"
[ "$fail_n" -gt 0 ] && echo "  失敗: ${fail_n} 件（権限か、既に無いか）"
echo "  退避先: $BACKUP_DIR"
echo "  元に戻す: bash $RESTORE"
echo
echo "  再起動すると、外した常駐が居ない状態で立ち上がる。"
echo "  効果の確認: bash mac/diagnose_mac.sh"
