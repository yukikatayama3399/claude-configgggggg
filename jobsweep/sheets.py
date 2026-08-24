# -*- coding: utf-8 -*-
"""スプレッドシート入出力（gws CLI 経由）。

CLAUDE.md の方針どおり Google Workspace 操作は gog/gws を使う。
ここでは生の API を素直に叩ける gws を使用する。
"""
import json
import os
import re
import shutil
import subprocess

from . import config


def _gws() -> str:
    for p in ("gws", os.path.expanduser("~/.local/bin/gws"), "/root/.local/bin/gws"):
        if shutil.which(p) or os.path.exists(p):
            return p
    raise RuntimeError("gws が見つからない。setup_gws_remote.sh を実行すること。")


def _run(args, json_body=None) -> dict:
    cmd = [_gws()] + args
    if json_body is not None:
        cmd += ["--json", json.dumps(json_body, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"gws失敗: {' '.join(args)[:120]}\n{r.stderr[:600]}")
    out = r.stdout.strip()
    return json.loads(out) if out.startswith(("{", "[")) else {}


def read(tab: str, a1: str = "A1:AD5000", spreadsheet_id: str = None) -> list:
    params = {"spreadsheetId": spreadsheet_id or config.SPREADSHEET_ID,
              "range": f"{tab}!{a1}"}
    d = _run(["sheets", "spreadsheets", "values", "get", "--params",
              json.dumps(params, ensure_ascii=False)])
    return d.get("values", [])


def append(tab: str, rows: list) -> int:
    """行を追記する。戻り値は追記した行数。"""
    if not rows:
        return 0
    params = {
        "spreadsheetId": config.SPREADSHEET_ID,
        "range": f"{tab}!A1",
        "valueInputOption": "USER_ENTERED",
        "insertDataOption": "INSERT_ROWS",
    }
    # 一度に投げすぎないよう分割
    total = 0
    for i in range(0, len(rows), 400):
        chunk = rows[i:i + 400]
        _run(["sheets", "spreadsheets", "values", "append", "--params",
              json.dumps(params, ensure_ascii=False)], {"values": chunk})
        total += len(chunk)
    return total


def update(tab: str, a1: str, values: list) -> None:
    params = {
        "spreadsheetId": config.SPREADSHEET_ID,
        "range": f"{tab}!{a1}",
        "valueInputOption": "USER_ENTERED",
    }
    _run(["sheets", "spreadsheets", "values", "update", "--params",
          json.dumps(params, ensure_ascii=False)], {"values": values})


# --- 正規化・重複判定 ------------------------------------------------------
_CORP = re.compile(r"(株式会社|有限会社|合同会社|合資会社|一般社団法人|"
                   r"公益社団法人|㈱|\(株\)|（株）|inc\.?|co\.,?\s*ltd\.?|corporation)",
                   re.I)


def norm_company(name: str) -> str:
    s = _CORP.sub("", name or "")
    s = re.sub(r"[\s　・,，.．\-–—_/／「」『』（）\(\)]", "", s)
    return s.lower()


def domain(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    if not m:
        return ""
    return m.group(1).lower().replace("www.", "")


def existing_keys() -> dict:
    """既存シートから重複判定用のキー集合を作る。"""
    rows = read(config.TAB_ALL, "A1:O5000")
    if not rows:
        return {"companies": set(), "domains": set(), "header": []}
    header, data = rows[0], rows[1:]
    i_name = header.index("会社名")
    i_url = header.index("サイトURL")
    companies, domains = set(), set()
    for r in data:
        r = r + [""] * (len(header) - len(r))
        if r[i_name].strip():
            companies.add(norm_company(r[i_name]))
        d = domain(r[i_url])
        if d:
            domains.add(d)
    return {"companies": companies, "domains": domains, "header": header,
            "rows": data, "index": {"name": i_name, "url": i_url}}


def batch_update(items: list) -> int:
    """[{"range": "タブ!D5", "values": [[...]]}, ...] をまとめて書く。"""
    if not items:
        return 0
    total = 0
    for i in range(0, len(items), 200):
        chunk = items[i:i + 200]
        _run(["sheets", "spreadsheets", "values", "batchUpdate", "--params",
              json.dumps({"spreadsheetId": config.SPREADSHEET_ID}, ensure_ascii=False)],
             {"valueInputOption": "USER_ENTERED", "data": chunk})
        total += len(chunk)
    return total


# --- 送信済み/除外の突合 ----------------------------------------------------
_DOMAIN_RE = re.compile(r"^(?:https?://)?(?:www\.)?([a-z0-9.\-]+\.[a-z]{2,})", re.I)


def excluded_domains() -> set:
    """既に接触済み・除外済みのドメイン集合を読む。"""
    try:
        rows = read(config.EXCLUDE_TAB_DOMAIN, "A1:H14000",
                    spreadsheet_id=config.EXCLUDE_SPREADSHEET_ID)
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] 除外ドメインを読めなかった: {e}")
        return set()
    out = set()
    for r in rows:
        for cell in r:
            m = _DOMAIN_RE.match((cell or "").strip())
            if m:
                out.add(m.group(1).lower().replace("www.", ""))
    return out


def excluded_companies() -> set:
    """除外リストの企業名（正規化済み）。"""
    try:
        rows = read(config.EXCLUDE_TAB_COMPANY, "A1:B3000",
                    spreadsheet_id=config.EXCLUDE_SPREADSHEET_ID)
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] 除外リストを読めなかった: {e}")
        return set()
    out = set()
    for r in rows[1:]:
        if len(r) > 1 and r[1].strip():
            out.add(norm_company(r[1]))
    return out
