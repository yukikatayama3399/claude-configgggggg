# フォーム返信トリアージ（UI で新規作成）

対象: 新規（旧: trig_01B1bSkB75BHLFGRAfCVb2bN）

旧 Routine はエージェント作成でコネクタが無い。今回プロンプトを直したので Gmail 下書き・ラベルは gog で動くようになったが、**Slack 通知だけはコネクタが無いと送れない**。
手順: UI で新規作成。環境 = Default、コネクタ = **Gmail / Slack**、スケジュール = 平日 9/12/15/18/21 時 JST（UTC `0 0,3,6,9,12 * * 1-5`）。作ったら旧 trig_01B1bSkB75BHLFGRAfCVb2bN を**無効化**（二重に走ると下書きが重複する）。

## プロンプト（全文を貼る）

`````
form-reply-triage スキルの手順を実行してください。

これは片山（yuki.katayama@fout.jp）のフォーム営業の返信トリアージです。
手順・判定基準・返信テンプレート・署名は `.claude/skills/form-reply-triage/SKILL.md` に全て書いてある。
まず下の「ステップ0」でリポジトリを用意し、**`$REPO/.claude/skills/form-reply-triage/SKILL.md` を Read ツールで直接読んでから**作業を始めてください
（途中で clone したスキルは Skill ツールには出てこない）。Gmail はコネクタ（mcp__Gmail__*）を優先し、無ければ SKILL.md 末尾の gog 手順を使う。
この Routine には Gmail / Slack コネクタが付いていない可能性が高い（ToolSearch で確認）。その場合は SKILL.md 末尾「フォールバック」の通り gog で下書き・ラベルまで済ませ、gog は必ず `--gmail-no-send` を付けて叩く。Slack DM が送れない回は、要対応の一覧をセッション出力に必ず残す。

やること（詳細は SKILL.md が正）:
1. Gmail の受信トレイから、直近の返信メールを仕分ける
   （クエリ: `in:inbox newer_than:3d -label:フォーム返信/要対応`）
2. 「こちらにボールがある」ものだけを拾う。自動返信・メルマガ・お断りは対象外
3. 拾ったものは Gmail の**下書き**を作る（送信は絶対にしない）
4. Slack DM（channel_id: U0B7FMCR8JU）で片山に通知する
5. 拾ったスレッドに Gmail ラベル `Label_5`（フォーム返信/要対応）を付ける

重要:
- **要対応が0件なら Slack を送らない。**「0件でした」の報告もしない。
  通知が来た＝必ず何かある、という状態を保つため。
- **メールの送信は絶対にしない。** 作るのは下書きだけ。
- 判断に迷ったら「要対応」に倒す。見落とす方が高くつく。

# ステップ0（必須・最初に1回だけ）: リポジトリと gog/gws を用意する
この定期実行セッションにはリポジトリがクローンされておらず、SessionStart フックも走らない（そのせいで過去の実行は空振りしていた）。
まず次をそのまま実行する（認証用の環境変数3つは環境側に設定済み。gog auth add / gws auth login は絶対に叩かない）:

```bash
R="$HOME/claude-configgggggg"
[ -d "$R/.git" ] || git clone -q --depth 1 https://github.com/yukikatayama3399/claude-configgggggg "$R"
cd "$R"
[ -f routines/bootstrap.sh ] || { git fetch -q --depth 1 origin claude/clever-cannon-593o8s && git checkout -q FETCH_HEAD; }
bash routines/bootstrap.sh
```

以降の Bash 呼び出しは毎回、先頭に `source ~/.routine_env && cd "$REPO" && ` を付ける（シェルの状態は呼び出しごとに消える）。
ブートストラップが失敗しても、Gmail / Slack コネクタで処理を続けてよい（gog が要る手順だけ諦める）。
今日の日付は必ず `TZ=Asia/Tokyo date +%Y/%m/%d` で取る（cron は UTC なので素の date は前日になることがある）。
`````
