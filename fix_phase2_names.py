#!/usr/bin/env python3
"""
fix_phase2_names.py

HAWK フェーズ2 下書きの宛名「名 姓」→「姓 名」を、下書きIDを保ったまま
Gmail API (users.drafts.update) でその場修正する。

ポイント:
- 下書きIDは変わらないので phase2_draft_ids.txt はそのまま使える（送信フローを壊さない）。
- 宛名は「元データ（姓/名が分かれた CSV）」を正として置換する。
  レンダリング済み本文の文字列を当て推量で入れ替えない（外国名・スペース入り名で誤爆するため）。
- まずドライラン（--apply なし）で必ず内容確認してから本適用すること。

必要ライブラリ:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
スコープ:
    https://www.googleapis.com/auth/gmail.modify
    ※ credentials.json（OAuthクライアント）を同じディレクトリに置く。初回に token.json が作られる。

CSV 形式（ヘッダ必須／UTF-8）:
    email,last_name,first_name
    miz15854@casio.co.jp,水谷,早希
    i-kuwahara@stf.kodansha.co.jp,桑原,勲
    ...
    ※ Salesforce から「宛先メール / LastName / FirstName」でエクスポートして作る。

使い方:
    # 1) ドライラン（変更予定を表示するだけ・何も書き換えない）
    python3 fix_phase2_names.py --ids ~/hawk_send/phase2_draft_ids.txt --names ~/hawk_send/phase2_names.csv

    # 2) 問題なければ本適用
    python3 fix_phase2_names.py --ids ~/hawk_send/phase2_draft_ids.txt --names ~/hawk_send/phase2_names.csv --apply
"""
import argparse
import base64
import csv
import email.utils
import os.path
import sys
from email import message_from_bytes
from email.policy import default as default_policy

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def load_names(path):
    m = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m[row["email"].strip().lower()] = (
                row["last_name"].strip(),
                row["first_name"].strip(),
            )
    return m


def load_ids(path):
    ids = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                ids.append(s)
    return ids


def to_address(to_header):
    _, addr = email.utils.parseaddr(to_header or "")
    return addr.strip().lower()


def fix_text(text, last, first):
    """姓/名を正として置換する。当て推量の分割はしない。"""
    # 宛名行:   "名 姓 様" -> "姓 名 様"
    text = text.replace(f"{first} {last} 様", f"{last} {first} 様")
    # 本文中の呼称: "名様" -> "姓様"  (例: "…ご参加いただいた早希様へ")
    text = text.replace(f"{first}様", f"{last}様")
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="下書きIDリスト (phase2_draft_ids.txt)")
    ap.add_argument("--names", required=True, help="email,last_name,first_name の CSV")
    ap.add_argument("--apply", action="store_true", help="指定しないとドライラン")
    args = ap.parse_args()

    names = load_names(args.names)
    ids = load_ids(args.ids)
    svc = get_service()
    drafts = svc.users().drafts()

    fixed = skipped = errors = 0
    for i, draft_id in enumerate(ids, 1):
        try:
            d = drafts.get(userId="me", id=draft_id, format="raw").execute()
            raw = base64.urlsafe_b64decode(d["message"]["raw"])
            msg = message_from_bytes(raw, policy=default_policy)

            addr = to_address(msg["To"])
            if addr not in names:
                print(f"[{i}] SKIP {draft_id}: 宛先 {addr} が CSV に無い")
                skipped += 1
                continue
            last, first = names[addr]

            touched = False
            parts = msg.walk() if msg.is_multipart() else [msg]
            for part in parts:
                ctype = part.get_content_type()
                if ctype in ("text/plain", "text/html"):
                    body = part.get_content()
                    new = fix_text(body, last, first)
                    if new != body:
                        part.set_content(new, subtype=ctype.split("/", 1)[1])
                        touched = True

            if not touched:
                print(f"[{i}] no-change {draft_id} ({addr})")
                skipped += 1
                continue

            if args.apply:
                new_raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                drafts.update(
                    userId="me",
                    id=draft_id,
                    body={"id": draft_id, "message": {"raw": new_raw}},
                ).execute()
                print(f"[{i}] FIXED {draft_id} -> {last} {first} 様 ({addr})")
            else:
                print(f"[{i}] would fix {draft_id} -> {last} {first} 様 ({addr})")
            fixed += 1
        except Exception as e:  # noqa: BLE001
            print(f"[{i}] ERROR {draft_id}: {e}", file=sys.stderr)
            errors += 1

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"\n{mode}: fix={fixed} skip={skipped} err={errors} total={len(ids)}")
    if not args.apply:
        print("内容に問題なければ --apply を付けて再実行してください。")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
