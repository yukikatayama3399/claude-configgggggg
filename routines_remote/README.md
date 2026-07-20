# routines_remote — Mac scheduled-tasks → claude.ai remote Routines 移行キット

7/16 棚卸しの続き（A組移行）。各 `NN_<name>.md` は Mac の SKILL.md を **claude.ai Routines UI にそのまま貼れる形**に翻訳したもの。
各ファイルの `=== ここからUIに貼るプロンプト ===` 〜 `=== ここまで ===` を丸ごとコピーして UI に貼る。

## なぜUI作成が必須か（重要）
- このリモートセッションの `create_trigger` では **Routineにコネクタもソースrepoも紐付けできない**（動かないRoutineになる）。検証済み。
- ∴ Routine作成は **claude.ai の Routines UI で行う**（コネクタ・ソースrepoが正しく付く）。ここのファイルは「貼り付け原稿」。

## 移行手順（各ルーティン共通・7/16の型）
1. 該当ファイルのプロンプト部を UI の新規Routineに貼る。
2. **コネクタは下表の必要最小限のみ**紐付ける（Gmail/Drive等を余計に付けない＝7/16教訓）。
3. **ソースrepo**（gog使用ルーティンのみ）に `yukikatayama3399/claude-configgggggg` を指定（SessionStartフックが gog を自動セットアップ）。
4. **トリガー時刻は下表（UIはJST解釈）**。
5. **手動実行 → Slack DM で検品**（件数を検算・誤報告・行落ちがないか）。DRY_RUN付きのものは検品後に LIVE 化。
6. OK なら **Mac 側の該当 cron/launchd を停止**（二重実行防止。停止は動作確認後の順番厳守）。
7. Mac の SKILL.md に「remote移行済み」注記（url-index の SKILL 24 が見本）。

## コネクタ / 時刻マトリクス

| # | ルーティン | JST時刻 | cron | コネクタ(最小) | source repo | gog | 冪等の要 | 初回MODE |
|---|-----------|--------|------|---------------|-------------|-----|----------|---------|
| ① | daily-calendar-color-coding | 毎日10:00,18:00 | `0 10,18 * * *` | **Calendar** | 不要 | ✗ | 現colorId一致でskip | LIVE |
| ③ | hawk-customer-folder-sweep | 平日9:30,13:30 | `30 9,13 * * 1-5` | **Slack** | ✅ | ✅ | 既に10_顧客配下はskip | DRYRUN |
| ④ | gemini-gijiroku-collector | 平日18:40 | `40 18 * * 1-5` | **Slack** | ✅ | ✅ | ★コピー先の同名有無で判定(state廃止) | LIVE |
| ⑤ | hawk-meeting-reminder-drafts | 平日12:00 | `0 12 * * 1-5` | **Calendar + Slack** | ✅ | ✅(gmail) | ★既存Gmail下書きチェック(state廃止) | DRY_RUN |
| ⑥ | hawk-lead-autolog | 平日8:00,18:00 | `0 8,18 * * 1-5` | **Slack** | ✅ | ✅ | Email+会社名で重複排除 | DRY_RUN |
| ⑦ | hawk-proposal-status-weekly-update | 木10:30 | `30 10 * * 4` | **Slack** | ✅ | ✅ | 同一事実は重複追記しない | 初回は本人確認モード |
| ⑧ | hawk-weekly-report-draft（検証枠） | 金17:35 | `35 17 * * 5` | **Slack** | ✅ | ✅ | 既存Docあればskip | 未完(要インライン) |

- Google の**書き込み**（Sheets/Docs/Drive move/copy/append）は MCPコネクタ不可 → すべて **gog CLI** で行う（読み取りも gog に統一）。よってGoogle系コネクタは付けず **source repo＋Slackのみ**が基本。①⑤だけ Calendar MCP を使う（read中心）。

## 全ルーティンに入れた共通の remote 化変更
- **§0 フェイルセーフ**：gog/コネクタが死んでいたら処理せず Slack（①は最終テキスト）に「要再認証」を通知。無言終了を禁止（毎回1通）。
- **ローカルパス依存を除去**：`~/.claude/scheduled-tasks/.../state.json`・`LEARNINGS.md` は remote 非永続のため廃止。
  - state依存の冪等（④⑤）は「実体（コピー先の同名／既存下書き）を見る」方式に作り替え。
  - 自己改善ログは廃止し、申し送りは完了報告Slackの「💡次回メモ」1〜2行に集約。
- Mac固有の「復旧/設置PC注意」節を削除。

## 移行ステータス（A組）
- ✅ 済（7/16バッチ）: hawk-url-index / daily-calendar-free-sweep / daily-calendar-naming-normalize(②)
- 🆕 本キットで用意: ①③④⑤⑥⑦（UI貼付原稿・検品待ち）
- 🚧 未完: ⑧検証枠（別skill本体のインライン要）
- ❗ 別件: hawk-url-index の §0フェイルセーフ追記 → UIで本体編集して保存（`create_trigger`では本体編集不可）

---

## 作業1: C組（廃止候補）SKILL.md 冒頭注記 ※Mac側で実施
対象3本の **iCloud の SKILL.md 冒頭**に以下を1行追記（定義本体は消さない）。ファイルは iCloud にありこのリモートからは編集不可なので Mac で。

追記テンプレ：
`⚠️ 2026-07-16 廃止候補判定。1ヶ月支障なければ削除予定。理由: <下記>`

理由ドラフト（**要確認**・棚卸し文脈からの推定。実際の判定理由に直して）：
- **hawk-unreplied-mail-alert**（平日8-21時30分おきの未返信通知）: 「Slack見落とし防止ルーティン(8/14/19/23時)と機能重複。高頻度でノイズ過多のため。」
- **hawk-bounce-inbox-sweep**（バウンス掃除）: 「hawk-lead-autolog にバウンス検知(newer_than:3d)が統合済みのため重複。」
- **hawk-lead-autolog-watchdog**（lead-autolog の見張り）: 「lead-autolog を remote Routine 化しフェイルセーフを内蔵したため、外部からの見張りが不要に。」
