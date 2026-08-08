#!/bin/bash
# ============================================================
# diagnose_mac_slow.sh
#   「Mac が重い。Claude のせいか？」を切り分けるための診断スクリプト。
#
#   ★ 読み取り専用。何も削除・変更・送信しない。いつ実行しても安全。
#
#   使い方（会社Mac / 家Mac のどちらでも、重いと感じている時に実行）:
#       bash diagnose_mac_slow.sh
#       bash diagnose_mac_slow.sh > /tmp/mac_slow.txt 2>&1   # 結果を貼り付けたい時
#
#   最後に「疑わしい点」と「推奨アクション」を自動でまとめる。
#   推奨アクションは表示するだけで、実行はしない。
# ============================================================
set -uo pipefail
export LANG=C

if [ "$(uname -s)" != "Darwin" ]; then
  echo "このスクリプトは macOS 専用です（現在: $(uname -s)）。あなたの Mac 上で実行してください。" >&2
  exit 1
fi

FINDINGS_FILE="$(mktemp "${TMPDIR:-/tmp}/macslow.XXXXXX")"
trap 'rm -f "$FINDINGS_FILE"' EXIT

sec()  { printf '\n========== %s ==========\n' "$1"; }
flag() { printf '%s\n' "$1" >> "$FINDINGS_FILE"; }
# 小数入りの数値比較（bash に浮動小数演算が無いので awk で判定）
gt()   { awk -v a="${1:-0}" -v b="$2" 'BEGIN{exit !(a+0 > b+0)}'; }

CLAUDE_DIR="$HOME/.claude"
NCPU="$(sysctl -n hw.ncpu 2>/dev/null || echo 1)"

# ------------------------------------------------------------
sec "1. システム全体"
sw_vers 2>/dev/null | sed 's/^/  /'
echo "  CPUコア数: $NCPU"
echo "  稼働時間/ロードアベレージ:"
uptime | sed 's/^/    /'

LOAD1="$(sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}')"
if gt "$LOAD1" "$(awk -v n="$NCPU" 'BEGIN{print n*1.5}')"; then
  flag "ロードアベレージが高い（1分平均 ${LOAD1} / ${NCPU}コア）。何かが CPU を食い続けている。セクション2・3の上位プロセスを見る。"
fi

echo "  スワップ:"
sysctl -n vm.swapusage 2>/dev/null | sed 's/^/    /'
SWAP_USED="$(sysctl -n vm.swapusage 2>/dev/null | sed -n 's/.*used = \([0-9.]*\)M.*/\1/p')"
if [ -n "${SWAP_USED:-}" ] && gt "$SWAP_USED" 2048; then
  flag "スワップ使用量が多い（${SWAP_USED}MB）。メモリ不足でディスクに退避している＝体感が最も悪化するパターン。セクション3のメモリ上位プロセスを疑う。"
fi

echo "  メモリ空き率:"
MEMFREE="$(memory_pressure 2>/dev/null | tail -1)"
echo "    ${MEMFREE:-取得不可}"
MEMPCT="$(printf '%s' "${MEMFREE:-}" | sed -n 's/.*: \([0-9]*\)%.*/\1/p')"
if [ -n "${MEMPCT:-}" ] && [ "$MEMPCT" -lt 15 ] 2>/dev/null; then
  flag "空きメモリが ${MEMPCT}% しかない。メモリ逼迫。"
fi

echo "  ディスク空き:"
df -h /System/Volumes/Data 2>/dev/null | sed 's/^/    /'
DISKPCT="$(df -H /System/Volumes/Data 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5}')"
if [ -n "${DISKPCT:-}" ] && [ "$DISKPCT" -ge 90 ] 2>/dev/null; then
  flag "ディスク使用率 ${DISKPCT}%。空きが1割を切ると macOS 全体が目に見えて遅くなる。セクション5の ~/.claude 肥大化も確認。"
fi

# ------------------------------------------------------------
sec "2. CPU使用率 上位15プロセス（Mac全体）"
ps -A -r -o 'pcpu,pmem,rss,etime,comm' 2>/dev/null | head -16 | sed 's/^/  /'

