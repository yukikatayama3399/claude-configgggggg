# Remote Routines 棚卸し（2026-07-20 時点）

scheduled-tasks 棚卸し（7/16実施）の続き。claude.ai の **remote Routines** の現状を、
このリモートセッションの `list_triggers` 実データから起こしたスナップショット。
（Mac ローカルの `~/Desktop/routines_inventory.md` とは別。こちらは remote 側の実在Routine一覧）

cron は UTC 表記。JST = UTC+9。

## 稼働中の Routine 一覧（enabled）

| # | 名前 | cron (UTC) | 実行時刻(JST) | 作成日 | 直近発火 | コネクタ | フェイルセーフ |
|---|------|-----------|--------------|--------|----------|----------|----------------|
| 1 | hawk-url-index-original-refresh | `0 0 * * 1-5` | 平日 09:00 | 07-16 | 07-20 09:04 | Drive, Slack | ❌ **なし** |
| 2 | daily-calendar-free-sweep | `0 10 * * *` | 毎日 19:00 | 07-16 | 07-19 19:03 | Calendar, Slack | ✅ §0あり |
| 3 | 木曜10am KPI活動集計→Slack DM | `0 1 * * 4` | 木 10:00 | 07-13 | 07-16 | (persistent session) | 部分 |
| 4 | カレンダー命名＆予定あり/なし仕分け | `0 0,6 * * *` | 毎日 09:00 / 15:00 | 07-13 | 07-20 09:05 | (persistent session) | あり |
| 5 | 競合ウォッチ 朝のブリーフィング | `0 22 * * 0-4` | 平日 07:00 | 06-07 | 07-19 22:07 | Slack (repo: claude-config) | 一部 |
| 6 | AI動向 朝のチェック | `0 22 * * 0-4` | 平日 07:00 | 06-07 | 07-19 22:08 | Slack | 一部 |
| 7 | 米国市場 朝の要約 | `0 22 * * 0-4` | 平日 07:00 | 06-07 | 07-19 22:07 | Slack | 一部 |
| 8 | Slack見落とし防止（14/19/23時） | `0 5,10,14 * * 1-5` | 平日 14/19/23:00 | 06-04 | 07-17 | Gmail/Drive/Cal/Slack | - |
| 9 | Slack見落とし防止（朝8時） | `0 23 * * 0-4` | 平日 08:00 | 06-04 | 07-19 | Gmail/Drive/Cal/Slack | - |

（run-once の send_later 2件は発火済み・失効のため除外）

## A組（task優先リスト）移行ステータス

| 優先 | SKILL名 | remote移行 | 対応Routine / 備考 |
|------|---------|-----------|--------------------|
| — | hawk-url-index | ✅ 済 | #1（ただしフェイルセーフ未実装） |
| — | daily-calendar-free-sweep | ✅ 済 | #2 |
| ② | daily-calendar-naming-normalize | ✅ 済 | #4 に統合（命名＋availability） |
| ① | daily-calendar-color-coding | ❌ 未 | #4 は色分けを含まない。別途要移行 |
| ③ | hawk-customer-folder-sweep | ❌ 未 | 該当Routineなし |
| ④ | gemini-gijiroku-collector | ❌ 未 | 該当Routineなし |
| ⑤ | hawk-meeting-reminder-drafts | ❌ 未 | 該当Routineなし |
| ⑥ | hawk-lead-autolog | ❌ 未 | 該当Routineなし |
| ⑦ | hawk-proposal-status-weekly-update | ❌ 未 | #3(KPI木曜)が週報更新を一部担うが別物 |
| 検証 | hawk-weekly-report-draft | ❌ 未 | #3が近いが Doc書込テストは未実施 |

→ **残り本番＝ ①③④⑤⑥⑦ ＋検証枠**。②とurl-index/free-sweepは7/16バッチで完了済み。

## C組（廃止候補・SKILL.md注記対象）

Mac/iCloud 側の SKILL.md にのみ存在（このリポジトリには無い＝remoteからは編集不可）。
注記作業は Mac ローカルの `claude` で実施する。

- hawk-unreplied-mail-alert
- hawk-bounce-inbox-sweep
- hawk-lead-autolog-watchdog

## 事前チェック結果（7/17 の定期実行DM）

自分宛DM `D0B6P80CF6D` の実履歴で検証。

- **hawk-url-index（金9:00）: ❌ 未達。** 7/17 は 08:13→14:12→19:05 と飛んでおり 9時台のDMなし。
  7/20 09:06 は正常配信。→ **7/17 初回平日実行が1回だけ抜けた**。
- **daily-calendar-free-sweep（金19:00）: ✅ 到達。** 7/17 19:05「FREEに変更:2件」。7/18・7/19も毎日到達。

### 原因仮説と対策
- free-sweep には §0 フェイルセーフ（コネクタ死亡時にSlack通知して終了）があり、失敗しても通知される。
- url-index には **フェイルセーフ節が無く、失敗すると無言で消える**。7/17の欠落はこの設計と整合。
- **対策：url-index に free-sweep 型フェイルセーフ＋「1行でも必ず報告」節を追加する。**
