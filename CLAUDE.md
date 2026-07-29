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

### 認証は「1台」でしかやらない（重要な運用ルール）

`gog auth add` を叩く端末を**1台に固定**する（=「正」の端末）。
他の端末・クラウド・CI では**絶対に `gog auth add` を叩かない**。
必ず「正」の端末で `bash sync_gog_token.sh` を実行し、出力された3値を配る。

```bash
# 「正」の Mac でだけ実行
bash sync_gog_token.sh            # 既存トークンを書き出すだけ（安全）
bash sync_gog_token.sh --reauth   # 認証をやり直してから書き出す
```

配る先は2箇所あり、**別物なので両方更新が必要**:
1. Claude Code on the web の環境変数（クラウドセッション用）
2. GitHub Secrets（Actions を使う場合。`--gh-secrets` で自動 push 可）

バラバラに認証すると壊れる理由:
- **スコープが縮む**: `gog auth add` の `--services` の既定値は `user` なので、
  指定を忘れると 22 個あるスコープが最小構成に上書きされる。
  `sync_gog_token.sh` は現在のスコープ一覧を明示的に渡してこれを防いでいる。
- **gog のバージョン差**: ローカルとクラウドで版が違うとトークン形式が合わず
  import が壊れる。`sync_gog_token.sh` は
  `setup_gog_remote.sh` の `GOG_VERSION` と一致しない場合は中断する。
- **keyring パスワード不一致**: `GOG_KEYRING_PASSWORD` は全環境で同一必須。

なお「再認証すると他端末のトークンが即失効する」わけではない。
リフレッシュトークンは同一クライアント×同一アカウントで個数上限があり
（100個程度）、端末が数台なら共存する。
本当のリスクは上記のスコープ縮小とバージョン差。

※ Cloud Console の「OAuth ユーザー数の上限 100」は**別の指標**。
　 あれは未承認の機微スコープで同意できる**ユーザー数**の上限であって、
　 リフレッシュトークンの個数上限とは無関係。混同しないこと。

### 使い方の基本
**グローバルフラグはサブコマンドの「前」に置く**（`gog --account ... sheets get ...`）。
サブコマンドの後ろに置くと `unknown flag` になる。

- アカウント指定: `--account`（`-a`） … `gog --account yuki.katayama@fout.jp ...`
- JSON 出力: `-j` / TSV 出力: `-p`
- 変更せず意図だけ表示: `-n`（`--dry-run`）
- 確認プロンプトを出さない: `--no-input`（CI 用）／スキップする: `-y`（`--force`）

`--readonly` の注意点:
- **コマンド実行時のグローバルフラグとしては存在しない。**
  `gog --readonly calendar events` / `gog calendar events --readonly` は
  どちらも `unknown flag --readonly` になる。
- 存在するのは `gog auth add --readonly`（=認可の時点で読み取り専用スコープを取る）だけ。
  既に書き込みスコープで認証済みのトークンを、実行時に読み取り専用へ落とす用途には使えない。

実行時に安全側へ寄せたい時は代わりにこれを使う:
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