sec "3. メモリ使用量 上位15プロセス（Mac全体）"
ps -A -m -o 'pmem,rss,pcpu,etime,comm' 2>/dev/null | head -16 | sed 's/^/  /'

# ------------------------------------------------------------
sec "4. Claude 関連プロセス"

# プロセス一覧を1回だけ取って使い回す（pid pcpu rss etime に続けてコマンドライン）
PS_FILE="$(mktemp "${TMPDIR:-/tmp}/macslow_ps.XXXXXX")"
trap 'rm -f "$FINDINGS_FILE" "$PS_FILE"' EXIT
ps -Ao 'pid,pcpu,rss,etime,command' 2>/dev/null > "$PS_FILE"

# Claude Code 本体(cli) と MCP サーバ(mcp) を仕分けして表示する。
# 最終行に "###<件数> <合計RSS(KB)>" を出し、呼び出し側で拾う。
classify_ps() {
  awk -v mode="$1" '
    NR == 1 { next }
    {
      cmd = ""
      for (i = 5; i <= NF; i++) cmd = cmd (i > 5 ? " " : "") $i
      # シェルのラッパー行・自分自身・grep は数えない（二重計上と誤検出の元）
      if (cmd ~ /diagnose_mac_slow/)                 next
      if (cmd ~ /^(\/[A-Za-z\/]*\/)?(sh|bash|zsh) /) next
      if (cmd ~ /(^| )grep /)                        next

      isCli = (cmd ~ /(^|\/| )claude( |$)/) || (cmd ~ /claude-code/)
      isMcp = (!isCli) && (tolower(cmd) ~ /mcp|modelcontextprotocol/)
      if (mode == "cli" ? !isCli : !isMcp) next

      n++; rss += $3
      printf "    %7s %5s%% %7d MB %10s  %s\n", $1, $2, $3/1024, $4, substr(cmd, 1, 100)
    }
    END { printf "###%d %d\n", n + 0, rss + 0 }
  ' "$PS_FILE"
}

# 4-1. Claude Code 本体（CLI）
echo "  [Claude Code CLI]"
CLI_OUT="$(classify_ps cli)"
printf '%s\n' "$CLI_OUT" | grep -v '^###' | grep -v '^$' || true
CLI_SUM="$(printf '%s\n' "$CLI_OUT" | sed -n 's/^###//p')"
CLI_COUNT="$(printf '%s' "$CLI_SUM" | awk '{print $1+0}')"
CLI_RSS="$(printf '%s' "$CLI_SUM" | awk '{print $2+0}')"
[ "$CLI_COUNT" -eq 0 ] && echo "    （検出なし）"
echo "    → 起動中のセッション数: ${CLI_COUNT} / 合計RSS: $((CLI_RSS / 1024)) MB"
if [ "$CLI_COUNT" -ge 4 ]; then
  flag "Claude Code CLI が ${CLI_COUNT} 個動いている（合計 $((CLI_RSS / 1024))MB）。ターミナルを閉じても裏に残っている可能性。各セッションが MCP サーバ群を丸ごと抱えるので、数が増えるとメモリを最も食う。"
fi

# 4-2. MCP サーバ（node/python の子プロセス）
echo
echo "  [MCP サーバ プロセス]"
MCP_OUT="$(classify_ps mcp)"
printf '%s\n' "$MCP_OUT" | grep -v '^###' | grep -v '^$' || true
MCP_SUM="$(printf '%s\n' "$MCP_OUT" | sed -n 's/^###//p')"
MCP_COUNT="$(printf '%s' "$MCP_SUM" | awk '{print $1+0}')"
MCP_RSS="$(printf '%s' "$MCP_SUM" | awk '{print $2+0}')"
[ "$MCP_COUNT" -eq 0 ] && echo "    （検出なし）"
echo "    → MCP プロセス数: ${MCP_COUNT} / 合計RSS: $((MCP_RSS / 1024)) MB"
if [ "$MCP_COUNT" -ge 10 ]; then
  flag "MCP サーバが ${MCP_COUNT} 個常駐（合計 $((MCP_RSS / 1024))MB）。セッション数 × 設定MCP数だけ増える。使っていない MCP を .mcp.json / settings.json から外すのが一番効く。"
