---
name: tentative-onboarding-cleanup
description: 杉浦さん(sugiura@fout.jp)が参加者に入っている HAWK オンボーディングの「仮」予定を、確定していなければ前日 18:00 JST に自動削除する運用。「仮予定を掃除して」「オンボーディング候補枠を消して」「明日の仮枠どうなってる」などの依頼、および毎日 18:00 JST の Routine で使う。片山が作った未確定の予定のみが対象で、他人の予定・確定済み・繰り返し予定には触らない。
---

# tentative-onboarding-cleanup: オンボーディング仮予定の前日削除

## ルール（2026-09-18 片山決定）

HAWK 無料トライアルのオンボーディング（つなぎ込み）は、片山・杉浦が空いている枠を
複数社向けに**仮押さえ**してから、各社の回答で 1 枠に確定する運用。
確定しなかった仮枠を放置すると杉浦さんのカレンダーが塞がったままになるので、

> **sugiura@fout.jp が参加者に入っている、片山が作った未確定の予定は、
> どんな理由があっても前日 18:00 JST に削除する。**

## 「未確定」の判定（全部満たすものだけ削除。迷ったら消さない）

| # | 条件 | 意図 |
|---|---|---|
| 1 | creator と organizer が `yuki.katayama@fout.jp` | 他人が作った予定は絶対に触らない |
| 2 | attendees に `sugiura@fout.jp` | 杉浦さんが入る予定だけ |
| 3 | タイトルに **「仮」** を含む | `[仮] HAWKオンボーディング候補（…）` / `[作業] 仮/〇〇_…候補日` の両形式に対応 |
| 4 | タイトルに「確定」を含まない | 二重ガード |
| 5 | `recurringEventId` が無い | 定例会などの繰り返し予定を誤って消さない |
| 6 | status が `cancelled` でない | 既に消えているものは対象外 |

**確定の合図はタイトルから「仮」を外すこと。** 確定した枠は必ずタイトルを直す
（例: `[仮] HAWKオンボーディング候補（ノビテル）` → `HAWKオンボーディング（ノビテル）`）。
直さないと前日 18:00 に消える。

## 実行（スクリプト）

```bash
bash calendar/delete_tentative_onboarding.sh --dry-run          # 翌日分の対象を表示（消さない）
bash calendar/delete_tentative_onboarding.sh                    # 翌日分を削除
bash calendar/delete_tentative_onboarding.sh --date 2026-10-02 --dry-run   # 日付指定
bash calendar/delete_tentative_onboarding.sh --send-updates all # 参加者に取消通知メールを送る
```

- 既定は `--send-updates none`（杉浦さんに取消メールを飛ばさない。カレンダーからは消える）。
- 出力は 1 行 1 件 `DELETE|DRY-RUN <開始> <タイトル> (<eventId>)` と末尾サマリ。
- 終了コード: 0 = 正常（0 件含む）/ 1 = 削除失敗あり / 2 = 前提エラー（この時は何も消していない）。
- ページングは自前で回している（gog の `--all-pages` は JSON 出力だと初回ページしか返さないことがあった）。

スクリプトが手元に無い環境では同等をインラインで行う:
`gog -j calendar events primary --from <翌日 00:00+09:00> --to <翌日 23:59:59+09:00>` で取得し、
上の 6 条件で絞って `gog calendar delete primary <eventId> --send-updates none -y --no-input`。

## Routine

- 毎日 **18:00 JST**（cron `0 9 * * *` UTC）に新規セッションで発火し、翌日分を処理する。
  Routine 名: 「オンボーディング仮予定の前日削除（毎日18:00 JST）」
- 土日も回す（月曜のオンボーディングは日曜 18:00 に判定される）。
- gog が使えない時はカレンダーに一切触らず中止する（推測で消さない）。

## 関連

- スクリプト: `calendar/delete_tentative_onboarding.sh`
- 仮押さえの作り方は hawk-inbound-lead / hawk-meeting-setup 側。ここは**削除だけ**を担当する。
