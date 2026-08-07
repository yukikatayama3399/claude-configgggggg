#!/bin/bash
# ============================================================
# gog-health.sh — gog の死活チェック（読み取り専用・副作用なし）
#
# 置き場所: ~/Library/Mobile Documents/com~apple~CloudDocs/Claude/bin/gog-health.sh
# 呼び出し元: inbox-calendar-watchdog / gemini-gijiroku-collector ほか
#
# 背景:
#   2026-06-25 に fout.jp トークンが invalid_grant で失効し、gog 依存の
#   定期タスク群が気づかれないまま停止した。再発時に即検知するためのもの。
#
# 2026-08-07 改訂の理由:
#   旧版は失敗を全部「トークン失効の疑い」に丸め、復旧手順として
#   `gog auth add` を案内していた。これが 16 日以上にわたる毎朝の誤報と、
#   複数ルーティンの work スキップを生んだ。実際にはトークンは終始正常で、
#   別の理由（権限不足・PATH・keyring）で落ちていた。
#   `gog auth add` は --services の既定値が user なので、案内どおり叩かれると
#   22 個あるスコープが最小構成に潰れる。二重に有害だった。
#
#   このため、失敗の「種類」を出し分けるようにした。呼び出し側は
#   exit code だけでなく行頭のラベルを見て判断すること。
#
# 出力ラベル:
#   OK       … 正常
#   NOPATH   … gog が見つからない（認証とは無関係）
#   NOAUTH   … そのアカウントの認証情報が無い（失効ではない。未登録）
#   NOPERM   … 権限不足 / スコープ不足（403。失効ではない）
#   KEYRING  … keyring を開けない（実行文脈の問題。失効ではない）
#   EXPIRED  … invalid_grant。本当の失効。ここだけ再認証が正当化される
#   BADCLIENT… invalid_client。クライアントシークレット無効。
#              対処は `gog auth credentials set <client_secret_*.json>` で、
#              ブラウザ再認証は不要（2026-08-03 の実例）
#   FAIL     … 上記に当てはまらない不明な失敗
#
# 終了コード: 0 = 全 OK / 1 = EXPIRED あり / 2 = それ以外の異常あり
#   ※ 旧版は全ての異常で 1 を返していた。1 を「失効」と解釈している
#     呼び出し側があれば、2 と区別するよう直すこと。
# ============================================================
set -u

GOG="$(command -v gog || echo "$HOME/bin/gog")"
if [ ! -x "$GOG" ]; then
  echo "NOPATH gog が見つからない ($GOG)。認証の問題ではない。"
  echo "       cron / launchd から呼ぶ場合は PATH に注意するか絶対パスで呼ぶこと。"
  exit 2
fi

ACCOUNTS=$("$GOG" auth list 2>/dev/null | awk '{print $1}' | grep '@' | sort -u)

if [ -z "$ACCOUNTS" ]; then
  echo "SKIP gogアカウント未登録（このMacでは検査対象なし）"
  exit 0
fi

EXPIRED=0
OTHER=0

for acct in $ACCOUNTS; do
  # --account は必ず明示する。省略すると既定アカウントで走り、
  # スコープの狭いアカウントだと 403 になって誤検知する。
  OUT="$("$GOG" --account "$acct" calendar list 2>&1)"
  if [ $? -eq 0 ]; then
    echo "OK   $acct"
    continue
  fi

  case "$OUT" in
    *invalid_grant*)
      echo "EXPIRED   $acct — 本当に失効している。"
      echo "          復旧: 会社 Mac で bash sync_gog_token.sh --reauth"
      EXPIRED=1 ;;
    *invalid_client*)
      echo "BADCLIENT $acct — クライアントシークレットが無効。失効ではない。"
      echo "          復旧: gog auth credentials set <client_secret_*.json>"
      echo "          ブラウザ再認証は不要（refresh token は client_id に紐づく）。"
      OTHER=1 ;;
    *403*|*forbidden*|*"does not have permission"*|*insufficient*|*scope*)
      echo "NOPERM    $acct — 権限 / スコープ不足。トークンは生きている。"
      echo "          このアカウントに必要なスコープが無いだけ。再認証しても直らない。"
      OTHER=1 ;;
    *"No auth for"*)
      echo "NOAUTH    $acct — このサービスの認証情報が無い。失効ではない。"
      OTHER=1 ;;
    *keyring*|*"no TTY"*|*GOG_KEYRING_PASSWORD*)
      echo "KEYRING   $acct — keyring を開けない。実行文脈の問題で、失効ではない。"
      echo "          cron / launchd では対話シェルの環境や Keychain 解錠が"
      echo "          引き継がれないことがある。再認証しても直らない。"
      OTHER=1 ;;
    *)
      echo "FAIL      $acct — 分類できない失敗:"
      printf '%s\n' "$OUT" | head -2 | sed 's/^/          /'
      OTHER=1 ;;
  esac
done

# gog auth add は絶対に案内しない。--services の既定値が user のため、
# 叩かれると 22 スコープが最小構成に上書きされる。
[ "$EXPIRED" -eq 1 ] && exit 1
[ "$OTHER"   -eq 1 ] && exit 2
exit 0