fi
if [ "$((MCP_RSS / 1024))" -ge 2000 ]; then
  flag "MCP サーバだけで $((MCP_RSS / 1024))MB 使用。メモリ逼迫の主因になり得る。"
fi

# 4-3. Claude Desktop アプリ（Electron）
echo
echo "  [Claude Desktop アプリ]"
DESK_RSS=0
DESK_COUNT=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  DESK_COUNT=$((DESK_COUNT + 1))
  R="$(printf '%s' "$line" | awk '{print $3}')"
  DESK_RSS=$((DESK_RSS + R))
  echo "    $(printf '%s' "$line" | cut -c1-140)"
done < <(ps -Ao 'pid,pcpu,rss,etime,command' 2>/dev/null \
          | grep -E 'Claude Helper|Claude\.app' \
          | grep -v 'grep')
[ "$DESK_COUNT" -eq 0 ] && echo "    （検出なし）"
[ "$DESK_COUNT" -gt 0 ] && echo "    → 合計RSS: $((DESK_RSS / 1024)) MB"
if [ "$((DESK_RSS / 1024))" -ge 3000 ]; then
  flag "Claude Desktop アプリが $((DESK_RSS / 1024))MB 使用。CLI と併用しているなら片方だけにすると軽くなる。"
fi

# 4-4. 検索プロセス（巨大ディレクトリの走査）
echo
echo "  [ripgrep / find など検索プロセス]"
RG_LINES="$(ps -Ao 'pid,pcpu,etime,command' 2>/dev/null | grep -E '[r]g |[r]ipgrep|[f]ind /Users' | head -10)"
if [ -n "$RG_LINES" ]; then
  printf '%s\n' "$RG_LINES" | cut -c1-160 | sed 's/^/    /'
  flag "ripgrep/find が実行中。ホームディレクトリや iCloud 配下など巨大な場所で Claude Code を起動していると、毎回の検索が重くなる。"
else
  echo "    （検出なし）"
fi

