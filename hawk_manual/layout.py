"""HAWK 機能取扱説明書のスライドレイアウト（HAWK 概要資料のトンマナに合わせる）。

方針: 余白を詰めて情報量を優先する。1画面 = 1ページ（左にスクショ、右に機能表）。
文字は 7〜8pt。表の行の高さを文字数から見積もり、溢れる分は「（続き）」ページに送る。
座標はすべて pt（16:9 = 720 x 405）。
"""
import math
import re

# HAWK 概要資料から採った色
GREEN = "#6b7b5a"       # メイン（見出し帯・表ヘッダー）
GREEN_LIGHT = "#a3b48a"
GREEN_PALE = "#eef2e8"  # 囲み・縞
GREEN_DARK = "#3e4a33"
TEXT = "#1a1a1a"
SUB = "#5c6b5e"
MUTED = "#9aa69c"
RED = "#e60012"
LINE = "#c9d1bf"
WHITE = "#ffffff"
FONT = "Noto Sans JP"

W, H = 720, 405
MX = 18                 # 左右余白
BODY_TOP, BODY_BOTTOM = 50, 382


def rgb(hex_: str) -> dict:
    h = hex_.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def pt(v: float) -> dict:
    return {"magnitude": v, "unit": "PT"}


def est_lines(text: str, width_pt: float, size: float) -> int:
    """全角1文字 ≒ size pt、半角 ≒ 0.55 size pt として折り返し行数を見積もる。"""
    usable = max(width_pt - 14, 10)  # セル内余白（左右）
    n = 0
    for para in (text or "").split("\n"):
        w = sum(size if ord(ch) > 0x2E80 else size * 0.55 for ch in para)
        n += max(1, math.ceil(w / usable))
    return n


def row_height(cells: list[str], widths: list[float], size: float) -> float:
    lines = max(est_lines(c, w, size) for c, w in zip(cells, widths))
    return lines * size * 1.4 + 9.5  # 実測: 行送り約1.4倍＋上下余白


