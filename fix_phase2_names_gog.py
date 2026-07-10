#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HAWK フェーズ2 下書きの宛名「名 姓」→「姓 名」を、下書きIDを保ったまま
gog (gmail drafts get/update) でその場修正する。

- update_signature.py と同じ方式（get→本文書換→drafts update）。認証は gog がすでに保持。
- 下書きIDは変わらないので送信キュー（phase2_ready_queue.txt）はそのまま使える。
- 宛名は「元データ CSV（email,last_name,first_name）」を正として置換する。
  レンダリング済み本文の当て推量分割はしない（外国名・スペース入り名で誤爆するため）。
- 冪等：変換結果が元と同じ下書きはスキップ（再実行で続きから）。fix_names_log.jsonl に追記。
- 既定はドライラン。実際に書き換えるときだけ --apply を付ける。

使い方:
  # ドライラン（何も書き換えない・変更予定を表示）
  python3 fix_phase2_names_gog.py --ids ~/hawk_send/phase2_ready_queue.txt --names ~/hawk_send/phase2_names.csv

  # 本適用
  python3 fix_phase2_names_gog.py --ids ~/hawk_send/phase2_ready_queue.txt --names ~/hawk_send/phase2_names.csv --apply
"""
import argparse
import base64
import csv
import datetime
import email.utils
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

BASE = os.path.expanduser("~/hawk_send")
ACCOUNT = "yuki.katayama@fout.jp"
GOG = "/Users/yuki/bin/gog"
JST = ZoneInfo("Asia/Tokyo")
LOG = os.path.join(BASE, "fix_names_log.jsonl")
BODY_TMP = os.path.join(BASE, "_fixname_body.tmp")


def b64url_decode(data):
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8", "replace")


def get_draft(did):
    r = subprocess.run(
        [GOG, "gmail", "drafts", "get", did, "--account", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=90,
    )
    if r.returncode != 0:
        return None, r.stderr.strip()[:200]
    d = json.loads(r.stdout)["draft"]
    msg = d["message"]
    headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
    body = b64url_decode(msg["payload"]["body"]["data"])
    return {
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "bcc": headers.get("bcc", ""),
        "subject": headers.get("subject", ""),
        "body": body,
    }, ""


def update_draft(did, info, new_body):
    with open(BODY_TMP, "w") as f:
        f.write(new_body)
    cmd = [GOG, "gmail", "drafts", "update", did,
           "--account", ACCOUNT,
           "--subject", info["subject"],
           "--body-file", BODY_TMP,
           "--to", info["to"], "--json"]
    if info["cc"]:
        cmd += ["--cc", info["cc"]]
    if info["bcc"]:
        cmd += ["--bcc", info["bcc"]]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    return r.returncode == 0, r.stderr.strip()[:200]


def load_names(path):
    m = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m[row["email"].strip().lower()] = (
                row["last_name"].strip(),
                row["first_name"].strip(),
            )
    return m


def to_address(to_header):
    _, addr = email.utils.parseaddr(to_header or "")
    return addr.strip().lower()


def fix_text(body, last, first):
    """姓/名を正として置換。当て推量の分割はしない。"""
    # 宛名行: "名 姓 様" -> "姓 名 様"
    body = body.replace(f"{first} {last} 様", f"{last} {first} 様")
    # 本文中の呼称: "名様" -> "姓様"  (例: "…ご参加いただいた早希様へ")
    body = body.replace(f"{first}様", f"{last}様")
    return body


def done_ids():
    ok = set()
    if os.path.exists(LOG):
        for line in open(LOG):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ok"):
                ok.add(r["id"])
    return ok


def log_rec(rec):
    rec["ts"] = datetime.datetime.now(JST).isoformat()
    with open(LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="送信キュー（既定: phase2_ready_queue.txt）")
    ap.add_argument("--names", required=True, help="email,last_name,first_name の CSV")
    ap.add_argument("--apply", action="store_true", help="指定しないとドライラン")
    ap.add_argument("--cap", type=int, default=999999)
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()

    names = load_names(args.names)
    ids = [l.strip() for l in open(os.path.expanduser(args.ids)) if l.strip()]
    already = done_ids() if args.apply else set()
    todo = [i for i in ids if i not in already][: args.cap]
    print(f"キュー {args.ids}: 総数 {len(ids)} / 適用済み {len(already)} / 今回 {len(todo)}")
    print(f"CSV名簿: {len(names)} 件  モード: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("-" * 40)

    fixed = skipped = missing = failed = 0
    for n, did in enumerate(todo, 1):
        info, err = get_draft(did)
        if info is None:
            failed += 1
            print(f"  [{n}/{len(todo)}] GET失敗 {did}: {err}")
            continue
        addr = to_address(info["to"])
        if addr not in names:
            missing += 1
            print(f"  [{n}/{len(todo)}] CSVに無い宛先 {addr} (draft {did})")
            continue
        last, first = names[addr]
        if not last or not first:
            missing += 1
            print(f"  [{n}/{len(todo)}] 姓か名が空 {addr}")
            continue
        new_body = fix_text(info["body"], last, first)
        if new_body == info["body"]:
            skipped += 1
            continue
        if args.apply:
            ok, uerr = update_draft(did, info, new_body)
            log_rec({"id": did, "ok": ok, "email": addr, "name": f"{last} {first}", "error": uerr})
            if ok:
                fixed += 1
            else:
                failed += 1
                print(f"  [{n}/{len(todo)}] 更新失敗 {did}: {uerr}")
            time.sleep(args.interval)
        else:
            print(f"  [{n}/{len(todo)}] would fix {did} {addr} -> {last} {first} 様")
            fixed += 1

    print("-" * 40)
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"{mode}: fix={fixed} skip(既に正)={skipped} missing(CSV無/空)={missing} fail={failed} total={len(todo)}")
    if not args.apply:
        print("内容に問題なければ --apply を付けて再実行してください。")
    if missing:
        print("⚠ missing がある間は送信しないこと（その宛先は直っていません）。")


if __name__ == "__main__":
    main()