# ------------------------------------------------------------
sec "5. ~/.claude のディスク使用量"
if [ -d "$CLAUDE_DIR" ]; then
  TOTAL_MB="$(du -sm "$CLAUDE_DIR" 2>/dev/null | awk '{print $1}')"
  echo "  合計: ${TOTAL_MB} MB  ($CLAUDE_DIR)"
  echo "  内訳（上位10）:"
  du -sm "$CLAUDE_DIR"/* 2>/dev/null | sort -rn | head -10 | awk '{printf "    %6d MB  %s\n", $1, $2}'

  if [ -n "${TOTAL_MB:-}" ] && [ "$TOTAL_MB" -ge 3000 ] 2>/dev/null; then
    flag "~/.claude が ${TOTAL_MB}MB。会話ログ(projects)とシェルスナップショットが溜まり続ける。Spotlight / iCloud / Time Machine がこれを舐め続けると常時重くなる。"
  fi

  # shell-snapshots（放置すると数万ファイルになる既知の肥大化ポイント）
  if [ -d "$CLAUDE_DIR/shell-snapshots" ]; then
    SNAP_N="$(find "$CLAUDE_DIR/shell-snapshots" -type f 2>/dev/null | wc -l | tr -d ' ')"
    echo "  shell-snapshots: ${SNAP_N} ファイル"
    if [ "$SNAP_N" -ge 500 ] 2>/dev/null; then
      flag "shell-snapshots が ${SNAP_N} ファイル。セッションごとに増え、自動削除されない。削除しても支障なし（推奨アクション参照）。"
    fi
  fi

  # projects（会話トランスクリプト）
  if [ -d "$CLAUDE_DIR/projects" ]; then
    PROJ_N="$(find "$CLAUDE_DIR/projects" -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
    JSONL_N="$(find "$CLAUDE_DIR/projects" -name '*.jsonl' 2>/dev/null | wc -l | tr -d ' ')"
    echo "  projects: $((PROJ_N - 1)) プロジェクト / ${JSONL_N} セッションログ"
    echo "  大きいログ 上位5:"
    find "$CLAUDE_DIR/projects" -name '*.jsonl' -size +5M 2>/dev/null \
      | while IFS= read -r f; do printf '%6d MB  %s\n' "$(du -m "$f" | awk '{print $1}')" "$f"; done \
      | sort -rn | head -5 | sed 's/^/    /'
    if [ "$JSONL_N" -ge 2000 ] 2>/dev/null; then
      flag "会話ログが ${JSONL_N} 件。/resume の一覧表示やインデックス対象が膨らむ。古いものは消してよい。"
    fi
  fi
else
  echo "  $CLAUDE_DIR が見つかりません。"
fi

# ------------------------------------------------------------
sec "6. 定期実行（cron / launchd / scheduled-tasks）"
echo "  [crontab]"
CRON_OUT="$(crontab -l 2>/dev/null)"
if [ -n "$CRON_OUT" ]; then
  printf '%s\n' "$CRON_OUT" | sed 's/^/    /'
  CRON_CLAUDE="$(printf '%s\n' "$CRON_OUT" | grep -icE 'claude' || true)"
  if [ "${CRON_CLAUDE:-0}" -ge 1 ] 2>/dev/null; then
    flag "crontab に Claude を起動するジョブが ${CRON_CLAUDE} 件。発火のたびに新しい Claude Code + MCP サーバ一式が立ち上がる。前回の実行が終わる前に次が発火すると多重起動で一気に重くなる（セクション4のCLI数と突き合わせる）。"
  fi
else
  echo "    （空 or 未設定）"
fi

echo
echo "  [launchd（ユーザー領域の claude/anthropic 関連）]"
LD_OUT="$(launchctl list 2>/dev/null | grep -iE 'claude|anthropic' || true)"
if [ -n "$LD_OUT" ]; then printf '%s\n' "$LD_OUT" | sed 's/^/    /'; else echo "    （検出なし）"; fi
ls -1 "$HOME/Library/LaunchAgents" 2>/dev/null | grep -iE 'claude|anthropic' | sed 's/^/    LaunchAgent: /'

echo
echo "  [~/.claude/scheduled-tasks]"
if [ -d "$CLAUDE_DIR/scheduled-tasks" ]; then
  ls -1 "$CLAUDE_DIR/scheduled-tasks" 2>/dev/null | sed 's/^/    /'
  TASK_N="$(ls -1 "$CLAUDE_DIR/scheduled-tasks" 2>/dev/null | wc -l | tr -d ' ')"
  echo "    → ${TASK_N} 件"
else
  echo "    （なし）"
fi

# ------------------------------------------------------------
sec "7. iCloud 同期"
echo "  [同期デーモンの負荷]"
ICLOUD_LINES="$(ps -Ao 'pid,pcpu,rss,etime,comm' 2>/dev/null | grep -E 'bird|cloudd|fileproviderd' | grep -v grep)"
printf '%s\n' "${ICLOUD_LINES:-    （検出なし）}" | sed 's/^/    /'
ICLOUD_CPU="$(printf '%s\n' "$ICLOUD_LINES" | awk '{s+=$2} END{print s+0}')"
if gt "$ICLOUD_CPU" 30; then
  flag "iCloud 同期プロセス(bird/cloudd/fileproviderd)が CPU ${ICLOUD_CPU}% を使用中。Claude が iCloud 配下のファイルを頻繁に書き換えると、同期が延々と走り Mac 全体が重くなる。scheduled-tasks を iCloud マスターで運用している構成では起きやすい。"
fi

echo
echo "  [Claude が iCloud 配下にあるか]"
ICDIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
if [ -d "$ICDIR" ]; then
  for d in "Claude" "scheduled-tasks" "Claude/memory"; do
    if [ -e "$ICDIR/$d" ]; then
      echo "    $(du -sm "$ICDIR/$d" 2>/dev/null | awk '{print $1}') MB  $ICDIR/$d"
    fi
  done
  # ~/.claude 自体が iCloud 配下にシンボリックリンクされていないか
  if [ -L "$CLAUDE_DIR" ]; then
    LINKDST="$(readlink "$CLAUDE_DIR")"
    echo "    ~/.claude はシンボリックリンク → $LINKDST"
    case "$LINKDST" in
      *Mobile\ Documents*) flag "~/.claude 自体が iCloud 配下にリンクされている。会話ログを書くたびに iCloud 同期が走る＝常時重い。最悪の構成なのでローカル実体に戻すべき。" ;;
    esac
  fi
else
  echo "    （iCloud Drive 未使用）"
fi

# ------------------------------------------------------------
sec "8. Spotlight インデックス"
mdutil -s / 2>/dev/null | sed 's/^/  /'
if [ -d "$CLAUDE_DIR" ]; then
  if [ -e "$CLAUDE_DIR/.metadata_never_index" ]; then
    echo "  ~/.claude: Spotlight 除外済み（.metadata_never_index あり）"
  else
    echo "  ~/.claude: Spotlight 除外なし"
    if [ -n "${TOTAL_MB:-}" ] && [ "$TOTAL_MB" -ge 1000 ] 2>/dev/null; then
      flag "~/.claude(${TOTAL_MB}MB) が Spotlight のインデックス対象。会話ログが書かれるたびに mds_stores が再インデックスして CPU とディスクを食う。除外推奨。"
    fi
  fi
fi
MDS_CPU="$(ps -Ao 'pcpu,comm' 2>/dev/null | grep -E 'mds|mdworker' | awk '{s+=$1} END{print s+0}')"
echo "  mds/mdworker の合計CPU: ${MDS_CPU}%"
if gt "$MDS_CPU" 40; then
  flag "Spotlight(mds/mdworker)が CPU ${MDS_CPU}% を使用中。インデックス対象に巨大な作業ディレクトリや ~/.claude が入っている疑い。"
fi

# ------------------------------------------------------------
sec "診断結果まとめ"
if [ -s "$FINDINGS_FILE" ]; then
  echo
  echo "▼ 疑わしい点"
  N=0
  while IFS= read -r f; do
    N=$((N + 1))
    echo "  [$N] $f"
  done < "$FINDINGS_FILE"
else
  echo
  echo "  明らかな異常は検出されませんでした。"
  echo "  重さが続くなら、セクション2・3の上位プロセスに Claude 以外の犯人がいないか確認してください。"
fi

cat <<'EOS'

▼ 推奨アクション（表示のみ。実行はしていません。必要なものだけ手で流してください）

  # --- 1. 裏に残った Claude Code セッションを畳む -------------------
  #   まず何が動いているか確認してから、不要な PID だけ落とす
  ps -Ao pid,pcpu,rss,etime,command | grep '[c]laude'
  #   kill <PID>        # ← 個別に。全消しは走行中の cron ルーティンも巻き込むので非推奨

  # --- 2. shell-snapshots の掃除（削除して支障なし） ----------------
  #   まず件数と容量を確認
  du -sh ~/.claude/shell-snapshots; ls ~/.claude/shell-snapshots | wc -l
  #   7日より古いものを削除
  find ~/.claude/shell-snapshots -type f -mtime +7 -delete

  # --- 3. 古い会話ログの掃除（/resume で遡れなくなる点だけ注意） ----
  #   まず「何がどれだけ消えるか」を確認（-delete を付けない）
  find ~/.claude/projects -name '*.jsonl' -mtime +60 | wc -l
  #   納得したら削除
  find ~/.claude/projects -name '*.jsonl' -mtime +60 -delete

  # --- 4. ~/.claude を Spotlight から除外（体感差が大きい） ---------
  touch ~/.claude/.metadata_never_index
  #   反映（再インデックス抑止）
  sudo mdutil -i off ~/.claude 2>/dev/null || true

  # --- 5. Time Machine からも除外 -----------------------------------
  sudo tmutil addexclusion ~/.claude

  # --- 6. 使っていない MCP サーバを外す（メモリに一番効く） ---------
  #   セッション数 × MCP数 だけ node プロセスが常駐する。
  #   ~/.claude.json / ~/.claude/settings.json / プロジェクトの .mcp.json を見直す。
  claude mcp list

  # --- 7. cron ルーティンの多重発火を防ぐ ---------------------------
  crontab -l
  #   同時刻に集中しているならジッター（数分ずらし）を入れる。
  #   実行に時間がかかるジョブは、間隔を実行時間より長くする。
EOS

echo
echo "この出力をそのまま Claude に貼れば、原因の特定と対処まで続けられます。"
