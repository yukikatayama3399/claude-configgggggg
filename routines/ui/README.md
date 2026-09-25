# UI で直す Routine（エージェントからは直せないもの）

エージェント（Claude のセッション）からは、(1) claude.ai の UI で作った Routine のプロンプトを編集できない、
(2) Routine にコネクタ（Slack / Gmail 等）を付けられない。以下はそのどちらかに当たるので、
https://claude.ai/code/routines で手作業が要る。各ファイルのプロンプトをそのまま貼ればよい。

| # | 対象 | 作業 |
|---|---|---|
| [01](01_competitor_watch.md) | 競合ウォッチ 朝のブリーフィング（既存を編集） | 既存 Routine のプロンプトを下で**置き換える**だけ（スケジュール・コネクタはそのまま）。 |
| [02](02_us_market.md) | 米国市場 朝の要約（既存を編集） | 既存 Routine のプロンプトを下で置き換える。 |
| [03](03_url_index.md) | hawk-url-index-original-refresh（既存を編集） | 既存 Routine のプロンプトを下で置き換える。 |
| [04](04_ai_news.md) | AI動向 朝のチェック（UI の旧 Routine を再利用） | 手順: UI の旧「AI動向 朝のチェック」（無効中・Slack 付き）を開き、プロンプトを下で置き換え、スケジュールを平日 8:00 JST（UTC `0 23 * * 0-4`）にして**有効化**。その後 trig_01BoGUEUUSEdBxSdwGWtgtbF を**無効化**。 |
| [05](05_kpi_thursday.md) | 木曜10am KPI活動集計（UI で新規作成） | 手順: UI で新規作成。環境 = Default、コネクタ = **Slack / Gmail / Google Calendar / Google Drive**、スケジュール = 毎週木曜 10:00 JST（UTC `0 1 * * 4`）、毎回新規セッション。作ったら旧 trig_01Jv858w24Mr3PfyNtAXZTmy を**無効化**。 |
| [06](06_form_reply_triage.md) | フォーム返信トリアージ（UI で新規作成） | 手順: UI で新規作成。環境 = Default、コネクタ = **Gmail / Slack**、スケジュール = 平日 9/12/15/18/21 時 JST（UTC `0 0,3,6,9,12 * * 1-5`）。作ったら旧 trig_01B1bSkB75BHLFGRAfCVb2bN を**無効化**（二重に走ると下書きが重複する）。 |
| [07](07_calendar_color_sweep.md) | カレンダー色分けスイープ（UI で新規作成・通知ハブから移設） | 手順: UI で新規作成。環境 = Default、コネクタ = **Slack**、スケジュール = 毎日 9:20 / 15:20 JST（UTC `20 0,6 * * *`）、毎回新規セッション。作ったら旧 trig_01DqE28d24nqRRGhA2LEhxjP を**無効化**。 |
| [08](08_hawk_digest.md) | HAWK提案ステータス 日次ダイジェスト（UI で新規作成・通知ハブから移設） | 手順: UI で新規作成。環境 = Default、コネクタ = **Slack**、スケジュール = 平日 9:30 JST（UTC `30 0 * * 1-5`）、毎回新規セッション。作ったら旧 trig_01NMn8xLGkG3kSU8eR3MfmZY を**無効化**。 |
