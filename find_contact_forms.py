#!/usr/bin/env python3
"""
生収集_0804 の各社について、問い合わせフォームURLを実際に到達確認しながら特定する。

クラウドセッションでは外部サイトへの egress が遮断されていて到達確認ができないので、
このスクリプトは会社Mac（外に出られる環境）で回す前提で書いてある。

やること:
  1. gog 経由でシートを読む
  2. 会社URL のトップページを取得し、生存を確認する（死んでいるドメインを検出する）
  3. ページ内のリンクから「お問い合わせ」導線を探す
  4. 見つからなければ /contact 等の定番パスを実際に叩く
  5. 候補が本当にフォームページか（<form> や送信ボタンがあるか）を確認する
  6. --write を付けたときだけシートに書き戻す

モデル(LLM)は一切使わない。ただのHTTPクライアント。

依存: Python 3.9+ の標準ライブラリのみ。pip install 不要。

使い方:
    python3 find_contact_forms.py --limit 20            # まず20社で試す（書き込みなし）
    python3 find_contact_forms.py                       # 全社スキャン（書き込みなし）
    python3 find_contact_forms.py --write               # 結果をシートに反映
    python3 find_contact_forms.py --write --only-missing  # フォームURLが空の行だけ

途中で止めても cache.json に貯まるので、同じコマンドで再開すれば続きから走る。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import html
import json
import os
import re
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

SPREADSHEET_ID = "1iyhwVNhN_HJNdIBL_pREhrhBdQu2it5ktFOYq-DDm_w"
TAB = "生収集_0804"
ACCOUNT = "yuki.katayama@fout.jp"
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".contact_form_cache.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 15
PER_HOST_INTERVAL = 1.0   # 同一ホストへの連続アクセスは1秒あける

# アンカーテキストに出たら問い合わせ導線とみなす語。左ほど強い。
ANCHOR_WORDS = [
    ("お問い合わせ", 100), ("お問合せ", 100), ("お問合わせ", 100),
    ("問い合わせ", 95), ("問合せ", 95), ("ご相談", 70), ("相談する", 70),
    ("資料請求", 60), ("お見積", 55),
    ("contact us", 90), ("contact", 85), ("inquiry", 85), ("enquiry", 80),
]
# href に出たら加点するパターン
HREF_WORDS = [
    ("/contact", 60), ("/inquiry", 60), ("/otoiawase", 60), ("/toiawase", 60),
    ("/form", 40), ("/support", 20), ("/request", 25),
]
# リンクが見つからなかったときに直接叩く定番パス
FALLBACK_PATHS = [
    "/contact/", "/contact", "/contact-us/", "/inquiry/", "/inquiry",
    "/contact.html", "/contact.php", "/form/", "/otoiawase/", "/toiawase/",
    "/support/contact/", "/company/contact/",
]
# 明らかに問い合わせ窓口でないもの
NEGATIVE = ["/recruit", "/entry", "/privacy", "/policy", "/news", "/blog",
            "career", "saiyo", "mailto:", "tel:", "javascript:", ".pdf"]

_host_lock = threading.Lock()
_host_last: dict[str, float] = defaultdict(float)


def polite_wait(host: str) -> None:
    """同一ホストへの連投を避ける。相手のサーバに迷惑をかけないため。"""
    with _host_lock:
        wait = _host_last[host] + PER_HOST_INTERVAL - time.time()
        if wait > 0:
            time.sleep(wait)
        _host_last[host] = time.time()


def fetch(url: str, method: str = "GET") -> tuple[int, str, str]:
    """(status, final_url, body) を返す。失敗時は status=0 で理由を body に入れる。"""
    host = urllib.parse.urlparse(url).netloc
    polite_wait(host)
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.8",
        "Accept-Encoding": "gzip",
    })
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            raw = resp.read(600_000)
            if resp.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            charset = resp.headers.get_content_charset()
            if not charset:
                m = re.search(rb'charset=["\']?([\w\-]+)', raw[:4000], re.I)
                charset = m.group(1).decode("ascii", "ignore") if m else "utf-8"
            body = raw.decode(charset, "replace")
            return resp.status, resp.geturl(), body
    except urllib.error.HTTPError as e:
        return e.code, url, ""
    except Exception as e:                      # タイムアウト/DNS/SSL 等
        return 0, url, f"{type(e).__name__}: {e}"


LINK_RE = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                     re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def find_contact_links(base_url: str, body: str) -> list[tuple[int, str]]:
    """トップページのHTMLから問い合わせ導線の候補を、スコア降順で返す。"""
    out: dict[str, int] = {}
    for href, inner in LINK_RE.findall(body):
        text = html.unescape(TAG_RE.sub("", inner)).strip().lower()
        low = href.lower()
        if any(n in low for n in NEGATIVE):
            continue
        score = 0
        for word, pt in ANCHOR_WORDS:
            if word and word.lower() in text:
                score = max(score, pt)
        for word, pt in HREF_WORDS:
            if word in low:
                score += pt
        if score <= 0:
            continue
        absolute = urllib.parse.urljoin(base_url, html.unescape(href))
        absolute, _ = urllib.parse.urldefrag(absolute)
        if not absolute.startswith(("http://", "https://")):
            continue
        out[absolute] = max(out.get(absolute, 0), score)
    return sorted(((s, u) for u, s in out.items()), reverse=True)


FORM_HINT = re.compile(
    r"<form\b|お問い?合わ?せ|問合せ|送信する|必須項目|プライバシーポリシーに同意"
    r"|recaptcha|formrun|hubspot|typeform|google\.com/forms",
    re.I)


def looks_like_form(body: str) -> bool:
    return bool(FORM_HINT.search(body))


def same_site(a: str, b: str) -> bool:
    """フォームが別ドメインのASP（formrun等）でも、リンク元が公式なら許容する。"""
    ha = urllib.parse.urlparse(a).netloc.lower().removeprefix("www.")
    hb = urllib.parse.urlparse(b).netloc.lower().removeprefix("www.")
    if ha == hb:
        return True
    return ha.split(".")[-2:] == hb.split(".")[-2:]


def probe_company(name: str, url: str) -> dict:
    """1社ぶんの調査。会社URLの生死とフォームURLを返す。"""
    result = {"name": name, "input_url": url, "site_status": 0,
              "final_url": "", "form_url": "", "form_status": 0,
              "method": "", "note": ""}
    if not url:
        result["note"] = "会社URLなし（先に検索で特定が必要）"
        return result

    status, final, body = fetch(url)
    result["site_status"] = status
    result["final_url"] = final
    if status != 200:
        result["note"] = f"トップページに到達できず（{status or body[:60]}）"
        return result

    # 1) トップページのリンクから探す
    for score, cand in find_contact_links(final, body)[:5]:
        st, fin, cbody = fetch(cand)
        if st == 200 and looks_like_form(cbody):
            result.update(form_url=fin, form_status=st, method=f"link(score={score})")
            if not same_site(final, fin):
                result["note"] = "フォームが外部ASPドメイン"
            return result

    # 2) 定番パスを直接叩く
    root = f"{urllib.parse.urlparse(final).scheme}://{urllib.parse.urlparse(final).netloc}"
    for path in FALLBACK_PATHS:
        st, fin, cbody = fetch(root + path)
        if st == 200 and looks_like_form(cbody):
            result.update(form_url=fin, form_status=st, method=f"probe({path})")
            return result

    result["note"] = "フォーム未発見（電話/メールのみの可能性）"
    return result


def gog(args: list[str], capture=True) -> str:
    cmd = ["gog", "--account", ACCOUNT] + args
    p = subprocess.run(cmd, capture_output=capture, text=True)
    if p.returncode != 0:
        sys.exit(f"gog 失敗: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout


def read_sheet() -> list[list[str]]:
    out = gog(["-j", "sheets", "get", SPREADSHEET_ID, f"{TAB}!A1:J1000"])
    return json.loads(out).get("values", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="先頭N社だけ処理（試運転用）")
    ap.add_argument("--only-missing", action="store_true",
                    help="フォームURLが空の行だけ処理")
    ap.add_argument("--write", action="store_true", help="シートに書き戻す")
    ap.add_argument("--workers", type=int, default=8, help="並列数（既定8）")
    ap.add_argument("--fresh", action="store_true", help="キャッシュを無視して再取得")
    args = ap.parse_args()

    rows = read_sheet()
    if not rows:
        sys.exit("シートが読めなかった")
    header, data = rows[0], rows[1:]
    cell = lambda r, i: (r[i].strip() if len(r) > i and r[i] else "")

    cache = {}
    if os.path.exists(CACHE_PATH) and not args.fresh:
        cache = json.load(open(CACHE_PATH))

    targets = []
    for idx, r in enumerate(data, start=2):     # シート行番号（ヘッダが1行目）
        name = cell(r, 1)
        if not name:
            continue
        if args.only_missing and cell(r, 3):
            continue
        targets.append((idx, name, cell(r, 2)))
    if args.limit:
        targets = targets[:args.limit]

    todo = [t for t in targets if str(t[0]) not in cache]
    print(f"対象 {len(targets)}社 / キャッシュ済 {len(targets) - len(todo)}社 / これから {len(todo)}社")

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(probe_company, n, u): (i, n) for i, n, u in todo}
        for fut in concurrent.futures.as_completed(futs):
            i, n = futs[fut]
            try:
                cache[str(i)] = fut.result()
            except Exception as e:
                cache[str(i)] = {"name": n, "note": f"例外: {e}"}
            done += 1
            if done % 20 == 0:
                json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False)
                print(f"  ... {done}/{len(todo)}", flush=True)
    json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False)

    picked = [cache[str(i)] for i, _, _ in targets if str(i) in cache]
    found = [p for p in picked if p.get("form_url")]
    dead = [p for p in picked if p.get("site_status") not in (200, 0) or
            (p.get("site_status") == 0 and p.get("input_url"))]
    print("\n===== 結果 =====")
    print(f"  フォームURL 特定 : {len(found)} / {len(picked)}")
    print(f"  トップページ到達不可: {len(dead)}")
    print(f"  会社URL 未取得    : {sum(1 for p in picked if not p.get('input_url'))}")

    if not args.write:
        print("\n（--write なしなので書き込みはしていない）")
        for p in found[:15]:
            print(f"  {p['name']}  ->  {p['form_url']}  [{p['method']}]")
        return

    updates = []
    for i, _, _ in targets:
        p = cache.get(str(i))
        if not p:
            continue
        if p.get("form_url"):
            updates.append({"range": f"{TAB}!D{i}", "values": [[p["form_url"]]]})
        flag = p.get("note", "")
        if flag:
            updates.append({"range": f"{TAB}!I{i}", "values": [[flag]]})
    if not updates:
        print("書き込むものがない")
        return
    payload = os.path.join(os.path.dirname(CACHE_PATH), ".contact_form_payload.json")
    json.dump(updates, open(payload, "w"), ensure_ascii=False)
    gog(["sheets", "batch-update", SPREADSHEET_ID,
         f"--data-json=@{payload}", "--input=RAW", "-y"], capture=False)
    print(f"シートに {len(updates)} レンジ書き込んだ")


if __name__ == "__main__":
    main()
