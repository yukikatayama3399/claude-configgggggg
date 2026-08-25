# -*- coding: utf-8 -*-
"""求人媒体からのカード抽出。

求人ボックス: onClick の addDetailHistoryValues(...) に構造化データが載っている。
スタンバイ:   job-card の DOM から抽出（掲載元の表記は無い）。
"""
import html
import re
import urllib.parse

from . import config
from .fetch import get

KB_BASE = "https://xn--pckua2a7gp15o89zb.com"
SB_BASE = "https://jp.stanby.com"


def _q(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def _clean(s: str) -> str:
    s = html.unescape(s or "")
    return re.sub(r"\s+", " ", s).strip()


def _unesc_js(s: str) -> str:
    if "\\u" in s:
        try:
            return s.encode().decode("unicode_escape")
        except Exception:  # noqa: BLE001
            pass
    return s.replace("\\/", "/").replace("\\'", "'")


# --------------------------------------------------------------------------
# 求人ボックス
# --------------------------------------------------------------------------
def kyujinbox_url(query: str, prefecture: str = "", page: int = 1,
                  fulltime: bool = True, within_24h: bool = False) -> str:
    path = f"{query}の仕事"
    if prefecture:
        path += f"-{prefecture}"
    params = []
    if fulltime:
        params.append("e=1")          # 正社員
    if within_24h:
        params.append("u=1")          # 24時間以内
    if page > 1:
        params.append(f"pg={page}")
    qs = ("?" + "&".join(params)) if params else ""
    return f"{KB_BASE}/{_q(path)}{qs}"


_KB_SNIPPET = re.compile(r'class="p-result_lines[^"]*"[^>]*>(.*?)</div>', re.S)


def _strip(seg: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", seg))


def parse_kyujinbox(body: str) -> list:
    snippets = [_strip(x) for x in _KB_SNIPPET.findall(body)]
    out = []
    for m in re.finditer(r"addDetailHistoryValues\((.*?)\);", body, re.S):
        args = re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))
        if len(args) < 8:
            continue
        a = [_clean(_unesc_js(x)) for x in args[:8]]
        out.append({
            "media": "求人ボックス",
            "job_id": a[0],
            "title": a[1],
            "company": a[2],
            "area": a[4],
            "pay": a[5],
            "employ_type": a[6],
            "source": a[7],
            "snippet": "",
        })
    # スニペットはカードと同順で並ぶので位置で対応付ける
    for i, r in enumerate(out):
        if i < len(snippets):
            r["snippet"] = snippets[i]
    return out


def kyujinbox_count(body: str):
    m = re.search(r"s-serchCounter[^>]*>([\d,]+)", body)
    return int(m.group(1).replace(",", "")) if m else None


# --------------------------------------------------------------------------
# スタンバイ
# --------------------------------------------------------------------------
def stanby_url(query: str, prefecture: str = "", page: int = 1,
               fulltime: bool = True) -> str:
    params = {"q": query}
    if prefecture:
        params["l"] = prefecture
    if fulltime:
        params["emt"] = "1"           # 正社員
    if page > 1:
        params["p"] = str(page)
    return f"{SB_BASE}/search?" + urllib.parse.urlencode(params)


_SB_CARD = re.compile(r'class="job-card"(.*?)(?=class="job-card"|$)', re.S)


def parse_stanby(body: str) -> list:
    out = []
    for m in _SB_CARD.finditer(body):
        seg = m.group(1)
        t = re.search(r'class="title-link"[^>]*>(.*?)</a>', seg, re.S)
        c = re.search(r'class="company"[^>]*>(.*?)</p>', seg, re.S)
        if not t or not c:
            continue
        attrs = [_clean(re.sub(r"<[^>]+>", "", x))
                 for x in re.findall(r'class="caption-medium text"[^>]*>(.*?)</span>', seg, re.S)]
        sn = re.search(r'class="snippet"[^>]*>(.*?)</div>', seg, re.S)
        jid = re.search(r"[?&]id=(\d+)", seg)
        out.append({
            "media": "スタンバイ",
            "job_id": jid.group(1) if jid else "",
            "title": _clean(re.sub(r"<[^>]+>", "", t.group(1))),
            "company": _clean(re.sub(r"<[^>]+>", "", c.group(1))),
            "area": attrs[0] if attrs else "",
            "pay": next((a for a in attrs if "円" in a), ""),
            "employ_type": "正社員",
            "source": "",
            "snippet": _clean(re.sub(r"<[^>]+>", " ", sn.group(1))) if sn else "",
            "is_new": "new-label" in seg,
        })
    return out


def stanby_count(body: str):
    m = re.search(r"([\d,]+)\s*件", body)
    return int(m.group(1).replace(",", "")) if m else None


# --------------------------------------------------------------------------
def collect(query: str, prefecture: str = "", max_pages: int = 3,
            within_24h: bool = False, media=("kyujinbox", "stanby")) -> list:
    """1クエリ×1地域を両媒体から収集する。"""
    rows = []
    if "kyujinbox" in media:
        for pg in range(1, max_pages + 1):
            body = get(kyujinbox_url(query, prefecture, pg, within_24h=within_24h))
            if not body:
                break
            cards = parse_kyujinbox(body)
            if not cards:
                break
            rows.extend(cards)
            if len(cards) < 20:      # 最終ページ
                break
    if "stanby" in media and not within_24h:
        for pg in range(1, max_pages + 1):
            body = get(stanby_url(query, prefecture, pg))
            if not body:
                break
            cards = parse_stanby(body)
            if not cards:
                break
            rows.extend(cards)
            if len(cards) < 20:
                break
    for r in rows:
        r["query"] = query
        r["prefecture"] = prefecture
    return rows
