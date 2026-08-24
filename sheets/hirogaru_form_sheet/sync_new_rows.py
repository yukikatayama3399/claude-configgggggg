#!/usr/bin/env python3
"""自動追加中リスト_SNS広告求人 の新着取込。

_取込元_SNS広告求人（IMPORTRANGE+FILTER の生データ）と作業シートを会社名で突き合わせ、
未取込の行だけを追記する。追記するのは A:G と J:O だけで、
H列(入力状況) / I列(送信日時) には一切書かないので、外部作業者の入力が消えたりズレたりしない。

依存: gws (Google Workspace CLI) が PATH にあり認証済みであること。
使い方:
    python3 sync_new_rows.py            # 実行
    python3 sync_new_rows.py --dry-run  # 追記せず件数だけ表示
"""

import argparse
import json
import subprocess
import sys

SPREADSHEET_ID = "1gYL-_-rM52JrWEtsL-Cx-Wv4BPjS49qg9g_n2xq8WqQ"
# タブは名前ではなく sheetId で指す。名前は実際に変わった
# (自動追加中リスト_SNS広告求人 → 注力_最新SNS広告求人(自動追加))ので、
# 名前で参照すると改名のたびに同期が止まる。
WORK_SHEET_ID = 892888463
RAW_SHEET_ID = 1963927632

# 取込元の列構成。ここが変わったら追記せず中止する。
EXPECTED_HEADER = [
    "優先度", "会社名", "サイトURL", "フォームURL", "Eメール", "営業お断り", "取得日",
    "入力状況", "送信日時", "種別", "求人タイトル", "シグナル", "勤務地", "検索クエリ", "備考",
]

KEY_COL = 2   # B列 = 会社名（重複判定キー）
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
    for sid in (WORK_SHEET_ID, RAW_SHEET_ID):
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


def read_work(sheet):
    """作業シートの既存キーと、キー列から求めた最終データ行を返す。

    作業シートはヘッダー行が消されることがある（実際に消された）ので、
    1行目がヘッダーかどうかは中身を見て判定し、データなら取りこぼさない。
    """
    rows = [pad(r)[:LAST_COL] for r in get_values(sheet, f"A1:{col_letter(LAST_COL)}")]
    if not rows:
        raise SyncError(f"{sheet} が空です")
    start = 1 if is_header(rows[0]) else 0
    keys = set()
    last_data_row = start
    for i, row in enumerate(rows[start:], start=start):
        key = norm(row[KEY_COL - 1])
        if key:
            keys.add(key)
            last_data_row = i + 1  # H:I だけ入力された行を「データあり」と誤認しない
    return keys, last_data_row


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
    existing, last_data_row = read_work(work_sheet)

    fresh, seen = [], set()
    for row in raw_rows:
        key = norm(row[KEY_COL - 1])
        if key in existing or key in seen:
            continue
        seen.add(key)
        fresh.append(row)

    print(f"取込元 {len(raw_rows)}件 / 作業シート {len(existing)}件 / 新着 {len(fresh)}件")
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
