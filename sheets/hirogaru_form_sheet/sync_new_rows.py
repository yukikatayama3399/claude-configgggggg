#!/usr/bin/env python3
"""自動追加中リスト_SNS広告求人 の新着取込。

_取込元_SNS広告求人（IMPORTRANGE+FILTER の生データ）と作業シートを会社名で突き合わせ、
未取込の行だけを追記する。追記するのは A:G と J:O だけで、
H列(入力状況) / I列(送信日時) には一切書かないので、外部作業者の入力が消えたりズレたりしない。

追記の前に必ず除外リスト（既存顧客・お断り先）と照合する。取込元の FILTER も
除外リストを見ているが COUNTIF の完全一致なので、「株式会社電通デジタル 港区」
「パナソニックコネクト株式会社」のような表記ゆれが素通りする。既存顧客に営業を
かけるのが一番まずいので、company_match.py の正規化照合でもう一段落とす。
重複判定も社名の正規化キーとドメインの両方で見る。

依存: gws (Google Workspace CLI) が PATH にあり認証済みであること。
使い方:
    python3 sync_new_rows.py            # 実行
    python3 sync_new_rows.py --dry-run  # 追記せず件数だけ表示
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_match import Exclusion, domain, load_extra  # noqa: E402
from company_match import key as company_key  # noqa: E402

SPREADSHEET_ID = "1gYL-_-rM52JrWEtsL-Cx-Wv4BPjS49qg9g_n2xq8WqQ"
# タブは名前ではなく sheetId で指す。名前は実際に変わった
# (自動追加中リスト_SNS広告求人 → 注力_最新SNS広告求人(自動追加))ので、
# 名前で参照すると改名のたびに同期が止まる。
WORK_SHEET_ID = 892888463
RAW_SHEET_ID = 1963927632
# 除外リスト（既存顧客・お断り先）。B列が社名。
EXCLUDE_SHEET_ID = 785706625
EXCLUDE_KEY_COL = "B"
# 除外リストには無いが取込んではいけない社名（社名変更・親子会社など）。
# 顧客マスタを書き換えたくないのでリポジトリ側で持つ。
EXTRA_EXCLUDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exclude_extra.tsv")

# 取込元の列構成。ここが変わったら追記せず中止する。
EXPECTED_HEADER = [
    "優先度", "会社名", "サイトURL", "フォームURL", "Eメール", "営業お断り", "取得日",
    "入力状況", "送信日時", "種別", "求人タイトル", "シグナル", "勤務地", "検索クエリ", "備考",
]

KEY_COL = 2   # B列 = 会社名（重複判定キー）
URL_COL = 3   # C列 = サイトURL（ドメインでの重複判定に使う）
LAST_COL = 15  # O列まで
# 追記する列ブロック [開始列, 終了列]。H(8)・I(9) は意図的に除外している。
WRITE_BLOCKS = [(1, 7), (10, 15)]

CHUNK = 100   # 1回の書込行数（gws の引数長上限を避けるため分割する）
ERROR_MARKERS = ("#REF!", "#N/A", "#ERROR!", "#VALUE!", "#NAME?", "Loading...")


class SyncError(RuntimeError):
    pass


def gws(*args, params=None, body=None):
    cmd = ["gws", *args]
    if params is not None:
        cmd += ["--params", json.dumps(params, ensure_ascii=False)]
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    head = proc.stdout.split("error[api]")[0].strip()
    try:
        data = json.loads(head) if head else {}
    except json.JSONDecodeError:
        raise SyncError(f"gws の出力を解釈できません: {proc.stdout[:300]} {proc.stderr[:300]}")
    if "error" in data:
        raise SyncError(f"API エラー: {data['error'].get('message', data['error'])}")
    if proc.returncode != 0 and not data:
        raise SyncError(f"gws が失敗しました (rc={proc.returncode}): {proc.stderr[:300]}")
    return data


def col_letter(n):
    s = ""
    while n > 0:
        n, m = divmod(n - 1, 26)
        s = chr(65 + m) + s
    return s


def sheet_titles():
    """sheetId -> タイトルの対応を引く。改名に追従するため毎回引き直す。"""
    got = gws(
        "sheets", "spreadsheets", "get",
        params={"spreadsheetId": SPREADSHEET_ID, "fields": "sheets(properties(sheetId,title))"},
    )
    by_id = {s["properties"]["sheetId"]: s["properties"]["title"] for s in got.get("sheets", [])}
    for sid in (WORK_SHEET_ID, RAW_SHEET_ID, EXCLUDE_SHEET_ID):
        if sid not in by_id:
            raise SyncError(f"sheetId {sid} のタブが見つかりません（削除された可能性）")
    return by_id


def get_values(sheet, a1):
    # UNFORMATTED_VALUE: 日付シリアル等を数値のまま読む。表示文字列で読むと
    # 書き戻したとき数値が文字列に化けて型が混ざる。
    got = gws(
        "sheets", "spreadsheets", "values", "get",
        params={
            "spreadsheetId": SPREADSHEET_ID,
            "range": f"{sheet}!{a1}",
            "valueRenderOption": "UNFORMATTED_VALUE",
        },
    )
    return got.get("values", [])


def pad(row):
    return [("" if c is None else c) for c in row] + [""] * (LAST_COL - len(row))


def norm(v):
    return "".join(str("" if v is None else v).split())


def read_raw(sheet):
    """取込元を読む。壊れた取込（#REF! / 読込中 / 空）なら例外を投げて追記させない。"""
    rows = [pad(r)[:LAST_COL] for r in get_values(sheet, f"A1:{col_letter(LAST_COL)}")]
    if not rows:
        raise SyncError(f"{sheet} が空です（IMPORTRANGE の数式が消えた可能性）")
    for row in rows[:5]:
        for cell in row:
            if str(cell).strip() in ERROR_MARKERS:
                raise SyncError(f"{sheet} が {cell} 状態です。取込を中止しました")
    assert_header(rows[0], sheet)
    # 有効行 0 件は異常ではない。取込元は FILTER で既出企業を落とすので、
    # 全部処理済みならヘッダーだけになる。ここで落とすと定期実行が毎回
    # 誤警報を出すので、空リストを返して「新着なし」に合流させる。
    return [r for r in rows[1:] if norm(r[KEY_COL - 1])]


