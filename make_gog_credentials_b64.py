#!/usr/bin/env python3
"""GOG_CREDENTIALS_B64 の値を作ってクリップボードに入れる。

    python3 make_gog_credentials_b64.py

client_id はローカルの gog の credentials.json から自動で拾う (--client-id で上書き)。
client_secret は次の順で探す:

  1. クリップボード内の生の secret
  2. クリップボード内の、このスクリプトが以前作った b64 (作り直しに使える)
  3. 上記が使えなければプロンプトで受け取る (入力は表示されない。Cmd+V 可)

クリップボードを入力に使うだけでは足りない。このスクリプトを chat や README から
コピーして貼り付けた時点でクリップボードは上書きされるので、必ずファイルに置いて
実行する運用にすること。プロンプトのフォールバックがあるのはそのため。

出力は b64 をクリップボードに書くだけで、画面には secret の末尾4文字しか出さない。
base64 は暗号化ではないので、b64 を画面に出すのは secret を平文で晒すのと同じ。
"""
import argparse
import base64
import getpass
import json
import os
import shutil
import subprocess
import sys

# gog が client_id を書く場所。macOS は ConfigDir と DataDir が同じ所に落ちる。
CREDENTIAL_PATHS = (
    "~/Library/Application Support/gogcli/credentials.json",  # macOS
    "~/.local/share/gogcli/credentials.json",                 # Linux DataDir
    "~/.config/gogcli/credentials.json",                      # Linux 旧/中継
)

MIN_SECRET_LEN = 20


def die(msg):
    sys.exit("NG: %s" % msg)


def unwrap(doc):
    """{"installed":{...}} / {"web":{...}} / フラット形 のどれでも中身を返す。"""
    if not isinstance(doc, dict):
        return {}
    for key in ("installed", "web"):
        section = doc.get(key)
        if isinstance(section, dict):
            return section
    return doc


def find_client_id():
    for raw in CREDENTIAL_PATHS:
        path = os.path.expanduser(raw)
        if not os.path.exists(path):
            continue
        try:
            with open(path) as fh:
                client_id = str(unwrap(json.load(fh)).get("client_id") or "").strip()
        except Exception:
            continue
        if client_id:
            return client_id, path
    return None, None


def read_clipboard():
    if not shutil.which("pbpaste"):
        return ""
    try:
        return subprocess.run(["pbpaste"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def secret_from_clipboard(clip):
    """クリップボードから secret を取り出す。取れなければ (None, 理由)。"""
    if not clip:
        return None, "クリップボードが空"

    try:
        decoded = json.loads(base64.b64decode(clip, validate=True))
    except Exception:
        decoded = None

    if isinstance(decoded, dict):
        # 以前作った b64 が入っている
        secret = str(unwrap(decoded).get("client_secret") or "").strip()
        if secret:
            return secret, "クリップボードの b64"
        return None, "クリップボードの b64 に client_secret が無い"

    if len(clip.split()) != 1:
        return None, "クリップボードが単一の文字列でない(スクリプト本文などが入っている)"
    if len(clip) < MIN_SECRET_LEN:
        return None, "クリップボードの文字列が短すぎる(%d文字)" % len(clip)
    return clip, "クリップボードの生 secret"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client-id", help="OAuth クライアントID (既定: ローカルの gog から取得)")
    parser.add_argument("--out", help="クリップボードではなくこのファイルに書く (0600)")
    args = parser.parse_args()

    if args.client_id:
        client_id, source = args.client_id.strip(), "--client-id"
    else:
        client_id, source = find_client_id()
        if not client_id:
            die("client_id が見つからない。--client-id で指定して。探した場所: %s"
                % ", ".join(CREDENTIAL_PATHS))
    print("client_id: %s (%s)" % (client_id, source))

    secret, why = secret_from_clipboard(read_clipboard())
    if secret:
        print("secret: %s" % why)
    else:
        print("secret: %s → プロンプトで受け取る" % why)
        secret = getpass.getpass("client secret (貼り付け可、表示されません): ").strip()
        if not secret:
            die("secret が空。Console の Add secret で表示された値を貼り付けて。")
        if len(secret.split()) != 1:
            die("secret に空白が含まれている。貼り付けた内容を確認して。")
        if len(secret) < MIN_SECRET_LEN:
            die("secret が短すぎる(%d文字)。" % len(secret))

    doc = {"installed": {
        "client_id": client_id,
        "client_secret": secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}
    b64 = base64.b64encode(json.dumps(doc).encode()).decode()

    if args.out:
        with open(os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                  "w") as fh:
            fh.write(b64)
        where = args.out
    elif shutil.which("pbcopy"):
        subprocess.run(["pbcopy"], input=b64, text=True, check=True)
        where = "クリップボード"
    else:
        die("pbcopy が無い。--out でファイルに書いて。")

    print("OK: secret ...%s (%d文字) を埋め込んだ b64 (%d文字) を %s に入れた"
          % (secret[-4:], len(secret), len(b64), where))


if __name__ == "__main__":
    main()
