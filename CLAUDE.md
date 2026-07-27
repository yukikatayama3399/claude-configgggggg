# claude-configgggggg

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

### 複数アカウントを使う場合
`gog auth tokens export <email>` は1アカウント1ファイルなので、
2つ目以降は環境変数を接尾辞付きで足す（`GOG_TOKEN_EXPORT_B64_2`,
`GOG_TOKEN_EXPORT_B64_3`, …）。`setup_gog_remote.sh` が全部インポートする。

```bash
# Mac側: アカウント追加 → トークン書き出し → base64
gog auth add <email> --services gmail --gmail-scope full
gog auth tokens export <email> --out /tmp/gog_token.json
openssl base64 -A -in /tmp/gog_token.json | pbcopy && rm /tmp/gog_token.json
# → Claude Code web の環境変数 GOG_TOKEN_EXPORT_B64_2 に貼る → 新セッション開始
```

Mac で `keyring connection timed out` が出たら、キーチェーンの許可待ち。
`gog auth list` を実行してダイアログに「常に許可」を押してから再実行する。

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
