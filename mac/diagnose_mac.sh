#!/usr/bin/env bash
# ============================================================
# mac/diagnose_mac.sh — Mac が遅い原因を洗い出す（読み取り専用）
#
# 何も消さない・何も変えない。いつ実行しても安全。
# 「遅い」の原因は大きく4つに分かれるので、その順に見ていく:
#   1. 空き容量が足りない（残り 10% を切ると体感で分かるほど遅くなる）
#   2. メモリが足りずスワップしている
#   3. 常駐プロセスが CPU を食っている
#   4. 熱で CPU が絞られている（kernel_task が上位に来るのが目印）
#
# 使い方:
#   bash mac/diagnose_mac.sh          # 全部見る
#   bash mac/diagnose_mac.sh --quick  # ディスク使用量の集計を省いて速く終わる
#
# du でディレクトリを1つずつ測るので、--quick なしだと数十秒〜数分かかる。
# 消す作業は cleanup_mac.sh（既定はドライラン）が担当。
# ============================================================
set -uo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "!! このスクリプトは macOS 専用（今は $(uname -s) で動いている）"
  echo "   Claude のクラウドセッションからは Mac 本体を見られないので、"
  echo "   お使いの Mac のターミナルで実行すること。"
  exit 1
fi

QUICK=0
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "!! 不明な引数: $arg"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=mac/_targets.sh
. "$SCRIPT_DIR/_targets.sh"

section() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

# KB を人間が読める単位にする（小数1桁）
human_kb() {
  awk -v kb="$1" 'BEGIN{
    if (kb >= 1048576) printf "%.1f GB", kb/1048576;
    else if (kb >= 1024) printf "%.1f MB", kb/1024;
    else printf "%d KB", kb;
  }'
}

# ------------------------------------------------------------
section "1. 本体とディスクの空き"
# ------------------------------------------------------------
sw_vers 2>/dev/null | sed 's/^/  /'
printf '  Model:\t\t%s\n' "$(sysctl -n hw.model 2>/dev/null || echo '?')"
printf '  CPU:\t\t%s\n' "$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo '?')"
printf '  Memory:\t%s GB\n' "$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))"
printf '  Uptime:\t%s\n' "$(uptime | sed 's/^ *//')"

echo
df -h / | sed 's/^/  /'

# 空きが少ないと macOS 自体（スワップ・Spotlight・スナップショット）が遅くなる
capacity="$(df -k / | awk 'NR==2{gsub("%","",$5); print $5+0}')"
free_pct=$(( 100 - capacity ))
if [ "$free_pct" -lt 10 ]; then
  echo "  ⚠️  空きが ${free_pct}% しかない。これ自体が遅さの主要因になる（目標: 15% 以上）"
elif [ "$free_pct" -lt 20 ]; then
  echo "  △ 空きは ${free_pct}%。余裕は少ない（目標: 15〜20% 以上）"
else
  echo "  ✅ 空きは ${free_pct}%。容量は足りている"
fi

# Time Machine のローカルスナップショットは「消せない使用量」に見える犯人
if command -v tmutil >/dev/null 2>&1; then
  snap_count="$(tmutil listlocalsnapshots / 2>/dev/null | grep -c 'com.apple.TimeMachine' || true)"
  if [ "${snap_count:-0}" -gt 0 ]; then
    echo "  ・Time Machine のローカルスナップショット: ${snap_count} 個"
    echo "    （ディスクを掴んでいる。cleanup_mac.sh --snapshots で削除できる）"
  fi
fi

# ------------------------------------------------------------
section "2. メモリとスワップ"
# ------------------------------------------------------------
sysctl vm.swapusage 2>/dev/null | sed 's/^/  /'
swap_used_mb="$(sysctl -n vm.swapusage 2>/dev/null | sed -n 's/.*used = \([0-9.]*\)M.*/\1/p')"
if [ -n "${swap_used_mb:-}" ]; then
  # 小数を含むので awk で比較する
  verdict="$(awk -v u="$swap_used_mb" 'BEGIN{ if (u > 4096) print "heavy"; else if (u > 1024) print "some"; else print "ok" }')"
  case "$verdict" in
    heavy) echo "  ⚠️  スワップを ${swap_used_mb}MB 使っている。メモリ不足で遅くなっている状態" ;;
    some)  echo "  △ スワップ ${swap_used_mb}MB。常駐アプリを減らすと効く" ;;
    ok)    echo "  ✅ スワップはほぼ使っていない。メモリは足りている" ;;
  esac
