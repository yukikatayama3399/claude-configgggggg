# -*- coding: utf-8 -*-
"""既存行のエンリッチ（① 手持ちストックの回収 ＋ 新規収集行の後処理）。

2段階:
  domain … サイトURLが空の行に、会社名から公式サイトを解決して埋める
  form   … サイトURLはあるがフォームURLが未特定の行に、フォームURLを埋める

見つからなければ「なし」を書いて確定させ、次回以降は再試行しない
（「フォームのURLのため、ないものは仕方ない」）。

注意:
  Claude Code on the web のセッションはエージェントプロキシの egress ポリシーで
  各社サイト・検索エンジンへの CONNECT が 403 拒否される。
  このスクリプトは GitHub Actions か手元の Mac で実行すること。
"""
import argparse
import sys

from . import config, sheets
from .enrich import find_contact_form, resolve_domain

UNRESOLVED = ("", "不明", "-", "要確認")
GIVEN_UP = ("なし",)


def _col(i: int) -> str:
    return chr(ord("A") + i)


def pick_targets(rows, header, stage):
    i_url = header.index("サイトURL")
    i_form = header.index("フォームURL")
    i_name = header.index("会社名")
    out = []
    for n, r in enumerate(rows, start=2):
        r = r + [""] * (len(header) - len(r))
        site, form, name = r[i_url].strip(), r[i_form].strip(), r[i_name].strip()
        if not name or name in ("非公開", "不明"):
            continue
        has_site = site.startswith("http")
        if stage == "domain":
            if not has_site and site in UNRESOLVED:
                out.append({"row": n, "company": name, "site": ""})
        else:
            if has_site and form in UNRESOLVED:
                out.append({"row": n, "company": name, "site": site})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["domain", "form"], default="form")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    values = sheets.read(config.TAB_ALL, "A1:O5000")
    header, rows = values[0], values[1:]
    todo = pick_targets(rows, header, a.stage)
    print(f"[{a.stage}] 対象 {len(todo)} 行")
    todo = todo[a.offset:]
    if a.limit:
        todo = todo[:a.limit]
    print(f"[{a.stage}] 今回処理 {len(todo)} 行")

    exclude_dom = sheets.excluded_domains() if a.stage == "domain" else set()
    if exclude_dom:
        print(f"除外ドメイン {len(exclude_dom)} 件と突合する")
    c_pri = _col(header.index("優先度"))
    c_url = _col(header.index("サイトURL"))
    c_form = _col(header.index("フォームURL"))
    c_nos = _col(header.index("営業お断り"))

    updates, found, miss = [], 0, 0
    excluded_hits = [0]

    def flush():
        nonlocal updates
        if updates and not a.dry_run:
            sheets.batch_update(updates)
        updates = []

    for k, t in enumerate(todo, 1):
        if a.stage == "domain":
            site = resolve_domain(t["company"])
            if site:
                found += 1
                updates.append({"range": f"{config.TAB_ALL}!{c_url}{t['row']}",
                                "values": [[site]]})
                # 既に接触済み・除外済みのドメインなら優先度を「除外」にする
                dom = sheets.domain(site)
                if dom and dom in exclude_dom:
                    excluded_hits[0] += 1
                    updates.append({"range": f"{config.TAB_ALL}!{c_pri}{t['row']}",
                                    "values": [["除外"]]})
            else:
                miss += 1
        else:
            r = find_contact_form(t["site"])
            if r["form_url"]:
                found += 1
            else:
                miss += 1
            updates.append({"range": f"{config.TAB_ALL}!{c_form}{t['row']}",
                            "values": [[r["form_url"] or "なし"]]})
            if r["no_sales"] != "不明":
                updates.append({"range": f"{config.TAB_ALL}!{c_nos}{t['row']}",
                                "values": [[r["no_sales"]]]})
        if k % 25 == 0:
            print(f"  {k}/{len(todo)}  発見{found} 未発見{miss}", flush=True)
            flush()

    flush()
    msg = f"✅ [{a.stage}] 発見 {found} 件 / 未発見 {miss} 件"
    if excluded_hits[0]:
        msg += f" / うち既接触ドメインとして除外 {excluded_hits[0]} 件"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
