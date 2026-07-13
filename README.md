# claude-configgggggg

## gog (gogcli) セットアップ

新しい Claude Code セッションでは、まず以下を実行して gog を使えるようにする:

```bash
bash setup_gog_remote.sh
```

前提として、以下3つの環境変数がセッションに登録済みであること:

- `GOG_CREDENTIALS_B64` … credentials.json (client_id) の base64
- `GOG_TOKEN_EXPORT_B64` … `gog auth tokens export` 出力の base64
- `GOG_KEYRING_PASSWORD` … 暗号化ファイルkeyringのパスワード

`bin/gogcli_0.19.0_linux_amd64.tar.gz` を同梱しているので、gog バイナリのダウンロードは不要(未インストール時はこの同梱tarballを使う)。バージョンを上げる場合はこのtarballも差し替えること。
