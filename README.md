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
| `setup_gws_remote.sh` | クラウド | gws のインストールと認証生成。SessionStart フックが自動実行 |
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
セッション開始時に `setup_gog_remote.sh` と `setup_gws_remote.sh` を実行するため、
**手動実行は不要**。手動でやるなら:

```bash
bash setup_gog_remote.sh
bash setup_gws_remote.sh
```

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
`~/.config/gws/credentials.json` に置く。つまり:

- クラウドで `gws auth login` を叩く必要はない（叩いてはいけない）
- gog と同じ 22 スコープをそのまま使う
- トークンが失効したら直すのは 1 箇所。「正」の Mac で `bash sync_gog_token.sh --reauth`

環境変数 `GWS_CREDENTIALS_B64` が設定されている場合はそちらを優先する。
会社 Mac で `gws auth export --unmasked` した結果を base64 で配れば、
gog とは独立した認証に切り替えられる（通常は不要）。

### バージョン

`setup_gws_remote.sh` の `GWS_VERSION` で固定している。上げるときはこの1箇所。
（gog と違い npm 経由で取るので、リポジトリにバイナリは同梱していない）

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
