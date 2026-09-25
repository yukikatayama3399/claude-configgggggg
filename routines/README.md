# Routine（定期実行）の作法

2026-09-25 に全 Routine を棚卸しした結果、「成功（SUCCEEDED）」表示なのに実際には何もできていない
Routine が多数見つかった。原因はほぼ次の3つに集約される。

| 原因 | 症状 |
|---|---|
| **Routine のセッションにはリポジトリがクローンされない** | SessionStart フックが走らず gog/gws が入っていない。「リポジトリの〇〇.py を実行」「スキルを読む」が全部空振り |
| **エージェントが作った Routine にはコネクタ（Slack / Gmail 等）が付かない** | 「Slack DM で通知」「#ai-news に投稿」ができない。エージェントからは付けられない（この org では `create_trigger` の `connectors` が使えず、`update_trigger` にも無い）ので、UI で作り直す |
| **使うスクリプトが未マージのブランチにしか無い** | clone してもファイルが無い |

Routine の run 状態が SUCCEEDED なのは「セッションが起動した」という意味でしかない。
中身が成功したかは、書き込み先（シート・Doc・Slack）を見ないと分からない。

## 冒頭ブロック（gog/gws やリポジトリのファイルを使う Routine は必ず先頭に入れる）

````
# ステップ0（必須・最初に1回だけ）: リポジトリと gog/gws を用意する
この定期実行セッションにはリポジトリがクローンされておらず、SessionStart フックも走らない。
まず次をそのまま実行する（認証用の環境変数3つは環境側に設定済み。新規認証はしない）:

```bash
R="$HOME/claude-configgggggg"
[ -d "$R/.git" ] || git clone -q --depth 1 https://github.com/yukikatayama3399/claude-configgggggg "$R"
cd "$R"
[ -f routines/bootstrap.sh ] || { git fetch -q --depth 1 origin claude/clever-cannon-593o8s && git checkout -q FETCH_HEAD; }
bash routines/bootstrap.sh
```

以降の Bash 呼び出しは毎回、先頭に `source ~/.routine_env && cd "$REPO" && ` を付ける（シェルの状態は呼び出しごとに消える）。
最後に `[bootstrap] gog: NG` 等が出て失敗したら、Google への書き込みは一切せずエラー本文を報告して終了する。
````

- リポジトリは public なので認証なしで clone できる。
- `routines/bootstrap.sh` がまだデフォルトブランチに無い間は、作業ブランチから取ってくる。
  マージ後はこの分岐は何もしない。
- セッション途中で clone したスキルは Skill ツールに登録されない。
  **スキルは `Read` で `$REPO/.claude/skills/<名前>/SKILL.md` を直接読む**ように書く。
- Routine のセッションは GitHub への push 権限を持たない。「コミットしてプッシュ」は書かない
  （学習ログ等は報告に含めて、人が取り込む）。

## コネクタ

Slack / Gmail / Calendar / Drive のコネクタは **claude.ai の UI で作った Routine にしか付けられない**（2026-09-25 実測。
エージェントが作った Routine は `mcp_connections: []` になり、起動したセッションに mcp__Slack__* 等が無い）。
Slack に投稿する Routine は UI で作る。Google 系は gog/gws（冒頭ブロック）で代替できるのでコネクタ不要。

もう1つの制約: **UI で作った Routine のプロンプトはエージェントから編集できない**（`created_via: http_api`）。
UI 側で直す必要があるものは `routines/ui/` に貼り付け用のプロンプトを置いてある。

## 通知ハブ（永続セッションに束ねる方式）はやめる

「📮 Slack DM通知ハブ」のように 1 つの永続セッションへ複数 Routine を発火させる方式は、
コンテキストが膨らみ続け（2026-09-25 時点で 63 万トークン）、ターン中断で 9/12〜9/23 の間ほぼ全停止、
復旧後も通知が 2〜5 時間遅延した。**毎回新しいセッションを起こす方式にする。**
Slack 通知が要るものはコネクタを付けるために UI で作る（`routines/ui/07`・`08`）。
前回の状態が必要なものは、Slack DM の直近メッセージやシートから読み直す。

## 日付

cron は UTC。朝 8:30 JST の発火は UTC ではまだ前日なので、`date` をそのまま使うと日付が1日ずれる。
日付は必ず `TZ=Asia/Tokyo date +%Y/%m/%d` で取る。