fi

if command -v memory_pressure >/dev/null 2>&1; then
  memory_pressure 2>/dev/null | tail -3 | sed 's/^/  /'
fi

# ------------------------------------------------------------
section "3. いま重いプロセス（CPU 上位10）"
# ------------------------------------------------------------
ps -Ao pcpu,pmem,rss,comm -r 2>/dev/null | head -11 | \
  awk 'NR==1{printf "  %6s %6s %10s  %s\n","%CPU","%MEM","RSS(MB)","COMMAND"; next}
       {printf "  %6s %6s %10.0f  %s\n", $1, $2, $3/1024, $4}'

# kernel_task が上位に来ているなら CPU 使用ではなく熱による制御
if ps -Ao pcpu,comm -r 2>/dev/null | head -4 | grep -q kernel_task; then
  echo
  echo "  ⚠️  kernel_task が上位にいる = 熱で CPU が絞られているサイン。"
  echo "     排気口・ファン周りの埃、外付けディスプレイの負荷、充電器の位置を疑う。"
fi

if command -v pmset >/dev/null 2>&1; then
  therm="$(pmset -g therm 2>/dev/null | sed 's/^/  /')"
  [ -n "$therm" ] && { echo; echo "$therm"; }
fi

section "4. メモリ上位10"
ps -Ao pmem,rss,comm -m 2>/dev/null | head -11 | \
  awk 'NR==1{printf "  %6s %10s  %s\n","%MEM","RSS(MB)","COMMAND"; next}
       {printf "  %6s %10.0f  %s\n", $1, $2/1024, $3}'

# ------------------------------------------------------------
section "5. ログイン時に自動起動するもの（見直し候補）"
# ------------------------------------------------------------
# ここに並ぶものは起動直後から常駐する。使っていないアプリのものは
# 「システム設定 > 一般 > ログイン項目と機能拡張」から外すと軽くなる。
for d in "$HOME/Library/LaunchAgents" /Library/LaunchAgents /Library/LaunchDaemons; do
  if [ -d "$d" ]; then
    n="$(find "$d" -maxdepth 1 -name '*.plist' 2>/dev/null | wc -l | tr -d ' ')"
    echo "  $d ($n 件)"
    find "$d" -maxdepth 1 -name '*.plist' 2>/dev/null | sed 's|.*/||; s/^/    - /' | sort | head -20
  fi
done
echo
echo "  常駐中のサードパーティ製プロセス（Apple 純正を除く）:"
launchctl list 2>/dev/null | awk 'NR>1 && $3 !~ /^com\.apple\./ && $3 != "-" {print "    - " $3}' | sort -u | head -25

# ------------------------------------------------------------
section "6. Spotlight のインデックス状態"
# ------------------------------------------------------------
# インデックス作成中は数時間ずっと重い。Indexing enabled かつ進行中なら待つのが正解。
if command -v mdutil >/dev/null 2>&1; then
  mdutil -s / 2>/dev/null | sed 's/^/  /'
else
  echo "  mdutil が無い"
fi

# mdutil は「有効/無効」しか言わないので、進行中かは mds の CPU で判断する。
# 索引作成中は数十分〜数時間ずっと重く、待つ以外にできることが無い。
mds_cpu="$(ps -Ao pcpu,comm 2>/dev/null | awk '/Metadata\.framework/ {s+=$1} END{printf "%.0f", s+0}')"
if [ "${mds_cpu:-0}" -ge 20 ]; then
  echo "  ⚠️  索引作成が進行中（Spotlight 関連の合計 ${mds_cpu}% CPU）。"
  echo "     終わるまでは何をしても重い。電源を繋いで放置すれば収まる。"
  echo "     同期フォルダを「システム設定 > Spotlight > 検索プライバシー」で"
  echo "     除外すると、同期と索引が互いを呼び合う悪循環を切れる。"
