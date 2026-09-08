#!/usr/bin/env python3
"""Google Slides のフォントサイズを段階的に引き上げる／溢れを事前見積もりする。

使い方:
  # 現状の分析（書き込みなし）
  python3 tools/slides_font_scale.py analyze --pid <presentationId>

  # 変換リクエストを生成（そのまま gws slides presentations batchUpdate に渡す）
  python3 tools/slides_font_scale.py plan --pid <presentationId> --variant min15 \
      --out req.json --report report.txt

対象外にするもの（意図的にスキップ）:
  - objectId が memo_ で始まる作業メモ、8pt 未満の作業メモ
  - キャンバス外（x>=930 / 右端の縦帯ラベル）の装飾テキスト
  - 【Confidential】等のチロメ、29pt 以上のタイトル・章扉
  - ※ / ★ で始まる注記は「上限つき」で少しだけ大きくする

はみ出し見積もり(OVER)の精度について:
  needed_height は「文字が箱の高さに収まるか」を見ているだけなので、
  1行分の高さしかない箱に上寄せで入っているテキスト（このデッキのカード内は
  ほぼこの形）は、実際にはカード内の余白に流れて破綻しない。
  OVER は「目視確認すべき候補」であって、そのまま破綻数として読まないこと。
  最終判断は PDF エクスポート → 画像化して目で見る。
"""
import argparse, json, math, subprocess, sys, unicodedata

CANVAS_W, CANVAS_H = 960.0, 540.0
EMU = 12700.0
INSET = 7.2  # Slides のデフォルト内側余白(pt) 片側

VARIANTS = {
    # (下限, 上限, 変換後) の並び。上から順に最初にマッチしたものを使う。
    "min13": {"tiers": [(9, 10.5, 13), (11, 12.5, 14), (13, 14.5, 15.5), (15, 18, 17), (19, 26, "+2")],
              "note_cap": 11},
    "min15": {"tiers": [(9, 10.5, 15), (11, 12.5, 16), (13, 14.5, 17), (15, 18, 19), (19, 26, "+2")],
              "note_cap": 12},
    "min17": {"tiers": [(9, 10.5, 17), (11, 12.5, 18), (13, 14.5, 19), (15, 18, 21), (19, 26, "+3")],
              "note_cap": 13},
}
SKIP_CONTENT = ("Confidential", "ヒデさん確認事項")
NOTE_PREFIX = ("※", "★", "*")


