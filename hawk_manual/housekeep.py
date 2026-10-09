"""承認まわりの後始末。ループの最初に毎回流す（冪等）。

- 承認済なのに承認日が空 → 今日の日付を入れる
- 同じIDで新しい行が承認済になったら、古い承認済行を「置換済」にする
- 承認・提供状態の入力規則を schema.py の値に揃える
"""
import datetime as dt
import json
import pathlib

from gws import call
from schema import APPROVAL_VALUES, APPROVED, STATUS_VALUES, SUPERSEDED, TABS

CFG = json.loads((pathlib.Path(__file__).parent / "config.json").read_text())
SID = CFG["master_sheet_id"]
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")


def col_letter(i: int) -> str:
    return chr(ord("A") + i)


def main() -> None:
    meta = call("sheets.spreadsheets.get", {"spreadsheetId": SID, "fields": "sheets.properties"})
    gids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    updates, rules, log = [], [], []
    for tab, id_col in (("機能一覧", "機能ID"), ("サイトマップ", "画面ID"), ("逆引き", "UCID"), ("FAQ", "FAQID")):
        cols = TABS[tab]
        rows = call("sheets.spreadsheets.values.get", {"spreadsheetId": SID, "range": f"{tab}!A1:Z"}).get("values", [])
        header = rows[0] if rows else cols
        ia = header.index("承認")
        id_ = header.index(id_col)
        idate = header.index("承認日") if "承認日" in header else None
        latest_approved: dict[str, int] = {}
        for n, r in enumerate(rows[1:], start=2):
            r = r + [""] * (len(header) - len(r))
            if not r[id_].strip() or r[ia] != APPROVED:
                continue
            if idate is not None and not r[idate]:
                updates.append({"range": f"{tab}!{col_letter(idate)}{n}", "values": [[TODAY]]})
                log.append(f"{tab} {r[id_]}: 承認日を記入")
            prev = latest_approved.get(r[id_])
            if prev:
                updates.append({"range": f"{tab}!{col_letter(ia)}{prev}", "values": [[SUPERSEDED]]})
                log.append(f"{tab} {r[id_]}: {prev}行目を置換済に")
            latest_approved[r[id_]] = n
        for col, values in (("承認", APPROVAL_VALUES), ("提供状態", STATUS_VALUES)):
            if col in header:
                i = header.index(col)
                rules.append({"setDataValidation": {
                    "range": {"sheetId": gids[tab], "startRowIndex": 1, "startColumnIndex": i, "endColumnIndex": i + 1},
                    "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in values]},
                             "strict": True, "showCustomUi": True}}})
    if updates:
        call("sheets.spreadsheets.values.batchUpdate", {"spreadsheetId": SID},
             {"valueInputOption": "RAW", "data": updates})
    call("sheets.spreadsheets.batchUpdate", {"spreadsheetId": SID}, {"requests": rules})
    print("\n".join(log) or "後始末: 変更なし")


if __name__ == "__main__":
    main()
