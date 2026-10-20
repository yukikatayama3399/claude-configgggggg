#!/usr/bin/env python3
"""営業リスト × 除外リストの毎朝チェック（読み取り専用）。

「SNS広告求人リスト×除外リスト 毎朝チェック」Routine の本体。
以前は Google Drive コネクタの read_file_content でシート全体をテキスト化して
読んでいたが、シートが肥大化（全リスト / リスト元データ_backup / _除外ドメイン が
各1.2〜1.3万行）してから各タブ先頭数行の要約しか返らなくなり、毎朝「完遂できず」に
なっていた。必要なタブだけを gws で直接読む方式に置き換えたもの。

照合ロジックは sync_new_rows.py と同じ company_match.py を使う（取込時と判定を揃える）。
シートには一切書き込まない。

使い方:
    python3 check_exclusions.py          # 全行チェック
    python3 check_exclusions.py --days 3 # 「直近追加」とみなす日数（既定3）

終了コード: 0 = ヒットなし / 1 = ヒット・要確認あり / 2 = 読み取り失敗
"""

import argparse
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_match import Exclusion, domain, key, load_extra  # noqa: E402
from sync_new_rows import (  # noqa: E402
    EXCLUDE_SHEET_ID, EXTRA_EXCLUDE_FILE, WORK_SHEET_ID,
    SyncError, get_values, gws, SPREADSHEET_ID,
)

# 過去の一括クリーニングの記録（ヘッダー「元の行番号|会社名|分類|理由|サイトURL」の表）
CLEANING_LOG_SHEET_ID = 1783640395

# 名前に含まれていたらグループ会社の疑いとして「要確認」に出す共通グループ名。
# 除外リスト側にも同じ語を含む社名がある場合だけ出す。
GROUP_WORDS = [
    "パーソル", "電通", "博報堂", "gmo", "サイバーエージェント", "リクルート", "楽天",
    "ソフトバンク", "nttデータ", "ntt", "kddi", "ヤフー", "lineヤフー", "パナソニック",
    "ソニー", "トランスコスモス", "アドウェイズ", "セプテーニ", "オプト", "デジタルホールディングス",
    "carta", "d2c", "ベクトル", "マイナビ", "ディップ", "エン・ジャパン",
]

# Exclusion.hit の理由 → 確度
CERTAINTY = [
    ("完全一致(表記ゆれ含む)", "同一法人"),
    ("同一法人(拠点・部署付き表記)", "同一法人"),
    ("個別指定", "同一法人/グループ（個別指定）"),
    ("同一グループ", "グループ疑い"),
    ("法人格違い", "要確認"),
    ("社名の一部が一致", "要確認"),
]


def titles():
    got = gws("sheets", "spreadsheets", "get",
              params={"spreadsheetId": SPREADSHEET_ID, "fields": "sheets(properties(sheetId,title))"})
    by_id = {s["properties"]["sheetId"]: s["properties"]["title"] for s in got.get("sheets", [])}
    for sid in (WORK_SHEET_ID, EXCLUDE_SHEET_ID):
        if sid not in by_id:
            raise SyncError(f"sheetId {sid} のタブが見つかりません（削除された可能性）")
    return by_id


def q(t):
    return "'" + t.replace("'", "''") + "'"


def serial_to_date(v):
    """取得日はシリアル値（1899-12-30 起点）と文字列が混在している。"""
    if isinstance(v, (int, float)) and 30000 < v < 80000:
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", str(v or ""))
    if m:
        return dt.date(*map(int, m.groups()))
    return None


def read_exclusion(sheet):
    """除外リスト本体（B列）と、右側サブ表で「除外対象」=TRUE の会社名を返す。"""
    rows = get_values(q(sheet), "A1:Z")
    names = [str(r[1]).strip() for r in rows[1:] if len(r) > 1 and str(r[1]).strip()]
    if len(names) < 100:
        raise SyncError(f"除外リストから {len(names)}社しか読めません（壊れている可能性）")
    # サブ表: どこかの行に「除外対象」と「会社名」の両方があるヘッダーがある
    sub = []
    for i, r in enumerate(rows):
        cells = [str(c).strip() for c in r]
        if "除外対象" in cells and "会社名" in cells:
            flag_col, name_col = cells.index("除外対象"), cells.index("会社名")
            for rr in rows[i + 1:]:
                if len(rr) > name_col and rr[flag_col] is True and str(rr[name_col]).strip():
                    sub.append(str(rr[name_col]).strip())
            break
    return names, sub


def read_past(sheet):
    """過去チェックで除外該当と判定済みの {社名: 分類/理由}。重複扱いの行は除く。"""
    past = {}
    rows = get_values(q(sheet), "A1:E")
    in_table = False
    for r in rows:
        cells = [str(c).strip() for c in r] + [""] * 5
        if cells[0] == "元の行番号" and cells[1] == "会社名":
            in_table = True
            continue
        if not in_table or not cells[1] or cells[2] in ("", "重複", "分類"):
            continue
        past.setdefault(cells[1], f"{cells[2]} / {cells[3]}")
    return past


