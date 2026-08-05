#!/usr/bin/env bash
# ============================================================
# diagnose_gog.sh — gog が使えない原因を「切り分けて」断定する
#
# 読み取り専用。認証もしないし、トークンにも触らない。いつ実行しても安全。
#
# なぜ必要か:
#   check_gog_apis.sh は認証系の失敗を全部 "auth NG" に丸めてしまうため、
#   「keyring が開けないだけ」でも「トークン失効」と誤診される。
#   実際 2026-08-05 に、Mac のルーティンが「7/21 から invalid_grant で失効中」と
#   毎朝 Slack に誤報し続けていた一方で、同じリフレッシュトークンが
#   クラウドでは正常に動いていた（22 スコープ健在）。
#   このスクリプトは gog auth doctor の各段を個別に見て、原因を1つに絞る。
#
# 使い方:
#   bash diagnose_gog.sh
#   bash diagnose_gog.sh --account other@example.com
#
# 終了コード: 0 = 正常 / 1 = 異常（原因は標準出力に断定して出す）
# ============================================================
set -uo pipefail

ACCOUNT="${GOG_ACCOUNT:-yuki.katayama@fout.jp}"
if [ "${1:-}" = "--account" ] && [ -n "${2:-}" ]; then
  ACCOUNT="$2"
fi

GOG="$(command -v gog || echo "$HOME/bin/gog")"
if [ ! -x "$GOG" ]; then
  echo "判定: gog が見つからない ($GOG)"
  echo "対処: Mac なら gog をインストール。クラウドなら bash setup_gog_remote.sh"
  exit 1
fi

echo "gog       : $("$GOG" --version 2>/dev/null | head -1)"
echo "アカウント: $ACCOUNT"
echo "実行文脈  : user=$(whoami) shell=${SHELL:-?} host=$(hostname)"
echo ""

# ---- doctor の生出力を確保 ----
# --check を付けないとリフレッシュ交換が実行されず、refresh.* 行が出ない。
# それだと「本当に失効しているか」を判定できないので必ず付ける。
DOC="$("$GOG" auth doctor --check --no-input 2>&1)"
echo "--- gog auth doctor --check ---"
echo "$DOC"
echo "-----------------------"
echo ""

# doctor は「レベル<TAB>キー<TAB>メッセージ」で出す。キー単位で状態を引く。
level_of() {  # $1=キー名 → そのキーの最悪レベルを返す(無ければ absent)
  local key="$1" lv="absent" l k
  while IFS=$'\t' read -r l k _; do
    [ "$k" = "$key" ] || continue
    case "$l" in
      error|fail) lv="error" ;;
      warn)       [ "$lv" = "error" ] || lv="warn" ;;
      ok)         [ "$lv" = "absent" ] && lv="ok" ;;
    esac
  done <<< "$DOC"
  echo "$lv"
}

REFRESH_KEY="$(printf '%s\n' "$DOC" | awk -F'\t' '$2 ~ /^refresh\./ {print $2; exit}')"

KEYRING_PW="$(level_of keyring.password)"
KEYRING_OPEN="$(level_of keyring.open)"
TOKENS="$(level_of tokens)"
REFRESH="absent"
[ -n "$REFRESH_KEY" ] && REFRESH="$(level_of "$REFRESH_KEY")"

verdict() { echo "判定: $1"; shift; printf '対処: %s\n' "$@"; }

# ---- 上流から順に潰す。最初に引っかかったものが真因 ----

# 1) keyring のパスワードが「この実行文脈に」無い
#    cron / launchd / エージェントから起動すると、対話シェルの環境変数が
#    引き継がれずここで落ちる。トークンは無傷。最頻の誤診原因。
if [ -z "${GOG_KEYRING_PASSWORD:-}" ] || [ "$KEYRING_PW" = "error" ]; then
  verdict "GOG_KEYRING_PASSWORD がこの実行文脈に無い（トークンは無関係）" \
    "トークンは壊れていない。再認証は不要。" \
    "対話シェルでは動くのに cron / launchd / Claude Code のルーティンからだけ失敗するなら、ほぼこれ。" \
    "そのルーティンを起動する環境に GOG_KEYRING_PASSWORD を明示的に渡す。" \
    "値は全環境で完全に同一であること。"
  echo ""
  echo "!! gog auth add は絶対に叩かないこと（--services 既定が user でスコープが 22 → 最小に潰れる）"
  exit 1
