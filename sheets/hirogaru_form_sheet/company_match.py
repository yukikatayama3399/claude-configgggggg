#!/usr/bin/env python3
"""会社名の正規化と除外リスト照合。

除外リスト（既存顧客・お断り先）との突き合わせを、単純な文字列一致ではなく
表記ゆれを吸収した上で行う。スプレッドシート側の COUNTIF は完全一致しか見ないので、
「株式会社電通デジタル 港区」「パナソニックコネクト株式会社」「ADKマーケティング・ソリューションズ」
のような表記は素通りしてしまう。既存顧客に営業メールを送るのが一番まずいので、
取込の直前にこちらで判定する。

**方針は「迷ったら落とす」**。既存顧客に1通送る損害のほうが、見込み客1社を
落とす損害より大きい、という運用判断（2026-08-24 に確認）。判定は5段階で、
どれかに当たれば取込まない。

  1. 完全一致       … 正規化して一致（全角半角・スペース・ハイフン・法人格の差を吸収）
  2. 拠点・部署付き … 空白の前が一致し、後ろが「港区」「本部」「採用」等
  3. グループ表記   … 末尾の「グループ」「ホールディングス」を落とすと一致
  4. 法人格違い     … 正規化後は同名だが 株式会社 / 合同会社 が違う（別法人の可能性でも落とす）
  5. 社名の一部一致 … 空白の前だけが一致（株式会社LiB と 株式会社Lib Work のような形）

4と5は「別会社かもしれない」ケースなので、以前は通していた。当たると危ないので
落とす側に変えた。通したい社名が出てきたら `EXEMPT` に足す。

社名変更・親子会社は文字列では判定できないので `exclude_extra.tsv` に社名と理由を
書いて足す（除外リスト本体＝顧客マスタは触らない）。
"""

import os
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
# 判定4・5で落としたくない社名（別会社だと確認できたもの）を key() 済みで置く。
# 今は空。落としすぎて困る社名が出たらここに足す。
EXEMPT = set()


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


def load_extra(path):
    """exclude_extra.tsv（社名 <TAB> 理由）を読む。無ければ空。"""
    extra = {}
    if not os.path.exists(path):
        return extra
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            name, _, reason = line.partition("\t")
            if name.strip():
                extra[name.strip()] = reason.strip() or "個別指定"
    return extra


class Exclusion:
    """除外リストの社名を受け取り、照合できるようにする。

    names … 除外リストタブ(B列)の社名。extra … exclude_extra.tsv の {社名: 理由}。
    """

    def __init__(self, names, extra=None):
        self.exact, self.group, self.manual = {}, {}, {}
        for n in names:
            n = str(n).strip()
            if n:
                self.exact.setdefault(key(n), n)
                self.group.setdefault(key_nogroup(n), n)
        for n, reason in (extra or {}).items():
            n = str(n).strip()
            if n:
                self.manual.setdefault(key(n), (n, reason))

    def hit(self, name):
        """除外すべきなら (理由, 除外リスト上の社名) を返す。該当しなければ None。"""
        k = key(name)
        # 個別指定は「絶対に当たらない」ためのリストなので、拠点・部署付きの表記も拾う
        for cand in (k, key(head(name))):
            if cand in self.manual:
                src, reason = self.manual[cand]
                return f"個別指定({reason})", src
        if k in self.exact:
            src = self.exact[k]
            if legal_type(name) and legal_type(src) and legal_type(name) != legal_type(src):
                if k in EXEMPT:
                    return None
                # 株式会社 と 合同会社 など。別法人かもしれないが、当たると危ないので落とす
                return "法人格違いの完全一致(迷ったら落とす)", src
            return "完全一致(表記ゆれ含む)", src
        h = head(name)
        if h != nfkc(name) and key(h) in self.exact:
            rest = nfkc(name)[len(h):].strip()
            for lg, _ in LEGAL_TYPE:
                rest = rest.replace(nfkc(lg), "")
            if rest.strip() == "" or BRANCH_RE.search(rest.strip()):
                return "同一法人(拠点・部署付き表記)", self.exact[key(h)]
            if k in EXEMPT:
                return None
            # 「Lib Work」「Blue Zone」のように社名の一部が一致するだけ。
            # 別会社の可能性が高いが、当たると危ないので落とす
            return "社名の一部が一致(迷ったら落とす)", self.exact[key(h)]
        g = key_nogroup(name)
        if g != k and g in self.group:
            return "同一グループ(グループ/ホールディングス表記)", self.group[g]
        return None
