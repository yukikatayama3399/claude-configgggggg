#!/usr/bin/env python3
"""HAWK顧客の声マップ（業態×規模）スライドを企業マスタから再生成する。

データ源: スプレッドシート「HAWK企業マスタ（業態×規模・顧客の声）」の 企業マスタ タブ
出力先:   プレゼンテーション「HAWK顧客の声マップ（業態×規模）」を毎回1枚に作り直す

使い方:
    python3 weekly/build_voice_map_slide.py            # 再生成
    python3 weekly/build_voice_map_slide.py --dry-run  # リクエスト内容だけ表示

前提: gws がセットアップ済み（クラウドは SessionStart フックで自動）。
仕組み: 新しいスライドを作ってから旧スライドを全部消すので、常に1枚。
毎回全消し→再生成なので、マスタ側の行の増減・分類変更がそのまま反映される。
"""
import json
import subprocess
import sys
from datetime import date

MASTER_SHEET_ID = "1RPLV2_muMBQuOsDEC26857cHUrCFiCIH7jHnomyapuw"
PRESENTATION_ID = "1o6sJIas-_R4Z8k_EPhQXM1beFkDBqwRbM1-KTf2t7WE"
MASTER_DOC_NOTE = "出典: HAWK企業マスタ（業態×規模）／顧客からの要望まとめDoc／提案ステータス"

# 色（HTMLダッシュボードと同じ・検証済みパレット）
BUDGET = {"red": 0x2A / 255, "green": 0x78 / 255, "blue": 0xD6 / 255}
FUNC = {"red": 0xEB / 255, "green": 0x68 / 255, "blue": 0x34 / 255}
ORG = {"red": 0x0E / 255, "green": 0x8F / 255, "blue": 0x64 / 255}
STALL = {"red": 0x8A / 255, "green": 0x86 / 255, "blue": 0x7B / 255}
INK = {"red": 0.11, "green": 0.11, "blue": 0.09}
INK2 = {"red": 0.34, "green": 0.33, "blue": 0.30}
HEAD_BG = {"red": 0.93, "green": 0.93, "blue": 0.90}

REASONS = ["①予算・案件なし", "②機能・媒体", "③体制・分掌", "④停滞・未確定"]
REASON_COLOR = dict(zip(REASONS, [BUDGET, FUNC, ORG, STALL]))
REASON_SHORT = dict(zip(REASONS, ["予算・案件", "機能・媒体", "体制・分掌", "停滞"]))
SIZES = ["小", "中", "大"]
GYOTAI = ["代理店", "媒体社", "広告主", "その他"]


