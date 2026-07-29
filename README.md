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
`{"installed":{"client_id":..., "client_secret":...}}` 形式の OAuth クライアント
JSON (Cloud Console で作成時にダウンロードできるもの)。手元にあるならそれをそのまま:

```bash
openssl base64 -A -in ~/Downloads/client_secret_XXXX.json | pbcopy
```

Mac の `~/Library/Application Support/gogcli/credentials.json` は gog が書いた
別物で、2つの理由で使えない (v0.19.0 で確認):

1. **client_secret が入っていない。** `gog auth credentials set` は既定で
   client_secret を keyring に保存し、ファイル側には client_id しか書かない。
   `gog auth credentials list` の `SECRET_KEYRING` が `true` ならこの状態
   (`--insecure` を付けた場合だけファイルに入る)。keyring から secret を
   取り出すコマンドは無い。
2. **形式が違う。** gog が書くのは `{"client_id":...}` のフラット形だが、
   `gog auth credentials set` が受け付けるのは Console 版の
   `{"installed":{...}}` / `{"web":{...}}` だけ。自分が書いた形を戻せない。

`setup_gog_remote.sh` はこの2点を復元直後に検証して、後段の
`gog auth credentials set` や doctor で初めて落ちるのを防いでいる。

**client_secret は 1Password 等に保管すること。** `gog auth credentials set` すると
secret は keyring に移ってファイルからは消え、Console 側も**シークレットの表示と
ダウンロードは廃止済み** (詳細ページはマスク表示 `****XXXX` のみ)。つまり手元の
コピーを失うと、どこからも読み出せない。

### 手元に client JSON が無い場合 (シークレット追加)

Console のクライアント詳細ページの **`+ Add secret`** で、同じクライアントに
シークレットを追加できる。**client_id は変わらない**ので既存の refresh token
(`GOG_TOKEN_EXPORT_B64`) はそのまま有効で、Mac の再認証も token 再 export も不要。
既存シークレットも無効化されないので Mac 側の gog も動き続ける。

追加時に一度だけ表示される値をコピーし、Console は JSON をくれないので手で組む。
これは同梱の `make_gog_credentials_b64.py` がやる:

```zsh
python3 make_gog_credentials_b64.py
```

client_id はローカルの gog の credentials.json から自動で拾う (`--client-id` で上書き)。
client_secret は「クリップボードの生 secret」→「クリップボードにある前回の b64」→
「プロンプト入力」の順で探す。secret の末尾4文字を表示するので Console のマスク表示と
照合できる。失敗時はクリップボードを書き換えないので、コピーした secret を失わない。

**ファイルに置いて実行すること。ワンライナーで貼り付けて実行する形にしてはいけない。**
スクリプト本文をコピーした時点でクリップボードが上書きされ、渡したかった secret や
b64 が消える。ファイルにしておけばコマンドを打つだけなのでクリップボードは secret
専用に使える。プロンプトのフォールバックは、それでもクリップボードが潰れていた
場合の保険 (プロンプトは入力待ちで止まるので、そこで Console から secret をコピーして
貼り付ければよい)。

リポジトリが手元に無い時は、これでファイルを作ってから実行する:

```zsh
cat > ~/gog_b64.py <<'PY'
import base64, getpass, json, subprocess, sys
CLIENT_ID = "<クライアントID>.apps.googleusercontent.com"
s = getpass.getpass("client secret (貼り付け可、表示されません): ").strip()
if len(s.split()) != 1 or len(s) < 20:
    sys.exit("NG: secret が不正 (長さ %d)" % len(s))
doc = {"installed": {"client_id": CLIENT_ID, "client_secret": s,
                     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                     "token_uri": "https://oauth2.googleapis.com/token",
                     "redirect_uris": ["http://localhost"]}}
b64 = base64.b64encode(json.dumps(doc).encode()).decode()
subprocess.run(["pbcopy"], input=b64, text=True, check=True)
print("OK: secret ...%s (%d文字) / b64 %d文字 をクリップボードに入れた" % (s[-4:], len(s), len(b64)))
PY
python3 ~/gog_b64.py
```

**b64 をターミナルに表示させないこと。** base64 は暗号化ではないので、表示した b64 は
secret を平文で晒したのと同じ。上のどちらもクリップボードにだけ書き、標準出力には
マスクした確認行しか出さない。

なお、シェルの `read -s` で secret を受け取る形にはしないこと。複数行を一括で
貼り付けると `read` が後続の貼り付け行を標準入力として食ってしまい、
スクリプトのコード行が secret として読まれて残りがコマンドとして実行される。
入力待ちはスクリプト内 (python の `getpass`) に閉じ込めるのが安全。

**新規クライアントを作るのは最後の手段。** client_id が変わるため
`GOG_TOKEN_EXPORT_B64` 側の refresh token が無効になり、Mac での再認証と
`gog auth tokens export` のやり直し (= 環境変数2つの焼き直し) が必要になる。

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
