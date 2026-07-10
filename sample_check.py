#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
送信キューのうち「未送信(pending)」だけを対象に、無作為サンプルの宛名/CC/状態を表示する（読み取り専用）。
送信も更新も一切しない。gog gmail drafts get のみ使用。

send_manual.py と同じロジックで送信済み(send_log.jsonl の ok=true)を除外し、
実際に今日送られる pending から抽出する。

使い方:
  python3 sample_check.py --ids ~/hawk_send/phase2_ready_queue.txt --n 40

出力(TSV): 通番  draftId  宛先メール  宛名行  状態  CC有無
  状態: OK / EMPTY(本文空) / GONE(404) / ERROR
"""
import argparse
import base64
import json
import os
import random
import subprocess

GOG = "/Users/yuki/bin/gog"
ACCOUNT = "yuki.katayama@fout.jp"


def b64url_decode(data):
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8", "replace")


def load_sent(logpath):
    ok = set()
    if os.path.exists(logpath):
        for line in open(logpath):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ok") is True:
                ok.add(r.get("draftId"))
    return ok


def get_draft(did):
    r = subprocess.run(
        [GOG, "gmail", "drafts", "get", did, "--account", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=90,
    )
    if r.returncode != 0:
        err = (r.stderr or "").lower()
        if "404" in err or "not found" in err or "notfound" in err:
            return None, "GONE"
        return None, "ERROR"
    try:
        d = json.loads(r.stdout)["draft"]
        msg = d["message"]
        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        body = b64url_decode(msg["payload"]["body"]["data"])
        return {"to": headers.get("to", ""), "cc": headers.get("cc", ""), "body": body}, "OK"
    except Exception:  # noqa: BLE001
        return None, "ERROR"


def salutation(body):
    for line in body.splitlines():
        s = line.strip()
        if s.endswith("様"):
            return s
    return "(宛名行なし)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True)
    ap.add_argument("--log", default="~/hawk_send/send_log.jsonl")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    ids = [l.strip() for l in open(os.path.expanduser(args.ids)) if l.strip()]
    sent = load_sent(os.path.expanduser(args.log))
    pending = [d for d in ids if d not in sent]

    print(f"# キュー全{len(ids)}件 / 送信済み{len(ids)-len(pending)}件 / 未送信(pending){len(pending)}件")
    if not pending:
        print("# pending が0件。今日送る対象はありません（全部送信済み）。")
        return

    random.seed(args.seed)
    sample = random.sample(pending, min(args.n, len(pending)))
    print(f"# pending から{len(sample)}件を無作為抽出")
    print("idx\tdraftId\tto\t宛名\t状態\tCC有無")
    ng = 0
    for i, did in enumerate(sample, 1):
        info, status = get_draft(did)
        if info is None:
            print(f"{i}\t{did}\t-\t-\t{status}\t-")
            ng += 1
            continue
        cc = "cc有" if info["cc"] else "cc無"
        name = salutation(info["body"])
        state = status if info["body"].strip() else "EMPTY"
        if state != "OK":
            ng += 1
        print(f"{i}\t{did}\t{info['to']}\t{name}\t{state}\t{cc}")
    print(f"# 完了: 抽出{len(sample)} / 異常(GONE/EMPTY/ERROR){ng}")


if __name__ == "__main__":
    main()
