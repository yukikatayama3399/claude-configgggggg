# inbox-calendar-watchdog/SKILL.md 「gog死活チェック」節の差し替え

Mac の `~/.claude/scheduled-tasks/inbox-calendar-watchdog/SKILL.md` にある
`## gog死活チェック（毎回・5項目の検査より先に実行）` の節を、
以下の内容で**まるごと置き換える**。

## なぜ直すのか

旧版は `gog-health.sh` が返す非ゼロ終了を**種類を問わず全部「トークン失効」**
として扱っていた。実際にはトークンは正常で、別の理由（権限不足・実行文脈・
PATH）で落ちていただけだったが、その区別が無いため 2026-07-21 から 17 日以上
毎朝「失効」を報告し続け、HAWK 提案ステータス同期などが work を丸ごと
スキップしていた。

さらに旧版が案内していた `gog auth add` は `--services` の既定値が `user` の
ため、叩かれると 22 個あるスコープが最小構成に潰れる。誤診と危険な処方が
セットになっていた。

改訂した `gog-health.sh` は失敗を分類し、終了コードを
**1 = 真の失効 / 2 = それ以外の異常**に分離している。これを受ける側も
区別しないと分類した意味が無いため、この節を差し替える。

---

## 差し替え後の本文（ここから）

```markdown
## gog死活チェック（毎回・5項目の検査より先に実行）

- Bashで `"$HOME/Library/Mobile Documents/com~apple~CloudDocs/Claude/bin/gog-health.sh"` を実行する（読み取り専用・数秒で終わる）。
- 出力は行頭にラベルが付く（OK / NOPATH / NOAUTH / NOPERM / KEYRING / EXPIRED / BADCLIENT / FAIL）。**終了コードとラベルの両方を見ること。**

- **exit 0**（全アカウントOK）→ 何もせず次へ。

- **exit 1**（`EXPIRED` ＝ 本当に invalid_grant で失効）→ **HIGH所見**として扱う：
  「[gog失効] <アカウント> のgogトークンが invalid_grant で失効。gog依存の定期タスク（attacklist-morning-sync等）が止まる。復旧は会社Macで `bash sync_gog_token.sh --reauth`」

- **exit 2**（失効ではない異常）→ **MEDIUM所見**として扱う。
  **「失効」という語を使わないこと。** 出力のラベルと該当行をそのまま載せ、原因に応じて書く：
  - `NOPERM` … 権限 / スコープ不足（403）。`--account` の指定漏れが典型。トークンは生きており、再認証しても直らない
  - `KEYRING` … keyring を開けない。cron / launchd に対話シェルの環境や Keychain 解錠が引き継がれていない。再認証しても直らない
  - `BADCLIENT` … クライアントシークレット無効。`gog auth credentials set <client_secret_*.json>` の1発で直る。**ブラウザ再認証は不要**（refresh token は client_id に紐づくため生存）
  - `NOPATH` … gog が見つからない。認証とは無関係。cron から呼ぶ場合の PATH を疑う
  - `NOAUTH` … そのサービスの認証情報が無い。失効ではない
  - `FAIL` … 分類できない失敗。出力2行をそのまま貼る

- **`gog auth add` は絶対に案内しない。** `--services` の既定値が `user` のため、案内どおり叩かれると 22 スコープが最小構成に潰れる。正しい復旧経路は `sync_gog_token.sh` のみ。

- 状態キーは `"gog:"+アカウント+":"+ラベル` とする（既存の重複防止機構に載せる）。
  **ラベルをキーに含めるのが重要。** 含めないと原因が変わっても同じキーのままになり、古い誤診の初見日時が居座って「N日目」を延々と数え続ける。
  新規のみDM、24時間後に未解消なら再通知、復旧したらキー削除。

- 断定に迷ったら `bash ~/claude-configgggggg/diagnose_gog.sh` の判定を使う。**403 forbidden は権限不足であって失効ではない。**

- スクリプトが見つからない・実行できない場合はこのチェックをスキップして通常の5項目へ（チェック自体の失敗で警告は出さない）。
```

## 差し替え後にやること

**居座っている古い状態キーを消す。** `gog:yuki.katayama@fout.jp` が
2026-07-21 初見のまま残っていると、健全になっても報告が続く。
重複防止機構の保存先を特定して該当キーを削除するか、
キー命名にラベルを足した時点で旧キーが参照されなくなるなら放置でもよい。
