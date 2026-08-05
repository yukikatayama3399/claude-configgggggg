# claude-configgggggg

Claude Code から Google Workspace（Sheets / Docs / Slides / Drive / Gmail / Calendar）を
操作するための gog (gogcli) 設定リポジトリ。

運用ルールと使い方の詳細は **[CLAUDE.md](./CLAUDE.md)** を参照。

## スクリプト

| ファイル | 実行場所 | 用途 |
|---|---|---|
| `setup_gog_remote.sh` | クラウド | gog のインストールと認証復元。SessionStart フックが自動実行するので通常は手動実行不要 |
| `diagnose_gog.sh` | どこでも | **gog が使えない原因を切り分けて断定**（読み取り専用・いつでも安全） |
| `check_gog_apis.sh` | どこでも | 6 API の疎通を一括確認（**読み取り専用・いつでも安全**） |
| `sync_gog_token.sh` | **会社 Mac のみ** | 認証をやり直し、全環境へ配る値を書き出す |

### 調子が悪いときの一次切り分け

```bash
bash diagnose_gog.sh
```

原因を1つに絞って断定し、対処まで出す。**まずこれを実行すること。**

`check_gog_apis.sh` は「どの API が落ちているか」を見るためのもので、
**認証系の失敗を全部 `auth NG` に丸めてしまう**。これを「トークン失効」と
読むと誤診になる（実例は下記）。API の切り分けにだけ使う。

- `not enabled` が出た → OAuth プロジェクト側で該当 API が無効。CLAUDE.md の有効化手順へ

### ⚠️ 「トークン失効」と出ても、まず疑うのは失効ではない

2026-08-05、Mac のルーティンが毎朝「7/21 から `invalid_grant` で失効中」と
Slack に報告し続けていたが、**同じリフレッシュトークンがクラウドでは正常に動いていた**
（22 スコープ健在、Sheets / Gmail / Calendar 全て疎通）。誤報だった。

上流から順に潰すこと。上で引っかかったものが真因で、下は見なくていい。

1. **`GOG_KEYRING_PASSWORD` がその実行文脈に無い** ← 最頻。
   cron / launchd / エージェントから起動すると対話シェルの環境変数が
   引き継がれず落ちる。トークンは無傷。**再認証は不要。**
2. **keyring が開けない**（パスワード不一致・バックエンド違い）
3. **その端末にトークンが配られていない** … 失効ではない。import すれば済む
4. **本当に `invalid_grant`** … ここで初めて `--reauth` が正当化される

**復旧手順として `gog auth add` を案内しないこと。**
`--services` の既定が `user` なので、叩くと 22 スコープが最小構成に潰れる。

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

## 注意: 認証は会社 Mac でしかやらない

`gog auth add` を叩くのは**会社 Mac だけ**（2026-07-29 決定）。
家 Mac・クラウド・CI でバラバラに認証するとスコープが縮んで壊れる
（`--services` の既定値が `user` のため）。
詳細と理由は CLAUDE.md の「認証は『1台』でしかやらない」を参照。
