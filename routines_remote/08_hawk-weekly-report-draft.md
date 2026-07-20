# ⑧（検証枠）hawk-weekly-report-draft — remote Routine 移行用【要検証・未完】

## 状態
- **保留**。このルーティンは正本ワークフローとして別スキル **`hawk-weekly-report`（zip内 SKILL 20.md）本体**を読んで従う「ラッパー」。remote Routine では `~/.claude/skills/hawk-weekly-report/SKILL.md` が存在しないため、**hawk-weekly-report の本文をこのプロンプトにインライン展開する必要がある**。
- さらに Doc生成でURLを含むため `gdocs-hyperlink`（zip内 SKILL 2.md）の手順も必要になる可能性が高い。
- 検証枠（Doc書込テスト）なので優先度は最後。**インライン展開してよいか確認後に完成させる**。

## UI設定（確定済みの枠）
- **トリガー時刻（JST）**: 毎週 金 17:35（cron `35 17 * * 5`）。
- **コネクタ**: **Slack**（Doc/Sheets/Calendarは gog）。二重登録＝DM二重送信に注意（1つのRoutineのみ）。
- **ソースrepo**: `yukikatayama3399/claude-configgggggg`。

## ラッパー差分（Mac版の自律実行ルール・そのまま活かせる部分）
1. 対象期間＝実行日を含む週の月〜金（金曜実行＝Docタイトルの日付）。本人ヒアリングは省略、埋まらない判断部は `[要確認: 〜]` で残す（前回踏襲できるものは「（前回踏襲）」付記）。
2. 週次報告フォルダ `1sqtIs-recvaCiibNXWvV7M6nex4ja8R4` に当週「週次報告_YYYY-MM-DD_片山」が既存なら**新規作成せず何もしない**（Slackに「既存Docあり・スキップ」）。冪等。
3. 完了通知：Slack DM(`U0B7FMCR8JU`)にDocリンク＋`[要確認]`一覧＋Slack貼付用の敬体要約ドラフト（要確認は伏せて骨子）。
4. 書込先はDoc新規作成のみ。スプレッドシート・メール送信・本人以外への投稿はしない。数値未確証は`(暫定)`、判断部は`[要確認]`。
5. §0フェイルセーフ：gog認証エラー時はDoc作らずSlackに「gog認証エラー」通知。

## TODO（完成に必要）
- [ ] `hawk-weekly-report`(SKILL 20) の本文をインライン展開（固定値・レポート構成・書式・絶対ルール）
- [ ] 必要なら `gdocs-hyperlink`(SKILL 2) のUTF-16リンク化手順をインライン
- [ ] 週次報告フォルダ・参照シートIDの最終確認
