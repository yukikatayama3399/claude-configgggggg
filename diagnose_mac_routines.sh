#!/usr/bin/env bash
# ============================================================
# diagnose_mac_routines.sh — Mac(ローカル)側で実行する
#
# 目的: 「朝のルーティンが動かなかった」原因を切り分ける。
#       読み取りのみ。何も変更しない。
#
# 見るもの:
#   1. どっちの Mac か(会社=yuki / 家=FOyuki)とパスの食い違い
#   2. cron の登録内容と、存在しないパスを指していないか
#   3. scheduled-tasks 定義(ローカル / iCloud)と未ダウンロード状態
#   4. gog の健全性(doctor + 実API)
#   5. cron から環境変数が見えるか  ← 「手で叩くと動くのに朝は失敗」の主犯
#
# 使い方: bash diagnose_mac_routines.sh
# ============================================================
set -uo pipefail   # -e は付けない。失敗しても全項目を最後まで出す。

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"
VERIFY_SHEET_ID="${GOG_VERIFY_SHEET_ID:-1iyhwVNhN_HJNdIBL_pREhrhBdQu2it5ktFOYq-DDm_w}"

# 会社 Mac のユーザー名。家 Mac は FOyuki。
EXPECTED_USER="${GOG_EXPECTED_USER:-yuki}"
OTHER_USER="${GOG_OTHER_USER:-FOyuki}"

sec() { echo ""; echo "=============================================="; echo "$*"; echo "=============================================="; }
ok()   { echo "  [ok]   $*"; }
warn() { echo "  [warn] $*"; }
bad()  { echo "  [NG]   $*"; }

# ---- 1. どの Mac か ----
sec "1. この端末"
echo "  hostname : $(hostname)"
echo "  whoami   : $(whoami)"
echo "  HOME     : $HOME"
if [ "$(whoami)" = "$EXPECTED_USER" ]; then
  ok "会社 Mac(「正」の端末)"
elif [ "$(whoami)" = "$OTHER_USER" ]; then
  warn "家 Mac。ここでは gog auth add を叩かないこと(CLAUDE.md)"
else
  warn "想定外のユーザー名。ランブック内のパスの読み替えに注意"
fi

# ---- 2. cron ----
sec "2. crontab"
if CRON="$(crontab -l 2>/dev/null)"; then
  echo "$CRON" | sed 's/^/  | /'
  echo ""
  # 他方の Mac のパスを指していないか
  if echo "$CRON" | grep -q "/Users/${OTHER_USER}/"; then
    bad "crontab が /Users/${OTHER_USER}/ を参照している。この Mac には存在しないので必ず失敗する。"
    echo "$CRON" | grep -n "/Users/${OTHER_USER}/" | sed 's/^/         /'
  else
    ok "他方の Mac のパス(/Users/${OTHER_USER}/)への参照は無し"
  fi
  # 参照先ファイルの実在チェック
  echo ""
  echo "  -- cron が参照しているパスの実在確認 --"
  echo "$CRON" | grep -oE '/[^ "'"'"']+' | sort -u | while read -r p; do
    case "$p" in
      */) continue ;;
    esac
    if [ -e "$p" ]; then ok "存在: $p"; else bad "存在しない: $p"; fi
  done
else
  warn "crontab が空、または読めない。cron ではなく launchd で登録している可能性あり:"
  ls -1 "$HOME/Library/LaunchAgents" 2>/dev/null | sed 's/^/         /' || echo "         (LaunchAgents なし)"
fi

# ---- 3. scheduled-tasks 定義 ----
sec "3. scheduled-tasks 定義"
LOCAL_TASKS="$HOME/.claude/scheduled-tasks"
if [ -d "$LOCAL_TASKS" ]; then
  ok "ローカル: $LOCAL_TASKS"
  ls -1 "$LOCAL_TASKS" | sed 's/^/         /'
  # ランブック内に他方の Mac のパスが埋まっていないか
  if grep -rl "/Users/${OTHER_USER}/" "$LOCAL_TASKS" >/dev/null 2>&1; then
    bad "ランブック内に /Users/${OTHER_USER}/ のパスが埋まっている(この Mac では読み替えが必要):"
    grep -rn "/Users/${OTHER_USER}/" "$LOCAL_TASKS" | sed 's/^/         /'
  else
    ok "ランブック内に他方の Mac のパスは無し"
  fi
else
  bad "ローカル定義が無い: $LOCAL_TASKS"
