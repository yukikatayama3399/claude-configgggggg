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

### 使い方の基本
**グローバルフラグはサブコマンドの「前」に置く**（`gog --account ... sheets get ...`）。
サブコマンドの後ろに置くと `unknown flag` になる。

- アカウント指定: `--account`（`-a`） … `gog --account yuki.katayama@fout.jp ...`
- JSON 出力: `-j` / TSV 出力: `-p`
- 変更せず意図だけ表示: `-n`（`--dry-run`）
- 確認プロンプトを出さない: `--no-input`（CI 用）／スキップする: `-y`（`--force`）

安全側に寄せたい時（v0.19.0 に `--readonly` フラグは**無い**ので注意）:
- `-n` … 書き込みコマンドを実行せず、やろうとした内容だけ出す
- `--gmail-no-send` … Gmail の送信をブロック
- `--disable-commands 'gmail.send,sheets.update'` … コマンド単位で禁止
- `--enable-commands '...'` … 許可したコマンドだけに制限

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

### 使える API / 使えない API（2026-07-29 実測）

| API | 状態 |
|---|---|
| Sheets | ✅ 読み書き可（`sheets update` → `sheets get` で往復確認） |
| Docs | ✅ 読み書き可（`docs write` → `docs cat` で往復確認） |
| Drive | ✅ 作成・一覧・検索・削除 可 |
| Gmail | ✅ 可（`gmail labels list`） |
| Calendar | ✅ 可（`calendar events --today`） |
| **Slides** | ❌ **不可** |

**Slides は OAuth プロジェクト側で Slides API が無効**なため、
`slides list-slides` / `raw` / `insert-text` / `replace-text` 等が全て
`Slides API is not enabled for this OAuth project` で失敗する。

紛らわしい点: `gog slides create` は **Drive API 経由**なので成功してしまう。
「空のスライドは作れるが中身を一切書けない」状態なので、
**Slides 本文生成タスクは gog では現状できない**と判断してよい。

有効化するには OAuth プロジェクト `317751427169` で Slides API を ON にする必要があるが、
このプロジェクトは yuki.katayama@fout.jp からは参照権限が無い
（`resourcemanager.projects.get` 権限なし）。
自分の GCP プロジェクトで OAuth クライアントを作り直して
`gog auth add <account> --services slides` で再認証するのが本筋。
