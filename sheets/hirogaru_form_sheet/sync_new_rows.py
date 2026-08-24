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
WORK_SHEET = "自動追加中リスト_SNS広告求人"
RAW_SHEET = "_取込元_SNS広告求人"

KEY_COL = 2   # B列 = 会社名（重複判定キー）
LAST_COL = 15  # O列まで
# 追記する列ブロック [開始列, 終了列]。H(8)・I(9) は意図的に除外している。
WRITE_BLOCKS = [(1, 7), (10, 15)]

MAX_ROWS = 20000
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


def read_raw():
    """取込元を読む。壊れた取込（#REF! / 読込中 / 空）なら例外を投げて追記させない。"""
    rows = [pad(r)[:LAST_COL] for r in get_values(RAW_SHEET, f"A1:{col_letter(LAST_COL)}{MAX_ROWS}")]
    if len(rows) < 2:
        raise SyncError(f"{RAW_SHEET} にデータがありません（IMPORTRANGE 失敗の可能性）")
    for row in rows[:5]:
        for cell in row:
            if str(cell).strip() in ERROR_MARKERS:
                raise SyncError(f"{RAW_SHEET} が {cell} 状態です。取込を中止しました")
    data = [r for r in rows[1:] if norm(r[KEY_COL - 1])]
    if not data:
        raise SyncError(f"{RAW_SHEET} の有効行が 0 件です。取込を中止しました")
    return rows[0], data


def read_work():
    """作業シートのヘッダーと、キー列から求めた最終データ行・既存キーを返す。"""
    rows = [pad(r)[:LAST_COL] for r in get_values(WORK_SHEET, f"A1:{col_letter(LAST_COL)}{MAX_ROWS}")]
    if not rows:
        raise SyncError(f"{WORK_SHEET} が空です")
    header, body = rows[0], rows[1:]
    keys = set()
    last_data_row = 1
    for i, row in enumerate(body):
        key = norm(row[KEY_COL - 1])
        if key:
            keys.add(key)
            last_data_row = i + 2  # H:I だけ入力された行を「データあり」と誤認しない
    return header, keys, last_data_row


def assert_header_matches(raw_header, work_header):
    """列構成がずれていたら止める（列を足したときの事故防止）。"""
    for i in range(LAST_COL):
        if norm(raw_header[i]) != norm(work_header[i]):
            raise SyncError(
                f"列構成が一致しません（{col_letter(i + 1)}列: 取込元「{raw_header[i]}」"
                f"/ 作業シート「{work_header[i]}」）。取込を中止しました"
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="追記せず対象件数だけ表示する")
    args = ap.parse_args()

    raw_header, raw_rows = read_raw()
    work_header, existing, last_data_row = read_work()
    assert_header_matches(raw_header, work_header)

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
            rng = f"{WORK_SHEET}!{col_letter(first)}{top}:{col_letter(last)}{top + len(part) - 1}"
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
