# claude-configgggggg

## Google Docs では表（テーブル）を一切使わない

Google Docs を作成・更新するときは、**表を絶対に使わない**こと。
Docs 上では表が読みづらく、markdown インポート時にセル内の装飾（`**太字**` 等）が
エスケープされて崩れるため。

代わりに使う書き方:
- 見出し（`##` / `###`）で章立てする
- 「項目： 値」形式の**箇条書き**にする
- 補足はネストした箇条書きにする
- 比較（A案 vs B案）は**表にせず、対象ごとに見出しを立てて箇条書き**で並べる
- URL は箇条書きの中で `名前 → URL` の形で書く

この方針は既存Docsの書き換え時にも、今後の新規Docs作成時にも常に適用する。
Sheets（スプレッドシート）は当然表でよい。対象は Docs のみ。

## Google Workspace 操作は gog を最優先で使う

Google Sheets / Docs / Calendar / Gmail / Drive などの Google Workspace 操作は、
**原則 gog (gogcli) を最優先で使う**こと。

理由:
- MCP の Google 連携（Google Drive コネクタ等）は読み取り中心で、
  Sheets のセル書き込みや Docs 本文書き込みのツールが無い。**書き込みが絡むタスクは gog を使う。**
- gog はスコープに sheets / docs / drive(full) 等を保有しており、
  Drive 権限があれば他人所有ファイルにも読み書きできる（検証済み）。

### セットアップ
- クラウド(web)セッションでは SessionStart フック
  (`.claude/hooks/session-start.sh`) が開始時に自動セットアップする。
- 手動で使う場合: `bash setup_gog_remote.sh`

### 使い方の基本
- アカウント指定: `--account yuki.katayama@fout.jp`
- 読み取り専用にしたい時: `--readonly`
- JSON 出力: `-j`

### よく使う例
```bash
# Sheets 読み
gog --account yuki.katayama@fout.jp sheets get <ID> "<タブ名>!A1:C3"
# Sheets 書き
gog --account yuki.katayama@fout.jp sheets update <ID> "<タブ名>!W1633" "値"
# Docs 読み
gog --account yuki.katayama@fout.jp docs cat <docId>
# Docs 書き
gog --account yuki.katayama@fout.jp docs write <docId> --text "本文"
```
