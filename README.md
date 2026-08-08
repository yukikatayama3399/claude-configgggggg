# claude-configgggggg

Claude Code から Google Workspace（Sheets / Docs / Slides / Drive / Gmail / Calendar）を
操作するための gog (gogcli) 設定リポジトリ。

運用ルールと使い方の詳細は **[CLAUDE.md](./CLAUDE.md)** を参照。

## スクリプト

| ファイル | 実行場所 | 用途 |
|---|---|---|
| `setup_gog_remote.sh` | クラウド | gog のインストールと認証復元。SessionStart フックが自動実行するので通常は手動実行不要 |
| `check_gog_apis.sh` | どこでも | 6 API の疎通を一括確認（**読み取り専用・いつでも安全**） |
| `sync_gog_token.sh` | **会社 Mac のみ** | 認証をやり直し、全環境へ配る値を書き出す |
| `diagnose_mac_slow.sh` | **Mac のみ** | Mac が重いときの Claude 起因切り分け（既定は**読み取り専用**、`--fix` で掃除も実行） |

### Mac が重いとき

```bash
bash diagnose_mac_slow.sh --fix        # 診断 → そのまま安全な掃除まで
bash diagnose_mac_slow.sh              # 診断だけ（何も消さない）
```

常駐セッション数 / MCP サーバのメモリ / `~/.claude` の肥大化 / cron の多重発火 /
iCloud 同期 / Spotlight インデックスを一括で見て、「疑わしい点」を出す。

`--fix` が実際にやるのはこれだけ（いずれも戻せる、または再生成される）:

- `shell-snapshots` の7日超を削除
- 会話ログ（`projects/*.jsonl`）の60日超を削除 … 該当セッションは `/resume` で遡れなくなる。
  消したくないなら `--fix --keep-logs`、日数を変えるなら `--fix --days 30`
- `~/.claude` を Spotlight / Time Machine から除外（`mdutil` / `tmutil` は sudo 必要。
  未実行ならコマンドを表示する）

プロセスの kill・MCP 設定の変更・cron の変更は `--fix` でも**やらない**
（走行中のルーティンを巻き込むため）。該当したときにコマンドだけ提示する。

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

## 注意: 認証は会社 Mac でしかやらない

`gog auth add` を叩くのは**会社 Mac だけ**（2026-07-29 決定）。
家 Mac・クラウド・CI でバラバラに認証するとスコープが縮んで壊れる
（`--services` の既定値が `user` のため）。
詳細と理由は CLAUDE.md の「認証は『1台』でしかやらない」を参照。