def read_targets(sheet, label):
    """会社名(B)・URL(C)・取得日(G) を持つ行を返す。ヘッダー行は飛ばす。"""
    out = []
    for i, r in enumerate(get_values(q(sheet), "A1:O"), start=1):
        r = list(r) + [""] * 15
        name = str(r[1]).strip()
        if not name or name == "会社名":
            continue
        out.append({"src": label, "row": i, "name": name, "url": str(r[2]).strip(),
                    "date": serial_to_date(r[6])})
    return out


def group_suspect(name, excl_names):
    k = key(name)
    for w in GROUP_WORDS:
        wk = key(w)
        if wk and wk in k:
            for e in excl_names:
                if wk in key(e):
                    return w, e
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="直近追加とみなす日数")
    a = ap.parse_args()

    t = titles()
    excl, sub = read_exclusion(t[EXCLUDE_SHEET_ID])
    extra = load_extra(EXTRA_EXCLUDE_FILE)
    exclusion = Exclusion(excl + sub, extra)
    past = read_past(t[CLEANING_LOG_SHEET_ID]) if CLEANING_LOG_SHEET_ID in t else {}
    past_keys = {key(n): (n, why) for n, why in past.items()}

    # 取込元(_取込元_SNS広告求人)は見ない。除外該当は sync_new_rows.py が取込時に落とすので
    # 取込元に残り続け、毎朝同じ社名が「該当」に出るだけになる。営業をかけるのは注力タブ。
    targets = read_targets(t[WORK_SHEET_ID], "注力")
    if not targets:
        raise SyncError("対象リストから1行も読めませんでした")

    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    recent_from = today - dt.timedelta(days=a.days)

    hits = []
    for r in targets:
        h = exclusion.hit(r["name"])
        if h:
            why, src = h
            cert = next((c for p, c in CERTAINTY if why.startswith(p)), "要確認")
            hits.append((cert, r, f"{why} / 除外「{src}」"))
            continue
        pk = past_keys.get(key(r["name"]))
        if pk:
            hits.append(("要確認（過去チェックで除外該当）", r, pk[1]))
            continue
        g = group_suspect(r["name"], excl + sub + list(extra))
        if g:
            hits.append(("要確認（グループ疑い）", r, f"「{g[0]}」系 / 除外「{g[1]}」"))

    # 対象リスト内の重複（社名キー・ドメイン）。注力タブ内だけを見る
    dups, by_key, by_dom = [], {}, {}
    for r in (x for x in targets if x["src"] == "注力"):
        k, d = key(r["name"]), domain(r["url"])
        if k in by_key:
            dups.append((by_key[k], r, "社名"))
        elif d and d in by_dom:
            dups.append((by_dom[d], r, f"ドメイン {d} "))
        by_key.setdefault(k, r)
        if d:
            by_dom.setdefault(d, r)

    is_new = lambda r: bool(r["date"] and r["date"] >= recent_from)  # noqa: E731
    print(f"チェック対象: 注力タブ {len(targets)}社（うち取得日が直近{a.days}日 "
          f"{sum(map(is_new, targets))}社）")
    print(f"照合先: 除外リスト {len(excl)}社 + 除外対象サブ表 {len(sub)}社"
          f" + 個別指定 {len(extra)}社 + 過去チェック {len(past)}社")

    if not hits and not dups:
        print("除外リスト該当なし・重複なし")
        return 0

    order = {"同一法人": 0, "同一法人/グループ（個別指定）": 1, "グループ疑い": 2}
    hits.sort(key=lambda h: (order.get(h[0], 3), h[1]["row"]))
    fresh = [h for h in hits if is_new(h[1])]
    old = [h for h in hits if not is_new(h[1])]
    print(f"\n■ 直近{a.days}日の追加分で除外リスト該当・要確認 {len(fresh)}件")
    for cert, r, why in fresh:
        print(f"- [{cert}] {r['name']}（{r['row']}行目・取得日 {r['date']}） … {why}")
    if old:
        # 以前からある行は毎朝同じものが出るので1行ずつ短く
        print(f"\n■ 以前からある行の該当・要確認 {len(old)}件（前日までと同じなら対応不要）")
        for cert, r, why in old:
            print(f"- [{cert}] {r['name']}（{r['row']}行目） … {why}")
    if dups:
        print(f"\n■ 注力タブ内の重複 {len(dups)}件")
        for a_, b_, how in dups:
            print(f"- {b_['name']}（{b_['row']}行目）= {a_['name']}（{a_['row']}行目） … {how}一致")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SyncError as e:
        print(f"中止: {e}", file=sys.stderr)
        sys.exit(2)