class Deck:
    """Slides API リクエストを組み立てる。オブジェクトIDは build ごとの接頭辞で一意にする。"""

    def __init__(self, prefix: str, logos: dict[str, str], footer: str):
        self.prefix = prefix
        self.logos = logos
        self.footer = footer
        self.req: list[dict] = []
        self.page_no = 0
        self.page_id = ""
        self.n = 0

    # ---- 基本部品 -------------------------------------------------------------
    def _id(self) -> str:
        self.n += 1
        return f"{self.prefix}e{self.n:05d}"

    def new_page(self, bg: str | None = None) -> str:
        self.page_no += 1
        self.page_id = f"{self.prefix}p{self.page_no:03d}"
        self.req.append({"createSlide": {"objectId": self.page_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        if bg:
            self.req.append({"updatePageProperties": {"objectId": self.page_id, "pageProperties": {
                "pageBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(bg)}}}}, "fields": "pageBackgroundFill"}})
        return self.page_id

    def _place(self, x, y, w, h) -> dict:
        return {"pageObjectId": self.page_id, "size": {"width": pt(w), "height": pt(h)},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}

    def rect(self, x, y, w, h, fill: str, line: str | None = None) -> str:
        oid = self._id()
        self.req.append({"createShape": {"objectId": oid, "shapeType": "RECTANGLE", "elementProperties": self._place(x, y, w, h)}})
        props = {"shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(fill)}}}}
        fields = "shapeBackgroundFill.solidFill.color"
        if line:
            props["outline"] = {"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(line)}}}, "weight": pt(0.75)}
            fields += ",outline"
        else:
            props["outline"] = {"propertyState": "NOT_RENDERED"}
            fields += ",outline.propertyState"
        self.req.append({"updateShapeProperties": {"objectId": oid, "shapeProperties": props, "fields": fields}})
        return oid

    def text(self, x, y, w, h, text: str, size=8, color=TEXT, bold=False, align="START", valign="TOP",
             fill: str | None = None, runs: list[tuple[int, int, dict]] | None = None) -> str:
        """runs: [(start, end, style)] で部分的に太字・色を付ける。"""
        oid = self._id()
        self.req.append({"createShape": {"objectId": oid, "shapeType": "TEXT_BOX", "elementProperties": self._place(x, y, w, h)}})
        props = {"contentAlignment": valign, "autofit": {"autofitType": "NONE"}}
        fields = "contentAlignment,autofit.autofitType"
        if fill:
            props["shapeBackgroundFill"] = {"solidFill": {"color": {"rgbColor": rgb(fill)}}}
            fields += ",shapeBackgroundFill.solidFill.color"
        self.req.append({"updateShapeProperties": {"objectId": oid, "shapeProperties": props, "fields": fields}})
        if text:
            self.req.append({"insertText": {"objectId": oid, "text": text}})
            self._style(oid, None, size, color, bold)
            self.req.append({"updateParagraphStyle": {"objectId": oid, "textRange": {"type": "ALL"},
                                                      "style": {"alignment": align, "lineSpacing": 100, "spaceAbove": pt(0), "spaceBelow": pt(0)},
                                                      "fields": "alignment,lineSpacing,spaceAbove,spaceBelow"}})
            for s, e, st in runs or []:
                self._style(oid, None, st.get("size", size), st.get("color", color), st.get("bold", bold), s, e)
        return oid

    def _style(self, oid, cell, size, color, bold, start=None, end=None):
        rng = {"type": "ALL"} if start is None else {"type": "FIXED_RANGE", "startIndex": start, "endIndex": end}
        r = {"objectId": oid, "textRange": rng,
             "style": {"fontFamily": FONT, "fontSize": pt(size), "bold": bold,
                       "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
             "fields": "fontFamily,fontSize,bold,foregroundColor"}
        if cell:
            r["cellLocation"] = cell
        self.req.append({"updateTextStyle": r})

    def image(self, x, y, w, h, url: str, border=True) -> str:
        oid = self._id()
        self.req.append({"createImage": {"objectId": oid, "url": url, "elementProperties": self._place(x, y, w, h)}})
        if border:
            self.req.append({"updateImageProperties": {"objectId": oid, "imageProperties": {
                "outline": {"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(LINE)}}}, "weight": pt(0.75)}},
                "fields": "outline"}})
        return oid

    def table(self, x, y, widths: list[float], header: list[str], rows: list[list[str]], size=7.5,
              stripe=True, bold_first_col=True, marks: set[int] | None = None):
        """marks: 下書き行など、1列目を赤字にしたい行番号（0始まり, rows 基準）。"""
        oid = self._id()
        nrows, ncols = len(rows) + 1, len(widths)
        self.req.append({"createTable": {"objectId": oid, "rows": nrows, "columns": ncols,
                                         "elementProperties": self._place(x, y, sum(widths), 20 * nrows)}})
        for i, w in enumerate(widths):
            self.req.append({"updateTableColumnProperties": {"objectId": oid, "columnIndices": [i],
                                                             "tableColumnProperties": {"columnWidth": pt(w)}, "fields": "columnWidth"}})
        self.req.append({"updateTableRowProperties": {"objectId": oid, "rowIndices": list(range(nrows)),
                                                      "tableRowProperties": {"minRowHeight": pt(8)}, "fields": "minRowHeight"}})
        self.req.append({"updateTableBorderProperties": {"objectId": oid, "borderPosition": "ALL",
                                                         "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": nrows, "columnSpan": ncols},
                                                         "tableBorderProperties": {"tableBorderFill": {"solidFill": {"color": {"rgbColor": rgb(LINE)}}}, "weight": pt(0.5)},
                                                         "fields": "tableBorderFill,weight"}})
        self.req.append({"updateTableCellProperties": {"objectId": oid,
                                                       "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": nrows, "columnSpan": ncols},
                                                       "tableCellProperties": {"contentAlignment": "TOP"}, "fields": "contentAlignment"}})
        self.req.append({"updateTableCellProperties": {"objectId": oid,
                                                       "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": ncols},
                                                       "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(GREEN)}}}},
                                                       "fields": "tableCellBackgroundFill.solidFill.color"}})
        if stripe:
            for r in range(2, nrows, 2):
                self.req.append({"updateTableCellProperties": {"objectId": oid,
                                                               "tableRange": {"location": {"rowIndex": r, "columnIndex": 0}, "rowSpan": 1, "columnSpan": ncols},
                                                               "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb("#f6f8f2")}}}},
                                                               "fields": "tableCellBackgroundFill.solidFill.color"}})
        for r, cells in enumerate([header] + rows):
            for ci, val in enumerate(cells):
                if not val:
                    continue
                cell = {"rowIndex": r, "columnIndex": ci}
                self.req.append({"insertText": {"objectId": oid, "cellLocation": cell, "text": val}})
                if r == 0:
                    self._style(oid, cell, size, WHITE, True)
                else:
                    first = ci == 0 and bold_first_col
                    color = RED if (ci == 0 and marks and (r - 1) in marks) else (GREEN_DARK if first else TEXT)
                    self._style(oid, cell, size, color, first)
                    # 「設定：」「目的：」「注意：」などのラベルを太字に
                    for m in re.finditer(r"(?m)^【[^】]+】", val):
                        self._style(oid, cell, size, SUB, True, m.start(), m.end())
                self.req.append({"updateParagraphStyle": {"objectId": oid, "cellLocation": cell, "textRange": {"type": "ALL"},
                                                          "style": {"lineSpacing": 100, "spaceAbove": pt(0), "spaceBelow": pt(0)},
                                                          "fields": "lineSpacing,spaceAbove,spaceBelow"}})
        return oid

    # ---- ページ共通の枠 -------------------------------------------------------
    def frame(self, title: str, chapter: str = "", lead: str = ""):
        self.new_page()
        self.rect(MX, 13, 4, 22, GREEN)
        self.text(MX + 9, 9, 520, 28, title, size=15, bold=True, valign="MIDDLE")
        if chapter:
            self.text(W - MX - 200, 12, 200, 14, chapter, size=7.5, color=GREEN, bold=True, align="END")
        if lead:
            self.text(MX + 9, 34, W - 2 * MX - 9, 14, lead, size=7.5, color=SUB)
        self.footer_band()

    def footer_band(self):
        if self.logos.get("logo_hawk"):
            self.image(MX, 385, 46, 15, self.logos["logo_hawk"], border=False)
        self.text(MX + 54, 388, 420, 12, self.footer, size=6.5, color=MUTED, valign="MIDDLE")
        self.text(W - MX - 60, 388, 40, 12, str(self.page_no), size=7, color=MUTED, align="END", valign="MIDDLE")
        if self.logos.get("logo_fo"):
            self.image(W - MX - 16, 384, 16, 15, self.logos["logo_fo"], border=False)


def paginate(rows: list[list[str]], widths: list[float], size: float, avail: float, header_h: float | None = None):
    """行を avail(pt) に収まる塊に分ける。"""
    head = header_h or (size * 1.4 + 9.5)
    chunks, cur, used = [], [], head
    for r in rows:
        h = row_height(r, widths, size)
        if cur and used + h > avail:
            chunks.append(cur)
            cur, used = [], head
        cur.append(r)
        used += h
    if cur:
        chunks.append(cur)
    return chunks or [[]]