else
  echo "  ✅ 索引作成は進行中ではない"
fi

# ------------------------------------------------------------
section "7. クラウド同期と常駐デーモンの負荷"
# ------------------------------------------------------------
# 容量もメモリも白なのに遅い場合、ここが本命になりやすい。
# 同期クライアントは全ファイルを常時監視するので、2つ同時に動かすと
# CPU とディスクを取り合って、無操作でも延々と回り続ける。

# 実行パスにキーワードを含むプロセスの %CPU 合計とプロセス数を返す
cpu_sum_of() {
  ps -Ao pcpu,comm 2>/dev/null | awk -v key="$1" '
    index($0, key) > 0 { sum += $1; n++ }
    END { printf "%.1f %d", sum+0, n+0 }'
}

sync_active=0
sync_names=""
printf '  %-32s %7s %6s\n' "同期クライアント" "%CPU" "プロセス数"
while IFS='|' read -r label key; do
  set -- $(cpu_sum_of "$key")
  cpu="${1:-0}"; n="${2:-0}"
  [ "$n" -eq 0 ] && continue
  sync_active=$(( sync_active + 1 ))
  sync_names="${sync_names}${label} "
  printf '  %-32s %7s %6s\n' "$label" "$cpu" "$n"
done <<'EOF'
OneDrive|OneDrive
Google Drive|Google Drive
Dropbox|Dropbox
Box|Box.app
iCloud Drive (bird)|/bird
EOF
[ "$sync_active" -eq 0 ] && echo "  （動いていない）"

if [ "$sync_active" -ge 2 ]; then
  echo
  echo "  ⚠️  同期クライアントが ${sync_active} 種類同時に動いている: ${sync_names}"
  echo "     常駐が2つ以上あると互いにディスクを取り合う。使う方に寄せると効く。"
fi

printf '\n  %-32s %7s %6s\n' "常駐デーモン" "%CPU" "プロセス数"
while IFS='|' read -r label key; do
  set -- $(cpu_sum_of "$key")
  cpu="${1:-0}"; n="${2:-0}"
  [ "$n" -eq 0 ] && continue
  printf '  %-32s %7s %6s\n' "$label" "$cpu" "$n"
done <<'EOF'
fileproviderd (同期の仲介役)|fileproviderd
Spotlight の索引作成 (mds 系)|Metadata.framework
WindowServer (画面描画)|WindowServer
mediaanalysisd (写真の解析)|mediaanalysisd
photoanalysisd (写真の解析)|photoanalysisd
iconservicesagent (アイコン生成)|iconservicesagent
EOF

# 1コアを食い切っているプロセスは、それ単体で体感を落とす
hogs="$(ps -Ao pcpu,comm -r 2>/dev/null | awk '
  NR>1 { c=$1+0; sub(/^[ \t]*[0-9.]+[ \t]+/, ""); if (c>=50) printf "    %6.1f%%  %s\n", c, $0 }' | head -10)"
echo
if [ -n "$hogs" ]; then
  echo "  ⚠️  CPU を 50% 以上使っているプロセス（1コア級の負荷）:"
  printf '%s\n' "$hogs"
  echo "     MacBook Air はファンが無いので、この負荷が続くと熱で CPU が絞られ、"
  echo "     結果として「全体が遅い」状態になる。まずこれを止めるのが最短。"
else
  echo "  ✅ CPU を 50% 以上使い続けているプロセスは無し"
fi

if [ "$QUICK" -eq 1 ]; then
  echo
  echo "== 8. 消す候補（--quick なので集計を省略）"
  echo "  サイズを見るには --quick を外して実行する。"
  exit 0
fi

# ------------------------------------------------------------
section "8. 消す候補とサイズ（測るだけ。ここでは何も消さない）"
# ------------------------------------------------------------
echo "  du で1つずつ測るので少し待つ..."

rows=""
total_safe=0
total_careful=0

