"""マスターシートを新規作成する（初回だけ使う）。

    python3 hawk_manual/create_master.py "HAWK 機能取扱説明書マスター"

作成後に出る spreadsheetId を hawk_manual/config.json に書く。
"""
import sys

from gws import call
from schema import APPROVAL_VALUES, STATUS_VALUES, TABS

README = """HAWK 機能取扱説明書マスター — 運用ルール

■ このシートが「正」
  スライド（下書き版・本番版）はこのシートから自動生成する。スライドを直接直さない。

■ 承認フロー
  1. 自動ループ（3日おき）が #hawk-社内利用 / #hawk-product の新着から変更を拾い、
     各タブに「承認＝下書き」で行を足す。更新履歴タブにも1行残す。
  2. 片山が行を確認し、正しければ「承認」を承認済に、違えば差戻しにする。
  3. 本番スライドは「承認＝承認済」かつ「提供状態＝提供中」の行だけで作り直す。
     （下書きスライドは全行から作る。見え方の確認用）

■ 簡易版
  「簡易版」にチェックがある行だけで簡易版（10ページ程度）を作る。

■ ID のルール
  機能ID: F-カテゴリ略号-連番（例 F-AUD-003）／画面ID: S-連番／逆引き: UC-連番
  一度振った ID は変えない・使い回さない（削除するときは提供状態を提供終了にする）。

■ 版管理
  本番を作り直すたびに「版管理」タブに1行残し、PDF を書き出して日付付きで保存する。
"""


def main(title: str) -> None:
    sheets = [{"properties": {"title": name, "gridProperties": {"frozenRowCount": 0 if cols is None else 1}}}
              for name, cols in TABS.items()]
    ss = call("sheets.spreadsheets.create", {}, {"properties": {"title": title, "locale": "ja_JP"}, "sheets": sheets})
    sid = ss["spreadsheetId"]
    tab_ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in ss["sheets"]}

    data = [{"range": "README!A1", "values": [[line] for line in README.splitlines()]}]
    for name, cols in TABS.items():
        if cols:
            data.append({"range": f"{name}!A1", "values": [cols]})
    call("sheets.spreadsheets.values.batchUpdate", {"spreadsheetId": sid},
         {"valueInputOption": "RAW", "data": data})

    requests = []
    for name, cols in TABS.items():
        if not cols:
            continue
        gid = tab_ids[name]
        requests.append({"repeatCell": {
            "range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                           "backgroundColor": {"red": 0.91, "green": 0.93, "blue": 0.97}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}})

        def rule(col: str, values: list[str] | None, checkbox: bool = False):
            if col not in cols:
                return
            idx = cols.index(col)
            cond = {"type": "BOOLEAN"} if checkbox else {
                "type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in values]}
            requests.append({"setDataValidation": {
                "range": {"sheetId": gid, "startRowIndex": 1, "startColumnIndex": idx, "endColumnIndex": idx + 1},
                "rule": {"condition": cond, "strict": True, "showCustomUi": True}}})

        rule("承認", APPROVAL_VALUES)
        rule("提供状態", STATUS_VALUES)
        rule("簡易版", None, checkbox=True)

    call("sheets.spreadsheets.batchUpdate", {"spreadsheetId": sid}, {"requests": requests})
    print(sid)
    print(f"https://docs.google.com/spreadsheets/d/{sid}/edit")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "HAWK 機能取扱説明書マスター")