def fetch(pid):
    out = subprocess.run(
        ["gws", "slides", "presentations", "get", "--params", json.dumps({"presentationId": pid})],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def geo(el):
    t = el.get("transform", {}) or {}
    s = el.get("size", {}) or {}
    w = s.get("width", {}).get("magnitude", 0) * t.get("scaleX", 1) / EMU
    h = s.get("height", {}).get("magnitude", 0) * t.get("scaleY", 1) / EMU
    return t.get("translateX", 0) / EMU, t.get("translateY", 0) / EMU, w, h


def em_width(ch):
    """1文字の幅を font size に対する倍率で近似する。"""
    if ch in ("\n", "\r"):
        return 0.0
    if ch == " ":
        return 0.28
    return 1.0 if unicodedata.east_asian_width(ch) in ("W", "F", "A") else 0.52


def map_size(fs, variant, is_note):
    v = VARIANTS[variant]
    if fs is None or fs < 9 or fs >= 29:
        return None
    if is_note:
        return v["note_cap"] if fs < v["note_cap"] else None
    for lo, hi, to in v["tiers"]:
        if lo <= fs <= hi:
            new = fs + float(to[1:]) if isinstance(to, str) else float(to)
            return None if abs(new - fs) < 0.01 else new
    return None


def paragraphs(textobj):
    """[(runs=[(start,end,fontSize,content)], line_spacing)] を段落単位で返す。"""
    out, cur = [], []
    for pe in textobj.get("textElements", []):
        if "paragraphMarker" in pe:
            if cur:
                out.append(cur)
            ls = pe["paragraphMarker"].get("style", {}).get("lineSpacing", 100) or 100
            cur = {"runs": [], "ls": ls / 100.0}
        tr = pe.get("textRun")
        if tr and cur != []:
            cur["runs"].append((pe.get("startIndex", 0), pe["endIndex"],
                                tr.get("style", {}).get("fontSize", {}).get("magnitude"),
                                tr.get("content", "")))
    if cur:
        out.append(cur)
    return [p for p in out if isinstance(p, dict)]


def needed_height(paras, box_w, size_of):
    usable = max(box_w - 2 * INSET, 1.0)
    total = 2 * INSET
    for p in paras:
        w = 0.0
        maxfs = 0.0
        for st, en, fs, content in p["runs"]:
            fs2 = size_of(fs)
            if not fs2:
                continue
            maxfs = max(maxfs, fs2)
            w += sum(em_width(c) for c in content) * fs2
        if maxfs == 0:
            continue
        total += max(1, math.ceil(w / usable)) * maxfs * p["ls"]
    return total


def walk(deck):
    """(slide_id, element, shape) を返す。テキストを持つ図形のみ。表のセルも展開する。"""
    for s in deck.get("slides", []):
        for el in s.get("pageElements", []):
            if "shape" in el and el["shape"].get("text"):
                yield s["objectId"], el, el["shape"]["text"], el["objectId"]
            elif "table" in el:
                for r, row in enumerate(el["table"].get("tableRows", [])):
                    for c, cell in enumerate(row.get("tableCells", [])):
                        if cell.get("text"):
                            yield s["objectId"], el, cell["text"], (el["objectId"], r, c)


def skip_element(el, textobj):
    oid = el["objectId"]
    if oid.startswith("memo_"):
        return "作業メモ"
    x, y, w, h = geo(el)
    if x >= CANVAS_W - 30 or x + w <= 0 or y >= CANVAS_H:
        return "キャンバス外"
    body = "".join(pe.get("textRun", {}).get("content", "") for pe in textobj.get("textElements", []))
    for k in SKIP_CONTENT:
        if k in body:
            return "チロメ/作業note"
    if any((pe.get("textRun", {}).get("style", {}).get("fontSize", {}).get("magnitude") or 99) < 9
           for pe in textobj.get("textElements", []) if pe.get("textRun", {}).get("content", "").strip()):
        return "8pt作業メモ"
    return None


def is_note_para(paras):
    for p in paras:
        for _, _, _, content in p["runs"]:
            t = content.strip()
            if t:
                return t.startswith(NOTE_PREFIX)
    return False


def build(deck, variant):
    reqs, rows = [], []
    for sid, el, textobj, key in walk(deck):
        reason = skip_element(el, textobj)
        if reason:
            rows.append((sid, el["objectId"], "skip", reason, 0, 0))
            continue
        paras = paragraphs(textobj)
        note = is_note_para(paras)
        _, _, box_w, box_h = geo(el)
        changes = []
        for p in paras:
            for st, en, fs, content in p["runs"]:
                if not content.strip():
                    continue
                new = map_size(fs, variant, note)
                if new:
                    changes.append((st, en, fs, new))
        if not changes:
            continue
        def after_size(fs, _v=variant, _n=note):
            n = map_size(fs, _v, _n)
            return n or fs
        after = needed_height(paras, box_w, after_size)
        rows.append((sid, el["objectId"] if isinstance(key, str) else str(key), "resize",
                     f"{sorted({f for _,_,f,_ in changes})} -> {sorted({n for _,_,_,n in changes})}",
                     box_h, after))
        for st, en, fs, new in changes:
            r = {"updateTextStyle": {"style": {"fontSize": {"magnitude": new, "unit": "PT"}},
                                     "fields": "fontSize",
                                     "textRange": {"type": "FIXED_RANGE", "startIndex": st, "endIndex": en}}}
            if isinstance(key, str):
                r["updateTextStyle"]["objectId"] = key
            else:
                r["updateTextStyle"]["objectId"] = key[0]
                r["updateTextStyle"]["cellLocation"] = {"rowIndex": key[1], "columnIndex": key[2]}
            reqs.append(r)
    return reqs, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["analyze", "plan"])
    ap.add_argument("--pid", required=True)
    ap.add_argument("--variant", default="min15", choices=sorted(VARIANTS))
    ap.add_argument("--deck-json", help="取得済み JSON を使う（API を叩かない）")
    ap.add_argument("--out")
    ap.add_argument("--report")
    a = ap.parse_args()

    deck = json.load(open(a.deck_json)) if a.deck_json else fetch(a.pid)

    if a.cmd == "analyze":
        from collections import Counter
        c = Counter()
        for sid, el, textobj, key in walk(deck):
            if skip_element(el, textobj):
                continue
            for pe in textobj.get("textElements", []):
                tr = pe.get("textRun")
                if tr and tr.get("content", "").strip():
                    c[tr.get("style", {}).get("fontSize", {}).get("magnitude")] += len(tr["content"].strip())
        for k in sorted(c, key=lambda x: (x is None, x)):
            print(f"{k:>6} pt : {c[k]:5d} 文字")
        return

    reqs, rows = build(deck, a.variant)
    if a.out:
        json.dump({"requests": reqs}, open(a.out, "w"), ensure_ascii=False)
    over = [r for r in rows if r[2] == "resize" and r[5] > r[4] + 1]
    lines = [f"variant={a.variant}  updateTextStyle={len(reqs)}件  はみ出し見込み={len(over)}箱", ""]
    for sid, oid, kind, detail, bh, need in rows:
        if kind == "resize":
            flag = "OVER" if need > bh + 1 else "ok  "
            lines.append(f"{flag} {sid:>4} {oid:<22} 箱H={bh:5.0f} 必要H={need:5.0f}  {detail}")
    if a.report:
        open(a.report, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:2]))
    print(f"OVER: {len(over)} / resize対象 {sum(1 for r in rows if r[2]=='resize')}")


if __name__ == "__main__":
    main()
