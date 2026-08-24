# -*- coding: utf-8 -*-
"""収集した行を、作業者が入力するタブへ投入する。

これまでは
    全リスト →(数式) フォーム送信用 →(IMPORTRANGE) _取込元 →【手作業でコピー】→ 作業タブ
だった経路の、最後の手作業を置き換える。

守ること:
  * 作業タブは実データのまま。数式化しない（数式にすると H/I に手入力できない）。
  * 既存行は絶対に触らない。H列「入力状況」と I列「担当者」は人のもの。
  * 追加は末尾追記のみ。並べ替えると入力済みの H/I が行からずれる。
"""
import argparse
import re
import sys

from . import config, sheets

# フォーム送信用のA1数式が持っていた絞り込み条件と同じもの
def qualifies(row: dict) -> bool:
    if not row["会社名"].strip():
        return False
    if not re.match(r"^https?://", row["フォームURL"].strip()):
        return False
    if row["営業お断り"].strip() == "お断り明記":
        return False
    return True


def _column(tab: str, idx: int, sid: str) -> set:
    """指定タブの指定列から、正規化した企業名の集合を作る。"""
    try:
        rows = sheets.read(tab, "A1:H20000", spreadsheet_id=sid)
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] {tab} を読めなかった: {e}")
        return set()
    out = set()
    for r in rows[1:]:
        if len(r) > idx and str(r[idx]).strip():
            out.add(sheets.norm_company(str(r[idx])))
    return out


def contacted() -> set:
    """接触済み・接触禁止の企業名（正規化済み）をまとめて集める。"""
    names = set()
    for tab, idx in config.CONTACTED_SOURCES:
        got = _column(tab, idx, config.EXCLUDE_SPREADSHEET_ID)
        print(f"  除外元 {tab:24s} {len(got):5d} 件")
        names |= got
    return names


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="1回に投入する上限（0=無制限）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    src = sheets.read(config.TAB_ALL, "A1:O5000")
    header, data = src[0], src[1:]
    rows = [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in data]
    print(f"全リスト {len(rows)} 行")

    work = sheets.read(config.WORK_TAB, "A1:O20000",
                       spreadsheet_id=config.WORK_SPREADSHEET_ID)
    work_names = {sheets.norm_company(r[1]) for r in work[1:] if len(r) > 1 and r[1].strip()}
    print(f"作業タブ {len(work_names)} 社が既に入っている")

    ng_names = contacted()
    ng_domains = sheets.excluded_domains()
    print(f"接触済み企業名 {len(ng_names)} 件 / 除外ドメイン {len(ng_domains)} 件")

    seen, out, stats = set(work_names), [], {"未通過": 0, "接触済み": 0, "重複": 0}
    for r in rows:
        if not qualifies(r):
            stats["未通過"] += 1
            continue
        key = sheets.norm_company(r["会社名"])
        if key in seen:
            stats["重複"] += 1
            continue
        if key in ng_names or sheets.domain(r["サイトURL"]) in ng_domains:
            stats["接触済み"] += 1
            continue
        seen.add(key)
        # H列・I列は空のまま渡す。人が埋める列なので機械は書かない。
        out.append([r.get(c, "") if c not in ("入力状況", "担当者", "送信日時") else ""
                    for c in header])

    print(f"内訳: 条件未通過 {stats['未通過']} / 接触済み {stats['接触済み']} / 重複 {stats['重複']}")
    print(f"投入対象 {len(out)} 行")
    if a.limit:
        out = out[:a.limit]
        print(f"今回は {len(out)} 行に制限")

    if not out:
        print("投入なし。終了。")
        return 0
    if a.dry_run:
        for r in out[:15]:
            print("  DRY", r[0], r[1], "|", r[3][:48])
        return 0

    n = sheets.append(config.WORK_TAB, out, spreadsheet_id=config.WORK_SPREADSHEET_ID)
    print(f"✅ 作業タブに {n} 行を追記（H列・I列は空のまま）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
