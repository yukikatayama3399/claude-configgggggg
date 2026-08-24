#!/usr/bin/env python3
"""会社名の正規化と除外リスト照合。

除外リスト（既存顧客・お断り先）との突き合わせを、単純な文字列一致ではなく
表記ゆれを吸収した上で行う。スプレッドシート側の COUNTIF は完全一致しか見ないので、
「株式会社電通デジタル 港区」「パナソニックコネクト株式会社」「ADKマーケティング・ソリューションズ」
のような表記は素通りしてしまう。既存顧客に営業メールを送るのが一番まずいので、
取込の直前にこちらで判定する。

判定は3段階。いずれも「同一法人・同一グループとみなす」＝取込まない。
  1. 完全一致       … 正規化して一致（全角半角・スペース・ハイフン・法人格の差を吸収）
  2. 拠点・部署付き … 空白の前が一致し、後ろが「港区」「本部」「採用」等
  3. グループ表記   … 末尾の「グループ」「ホールディングス」を落とすと一致

似ているだけの別会社（株式会社LiB と 株式会社Lib Work など）は落とさない。
"""

import re
import unicodedata
from urllib.parse import urlparse

DASHES = "‐‑‒–—―−﹣－"
LEGAL = [
    "株式会社", "有限会社", "合同会社", "合資会社", "合名会社", "相互会社",
    "一般社団法人", "一般財団法人", "公益社団法人", "公益財団法人",
    "特定非営利活動法人", "医療法人", "学校法人", "社会福祉法人", "独立行政法人",
    "(株)", "㈱", "(有)", "㈲",
]
TAIL_NOISE = ["グループ", "ホールディングス", "group", "holdings", "hd"]
# 空白の後ろがこれなら「同じ法人の拠点・部署表記」とみなす
BRANCH_RE = re.compile(
    r"^[~〜【\(]|^(.*?[都道府県市区町村])$|"
    r"(本部|事業部|事業統括|統括|本社|支社|支店|営業所|カンパニー|グループ|部|課|室|"
    r"採用|中途|新卒|求人|募集|センター|エンジニア)"
)
LEGAL_TYPE = [
    ("合同会社", "合同"), ("有限会社", "有限"), ("合資会社", "合資"), ("合名会社", "合名"),
    ("一般社団法人", "社団"), ("一般財団法人", "財団"), ("株式会社", "株"), ("(株)", "株"), ("㈱", "株"),
]


def nfkc(s):
    s = unicodedata.normalize("NFKC", "" if s is None else str(s))
    for d in DASHES:
        s = s.replace(d, "-")
    return s.replace("・", "").replace("／", "/").replace("&", "and").strip()


def key(s):
    """比較用キー。空白・法人格・記号を落として小文字化する。"""
    s = re.sub(r"\s+", "", nfkc(s))
    for lg in LEGAL:
        s = s.replace(nfkc(lg), "")
    for ch in "-_.,'’ʼ":
        s = s.replace(ch, "")
    return s.lower()


def key_nogroup(s):
    """末尾の グループ / ホールディングス を落としたキー。"""
    k = key(s)
    changed = True
    while changed:
        changed = False
        for t in TAIL_NOISE:
            if len(k) > len(t) + 1 and k.endswith(t):
                k, changed = k[: -len(t)], True
    return k


def head(s):
    """原文の最初の空白より前（部署名・拠点名を切り落とす）。"""
    return re.split(r"\s+", nfkc(s))[0]


def legal_type(s):
    s = nfkc(s)
    for k, v in LEGAL_TYPE:
        if nfkc(k) in s:
            return v
    return ""


def domain(url):
    u = nfkc(url).lower()
    if not u:
        return ""
    if not u.startswith("http"):
        u = "http://" + u
    try:
        host = urlparse(u).netloc.split(":")[0]
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    # 「不明」「要確認」のような非URLを弾く
    return host if re.fullmatch(r"[a-z0-9][a-z0-9.\-]*\.[a-z]{2,}", host) else ""


class Exclusion:
    """除外リストの社名を受け取り、照合できるようにする。"""

    def __init__(self, names):
        self.exact, self.group = {}, {}
        for n in names:
            n = str(n).strip()
            if n:
                self.exact.setdefault(key(n), n)
                self.group.setdefault(key_nogroup(n), n)

    def hit(self, name):
        """除外すべきなら (理由, 除外リスト上の社名) を返す。該当しなければ None。"""
        k = key(name)
        if k in self.exact:
            src = self.exact[k]
            if legal_type(name) and legal_type(src) and legal_type(name) != legal_type(src):
                return None  # 株式会社 と 合同会社 など。別法人の可能性があるので落とさない
            return "完全一致(表記ゆれ含む)", src
        h = head(name)
        if h != nfkc(name) and key(h) in self.exact:
            rest = nfkc(name)[len(h):].strip()
            for lg, _ in LEGAL_TYPE:
                rest = rest.replace(nfkc(lg), "")
            if rest.strip() == "" or BRANCH_RE.search(rest.strip()):
                return "同一法人(拠点・部署付き表記)", self.exact[key(h)]
            return None  # 「Lib Work」「Blue Zone」のように社名の一部が一致するだけ
        g = key_nogroup(name)
        if g != k and g in self.group:
            return "同一グループ(グループ/ホールディングス表記)", self.group[g]
        return None
