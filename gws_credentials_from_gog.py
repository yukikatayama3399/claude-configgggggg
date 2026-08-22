#!/usr/bin/env python3
"""gog の認証情報から gws 用の credentials.json (authorized_user 形式) を作る。

gws (Google Workspace CLI) は yup-oauth2 の authorized_user 形式を受け付けるので、
gog が既に持っている refresh token をそのまま流用できる。これにより
「認証は会社 Mac 1台でしかやらない」という運用ルールを崩さずに gws が使える。

  usage: gws_credentials_from_gog.py --account <email> --token <token_export.json>
                                     --out <out.json> [<client_source.json> ...]

client_id / client_secret の在り処は環境によって違う:
  - gog が管理している credentials.json は **client_secret が抜かれている**
    ことがある(keyring に退避される。gog auth credentials list の
    SECRET_KEYRING=true がその状態)
  - その場合は token export 側に client 情報が入っている
そのため複数のファイルを候補として受け取り、**client_id と client_secret の
両方が揃っているファイル**を1つ選ぶ。片方ずつ別のファイルから拾うと、
別プロジェクトの client_id と secret を混ぜてしまうのでやらない。
候補は指定順に見て、最後に token export を見る。

秘密情報は標準出力にもエラーメッセージにも出さない。
"""

import argparse
import json
import os
import sys

REFRESH_KEYS = {"refresh_token", "refreshToken", "RefreshToken"}
CLIENT_ID_KEYS = {"client_id", "clientId"}
CLIENT_SECRET_KEYS = {"client_secret", "clientSecret"}


def die(msg):
    sys.exit(f"!! {msg}")


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


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


def pick_client(sources):
    """client_id と client_secret が両方揃っているファイルから両方を取る。

    戻り値: (client_id, client_secret, 採用したパス)
    """
    for path, data in sources:
        if data is None:
            continue
        cid = find_by_key(data, CLIENT_ID_KEYS)
        sec = find_by_key(data, CLIENT_SECRET_KEYS)
        if cid and sec:
            return cid, sec, path
    checked = ", ".join(p for p, _ in sources) or "(候補なし)"
    die("client_id と client_secret の両方が入っているファイルが無い。\n"
        f"   確認した候補: {checked}\n"
        "   gog が client_secret を keyring に退避していると、管理下の\n"
        "   credentials.json には入っていない(gog auth credentials list の\n"
        "   SECRET_KEYRING=true がその状態)。入手先は2つ:\n"
        "   (a) ~/.gog_sync/gog_env_*.env … sync_gog_token.sh の出力。\n"
        "       setup_gws_remote.sh が自動で見るので、あれば何もしなくてよい。\n"
        "   (b) Cloud Console の OAuth クライアント(Desktop app)の JSON を\n"
        "       ダウンロードして、その実際のパスを渡す:\n"
        "         GWS_CLIENT_SECRET_JSON=<落としたJSONのパス> bash setup_gws_remote.sh")


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
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--account", required=True)
    ap.add_argument("--token", required=True, help="gog auth tokens export の出力")
    ap.add_argument("--out", required=True)
    ap.add_argument("--verbose", action="store_true",
                    help="client 情報をどのファイルから採用したかを出す(値は出さない)")
    ap.add_argument("client_sources", nargs="*",
                    help="client_id/client_secret の候補ファイル")
    a = ap.parse_args()

    tok = load(a.token)
    if tok is None:
        die(f"token export を JSON として読めない: {a.token}")

    # client 情報の候補: 指定されたファイル → 最後に token export 自身。
    sources = [(p, load(p)) for p in a.client_sources]
    sources.append((a.token, tok))
    client_id, client_secret, used = pick_client(sources)
    if a.verbose:
        print(f"    client 情報の採用元: {used}")

    refresh = pick_refresh_token(tok, a.account)

    fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({
            "type": "authorized_user",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
        }, f)


if __name__ == "__main__":
    main()
