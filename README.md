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

### GOG_CREDENTIALS_B64 の作り方 (ハマりどころ)

**Mac 側の gog の credentials.json を base64 してはいけない。** base64 する対象は
Google Cloud Console からダウンロードした元の OAuth クライアント JSON:

```bash
openssl base64 -A -in ~/Downloads/client_secret_XXXX.json | pbcopy
```

Mac の `~/Library/Application Support/gogcli/credentials.json` は gog が書いた
別物で、2つの理由で使えない (v0.19.0 で確認):

1. **client_secret が入っていない。** `gog auth credentials set` は既定で
   client_secret を keyring に保存し、ファイル側には client_id しか書かない。
   `gog auth credentials list` の `SECRET_KEYRING` が `true` ならこの状態
   (`--insecure` を付けた場合だけファイルに入る)。keyring から secret を
   取り出すコマンドは無いので、Console から再ダウンロードするのが唯一の手。
2. **形式が違う。** gog が書くのは `{"client_id":...}` のフラット形だが、
   `gog auth credentials set` が受け付けるのは Console 版の
   `{"installed":{...}}` / `{"web":{...}}` だけ。自分が書いた形を戻せない。

`setup_gog_remote.sh` はこの2点を復元直後に検証して、後段の
`gog auth credentials set` や doctor で初めて落ちるのを防いでいる。

**ダウンロードした client JSON は消さずに保管すること (1Password 等)。**
`gog auth credentials set` すると secret は keyring に移ってファイルからは消えるため、
**あの JSON が client_secret の唯一の入手元**になる。手元から消すと Console で
再ダウンロードするしかなく、クライアントの作成時期によっては再ダウンロード自体が
できず (Google は作成時のみ secret 表示に変更済み) シークレットのローテートが
必要になる。ローテートしても client_id は変わらないので既存の refresh token は
そのまま使えるはずだが、`invalid_grant` 系で落ちたら Mac で再認証して
`gog auth tokens export` からやり直し、`GOG_TOKEN_EXPORT_B64` も焼き直す。

### gog の設定ファイルの場所

OS で違う (`internal/config/layout.go`)。`gog config path` (別名 `gog config where`)
で実効値が出る。

| | macOS | Linux |
|---|---|---|
| ConfigDir (`config.json`) | `~/Library/Application Support/gogcli` | `~/.config/gogcli` |
| DataDir (`credentials.json`, keyring) | `~/Library/Application Support/gogcli` | `~/.local/share/gogcli` |

macOS は XDG を使わず `os.UserConfigDir()` にフォールバックし、DataDir も同じ
ベースに落ちるので1ディレクトリにまとまる。Linux は分かれる。
`GOG_HOME` / `GOG_CONFIG_DIR` / `GOG_DATA_DIR`、および絶対パスの
`XDG_CONFIG_HOME` を設定している場合はそれが優先される。
