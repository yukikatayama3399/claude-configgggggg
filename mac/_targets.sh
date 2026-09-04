#!/usr/bin/env bash
# ============================================================
# mac/_targets.sh — 「消す候補」の定義ファイル（単体では実行しない）
#
# diagnose_mac.sh（サイズを測るだけ）と cleanup_mac.sh（実際に消す）の
# 両方が source する。候補を足したいときはここだけ直せば両方に効く。
#
# 1行 = 1候補。区切りは | で、フィールドは:
#   class | mode | label | path
#
# class:
#   safe    … 消して問題ないキャッシュ。使えば自動で再生成される
#   careful … 消しても壊れないが、再ダウンロード/再ビルドの時間を払う
#             （cleanup_mac.sh では --include-careful を付けた時だけ消す）
#   report  … 中身を人間が見て決めるもの。スクリプトは絶対に消さない
#
# mode:
#   contents … ディレクトリは残して中身だけ消す（キャッシュ置き場向き）
#   whole    … ディレクトリごと消す
#   none     … report 専用。消さないのでモードの意味はない
#
# path は $HOME を含む絶対パスで書く。$HOME 配下でないパスは
# cleanup_mac.sh 側が安全弁で弾く。
# ============================================================

# 候補を1行ずつ標準出力に吐く。
# path が存在しない候補も吐くので、受け取った側で存在チェックする。
emit_targets() {
  local brew_cache=""
  if command -v brew >/dev/null 2>&1; then
    brew_cache="$(brew --cache 2>/dev/null || true)"
  fi

  cat <<EOF
# --- ブラウザ / アプリのキャッシュ（消しても再生成される） ---
safe|contents|Chrome のキャッシュ|$HOME/Library/Caches/Google/Chrome
safe|contents|Safari のキャッシュ|$HOME/Library/Caches/com.apple.Safari
safe|contents|Slack のキャッシュ|$HOME/Library/Application Support/Slack/Cache
safe|contents|Slack の Code Cache|$HOME/Library/Application Support/Slack/Code Cache
safe|contents|Slack の GPUCache|$HOME/Library/Application Support/Slack/GPUCache
safe|contents|Slack の Service Worker キャッシュ|$HOME/Library/Application Support/Slack/Service Worker/CacheStorage
safe|contents|VS Code のキャッシュ|$HOME/Library/Application Support/Code/Cache
safe|contents|VS Code の CachedData|$HOME/Library/Application Support/Code/CachedData
safe|contents|VS Code の Code Cache|$HOME/Library/Application Support/Code/Code Cache
safe|contents|アプリのログ|$HOME/Library/Logs

# --- 開発ツールのビルド成果物 / キャッシュ ---
safe|contents|Xcode の DerivedData（ビルド中間物）|$HOME/Library/Developer/Xcode/DerivedData
safe|contents|Xcode 自体のキャッシュ|$HOME/Library/Caches/com.apple.dt.Xcode
safe|contents|iOS シミュレータのキャッシュ|$HOME/Library/Developer/CoreSimulator/Caches
safe|contents|npm のダウンロードキャッシュ|$HOME/.npm/_cacache
safe|contents|pip のダウンロードキャッシュ|$HOME/Library/Caches/pip
safe|contents|Go のビルドキャッシュ|$HOME/Library/Caches/go-build
safe|contents|Yarn のキャッシュ|$HOME/Library/Caches/Yarn
careful|contents|Homebrew のダウンロードキャッシュ|$brew_cache
careful|contents|pnpm のストア（再 install で再取得）|$HOME/Library/pnpm/store
careful|contents|Yarn Berry のキャッシュ|$HOME/.yarn/cache
careful|contents|Cargo のレジストリキャッシュ|$HOME/.cargo/registry/cache
careful|contents|Gradle のキャッシュ|$HOME/.gradle/caches
careful|contents|Maven のローカルリポジトリ|$HOME/.m2/repository
careful|contents|Playwright のブラウザ（再 install で再取得）|$HOME/Library/Caches/ms-playwright
careful|contents|~/.cache（puppeteer 等が使う）|$HOME/.cache
careful|contents|Xcode の iOS DeviceSupport（実機再接続で再生成）|$HOME/Library/Developer/Xcode/iOS DeviceSupport

# --- 消すと戻せないので既定では触らない ---
careful|contents|ゴミ箱|$HOME/.Trash
careful|contents|メールの添付ダウンロード|$HOME/Library/Containers/com.apple.mail/Data/Library/Mail Downloads

# --- 人が中身を見て決めるもの（スクリプトは消さない） ---
report|none|ダウンロードフォルダ|$HOME/Downloads
report|none|デスクトップ|$HOME/Desktop
report|none|iPhone / iPad のバックアップ|$HOME/Library/Application Support/MobileSync/Backup
report|none|Xcode の Archives（提出済みビルドと dSYM）|$HOME/Library/Developer/Xcode/Archives
report|none|iOS シミュレータの本体（使わない機種は Xcode から削除）|$HOME/Library/Developer/CoreSimulator/Devices
report|none|Docker のディスクイメージ|$HOME/Library/Containers/com.docker.docker/Data/vms
report|none|VS Code の拡張機能|$HOME/.vscode/extensions
report|none|~/Library/Caches 全体|$HOME/Library/Caches
EOF
}