while IFS='|' read -r class mode label path; do
  # コメント行と空行を飛ばす
  case "$class" in ''|'#'*) continue ;; esac
  [ -n "${path:-}" ] || continue
  [ -e "$path" ] || continue

  kb="$(du -sk "$path" 2>/dev/null | awk '{print $1+0}')"
  [ -n "${kb:-}" ] || continue
  # 10MB 未満は掃除しても体感が変わらないので出さない
  [ "$kb" -lt 10240 ] && continue

  rows="${rows}${kb}|${class}|${label}|${path}"$'\n'
  case "$class" in
    safe)    total_safe=$(( total_safe + kb )) ;;
    careful) total_careful=$(( total_careful + kb )) ;;
  esac
done < <(emit_targets)

if [ -z "$rows" ]; then
  echo "  10MB を超える候補は見つからなかった。ディスクは既に綺麗。"
else
  printf '\n  %10s  %-8s %s\n' "SIZE" "CLASS" "対象"
  printf '  %10s  %-8s %s\n' "----------" "--------" "----"
  # サイズ降順。大きいものから手を付けるのが効率的
  printf '%s' "$rows" | sort -t'|' -k1,1rn | while IFS='|' read -r kb class label path; do
    printf '  %10s  %-8s %s\n' "$(human_kb "$kb")" "$class" "$label"
    printf '  %10s  %-8s   %s\n' "" "" "$path"
  done
fi

echo
echo "  合計:"
echo "    safe    （消して問題ないキャッシュ）: $(human_kb "$total_safe")"
echo "    careful （消すと再取得・再ビルドが必要）: $(human_kb "$total_careful")"
echo "    report  … 上の一覧で class が report のものは中身を人が見て決める"

# ------------------------------------------------------------
section "8. 放置された node_modules（プロジェクトごと消せる）"
# ------------------------------------------------------------
# 深く探すと終わらないので浅い階層だけ。90日以上触っていないものを出す。
found=0
while IFS= read -r nm; do
  [ -n "$nm" ] || continue
  kb="$(du -sk "$nm" 2>/dev/null | awk '{print $1+0}')"
  [ "${kb:-0}" -lt 51200 ] && continue   # 50MB 未満は無視
  printf '  %10s  %s\n' "$(human_kb "$kb")" "$nm"
  found=$(( found + 1 ))
done < <(find "$HOME" -maxdepth 5 -type d -name node_modules -mtime +90 -prune 2>/dev/null | head -20)
if [ "$found" -eq 0 ]; then
  echo "  90日以上放置された大きい node_modules は無し"
else
  echo
  echo "  → 現役プロジェクトなら消しても npm install で戻る。判断が要るので自動削除はしない。"
fi

# ------------------------------------------------------------
section "次にやること"
# ------------------------------------------------------------
# 容量に余裕がある Mac で掃除を勧めるのは筋違いなので、状況で出し分ける。
if [ "$free_pct" -ge 25 ]; then
  cat <<'EOF'
  ディスクは余っているので、掃除しても速度は変わらない。
  見るべきは上の「3. 重いプロセス」と「7. クラウド同期と常駐デーモン」。

  1. 1コア級の負荷が出ていたアプリを一旦終了して、体感が戻るか確かめる。
     戻ればそれが原因。戻らなければ次を疑う。
  2. 索引作成や初回同期が進行中なら、終わるまで待つのが正解。
     電源を繋いで放置する。止めても次回また同じ処理が走る。
  3. 「5. ログイン時に自動起動するもの」に使っていないアプリの常駐があれば外す。
     これは容量ではなく常時の CPU を減らす作業で、体感に効く。

  容量目的で掃除したいときだけ:
       bash mac/cleanup_mac.sh
EOF
else
  cat <<'EOF'
  1. まずドライランで消える量を確認:
       bash mac/cleanup_mac.sh
  2. safe だけ実際に消す:
       bash mac/cleanup_mac.sh --apply
  3. それでも足りなければ careful も含める:
       bash mac/cleanup_mac.sh --apply --include-careful
  4. ディスク以外の遅さは上の 2〜7 が原因。スワップが多いなら常駐アプリを、
     ログイン項目に見覚えのないものがあればそれを外す。
EOF
fi
