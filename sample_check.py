#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
送信キューから無作為サンプルを抜き出し、各下書きの宛名/CC/本文先頭を表示する（読み取り専用）。
送信も更新も一切しない。gog gmail drafts get のみ使用。

使い方:
  # 今日送る先頭950件から40件を無作為抽出して表示
  python3 sample_check.py --ids ~/hawk_send/phase2_ready_queue.txt --cap 950 --n 40

出力（TSV）: 通番  draftId  宛先メール  宛名行  状態
  状態: OK / EMPTY(本文空) / GONE(404) / ERROR
"""
import argparse
import base64
import json
import random
import subprocess
import sys

GOG = "/Users/yuki/bin/gog"
ACCOUNT = "yuki.katayama@fout.jp"


def b64url_decode(data):
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8", "replace")


def get_draft(did):
    r = subprocess.run(
        [GOG, "gmail", "drafts", "get", did, "--account", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=90,
    )
    if r.returncode != 0:
        err = (r.stderr or "").lower()
        if "404" in err or "not found" in err or "notfound" in err:
            return None, "GONE"
        return None, "ERROR:" + (r.stderr or "").strip()[:80]
    try:
        d = json.loads(r.stdout)["draft"]
        msg = d["message"]
        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        body = b64url_decode(msg["payload"]["body"]["data"])
        return {"to": headers.get("to", ""), "cc": headers.get("cc", ""), "body": body}, "OK"
    except Exception as e:  # noqa: BLE001
        return None, "ERROR:parse:" + str(e)[:60]


def salutation(body):
    for line in body.splitlines():
        s = line.strip()
        if s.endswith("様"):
            return s
    return "(宛名行なし)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="送信キュー（例: ~/hawk_send/phase2_ready_queue.txt）")
    ap.add_argument("--cap", type=int, default=950, help="今日送る先頭N件から抽出（send_manualの最大送信数に合わせる）")
    ap.add_argument("--n", type=int, default=40, help="抽出件数")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import os
    ids = [l.strip() for l in open(os.path.expanduser(args.ids)) if l.strip()]
    pool = ids[: args.cap]
    random.seed(args.seed)
    sample = random.sample(pool, min(args.n, len(pool)))

    print(f"# キュー {args.ids}: 全{len(ids)}件 / 対象先頭{len(pool)}件 / 抽出{len(sample)}件")
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