def read_exclusion(sheet):
    """除外リストの社名を読む。空なら異常なので止める（全通しになるのを防ぐ）。"""
    rows = get_values(sheet, f"{EXCLUDE_KEY_COL}1:{EXCLUDE_KEY_COL}")
    names = [str(r[0]).strip() for r in rows if r and str(r[0]).strip()]
    names = [n for n in names if n not in ("企業名", "会社名")]
    if len(names) < 100:
        raise SyncError(
            f"{sheet} から読めた社名が {len(names)}件しかありません。"
            "除外リストが壊れている可能性があるので取込を中止しました"
        )
    return names


def read_work(sheet):
    """作業シートの既存キー・既存ドメイン・社数・最終データ行を返す。

    作業シートはヘッダー行が消されることがある（実際に消された）ので、
    1行目がヘッダーかどうかは中身を見て判定し、データなら取りこぼさない。
    """
    rows = [pad(r)[:LAST_COL] for r in get_values(sheet, f"A1:{col_letter(LAST_COL)}")]
    if not rows:
        raise SyncError(f"{sheet} が空です")
    start = 1 if is_header(rows[0]) else 0
    keys, domains, companies = set(), set(), 0
    last_data_row = start
    for i, row in enumerate(rows[start:], start=start):
        name = row[KEY_COL - 1]
        if norm(name):
            keys.add(norm(name))
            keys.add(company_key(name))
            dom = domain(row[URL_COL - 1])
            if dom:
                domains.add(dom)
            companies += 1
            last_data_row = i + 1  # H:I だけ入力された行を「データあり」と誤認しない
    return keys, domains, companies, last_data_row


def is_header(row):
    return norm(row[KEY_COL - 1]) == norm(EXPECTED_HEADER[KEY_COL - 1])


def assert_header(header, sheet):
    """取込元の列構成がずれていたら止める（列を足したときの事故防止）。"""
    for i in range(LAST_COL):
        if norm(header[i]) != norm(EXPECTED_HEADER[i]):
            raise SyncError(
                f"{sheet} の列構成が変わっています（{col_letter(i + 1)}列: "
                f"「{header[i]}」/ 期待「{EXPECTED_HEADER[i]}」）。取込を中止しました"
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="追記せず対象件数だけ表示する")
    args = ap.parse_args()

    titles = sheet_titles()
    work_sheet, raw_sheet = titles[WORK_SHEET_ID], titles[RAW_SHEET_ID]
    raw_rows = read_raw(raw_sheet)
    existing, existing_domains, existing_count, last_data_row = read_work(work_sheet)
    extra = load_extra(EXTRA_EXCLUDE_FILE)
    exclusion = Exclusion(read_exclusion(titles[EXCLUDE_SHEET_ID]), extra)

    fresh, seen, seen_domains, blocked = [], set(), set(), []
    for row in raw_rows:
        name = row[KEY_COL - 1]
        keys = {norm(name), company_key(name)}
        if keys & existing or keys & seen:
            continue
        dom = domain(row[URL_COL - 1])
        if dom and (dom in existing_domains or dom in seen_domains):
            continue
        hit = exclusion.hit(name)
        if hit:
            blocked.append((name, hit))
            continue
        seen |= keys
        if dom:
            seen_domains.add(dom)
        fresh.append(row)

    if blocked:
        print(f"除外リスト該当で取込まなかった: {len(blocked)}件"
              f"（除外リスト {len(exclusion.exact)}社 + 個別指定 {len(extra)}社と照合）")
        for name, (why, src) in blocked:
            print(f"  - {name} … {why} / 除外リスト「{src}」")

    print(f"取込元 {len(raw_rows)}件 / 作業シート {existing_count}社 / 新着 {len(fresh)}件")
    if not fresh:
        print("新着なし。何もしません。")
        return 0
    if args.dry_run:
        for row in fresh[:10]:
            print("  +", row[KEY_COL - 1])
        if len(fresh) > 10:
            print(f"  ... 他 {len(fresh) - 10}件")
        return 0

    start = last_data_row + 1
    for first, last in WRITE_BLOCKS:
        block = [r[first - 1:last] for r in fresh]
        # gws は引数渡しなので 1 回の書込を CHUNK 行ずつに割る（引数長 128KB の上限対策）
        for off in range(0, len(block), CHUNK):
            part = block[off:off + CHUNK]
            top = start + off
            rng = (f"'{work_sheet}'!{col_letter(first)}{top}"
                   f":{col_letter(last)}{top + len(part) - 1}")
            gws(
                "sheets", "spreadsheets", "values", "update",
                params={"spreadsheetId": SPREADSHEET_ID, "range": rng, "valueInputOption": "RAW"},
                body={"values": part},
            )
            print(f"  書込: {rng}")
    print(f"追記完了: {start}〜{start + len(fresh) - 1}行目 ({len(fresh)}件)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SyncError as e:
        print(f"中止: {e}", file=sys.stderr)
        sys.exit(1)
