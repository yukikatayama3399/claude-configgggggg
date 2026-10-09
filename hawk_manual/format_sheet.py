"""マスターシートの見た目を整える（何度流してもよい）。列を足したら流し直す。"""
import json
import pathlib

from gws import call
from schema import TABS

SID = json.loads((pathlib.Path(__file__).parent / "config.json").read_text())["master_sheet_id"]
GREEN = {"red": 0x6b / 255, "green": 0x7b / 255, "blue": 0x5a / 255}
WHITE = {"red": 1, "green": 1, "blue": 1}
WIDE = {"できること": 320, "設定項目・選択肢": 260, "何のため（目的）": 220, "制約・注意": 280, "メモ": 260,
        "質問": 300, "回答": 420, "この画面でやること": 280, "やりたいこと": 260, "手順（概要）": 320,
        "内容": 360, "確認したいこと": 380, "タイトル": 300, "URL": 220, "ソース": 200, "出典": 200,
        "機能名": 200, "画面名": 180, "README": 900}
CHECKBOX = {"簡易版", "要確認"}


def main() -> None:
    meta = call("sheets.spreadsheets.get", {"spreadsheetId": SID, "fields": "sheets.properties"})
    gids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    req = []
    for tab, cols in TABS.items():
        gid = gids[tab]
        if cols is None:
            req.append({"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                                      "properties": {"pixelSize": 900}, "fields": "pixelSize"}})
            continue
        req.append({"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
                                   "cell": {"userEnteredFormat": {"backgroundColor": GREEN, "wrapStrategy": "WRAP",
                                                                  "textFormat": {"bold": True, "foregroundColor": WHITE}}},
                                   "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy)"}})
        req.append({"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 1},
                                   "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP",
                                                                  "textFormat": {"fontSize": 9}}},
                                   "fields": "userEnteredFormat(wrapStrategy,verticalAlignment,textFormat.fontSize)"}})
        req.append({"updateSheetProperties": {"properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
                                              "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}})
        for i, c in enumerate(cols):
            req.append({"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                      "properties": {"pixelSize": WIDE.get(c, 90)}, "fields": "pixelSize"}})
            if c in CHECKBOX:
                req.append({"setDataValidation": {"range": {"sheetId": gid, "startRowIndex": 1, "startColumnIndex": i, "endColumnIndex": i + 1},
                                                  "rule": {"condition": {"type": "BOOLEAN"}, "strict": True}}})
        if "承認" in cols:  # 承認列の色分け
            i = cols.index("承認")
            rng = {"sheetId": gid, "startRowIndex": 1, "startColumnIndex": i, "endColumnIndex": i + 1}
            for val, color in (("承認済", {"red": 0.85, "green": 0.92, "blue": 0.83}), ("下書き", {"red": 1, "green": 0.95, "blue": 0.8}),
                               ("差戻し", {"red": 0.96, "green": 0.8, "blue": 0.8}), ("置換済", {"red": 0.9, "green": 0.9, "blue": 0.9})):
                req.append({"addConditionalFormatRule": {"index": 0, "rule": {"ranges": [rng], "booleanRule": {
                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": val}]},
                    "format": {"backgroundColor": color}}}}})
    # 条件付き書式は流すたびに増えるので先に消す
    existing = call("sheets.spreadsheets.get", {"spreadsheetId": SID, "fields": "sheets(properties.sheetId,conditionalFormats)"})
    clear = []
    for s in existing["sheets"]:
        for _ in s.get("conditionalFormats", []):
            clear.append({"deleteConditionalFormatRule": {"sheetId": s["properties"]["sheetId"], "index": 0}})
    for i in range(0, len(clear + req), 150):
        call("sheets.spreadsheets.batchUpdate", {"spreadsheetId": SID}, {"requests": (clear + req)[i:i + 150]})
    print(f"整形: {len(req)} 件")


if __name__ == "__main__":
    main()