fi

ICLOUD_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
echo ""
if [ -d "$ICLOUD_ROOT" ]; then
  ok "iCloud Drive: $ICLOUD_ROOT"
  # scheduled-tasks フォルダを探す(場所が動いていても拾えるように)
  find "$ICLOUD_ROOT" -maxdepth 4 -type d -name 'scheduled-tasks' 2>/dev/null | while read -r d; do
    echo "         見つけた: $d"
    # .icloud = 実体未ダウンロードのプレースホルダ。cron から読むと空に見える。
    PLACEHOLDERS="$(find "$d" -name '*.icloud' 2>/dev/null | wc -l | tr -d ' ')"
    if [ "$PLACEHOLDERS" != "0" ]; then
      bad "未ダウンロードのファイルが ${PLACEHOLDERS} 件ある(.icloud プレースホルダ)。cron からは読めない。"
      echo "         対策: brctl download \"$d\" もしくは Finder で開いて実体化する"
    else
      ok "全ファイルが実体化済み"
    fi
  done
else
  warn "iCloud Drive のパスが見つからない: $ICLOUD_ROOT"
fi

# ---- 4. gog ----
sec "4. gog"
if command -v gog >/dev/null 2>&1; then
  ok "gog: $(command -v gog) / $(gog --version 2>/dev/null | head -1)"
  echo ""
  echo "  -- auth list --"
  gog auth list --no-input 2>&1 | sed 's/^/  | /'
  echo ""
  echo "  -- auth doctor --"
  # パイプすると sed の終了ステータスを拾ってしまうので、先に出力を受け取る。
  DOCTOR_OUT="$(gog auth doctor --check --no-input 2>&1)"; DOCTOR_RC=$?
  echo "$DOCTOR_OUT" | sed 's/^/  | /'
  if [ "$DOCTOR_RC" = "0" ]; then
    ok "doctor: 通った"
  else
    bad "doctor: 異常。invalid_grant ならクラウドの生きた値を移し替える:"
    echo "         bash restore_gog_local.sh ~/.gog_sync/<最新>.env"
  fi
  echo ""
  echo "  -- 実API(Sheets 読み取り) --"
  API_OUT="$(gog --account "$ACCOUNT" sheets get "$VERIFY_SHEET_ID" "A1:B2" 2>&1)"; API_RC=$?
  echo "$API_OUT" | sed 's/^/  | /'
  if [ "$API_RC" = "0" ]; then
    ok "実API: 通った"
  else
    bad "実API: 弾かれた"
  fi
else
  bad "gog が PATH に無い。cron から呼ぶときは絶対パスで書くこと。"
fi

# ---- 5. cron から環境変数が見えるか ----
# ここが本命。ターミナルでは動くのに朝だけ失敗する、の典型原因。
sec "5. cron から見える環境変数"
echo "  ターミナル(このシェル)での状態:"
for v in GOG_KEYRING_PASSWORD GOG_CREDENTIALS_B64 GOG_TOKEN_EXPORT_B64; do
  val="${!v:-}"
  # 値そのものは出さない。長さだけ出して「入っているか」を確かめる。
  if [ -n "$val" ]; then ok "$v: セット済み (${#val} 文字)"; else bad "$v: 未設定"; fi
done

echo ""
echo "  cron に渡っているか(crontab 内の定義を確認):"
if crontab -l 2>/dev/null | grep -q 'GOG_KEYRING_PASSWORD'; then
  ok "crontab 内に GOG_KEYRING_PASSWORD の定義あり"
else
  bad "crontab 内に GOG_KEYRING_PASSWORD の定義が無い。"
  echo "         cron は ~/.zshrc / ~/.zprofile を読まないので、"
  echo "         シェルでだけ export していても無人実行では見えない。"
  echo "         crontab の先頭に直接書くか、ラッパースクリプトで読み込ませる。"
fi

echo ""
echo "  シェル起動ファイル側の定義:"
for f in "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.bash_profile" "$HOME/.bashrc"; do
  [ -f "$f" ] || continue
  if grep -q 'GOG_KEYRING_PASSWORD' "$f"; then
    echo "         $f: 定義あり(cron からは読まれない点に注意)"
  fi
done

sec "おわり"
echo "  [NG] が付いた項目を上から順に潰す。"
echo "  gog が invalid_grant なだけなら restore_gog_local.sh で直る(再認証不要)。"
