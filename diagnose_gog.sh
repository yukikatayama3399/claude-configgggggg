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

# backend によって必要なものが違う。
#   file  … GOG_KEYRING_PASSWORD が要る（クラウド Linux）
#   auto  … macOS Keychain。パスワード環境変数は不要
BACKEND="$(printf '%s\n' "$DOC" | awk -F'\t' '$2=="keyring.backend"{print $3; exit}')"

# 複数アカウントが入っていることがあるので、診断対象の行だけを拾う。
# 1行目を無条件に取ると別アカウントの結果を見てしまう。
REFRESH_KEY="$(printf '%s\n' "$DOC" \
  | awk -F'\t' -v acct="$ACCOUNT" '$2 ~ /^refresh\./ && $2 ~ acct"$" {print $2; exit}')"

KEYRING_OPEN="$(level_of keyring.open)"
TOKENS="$(level_of tokens)"
REFRESH="absent"
[ -n "$REFRESH_KEY" ] && REFRESH="$(level_of "$REFRESH_KEY")"

echo "keyring backend: ${BACKEND:-不明}"
if printf '%s\n' "$DOC" | grep -q '^\(ok\|warn\|error\)'$'\t''refresh\.'; then
  echo "アカウント別のリフレッシュ結果:"
  printf '%s\n' "$DOC" | awk -F'\t' '$2 ~ /^refresh\./ {printf "  %-6s %s\n", $1, $2}'
fi
echo ""

verdict() { echo "判定: $1"; shift; printf '対処: %s\n' "$@"; }

# ---- 上流から順に潰す。最初に引っかかったものが真因 ----

# 1〜2) keyring が開けない。開けているなら backend が何であれ問題なし。
#   GOG_KEYRING_PASSWORD の有無だけを見て犯人扱いしてはいけない。
#   macOS の backend は auto(Keychain) で、この変数を必要としない。
if [ "$KEYRING_OPEN" = "error" ]; then
  case "$BACKEND" in
    file*)
      if [ -z "${GOG_KEYRING_PASSWORD:-}" ]; then
        verdict "GOG_KEYRING_PASSWORD がこの実行文脈に無い（トークンは無関係）" \
          "トークンは壊れていない。再認証は不要。" \
          "対話シェルでは動くのに cron / launchd / ルーティンからだけ失敗するなら、ほぼこれ。" \
          "そのルーティンを起動する環境に GOG_KEYRING_PASSWORD を明示的に渡す。" \
          "値は全環境で完全に同一であること。"
      else
        verdict "file keyring を開けない（パスワード不一致が最有力）" \
          "設定されている GOG_KEYRING_PASSWORD が他環境と同一か確認する。" \
          "トークンの生死とは無関係。再認証の前にここを直す。"
      fi ;;
    *)
      verdict "keyring を開けない（backend=${BACKEND:-不明}／トークンの生死とは無関係）" \
        "macOS なら Keychain へのアクセス拒否を疑う。" \
        "非対話プロセス（cron / launchd）は login keychain を解錠できないことがある。" \
        "対話シェルで通るのにルーティンからだけ落ちるなら、ほぼこれ。" \
        "再認証しても直らない類の問題なので --reauth に逃げないこと。" ;;
  esac
  echo ""
  echo "!! gog auth add は絶対に叩かないこと（--services 既定が user でスコープが 22 → 最小に潰れる）"
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
echo "判定: 正常。認証は生きている（対話シェル文脈）。"
echo ""
echo "スコープ:"
"$GOG" auth list 2>/dev/null | sed 's/^/  /'
echo ""

# ---- 追加検査: cron / launchd 相当の最小環境で再現するか ----
# ルーティンは対話シェルの環境変数を引き継がない。ここで落ちるなら
# 「トークン失効」ではなく実行文脈の問題だと確定できる。
echo "--- cron / launchd 相当（環境変数を落とした最小文脈）で再検査 ---"
CRON_OUT="$(env -i HOME="$HOME" PATH="/usr/bin:/bin:/usr/local/bin:$HOME/bin" \
    "$GOG" auth doctor --check --no-input 2>&1)"
# 終了コードだけ見ると取りこぼす。doctor は status 行が error でも 0 を返すことがある。
CRON_STATUS="$(printf '%s\n' "$CRON_OUT" | awk -F'\t' '$1=="status"{print $2; exit}')"
CRON_REFRESH="$(printf '%s\n' "$CRON_OUT" \
  | awk -F'\t' -v acct="$ACCOUNT" '$2 ~ /^refresh\./ && $2 ~ acct"$" {print $1; exit}')"

if [ "$CRON_STATUS" = "ok" ] && [ "${CRON_REFRESH:-ok}" = "ok" ]; then
  echo "$CRON_OUT" | grep -E "keyring\.open|tokens|refresh\.|status" | sed 's/^/  /'
  echo ""
  echo "→ 最小文脈でも通った。実行文脈の問題でもない。"
else
  echo "$CRON_OUT" | grep -E "keyring|tokens|refresh\.|status|error" | sed 's/^/  /'
  echo ""
  echo "→ **ここで落ちた。これがルーティン失敗の正体。**"
  echo "   対話シェルでは通るので「トークン失効」ではない。再認証しても直らない。"
  echo "   ルーティンを起動する環境に、対話シェルと同じ設定を渡すこと"
  echo "   （macOS Keychain のアクセス許可、GOG_ACCOUNT、PATH など）。"
fi
echo ""
echo "この状態で「トークン失効」と報告してくるルーティンがあれば、それは誤報。"
echo "報告側の判定ロジックを直すこと（auth 系の失敗を一括で失効と決めつけていないか）。"
exit 0
