"""TSV をマスターシートのタブへ流し込む。

    python3 load_tsv.py 機能一覧 features.tsv            # 末尾に追記
    python3 load_tsv.py 機能一覧 features.tsv --replace  # 2行目以降を消してから書く（初期構築用）

TSV の1行目はヘッダー。schema.py の列名と一致する列だけを、シートの列順に並べ替えて書く。
足りない列は空欄、schema に無い列はエラーにする（列名の打ち間違い防止）。
"""
import argparse
import csv
import json
import pathlib
import sys

from gws import call
from schema import TABS

CFG = json.loads((pathlib.Path(__file__).parent / "config.json").read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tab")
    ap.add_argument("tsv")
    ap.add_argument("--replace", action="store_true")
    a = ap.parse_args()
    cols = TABS[a.tab]
    with open(a.tsv, newline="") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    header, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    unknown = [h for h in header if h not in cols]
    if unknown:
        sys.exit(f"{a.tab} に無い列: {unknown}")
    idx = {h: i for i, h in enumerate(header)}
    values = [[(r[idx[c]] if c in idx and idx[c] < len(r) else "").replace(" / ", "\n") for c in cols] for r in body]
    # チェックボックス列は TRUE/FALSE を真偽値として書く
    for row in values:
        for i, c in enumerate(cols):
            if c in ("簡易版", "要確認"):
                row[i] = row[i].strip().upper() == "TRUE"
    sid = CFG["master_sheet_id"]
    if a.replace:
        call("sheets.spreadsheets.values.clear", {"spreadsheetId": sid, "range": f"{a.tab}!A2:Z"})
        start = 2
    else:
        # append API はチェックボックス列の FALSE を「データあり」と見なして遠くに書くので、ID 列で末尾を数える
        ids = call("sheets.spreadsheets.values.get", {"spreadsheetId": sid, "range": f"{a.tab}!A:A"}).get("values", [])
        start = max((n for n, v in enumerate(ids, start=1) if v and v[0].strip()), default=1) + 1
    # コマンドライン引数の長さ制限があるので 50 行ずつ送る
    for i in range(0, len(values), 50):
        call("sheets.spreadsheets.values.update",
             {"spreadsheetId": sid, "range": f"{a.tab}!A{start + i}", "valueInputOption": "RAW"},
             {"values": values[i:i + 50]})
    print(f"{a.tab}: {len(values)} 行")


if __name__ == "__main__":
    main()
