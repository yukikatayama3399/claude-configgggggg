# -*- coding: utf-8 -*-
"""ドメインから問い合わせフォームURLを発見する。

手順:
  1) トップページを取得し、問い合わせ系のリンクを収集
  2) 見つからなければ定番パスを総当たり
  3) 候補ページに実際に <form> があるか / 既知のフォームSaaSかを検証
  4) ついでに「営業お断り」の文言も拾う
"""
import re
import urllib.parse

from .fetch import get

CONTACT_WORDS = [
    "お問い合わせ", "お問合せ", "問い合わせ", "問合せ", "各種お問い合わせ",
    "contact", "inquiry", "enquiry", "toiawase", "otoiawase",
]
# 定番パス（上ほど当たりやすい順）
CANDIDATE_PATHS = [
    "/contact", "/contact/", "/contact.html", "/contact.php",
    "/inquiry", "/inquiry/", "/inquiry.html",
    "/contact/index.html", "/contactus", "/contact-us",
    "/otoiawase", "/toiawase", "/form", "/forms",
    "/company/contact", "/company/contact/",
    "/support/contact", "/about/contact", "/ja/contact",
]
# フォームSaaS（ページ内に出たらフォームとみなす）
FORM_SAAS = [
    "formrun.io", "docs.google.com/forms", "forms.gle", "hsforms",
    "formzu.net", "tayori.com", "satori.marketing", "shanon", "kuroco",
    "secure.form", "ssl.form", "typeform.com", "hubspot",
]
# 営業お断りの文言
NO_SALES = [
    "営業目的", "営業のお問い合わせ", "営業に関するお問い合わせ", "営業行為",
    "セールス目的", "売り込み", "勧誘目的", "営業メールはお断り",
    "営業のご連絡はお断り", "営業目的でのご連絡",
]


def _abs(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href)


def _same_site(base: str, url: str) -> bool:
    b = urllib.parse.urlparse(base).netloc.replace("www.", "")
    u = urllib.parse.urlparse(url).netloc.replace("www.", "")
    return u.endswith(b) or b.endswith(u) if u else False


def _looks_like_form(body: str) -> bool:
    low = body.lower()
    if re.search(r"<form[\s>]", low) and re.search(r"<(input|textarea)[\s>]", low):
        return True
    return any(s in low for s in FORM_SAAS)


def _no_sales(body: str) -> bool:
    return any(w in body for w in NO_SALES)


def find_contact_form(site_url: str) -> dict:
    """サイトURLから問い合わせフォームURLを探す。

    戻り値: {"form_url": str|"", "no_sales": "お断り明記"|"可"|"不明", "checked": int}
    """
    result = {"form_url": "", "no_sales": "不明", "checked": 0}
    if not site_url:
        return result
    if not site_url.startswith("http"):
        site_url = "https://" + site_url
    base = site_url.rstrip("/")

    # 1) トップページからリンクを拾う
    home = get(base)
    result["checked"] += 1
    candidates = []
    if home:
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', home, re.S | re.I):
            href, text = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
            blob = (href + " " + text).lower()
            if any(w.lower() in blob for w in CONTACT_WORDS):
                u = _abs(base, href)
                if u.startswith("http") and _same_site(base, u) and u not in candidates:
                    candidates.append(u)
        if _no_sales(home):
            result["no_sales"] = "お断り明記"

    # 2) 定番パスを追加
    for p in CANDIDATE_PATHS:
        u = base + p
        if u not in candidates:
            candidates.append(u)

    # 3) 検証（上位のみ。無駄打ちを抑える）
    for u in candidates[:10]:
        body = get(u)
        result["checked"] += 1
        if not body:
            continue
        if _no_sales(body):
            result["no_sales"] = "お断り明記"
        if _looks_like_form(body):
            result["form_url"] = u
            if result["no_sales"] == "不明":
                result["no_sales"] = "可"
            return result
    return result


# --------------------------------------------------------------------------
# 会社名 → 公式サイトのドメイン解決
# --------------------------------------------------------------------------
_NG_DOMAINS = [
    "wikipedia.org", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "youtube.com", "note.com", "ameblo.jp", "hatena",
    "indeed.com", "stanby.com", "green-japan.com", "doda.jp", "mynavi.jp",
    "rikunabi.com", "en-japan.com", "type.jp", "wantedly.com", "bizreach",
    "jobmedley", "job-medley", "kyujinbox", "baitoru.com", "townwork.net",
    "hellowork", "openwork.jp", "engage-jp", "en-gage.net", "levtech",
    "recruit.co.jp", "mynavi-agent", "google.com", "yahoo.co.jp",
    "prtimes.jp", "alarmbox.jp", "houjin.jp", "baseconnect.in", "musubu.in",
    "salesnow.jp", "ullet.com", "buffett-code", "job.rikunabi",
]
_PREF_TLD = [".co.jp", ".jp", ".com", ".inc", ".net", ".io"]


def _ddg(query: str) -> list:
    """DuckDuckGo の HTML 版で検索し、結果URLを返す（APIキー不要）。"""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    body = get(url)
    if not body:
        return []
    out = []
    for m in re.finditer(r'href="(https?://[^"]+)"', body):
        u = urllib.parse.unquote(m.group(1))
        # DDG のリダイレクタを剥がす
        rm = re.search(r"uddg=([^&]+)", u)
        if rm:
            u = urllib.parse.unquote(rm.group(1))
        if u.startswith("http") and "duckduckgo.com" not in u:
            out.append(u)
    return out


def resolve_domain(company: str) -> str:
    """会社名から公式サイトURLを推定する。見つからなければ空文字。"""
    if not company or company in ("非公開", "不明"):
        return ""
    for q in (f"{company} 公式サイト", f"{company} 会社概要"):
        for u in _ddg(q)[:25]:
            host = urllib.parse.urlparse(u).netloc.lower()
            if not host or any(ng in host for ng in _NG_DOMAINS):
                continue
            if not any(host.endswith(t) or t in host for t in _PREF_TLD):
                continue
            return f"https://{host}/"
    return ""
