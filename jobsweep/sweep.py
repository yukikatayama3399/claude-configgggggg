# -*- coding: utf-8 -*-
"""SNS広告運用求人の収集本体。

モード:
  fresh   … 24時間以内の新着を全国×全クエリで拾う（毎時実行向け）
  region  … 都道府県ローテーション（東京・大阪は最後）
  backfill… 指定都道府県を深掘り

品質ゲートは relevance.classify のみ。優先度(S/A/B)は判定に使わない。
"""
import argparse
import collections
import datetime
import sys

from . import config, sources, sheets
from .relevance import classify
from .enrich import resolve_domain, find_contact_form

TIER_TO_PRIORITY = {"strong": "A", "medium": "B"}


def _today() -> str:
    return datetime.date.today().isoformat()


def rotation_slice(n_per_run: int = 3, seed_hour: int = None) -> list:
    """実行時刻から都道府県のスライスを決める（状態ファイル不要）。"""
    now = datetime.datetime.utcnow()
    tick = now.timetuple().tm_yday * 24 + (seed_hour if seed_hour is not None else now.hour)
    prefs = config.PREFECTURES
    start = (tick * n_per_run) % len(prefs)
    out = []
    for i in range(n_per_run):
        out.append(prefs[(start + i) % len(prefs)])
    return out


def harvest(queries, prefectures, max_pages, within_24h=False) -> list:
    """収集してゲートを通す。"""
    kept = []
    for pref in (prefectures or [""]):
        for q in queries:
            rows = sources.collect(q, pref, max_pages=max_pages, within_24h=within_24h)
            n_ok = 0
            for r in rows:
                c = classify(r["title"], r.get("snippet", ""), r.get("employ_type", ""))
                if c["tier"] not in ("strong", "medium"):
                    continue
                r["tier"] = c["tier"]
                r["tier_reason"] = c["reason"]
                kept.append(r)
                n_ok += 1
            label = pref or "全国"
            print(f"  {label:5s} / {q:14s} : 取得{len(rows):4d} → 採用{n_ok:3d}")
    return kept


def dedupe(rows: list, keys: dict, excluded: set = None) -> list:
    """既存シート・除外リスト・バッチ内での重複を除く。"""
    seen_company = set(keys["companies"])
    excluded = excluded or set()
    out = []
    for r in rows:
        if r["company"] in ("", "非公開", "不明"):
            continue
        key = sheets.norm_company(r["company"])
        if not key or key in seen_company or key in excluded:
            continue
        seen_company.add(key)
        out.append(r)
    return out


def build_rows(records: list, counts: dict, resolve: bool) -> list:
    """全リストのスキーマに合わせて行を作る。"""
    today = _today()
    out = []
    for r in records:
        site, form, no_sales = "", "不明", "不明"
        if resolve:
            site = resolve_domain(r["company"])
            if site:
                f = find_contact_form(site)
                form = f["form_url"] or "不明"
                no_sales = f["no_sales"]
        n = counts.get(sheets.norm_company(r["company"]), 1)
        signal = f"同時{n}求人" if n > 1 else ""
        biko = (f"媒体:{r['media']}"
                + (f"｜掲載元:{r['source']}" if r.get("source") else "")
                + f"｜判定:{r['tier']}({r['tier_reason']})"
                + "｜自動スイープ")
        out.append([
            TIER_TO_PRIORITY.get(r["tier"], "B"),  # 優先度（ゲートではない）
            r["company"],
            site,
            form,
            "不明",                                  # Eメール
            no_sales,
            today,
            "",                                      # 入力状況
            "",                                      # 送信日時
            "",                                      # 種別
            r["title"],
            signal,
            r.get("area", ""),
            r.get("query", ""),
            biko,
        ])
    return out


def ledger_rows(records: list) -> list:
    today = _today()
    return [[today, r["company"], r["media"], r["title"], today] for r in records]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["fresh", "region", "backfill"], default="fresh")
    ap.add_argument("--prefectures", default="", help="カンマ区切り。backfill用")
    ap.add_argument("--per-run", type=int, default=3, help="1実行あたりの都道府県数")
    ap.add_argument("--max-pages", type=int, default=0, help="0なら設定値")
    ap.add_argument("--no-resolve", action="store_true",
                    help="ドメイン/フォーム解決をスキップ（媒体だけ回す）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    if a.mode == "fresh":
        prefs, pages, fresh = [""], a.max_pages or config.MAX_PAGES_FRESH, True
    elif a.mode == "region":
        prefs = rotation_slice(a.per_run)
        pages, fresh = a.max_pages or config.MAX_PAGES_REGION, False
    else:
        prefs = [p.strip() for p in a.prefectures.split(",") if p.strip()]
        pages, fresh = a.max_pages or config.MAX_PAGES_REGION, False

    print(f"=== mode={a.mode} 対象={prefs} pages={pages} ===")
    records = harvest(config.CORE_QUERIES, prefs, pages, within_24h=fresh)
    print(f"ゲート通過 {len(records)} 件（重複前）")

    counts = collections.Counter(sheets.norm_company(r["company"]) for r in records)
    keys = sheets.existing_keys()
    excluded = sheets.excluded_companies()
    print(f"除外リスト(企業名) {len(excluded)} 件と突合")
    fresh_records = dedupe(records, keys, excluded)
    print(f"既存・除外を差し引いた純増 {len(fresh_records)} 件")

    if not fresh_records:
        print("純増なし。終了。")
        return 0

    rows = build_rows(fresh_records, counts, resolve=not a.no_resolve)
    if a.dry_run:
        for r in rows[:20]:
            print("  DRY", r[:3], r[10][:40])
        print(f"(dry-run) {len(rows)} 行を追記するはずだった")
        return 0

    n = sheets.append(config.TAB_ALL, rows)
    sheets.append(config.TAB_LEDGER, ledger_rows(fresh_records))
    print(f"✅ 全リストに {n} 行追記")
    return 0


if __name__ == "__main__":
    sys.exit(main())
