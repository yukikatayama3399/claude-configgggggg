# claude-configgggggg

Claude Code から Google Workspace（Sheets / Docs / Slides / Drive / Gmail / Calendar）を
操作するための gog (gogcli) 設定リポジトリ。

運用ルールと使い方の詳細は **[CLAUDE.md](./CLAUDE.md)** を参照。

## スクリプト

| ファイル | 実行場所 | 用途 |
|---|---|---|
| `setup_gog_remote.sh` | クラウド | gog のインストールと認証復元。SessionStart フックが自動実行するので通常は手動実行不要 |
| `check_gog_apis.sh` | どこでも | 6 API の疎通を一括確認（**読み取り専用・いつでも安全**） |
| `sync_gog_token.sh` | 「正」の Mac のみ | 認証をやり直し、全環境へ配る値を書き出す |

### 調子が悪いときの一次切り分け

```bash
bash check_gog_apis.sh
```

- `not enabled` が出た → OAuth プロジェクト側で該当 API が無効。CLAUDE.md の有効化手順へ
- `auth` が NG → トークン失効。「正」の Mac で `bash sync_gog_token.sh --reauth`

## クラウドセッションでの自動セットアップ

`.claude/hooks/session-start.sh`（SessionStart フック）が
セッション開始時に `setup_gog_remote.sh` を実行するため、**手動実行は不要**。
手動でやるなら:

```bash
bash setup_gog_remote.sh
```

前提として、以下3つの環境変数がセッションに登録済みであること:

- `GOG_CREDENTIALS_B64` … credentials.json (client_id) の base64
- `GOG_TOKEN_EXPORT_B64` … `gog auth tokens export` 出力の base64
- `GOG_KEYRING_PASSWORD` … 暗号化ファイル keyring のパスワード（**全環境で同一の値**）

これらの値は `sync_gog_token.sh` が生成する。

## gog バイナリ

`bin/gogcli_0.19.0_linux_amd64.tar.gz` を同梱しているので、
gog バイナリのダウンロードは不要（未インストール時はこの同梱 tarball を使う）。

バージョンを上げるときは**3箇所すべてを同時に**揃えること。ズレるとトークンの
import が壊れる:

1. この tarball
2. `setup_gog_remote.sh` の `GOG_VERSION`
3. `sync_gog_token.sh` の `GOG_VERSION_EXPECTED`

## 注意: 認証は1台でしかやらない

`gog auth add` を叩く端末は1台に固定する。複数端末でバラバラに認証すると
スコープが縮んで壊れる（`--services` の既定値が `user` のため）。
詳細と理由は CLAUDE.md の「認証は『1台』でしかやらない」を参照。