def gws(*args, json_body=None):
    cmd = ["gws", *args]
    if json_body is not None:
        cmd += ["--json", json.dumps(json_body, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"gws failed: {' '.join(cmd[:4])}...\n{r.stderr[-2000:]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def read_master():
    d = gws("sheets", "spreadsheets", "values", "get", "--params",
            json.dumps({"spreadsheetId": MASTER_SHEET_ID, "range": "企業マスタ!A1:L300"}))
    rows = d.get("values", [])
    head, body = rows[0], rows[1:]
    idx = {h: i for i, h in enumerate(head)}

    def cell(r, col):
        i = idx[col]
        return r[i].strip() if i < len(r) else ""

    out = []
    for r in body:
        if not r or not cell(r, "社名"):
            continue
        out.append({
            "name": cell(r, "社名"), "gyotai": cell(r, "業態"), "size": cell(r, "規模"),
            "status": cell(r, "ステータス"), "reason": cell(r, "失注理由カテゴリ"),
        })
    return out


def pt(v):
    return {"magnitude": v, "unit": "PT"}


def box(oid, slide, x, y, w, h):
    return {"createShape": {"objectId": oid, "shapeType": "TEXT_BOX", "elementProperties": {
        "pageObjectId": slide,
        "size": {"width": pt(w), "height": pt(h)},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}}


def text(oid, s):
    return {"insertText": {"objectId": oid, "text": s}}


def style(oid, start, end, size=None, bold=None, color=None):
    st, fields = {}, []
    if size is not None:
        st["fontSize"] = pt(size); fields.append("fontSize")
    if bold is not None:
        st["bold"] = bold; fields.append("bold")
    if color is not None:
        st["foregroundColor"] = {"opaqueColor": {"rgbColor": color}}; fields.append("foregroundColor")
    st["fontFamily"] = "Noto Sans JP"; fields.append("fontFamily")
    return {"updateTextStyle": {"objectId": oid, "style": st, "fields": ",".join(fields),
                                "textRange": {"type": "FIXED_RANGE", "startIndex": start, "endIndex": end}}}


def rect(oid, slide, x, y, w, h, color):
    return [{"createShape": {"objectId": oid, "shapeType": "RECTANGLE", "elementProperties": {
        "pageObjectId": slide,
        "size": {"width": pt(w), "height": pt(h)},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}},
        {"updateShapeProperties": {"objectId": oid, "fields": "shapeBackgroundFill.solidFill.color,outline.propertyState",
         "shapeProperties": {"shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": color}}},
                             "outline": {"propertyState": "NOT_RENDERED"}}}}]


def main():
    dry = "--dry-run" in sys.argv
    companies = read_master()
    today = date.today().strftime("%Y/%m/%d")

    # 集計
    lost = [c for c in companies if c["status"] in ("失注", "解約") and c["reason"]]
    lost_matrix = {s: {r: 0 for r in REASONS} for s in SIZES}
    for c in lost:
        if c["size"] in lost_matrix and c["reason"] in REASONS:
            lost_matrix[c["size"]][c["reason"]] += 1
    row_totals = {s: sum(lost_matrix[s].values()) for s in SIZES}
    max_total = max(row_totals.values()) or 1

    cellmap = {(g, s): [c for c in companies if c["gyotai"] == g and c["size"] == s]
               for g in GYOTAI for s in SIZES}

    pres = gws("slides", "presentations", "get", "--params",
               json.dumps({"presentationId": PRESENTATION_ID, "fields": "slides(objectId)"}))
    old_slides = [s["objectId"] for s in pres.get("slides", [])]

    SLIDE = "voiceMapSlide"
    if SLIDE in old_slides:
        gws("slides", "presentations", "batchUpdate", "--params",
            json.dumps({"presentationId": PRESENTATION_ID}),
            json_body={"requests": [{"deleteObject": {"objectId": SLIDE}}]})
        old_slides.remove(SLIDE)

    reqs = [{"createSlide": {"objectId": SLIDE, "insertionIndex": 0,
                             "slideLayoutReference": {"predefinedLayout": "BLANK"}}}]

    # タイトル
    reqs.append(box("vmTitle", SLIDE, 24, 14, 672, 30))
    t = f"顧客の声マップ 業態 × 規模（{today}時点・{len(companies)}社）"
    reqs += [text("vmTitle", t), style("vmTitle", 0, len(t), size=17, bold=True, color=INK)]

    # 発見サマリー（3行）
    small_lost = row_totals.get("小", 0)
    small_budget = lost_matrix["小"][REASONS[0]]
    big_lost = row_totals.get("大", 0)
    big_org = lost_matrix["大"][REASONS[2]]
    lines = [
        f"小規模の失注は予算に一極集中: {small_budget}/{small_lost}件。製品評価は高いまま価格で落ちる → 少額・従量メニューが解",
        f"大規模の壁は機能より体制・分掌: {big_org}/{big_lost}件が「運用は別部門・別会社の管掌」→ 横展開・OEMが解",
        "機能・チャネル要望の発生源は中規模（媒体拡張・レポート・クリ運用）→ 開発ロードマップの主要顧客像",
    ]
    body = "\n".join("・" + l for l in lines)
    reqs.append(box("vmFind", SLIDE, 24, 44, 672, 52))
    reqs += [text("vmFind", body), style("vmFind", 0, len(body), size=9.5, color=INK)]
    pos = 0
    for l in lines:
        head_len = l.index(":") + 1 if ":" in l else 0
        if head_len:
            reqs.append(style("vmFind", pos + 1, pos + 1 + head_len, size=9.5, bold=True, color=INK))
        pos += len("・" + l) + 1

    # マトリクス表（左）
    n_rows = 1 + len(GYOTAI)
    reqs.append({"createTable": {"objectId": "vmTable", "elementProperties": {
        "pageObjectId": SLIDE, "size": {"width": pt(440), "height": pt(230)},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": 24, "translateY": 104, "unit": "PT"}},
        "rows": n_rows, "columns": 4}})
    heads = ["", "小規模（運用1〜2人）", "中規模（Silver級）", "大規模（電通D級）"]
    for j, h in enumerate(heads):
        loc = {"objectId": "vmTable", "cellLocation": {"rowIndex": 0, "columnIndex": j}}
        if h:
            reqs.append({"insertText": {**loc, "text": h}})
            reqs.append({"updateTextStyle": {**loc, "style": {"bold": True, "fontSize": pt(8), "fontFamily": "Noto Sans JP"},
                                             "fields": "bold,fontSize,fontFamily", "textRange": {"type": "ALL"}}})
    reqs.append({"updateTableCellProperties": {"objectId": "vmTable",
                 "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": 4},
                 "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": HEAD_BG}}}},
                 "fields": "tableCellBackgroundFill.solidFill.color"}})
    for i, g in enumerate(GYOTAI, start=1):
        loc = {"objectId": "vmTable", "cellLocation": {"rowIndex": i, "columnIndex": 0}}
        reqs.append({"insertText": {**loc, "text": g}})
        reqs.append({"updateTextStyle": {**loc, "style": {"bold": True, "fontSize": pt(8), "fontFamily": "Noto Sans JP"},
                                         "fields": "bold,fontSize,fontFamily", "textRange": {"type": "ALL"}}})
        for j, s in enumerate(SIZES, start=1):
            items = cellmap[(g, s)]
            loc = {"objectId": "vmTable", "cellLocation": {"rowIndex": i, "columnIndex": j}}
            if not items:
                reqs.append({"insertText": {**loc, "text": "—"}})
                reqs.append({"updateTextStyle": {**loc, "style": {"fontSize": pt(7.5), "fontFamily": "Noto Sans JP",
                             "foregroundColor": {"opaqueColor": {"rgbColor": INK2}}},
                             "fields": "fontSize,fontFamily,foregroundColor", "textRange": {"type": "ALL"}}})
                continue
            n_in = sum(1 for c in items if c["status"] == "導入済")
            n_talk = sum(1 for c in items if c["status"] == "商談中")
            n_lost = len(items) - n_in - n_talk
            cnt = {}
            for c in items:
                if c["reason"]:
                    cnt[c["reason"]] = cnt.get(c["reason"], 0) + 1
            dom = max(cnt, key=cnt.get) if cnt else None
            order = {"導入済": 0, "商談中": 1}
            names = [c["name"] for c in sorted(items, key=lambda c: order.get(c["status"], 2))]
            shown = "、".join(names[:3]) + (f" ほか{len(names)-3}社" if len(names) > 3 else "")
            line1 = f"{len(items)}社（導{n_in}・商{n_talk}・失{n_lost}）"
            line2 = f"主因: {REASON_SHORT[dom]}" if dom and cnt[dom] >= 2 else ""
            txt = line1 + ("\n" + line2 if line2 else "") + "\n" + shown
            reqs.append({"insertText": {**loc, "text": txt}})
            reqs.append({"updateTextStyle": {**loc, "style": {"fontSize": pt(7.5), "fontFamily": "Noto Sans JP", "foregroundColor": {"opaqueColor": {"rgbColor": INK}}},
                                             "fields": "fontSize,fontFamily,foregroundColor", "textRange": {"type": "ALL"}}})
            reqs.append({"updateTextStyle": {**loc, "style": {"bold": True},
                                             "fields": "bold", "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": len(line1)}}})
            if line2:
                s2, e2 = len(line1) + 1, len(line1) + 1 + len(line2)
                reqs.append({"updateTextStyle": {**loc, "style": {"bold": True, "foregroundColor": {"opaqueColor": {"rgbColor": REASON_COLOR[dom]}}},
                                                 "fields": "bold,foregroundColor", "textRange": {"type": "FIXED_RANGE", "startIndex": s2, "endIndex": e2}}})

    # 失注バー（右）
    bx, bw_max = 486, 200
    reqs.append(box("vmBarT", SLIDE, bx, 104, 210, 16))
    bt = f"失注・解約{len(lost)}件 — 理由 × 規模"
    reqs += [text("vmBarT", bt), style("vmBarT", 0, len(bt), size=10, bold=True, color=INK)]
    y = 126
    for s in SIZES:
        total = row_totals[s]
        lbl = f"{s}規模  {total}件"
        reqs.append(box(f"vmBarL{SIZES.index(s)}", SLIDE, bx, y, 200, 12))
        reqs += [text(f"vmBarL{SIZES.index(s)}", lbl), style(f"vmBarL{SIZES.index(s)}", 0, len(lbl), size=8, bold=True, color=INK2)]
        x = bx
        for r in REASONS:
            n = lost_matrix[s][r]
            if not n:
                continue
            w = max(bw_max * n / max_total, 12)
            oid = f"vmSeg{SIZES.index(s)}_{REASONS.index(r)}"
            reqs += rect(oid, SLIDE, x, y + 16, w - 1.5, 16, REASON_COLOR[r])
            reqs += [text(oid, str(n)),
                     {"updateTextStyle": {"objectId": oid, "style": {"fontSize": pt(8), "bold": True, "fontFamily": "Noto Sans JP",
                      "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 1, "green": 1, "blue": 1}}}},
                      "fields": "fontSize,bold,fontFamily,foregroundColor", "textRange": {"type": "ALL"}}},
                     {"updateParagraphStyle": {"objectId": oid, "style": {"alignment": "CENTER"},
                      "fields": "alignment", "textRange": {"type": "ALL"}}}]
            x += w
        y += 41
    # 凡例
    ly = y + 4
    for i, r in enumerate(REASONS):
        reqs += rect(f"vmLg{i}", SLIDE, bx, ly + i * 15, 9, 9, REASON_COLOR[r])
        reqs.append(box(f"vmLgT{i}", SLIDE, bx + 14, ly + i * 15 - 3, 190, 14))
        lt = f"{r}（{sum(lost_matrix[s][r] for s in SIZES)}件）"
        reqs += [text(f"vmLgT{i}", lt), style(f"vmLgT{i}", 0, len(lt), size=8, color=INK2)]

    # フッター
    reqs.append(box("vmFoot", SLIDE, 24, 382, 672, 16))
    ft = f"{MASTER_DOC_NOTE}｜規模: 小=運用1〜2人／中=営業数十名・Silver級／大=電通デジタル級｜週次自動更新（水曜）"
    reqs += [text("vmFoot", ft), style("vmFoot", 0, len(ft), size=7, color=INK2)]

    # 旧スライドの削除（新スライド作成後）
    for oid in old_slides:
        reqs.append({"deleteObject": {"objectId": oid}})

    if dry:
        print(json.dumps({"requests": reqs}, ensure_ascii=False, indent=1)[:4000])
        print(f"... total {len(reqs)} requests")
        return
    gws("slides", "presentations", "batchUpdate", "--params",
        json.dumps({"presentationId": PRESENTATION_ID}),
        json_body={"requests": reqs})
    print(f"OK: {len(companies)}社 / 失注{len(lost)}件 を反映して1枚に再生成した")
    print(f"https://docs.google.com/presentation/d/{PRESENTATION_ID}/edit")


if __name__ == "__main__":
    main()