fi

# 2) keyring 自体が開けない（パスワード不一致 / バックエンド違い / ファイル破損）
if [ "$KEYRING_OPEN" = "error" ]; then
  verdict "keyring を開けない（トークンの生死とは無関係）" \
    "パスワード不一致が最有力。他環境と同じ GOG_KEYRING_PASSWORD か確認する。" \
    "バックエンド違いの可能性: gog auth status で backend を確認（クラウドは file）。" \
    "直らなければ「正」の Mac で bash sync_gog_token.sh（--reauth なし）を実行し、" \
    "出力された GOG_TOKEN_EXPORT_B64 を gog auth tokens import で焼き直す。"
  echo ""
  echo "!! gog auth add は絶対に叩かないこと（スコープが縮む）"
  exit 1
fi

# 3) トークンが読めない / 入っていない
if [ "$TOKENS" = "error" ] || [ "$TOKENS" = "absent" ]; then
  verdict "この端末の keyring にトークンが入っていない" \
    "失効ではない。単に配られていないだけ。" \
    "「正」の会社 Mac で bash sync_gog_token.sh（--reauth なし）を実行し、" \
    "出た GOG_TOKEN_EXPORT_B64 を base64 -d してファイルに落とし、" \
    "gog auth tokens import <file> --no-input --force で取り込む。"
  echo ""
  echo "!! gog auth add は絶対に叩かないこと（スコープが縮む）"
  exit 1
fi

# 3.5) refresh 行が出ていない = 交換が試されていない。断定できないので実弾で確かめる。
if [ "$REFRESH" = "absent" ]; then
  if PROBE="$("$GOG" --account "$ACCOUNT" drive ls --max 1 2>&1)"; then
    REFRESH="ok"
  else
    echo "参考: 実 API 呼び出しの結果 → $(printf '%s' "$PROBE" | grep -v '^$' | head -1 | cut -c1-120)"
    echo ""
    case "$PROBE" in
      *invalid_grant*) REFRESH="error" ;;
      *) verdict "認証は通っているが API 呼び出しが失敗している" \
           "失効ではない。API 無効化・スコープ不足・ネットワーク側を疑う。" \
           "bash check_gog_apis.sh でどの API が落ちているか特定する。" \
           "特定の API だけ not enabled なら OAuth プロジェクト側で有効化する（CLAUDE.md 参照）。"
         exit 1 ;;
    esac
  fi
fi

# 4) ここまで通ってリフレッシュ交換が落ちる = 本当の失効
if [ "$REFRESH" = "error" ]; then
  verdict "リフレッシュトークンが本当に失効している（invalid_grant）" \
    "ここで初めて再認証が正当化される。" \
    "「正」の会社 Mac だけで bash sync_gog_token.sh --reauth を実行する。" \
    "家 Mac・クラウド・CI では実行しない。" \
    "実行後、Claude Code on the web の環境変数と GitHub Secrets の両方を更新する。"
  echo ""
  echo "補足: OAuth 同意画面を「テストに戻す」とリフレッシュトークンの寿命が 7 日になる。"
  echo "      毎週この状態になるなら、公開ステータスが本番のままか確認すること。"
  exit 1
fi

# 5) 全段クリア
echo "判定: 正常。認証は生きている。"
echo ""
echo "スコープ:"
"$GOG" auth list 2>/dev/null | sed 's/^/  /'
echo ""
echo "この状態で「トークン失効」と報告してくるルーティンがあれば、それは誤報。"
echo "報告側の判定ロジックを直すこと（auth 系の失敗を一括で失効と決めつけていないか）。"
exit 0
