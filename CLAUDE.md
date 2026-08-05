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

**「正」の端末 = 会社 Mac**（2026-07-29 決定）。

`gog auth add` を叩くのは会社 Mac だけ。
**家 Mac・クラウド・CI では絶対に `gog auth add` を叩かない。**
必ず会社 Mac で `bash sync_gog_token.sh` を実行し、出力された3値を配る。

家 Mac で gog を使いたい場合も、認証はせず
会社 Mac が出した3値を環境変数として渡す（クラウドと同じ扱いにする）。

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

### 「gog トークン失効」を報告・診断するときの鉄則

**`gog auth add` を復旧手順として案内してはいけない。**
`--services` の既定値が `user` なので、案内どおり叩かれると 22 スコープが
最小構成に潰れる。正しい復旧は `sync_gog_token.sh` 経由だけ。

**認証系の失敗を一括で「トークン失効」と結論してはいけない。**
2026-08-05、Mac のルーティンが毎朝「7/21 から `invalid_grant` で失効中」と
Slack に誤報し続けていた一方で、同じリフレッシュトークンがクラウドでは
正常動作していた（22 スコープ健在、Sheets / Gmail / Calendar 全て疎通、
トークン保存日時 2026-07-13）。`check_gog_apis.sh` が認証系の失敗を全部
`auth NG` に丸める作りだったことが誤診の元。

切り分けは `bash diagnose_gog.sh` を使う。上流から順に潰し、
最初に引っかかったものが真因:

1. **`GOG_KEYRING_PASSWORD` がその実行文脈に無い** ← 最頻。
   cron / launchd / エージェント起動だと対話シェルの環境変数が引き継がれない。
   トークンは無傷なので**再認証は不要**
2. **keyring が開けない**（パスワード不一致・バックエンド違い）
3. **その端末にトークンが配られていない** … 失効ではなく import で解決
4. **本当に `invalid_grant`** … ここで初めて `--reauth` が正当化される

自動レポートを書くときは、4 に到達したときだけ「失効」と言うこと。

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
| Slides | ✅ 読み書き可（下記の注意点あり） |

### Slides の使い方（2026-07-29 に API 有効化して疎通確認済み）

`slides create` 直後のスライドには、**空のプレースホルダ2個**が入っている:
`i0` = タイトル、`i1` = サブタイトル。ここに `insert-text` で流し込む。

注意: **`read-slide` は空のプレースホルダを表示しない**ので、
「要素が無い」と誤解しやすい。objectId を確実に知るには `slides raw` を見る。

```bash
PID=<presentationId>
gog --account ... slides create "タイトル"          # 作成
gog --account ... slides raw "$PID"                 # objectId を確認(空要素も見える)
gog --account ... slides list-slides "$PID"         # スライド一覧
gog --account ... slides insert-text "$PID" i0 "見出し"
gog --account ... slides replace-text "$PID" "旧" "新"
gog --account ... slides read-slide "$PID" p        # 読み返し
```

#### スピーカーノート（既知バグと回避策）

**`slides update-notes` はノートが空のスライドで必ず失敗する。**
既存ノートを消す処理が先に走り、空(長さ0)に対して削除範囲 0〜0 を投げるため
`Invalid requests[0].deleteText: The startIndex 0 must be less than the endIndex 0`
になる。一度ノートが入っていれば `update-notes` は正常に動く（検証済み）。

**回避策: ノート図形の objectId を直接 `insert-text` で埋める。**

```bash
# 1) speakerNotesObjectId を取得（通常 i3 だが必ず raw で確認する）
gog --account ... slides raw "$PID" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['slides'][0]['slideProperties']['notesPage']['notesProperties']['speakerNotesObjectId'])"

# 2) その objectId に insert-text（update-notes ではなく insert-text を使う）
gog --account ... slides insert-text "$PID" i3 "ノート本文"

# 3) 以降は update-notes でも上書きできる
gog --account ... slides update-notes "$PID" p --notes "差し替え後のノート"
```

つまり**初回だけ `insert-text`、2回目以降は `update-notes`** でよい。
一律 `insert-text` で書くのが単純で安全。

フラグ名注意: ノート本文は `--notes` / `--notes-file`。`--text` は `unknown flag`。

前提: この疎通には OAuth プロジェクト側で Slides API が有効である必要がある。
無効だと `slides list-slides` / `raw` / `insert-text` / `replace-text` が全て
`Slides API is not enabled for this OAuth project` で落ちる。
紛らわしいのは **`slides create` は Drive API 経由なので無効でも成功する**点で、
「空のスライドは作れるが中身を書けない」状態になる。
再度この症状が出たら API 有効化を疑う（手順は下記）。

### API を有効化する手順（Slides は 2026-07-29 に実施済み）

API を追加で有効化したくなったら、OAuth プロジェクト `317751427169` で ON にする。
**このプロジェクトは @gmail.com 個人アカウント所有**（プロジェクト名 `My First Project`）
なので、Cloud Console には **@gmail.com でログインして**作業する。
@fout.jp では `resourcemanager.projects.get` が拒否されて画面すら開けない（実測済み）。

```
https://console.cloud.google.com/apis/api/slides.googleapis.com/overview?project=317751427169
```

API 有効化はプロジェクト側の設定なので、対象スコープを既にトークンが持っていれば
**有効化後は再認証も環境変数の更新も不要**。リトライすれば通る。
Slides でこれを実証済み（有効化しただけで、既存トークンのまま書き込みが成功した）。
付与済みスコープは `gog auth list` で確認できる（現在 22 個）。

### OAuth 設定の構造（触ると壊れる箇所）

| 項目 | 現在の値 | 触ってよいか |
|---|---|---|
| プロジェクト所有者 | **@gmail.com 個人アカウント** | — |
| 実際に使うアカウント | **@fout.jp**（外部ユーザーとして同意） | — |
| 公開ステータス | **本番環境** | ❌ 変えない |
| ユーザーの種類 | **外部** | ❌ 変えない |

Cloud Console の「対象」画面にある2つのボタンは**どちらも押してはいけない**:

- **「テストに戻る」** … 押すとテスト中に戻り、
  リフレッシュトークンの寿命が **7日** に戻って毎週切れるようになる。
  現在は本番環境なのでこの問題は起きていない（トークンが16日以上生存を実測）。
- **「内部に公開」** … 押すと同意できるユーザーが
  「プロジェクト所有組織の内部ユーザー」に限定される。
  所有者は個人 @gmail.com で組織を持たないため、
  **外部ユーザーである @fout.jp が同意できなくなり全機能が停止する。**
  「内部の方が安全そう」に見えるが、この構成では逆に壊れる。

なお「未確認のアプリ」警告が同意時に出るのは、機微スコープが未審査のまま
本番公開されているため。自分だけで使う分には支障はない。

構造的な留意点: @fout.jp の Gmail / Drive のデータを、
**個人所有の OAuth クライアント経由で扱っている**状態。
会社の情シスポリシー次第では問題になり得るし、
fout.jp 側でサードパーティアプリのアクセスが制限されると一斉に止まる。
恒久運用するなら会社側プロジェクトへの移設を検討する余地がある。
