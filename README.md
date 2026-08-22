# claude-configgggggg

Claude Code から Google Workspace（Sheets / Docs / Slides / Drive / Gmail / Calendar）を
操作するための CLI 設定リポジトリ。2つの CLI が入っている。

| CLI | 実体 | 位置づけ |
|---|---|---|
| `gog` | [gogcli](https://github.com/openclaw/gogcli) | **既定**。運用手順・スキルがこちら前提で書かれている |
| `gws` | [Google 公式 Google Workspace CLI](https://github.com/googleworkspace/cli) | 追加導入。Discovery 由来で全 API を叩けるので gog に無いメソッド用 |

**認証は 1 つだけ。** `gws` は `gog` の refresh token を流用するので、
gws のために新しく OAuth 認証を取る必要はない（詳細は下記）。

運用ルールと使い方の詳細は **[CLAUDE.md](./CLAUDE.md)** を参照。

## スクリプト

| ファイル | 実行場所 | 用途 |
|---|---|---|
| `setup_gog_remote.sh` | クラウド | gog のインストールと認証復元。SessionStart フックが自動実行するので通常は手動実行不要 |
| `check_gog_apis.sh` | どこでも | gog で 6 API の疎通を一括確認（**読み取り専用・いつでも安全**） |
| `setup_gws_remote.sh` | クラウド / Mac | gws のインストールと認証生成（gog のトークンを流用） |
| `gws_credentials_from_gog.py` | — | 上記から呼ばれる。gog のトークンを gws 形式に組み直す |
| `check_gws_apis.sh` | どこでも | gws で 6 API の疎通を一括確認（**読み取り専用・いつでも安全**） |
| `sync_gog_token.sh` | **会社 Mac のみ** | 認証をやり直し、全環境へ配る値を書き出す |

### 調子が悪いときの一次切り分け

```bash
bash check_gog_apis.sh   # gog 側
bash check_gws_apis.sh   # gws 側
```

- `not enabled` が出た → OAuth プロジェクト側で該当 API が無効。CLAUDE.md の有効化手順へ
- `auth` が NG → トークン失効。「正」の Mac で `bash sync_gog_token.sh --reauth`
  （gws も同じトークンを使うので、直せば両方直る）

## クラウドセッションでの自動セットアップ

`.claude/hooks/session-start.sh`（SessionStart フック）が
セッション開始時に `setup_gog_remote.sh` を実行するため、**gog は手動実行不要**。

**gws はまだフックに入っていない**ので、使う前に一度だけ叩く:

```bash
bash setup_gws_remote.sh
```

フックにも入れたい場合は下記「gws をフックに組み込む」を参照。

### Mac で使う場合

**リポジトリのクローン内で**実行すること（`~` で叩いても見つからない）。
Mac には `GOG_*_B64` 環境変数が無いので、スクリプトは
ローカルの gog から直接トークンをもらう（`gog auth tokens export`）。

```bash
cd path/to/claude-configgggggg
bash setup_gws_remote.sh
bash check_gws_apis.sh
```

会社 Mac には gog のアカウントが 2 つ（`@fout.jp` と `@gmail.com`）入っているため、
スクリプトは**アカウントを指定して**トークンを取り出す。既定は `@fout.jp`。
別アカウントで作るなら:

```bash
GWS_ACCOUNT=yuki.katayama3399@gmail.com bash setup_gws_remote.sh
```

#### client_secret の在り処に注意

gog は **client_secret を keyring に退避する**ことがある
（`gog auth credentials list` の `SECRET_KEYRING` が `true` の状態）。
この場合 gog 管理下の `credentials.json` には secret が入っていないので、
スクリプトは `gog auth tokens export` の出力側にある client 情報を使う。
`client_id` と `client_secret` は**同じファイルから対で**取る
（別プロジェクトの id と secret を混ぜないため）。

候補は次の順に見る:

1. `GWS_CLIENT_SECRET_JSON`（明示指定）
2. `~/.gog_sync/gog_env_*.env` の `GOG_CREDENTIALS_B64`（新しい順）
   … `sync_gog_token.sh` が過去に書き出した値。gog が keyring へ退避する前の
   secret が残っていることがあるので、**Mac ではこれが本命**
3. gog 管理下の `credentials.json`
4. token export

全部に secret が無いと止まる。その場合は Cloud Console
（**@gmail.com でログイン**、プロジェクト `317751427169`）の「認証情報」から
OAuth クライアント（Desktop app）の JSON をダウンロードして渡す:

```bash
# ローカル実行時: 落としたファイルの実際のパスを渡す
GWS_CLIENT_SECRET_JSON=<落としたJSONのパス> bash setup_gws_remote.sh

# クラウド用: base64 にしてセッション環境変数に入れておけば恒久的に効く
openssl base64 -A -in <落としたJSONのパス>   # → GWS_CLIENT_SECRET_JSON_B64 に設定
```

`GWS_CLIENT_SECRET_JSON_B64` を環境変数に入れておけば、
gog 側の配布値に secret が無くてもクラウドで gws が動く。

（macOS の keychain から secret を読む経路は実装していない。
Claude Code の権限ガードに引っかかるうえ、キーチェーンの許可プロンプトと
サービス名の当て推量に依存して壊れやすいので採らなかった。）

前提として、以下3つの環境変数がセッションに登録済みであること:

- `GOG_CREDENTIALS_B64` … credentials.json (client_id) の base64
- `GOG_TOKEN_EXPORT_B64` … `gog auth tokens export` 出力の base64
- `GOG_KEYRING_PASSWORD` … 暗号化ファイル keyring のパスワード（**全環境で同一の値**）

これらの値は `sync_gog_token.sh` が生成する。

## gws (Google Workspace CLI)

Google 公式の CLI。`npm i -g @googleworkspace/cli` で入る Rust 製バイナリで、
Google Discovery Service を実行時に読んでコマンドを組み立てるため、
Workspace の API メソッドはひと通り叩ける。

```bash
gws drive files list --params '{"pageSize":10}'
gws sheets spreadsheets values get --params '{"spreadsheetId":"<ID>","range":"Sheet1!A1:C3"}'
gws gmail users labels list --params '{"userId":"me"}'
gws schema drive.files.list          # 引数と戻り値のスキーマを見る
gws --help                           # サービス一覧
```

### 認証（新規に取らない）

`setup_gws_remote.sh` は **gog の refresh token を authorized_user 形式に組み直して**
`~/.config/gws/credentials.json` に置く（実際の組み立ては `gws_credentials_from_gog.py`）。
入手元は上から順に、`GWS_CREDENTIALS_B64` → `GOG_*_B64` 環境変数 → ローカルの gog。
つまり:

- クラウドで `gws auth login` を叩く必要はない（叩いてはいけない）
- gog と同じ 22 スコープをそのまま使う
- トークンが失効したら直すのは 1 箇所。「正」の Mac で `bash sync_gog_token.sh --reauth`

環境変数 `GWS_CREDENTIALS_B64` が設定されている場合はそちらを優先する。
会社 Mac で `gws auth export --unmasked` した結果を base64 で配れば、
gog とは独立した認証に切り替えられる（通常は不要）。

### バージョン

`setup_gws_remote.sh` の `GWS_VERSION` で固定している。上げるときはこの1箇所。
（gog と違い npm 経由で取るので、リポジトリにバイナリは同梱していない）

### gws をフックに組み込む

毎セッション自動で入れたいなら `.claude/hooks/session-start.sh` の
「PATH を通す」ブロックの手前に以下を足し、PATH 行を差し替える。
（`hooks/session-start-gws.patch` に同じ差分を置いてある: `git apply hooks/session-start-gws.patch`）

```bash
# gws セットアップ(冪等)。gog と同じく失敗してもセッションはブロックしない。
if bash "$CLAUDE_PROJECT_DIR/setup_gws_remote.sh"; then
  echo "[session-start] gws setup: OK"
else
  echo "[session-start] gws setup: FAILED (setup_gws_remote.sh を手動実行してエラー確認を)" >&2
fi
```

```bash
# PATH 行の差し替え(gws は $HOME/.local/bin に入る)
echo 'export PATH="$HOME/bin:$HOME/.local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
echo 'export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE="$HOME/.config/gws/credentials.json"' >> "$CLAUDE_ENV_FILE"
```

なお `$HOME/.local/bin` は既定で PATH に入っている環境が多く、
その場合 PATH 行を触らなくても `gws` は見つかる。

### 権限ルール（任意）

セットアップ/疎通確認スクリプトは認証系の環境変数に触るため、
auto モードの分類器に止められることがある。毎回止められるのが煩わしければ
`.claude/settings.json` に足しておく:

```json
"permissions": {
  "allow": [
    "Bash(bash setup_gog_remote.sh:*)",
    "Bash(bash check_gog_apis.sh:*)",
    "Bash(bash setup_gws_remote.sh:*)",
    "Bash(bash check_gws_apis.sh:*)"
  ]
}
```

## gog バイナリ

`bin/gogcli_0.19.0_linux_amd64.tar.gz` を同梱しているので、
gog バイナリのダウンロードは不要（未インストール時はこの同梱 tarball を使う）。

バージョンを上げるときは**3箇所すべてを同時に**揃えること。ズレるとトークンの
import が壊れる:

1. この tarball
2. `setup_gog_remote.sh` の `GOG_VERSION`
3. `sync_gog_token.sh` の `GOG_VERSION_EXPECTED`

## 注意: 認証は会社 Mac でしかやらない

`gog auth add` を叩くのは**会社 Mac だけ**（2026-07-29 決定）。
家 Mac・クラウド・CI でバラバラに認証するとスコープが縮んで壊れる
（`--services` の既定値が `user` のため）。
詳細と理由は CLAUDE.md の「認証は『1台』でしかやらない」を参照。
