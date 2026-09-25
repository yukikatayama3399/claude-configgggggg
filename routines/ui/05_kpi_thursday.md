# 木曜10am KPI活動集計（UI で新規作成）

対象: 新規（旧: trig_01Jv858w24Mr3PfyNtAXZTmy）

9/24 の回を含め、集計 DM が届いていない。旧 Routine はコネクタ無しの永続セッションに紐づいていて Slack に投稿できない。
手順: UI で新規作成。環境 = Default、コネクタ = **Slack / Gmail / Google Calendar / Google Drive**、スケジュール = 毎週木曜 10:00 JST（UTC `0 1 * * 4`）、毎回新規セッション。作ったら旧 trig_01Jv858w24Mr3PfyNtAXZTmy を**無効化**。

## プロンプト（全文を貼る）

`````
【木曜10amルーティン】今週分の活動集計と共有をしてください。KPIシート等のGoogle 3ファイル（週次KPI 1KbOQ…／週次Doc 1I7u2…／activity 1S5EB…）には書き込まない。読むのは下の「準備」で入れる gog で可（読み取りのみ）。数値は必ず Slack DM（自分宛＝ユーザー本人 U0B7FMCR8JU）に投稿する。メールは送らない。

1. 片山（yuki.katayama@fout.jp）の今週（月〜木）の活動を Gmail・カレンダーから集計し、KPI表フォーマットにマップする：
   - 初回接触＞コールドリスト(info@)：一括送信分。個人Gmail送信箱には出ないので、送信ログ／シート「ウェビナー_新規」ベース。数値が取れなければ「要確定」と明記。
   - 初回接触＞休眠・インバウンド／紹介：先方起点の返信・問い合わせ、紹介経由の接触。
   - 商談・デモ実施＞コールドリスト／休眠・インバウンド／紹介：カレンダーの [社外] HAWK商談・デモ予定を数え、流入経路（問い合わせフォーム＝インバウンド、紹介者同席＝紹介 等）で分類。不明は「要判断」とし、根拠（相手・日付・流入経路）を添える。社内予定は除外。
2. 集計結果を Slack DM（U0B7FMCR8JU）に、KPI表の片山ぶん（今週列）としてそのまま手入力できる形で投稿する。内訳分類の最終判断は片山さんに委ねる注記を付ける。
3. あわせて、今週の商談議事録・メールから出た機能要望／質問／不満を、同じ DM の末尾に「▼今週の顧客要望・質問・不満」として箇条書きで添える（社名・日付・出典付き。出典の無いものは書かない）。
   （以前は `顧客要望_機能リクエスト_トラッカー.md` への起票とリポジトリへのコミット＆プッシュだったが、定期実行セッションには push 権限もリポジトリも無く毎回失敗していたため廃止）

これは無人の定期実行。質問で止まらず、読める範囲で自動集計して DM を1通送って終わる。

# 準備（最初に1回だけ）: リポジトリと gog/gws を用意する
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
準備が失敗したら、コネクタ（Gmail / Calendar）だけで集計を続け、DM に「gog準備失敗」と1行添える。
今日の日付は必ず `TZ=Asia/Tokyo date +%Y/%m/%d` で取る（cron は UTC なので素の date は前日になることがある）。
`````
