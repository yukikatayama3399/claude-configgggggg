# sns-event-radar / LEARNINGS

実行して分かったことを追記していく。★印は SKILL 本体へ昇格させる候補。

- 2026-08-05(セットアップ時): 当初は Claude Code on the web の Routine 機能で組もうとしたが断念。
  (1) `create_trigger` の `connectors` がこの組織で無効で、コネクタ無しの発火セッションは
  `mcp__Slack__*` を持たず DM を送れない（テスト発火して無反応を確認）。
  (2) `update_trigger` の `model` が `model_update_disabled` で拒否され安いモデルに落とせない。
  (3) クラウド環境は egress ポリシーで一般 Web ホストが全面 403（`example.com` すら不可、
  `curl` も `WebFetch` も同様）。`hooks.slack.com` も塞がれており Webhook 迂回も不可。
  → Mac ローカル cron 方式へ移行。Mac にはこの制約が無いので、一覧ページを
  `WebFetch` で直接読む設計に戻せた。

- 2026-08-05: `gog sheets append` に値を**位置引数で並べると全部1セルに連結される**。
  `--values-json` で2次元配列を渡すのが正しい。複数件も1回で入る。

- 2026-08-05: `gog sheets get` の range は位置引数（`gog sheets get <id> "A1:B3"`）。
  タブ名を省略すると先頭シートが対象になる。台帳はシート名がファイル名と同じで
  範囲指定に書きにくいので、タブ名を省いた `"A2:I"` 形式で読んでいる。

- 2026-08-05: WebSearch は**クエリに年月を入れないと過去のイベントばかり返る**。
  `"2026年8月" ...` のように明示すると、ホットリンクやコムニコの実在する
  日付付きセミナーが拾えた。

- 2026-08-07: 初回セットアップ時、ベタ置きの `sns-event-radar.md` を
  `~/.claude/scheduled-tasks/` に置く手順を案内したが、**他のルーティンは全て
  `<名前>/SKILL.md` のディレクトリ形式**だった（ベタ置きは
  `cowork-write-queue-sweep.md` の1つだけ）。形式違いで登録されず、
  2日間で発火ゼロだった。★新規ルーティンは必ずディレクトリ形式で作る。

- 2026-08-07: `--account` の付け忘れは `403 forbidden: The caller does not have permission`
  になる。会社 Mac には fout.jp（22スコープ）と個人 gmail（gmail スコープのみ）の
  2アカウントが登録されており、`--account` 無しだと後者で実行される。
  **これを「トークン失効」と誤診すると 17 日間の誤報になる**（実際に他ルーティンで発生）。
  切り分けは `bash ~/claude-configgggggg/diagnose_gog.sh`。
  `gog auth add` は絶対に叩かない（`--services` 既定が `user` でスコープが潰れる）。
