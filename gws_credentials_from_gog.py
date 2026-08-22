#!/usr/bin/env python3
"""gog の credentials.json と token export から gws 用の credentials.json を作る。

gws (Google Workspace CLI) は yup-oauth2 の authorized_user 形式を受け付けるので、
gog が既に持っている refresh token をそのまま流用できる。これにより
「認証は会社 Mac 1台でしかやらない」という運用ルールを崩さずに gws が使える。

  usage: gws_credentials_from_gog.py <gog_credentials.json> <gog_token_export.json> \
             <account_email> <out_path>

秘密情報は一切標準出力に出さない(エラーメッセージにも載せない)。
gog のバージョンで export の JSON 構造が変わっても拾えるように、
キー名の候補を広めに取り、最後は "1//" 始まりの文字列を探す。
"""

import json
import os
import sys

REFRESH_KEYS = {"refresh_token", "refreshToken", "RefreshToken"}
CLIENT_ID_KEYS = {"client_id", "clientId"}
CLIENT_SECRET_KEYS = {"client_secret", "clientSecret"}


def die(msg):
    sys.exit(f"!! {msg}")


def load(path, label):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        die(f"{label} を JSON として読めない ({path}): {e}")


def walk_dicts(obj):
    """入れ子の dict を全部たどる(自分自身も含む)。"""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_dicts(v)


def strings(obj):
    """入れ子の中の文字列を全部たどる。"""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)
    elif isinstance(obj, str):
        yield obj


def find_by_key(obj, names):
    """names のどれかのキーに入っている非空文字列を1つ返す(浅い順)。"""
    for d in walk_dicts(obj):
        for k, v in d.items():
            if k in names and isinstance(v, str) and v:
                return v
    return None


def refresh_tokens_in(obj):
    """その部分木に含まれる refresh token 候補を集める。"""
    found = []
    for d in walk_dicts(obj):
        for k, v in d.items():
            if k in REFRESH_KEYS and isinstance(v, str) and v:
                found.append(v)
    if not found:
        # キー名が変わっている場合の保険。Google の refresh token は "1//" 始まり。
        found = [s for s in strings(obj) if s.startswith("1//")]
    return found


def subtree_size(obj):
    if isinstance(obj, dict):
        return 1 + sum(subtree_size(v) for v in obj.values())
    if isinstance(obj, list):
        return 1 + sum(subtree_size(v) for v in obj)
    return 1


def pick_refresh_token(tok, account):
    """account のトークンを選ぶ。

    複数アカウントが入った export から取り違えないことが目的。
    (会社 Mac には @fout.jp と @gmail.com の2つが入っている)
    1. account のメールアドレスと refresh token を両方含む、最も小さい部分木を選ぶ
    2. 見つからなければ、export 全体で refresh token が1つだけならそれを使う
    3. それ以外は取り違えるのでエラーにする
    """
    candidates = []
    for d in walk_dicts(tok):
        if account not in strings(d):
            continue
        found = refresh_tokens_in(d)
        if len(found) == 1:
            candidates.append((subtree_size(d), found[0]))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    all_found = set(refresh_tokens_in(tok))
    if len(all_found) == 1:
        return next(iter(all_found))
    if not all_found:
        die("token export から refresh token を取り出せない"
            "(gog のバージョンで export 形式が変わった可能性)")
    die(f"token export に refresh token が {len(all_found)} 個あるが "
        f"{account} のものを特定できない。"
        f"gog auth tokens export で対象アカウントを指定して作り直して。")


def main():
    if len(sys.argv) != 5:
        die(__doc__.strip().splitlines()[-1] if __doc__ else "引数が足りない")
    cred_path, tok_path, account, out_path = sys.argv[1:5]

    creds = load(cred_path, "gog の credentials.json")
    # Desktop app の JSON は {"installed": {...}} だが、{"web": {...}} や
    # フラットな形もありうるので、キー名で探す。
    client_id = find_by_key(creds, CLIENT_ID_KEYS)
    client_secret = find_by_key(creds, CLIENT_SECRET_KEYS)
    if not client_id or not client_secret:
        die(f"{cred_path} から client_id / client_secret を取り出せない")

    refresh = pick_refresh_token(load(tok_path, "gog の token export"), account)

    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({
            "type": "authorized_user",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
        }, f)


if __name__ == "__main__":
    main()
