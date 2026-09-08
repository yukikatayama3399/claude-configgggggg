#!/usr/bin/env python3
"""PDF の実レンダリング結果と Slides API の図形座標を突き合わせて、
フォントを大きくした後の「実際の」はみ出し・衝突を検出する。

  python3 tools/slides_layout_fit.py report --deck adj.json --pdf adj.pdf

needed_height の推定と違い、これは Google が実際に組んだ行位置を見るので
「箱からは出ているがカード内の余白に収まっている」ケースを誤検知しない。
"""
import argparse, json, re, sys, unicodedata
from collections import defaultdict

EMU = 12700.0
CANVAS_W, CANVAS_H = 960.0, 540.0
CARD_PAD = 4.0          # カード内側にこれだけ余裕が欲しい(pt)
CONTAINER_TYPES = ("RECTANGLE", "ROUND_RECTANGLE", "ELLIPSE")


def norm(s):
    return re.sub(r"\s+", "", s or "")


def compose(a, b):
    """アフィン変換の合成 (親 a のあとに子 b)。"""
    a = a or {}; b = b or {}
    ax, ay = a.get("scaleX", 1), a.get("scaleY", 1)
    ahx, ahy = a.get("shearX", 0), a.get("shearY", 0)
    atx, aty = a.get("translateX", 0), a.get("translateY", 0)
    bx, by = b.get("scaleX", 1), b.get("scaleY", 1)
    bhx, bhy = b.get("shearX", 0), b.get("shearY", 0)
    btx, bty = b.get("translateX", 0), b.get("translateY", 0)
    return {"scaleX": ax * bx + ahx * bhy,
            "shearX": ax * bhx + ahx * by,
            "shearY": ahy * bx + ay * bhy,
            "scaleY": ahy * bhx + ay * by,
            "translateX": ax * btx + ahx * bty + atx,
            "translateY": ahy * btx + ay * bty + aty,
            "unit": "EMU"}


def geo(el):
    t = el.get("_t") or el.get("transform", {}) or {}
    s = el.get("size", {}) or {}
    w = s.get("width", {}).get("magnitude", 0) * t.get("scaleX", 1) / EMU
    h = s.get("height", {}).get("magnitude", 0) * t.get("scaleY", 1) / EMU
    x = t.get("translateX", 0) / EMU
    y = t.get("translateY", 0) / EMU
    return [x, y, x + w, y + h]


def rotated(el):
    t = el.get("_t") or el.get("transform", {}) or {}
    return abs(t.get("shearX", 0)) > 1e-6 or abs(t.get("shearY", 0)) > 1e-6


def flat_elements(slide, _els=None, _t=None):
    """グループを再帰展開し、親グループの変換を合成した '_t' を付けて返す。"""
    if _els is None:
        _els = slide.get("pageElements", [])
    for el in _els:
        t = compose(_t, el.get("transform"))
        if "elementGroup" in el:
            yield from flat_elements(slide, el["elementGroup"].get("children", []), t)
        else:
            el = dict(el)
            el["_t"] = t
            yield el


def shape_text(el):
    sh = el.get("shape") or {}
    tx = sh.get("text") or {}
    return "".join(pe.get("textRun", {}).get("content", "") for pe in tx.get("textElements", []))


def opaque(el):
    """不透明な単色塗りの図形か。"""
    sp = (el.get("shape") or {}).get("shapeProperties") or {}
    sf = (sp.get("shapeBackgroundFill") or {}).get("solidFill")
    if not sf:
        return False
    a = sf.get("alpha", 1)
    return a is None or a >= 0.99


def collect(deck):
    """slide_id -> {'text': [...], 'box': [...], 'z': [...]}"""
    out = {}
    for s in deck.get("slides", []):
        texts, boxes, z = [], [], []
        for el in flat_elements(s):
            if rotated(el):
                continue
            r = geo(el)
            if "shape" not in el:
                continue
            sh = el["shape"]
            body = shape_text(el)
            item = {"id": el["objectId"], "rect": r, "text": body, "norm": norm(body),
                    "type": sh.get("shapeType", "?"), "el": el}
            z.append(item)
            if norm(body):
                texts.append(item)
            elif sh.get("shapeType") in CONTAINER_TYPES:
                boxes.append(item)
        out[s["objectId"]] = {"text": texts, "box": boxes, "z": z}
    return out


def pdf_lines(page):
    lines = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            t = "".join(sp["text"] for sp in l["spans"])
            if not norm(t):
                continue
            lines.append({"bbox": list(l["bbox"]), "text": t, "norm": norm(t),
                          "size": max((sp["size"] for sp in l["spans"]), default=0)})
    return lines


def assign(lines, texts):
    """PDF の行を Slides の図形に割り当てる。"""
    for ln in lines:
        cands = []
        lw = max(ln["bbox"][2] - ln["bbox"][0], 1.0)
        lcy = (ln["bbox"][1] + ln["bbox"][3]) / 2
        for t in texts:
            if len(ln["norm"]) >= 2 and ln["norm"] not in t["norm"]:
                continue
            x0, y0, x1, y1 = t["rect"]
            # 行の横幅の6割以上が図形の横範囲に入っていること
            ox = min(ln["bbox"][2], x1) - max(ln["bbox"][0], x0)
            if ox < 0.6 * lw:
                continue
            # 図形の縦中心に近いものを採用する(MIDDLE 揃えで上下対称に溢れるため)
            cands.append((abs(lcy - (y0 + y1) / 2), -len(t["norm"]), id(t), t))
        ln["owner"] = min(cands)[3] if cands else None


def container_of(t, boxes):
    cx = (t["rect"][0] + t["rect"][2]) / 2
    cy = (t["rect"][1] + t["rect"][3]) / 2
    best = None
    for b in boxes:
        x0, y0, x1, y1 = b["rect"]
        if x1 - x0 >= CANVAS_W - 5 or y1 - y0 >= CANVAS_H - 5:
            continue                      # 背景全面の矩形は容器扱いしない
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            area = (x1 - x0) * (y1 - y0)
            if best is None or area < best[0]:
                best = (area, b)
    return best[1] if best else None


def overlap(a, b):
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[1], b[1])
    return ox, oy


def analyze(deck, doc):
    coll = collect(deck)
    findings = defaultdict(list)
    for i, s in enumerate(deck["slides"]):
        sid = s["objectId"]
        info = coll[sid]
        lines = pdf_lines(doc[i])
        assign(lines, info["text"])
        # 図形ごとの実描画 bbox
        drawn = {}
        for ln in lines:
            o = ln["owner"]
            if not o:
                continue
            d = drawn.setdefault(o["id"], {"bbox": list(ln["bbox"]), "shape": o, "lines": []})
            d["lines"].append(ln)
            bb = d["bbox"]
            bb[0] = min(bb[0], ln["bbox"][0]); bb[1] = min(bb[1], ln["bbox"][1])
            bb[2] = max(bb[2], ln["bbox"][2]); bb[3] = max(bb[3], ln["bbox"][3])

        for oid, d in drawn.items():
            t = d["shape"]
            bb, r = d["bbox"], t["rect"]
            # 1) キャンバス外
            if bb[2] > CANVAS_W - 2 or bb[3] > CANVAS_H - 2 or bb[0] < 2:
                findings[sid].append(("CANVAS", oid, f"描画がキャンバス外 bbox={fmt(bb)}", d))
            # 2) 容器カードからのはみ出し
            c = container_of(t, info["box"])
            if c:
                cr = c["rect"]
                if bb[3] > cr[3] - CARD_PAD:
                    findings[sid].append(("CARD_OUT", oid,
                        f"カード {c['id']} の下端を {bb[3]-(cr[3]-CARD_PAD):.0f}pt 超過", d))
                if bb[1] < cr[1] + CARD_PAD:
                    findings[sid].append(("CARD_OUT", oid,
                        f"カード {c['id']} の上端を {(cr[1]+CARD_PAD)-bb[1]:.0f}pt 超過", d))
                if bb[2] > cr[2] - CARD_PAD:
                    findings[sid].append(("CARD_OUT", oid,
                        f"カード {c['id']} の右端を {bb[2]-(cr[2]-CARD_PAD):.0f}pt 超過", d))
        # 2b) 前面の不透明図形にテキストが隠されていないか
        zorder = {it["id"]: i for i, it in enumerate(info["z"])}
        for oid, d in drawn.items():
            t = d["shape"]
            bb = d["bbox"]
            ti = zorder.get(oid, -1)
            for it in info["z"]:
                if it["id"] == oid or zorder[it["id"]] <= ti:
                    continue
                if not opaque(it["el"]):
                    continue
                r = it["rect"]
                if r[2] - r[0] >= CANVAS_W - 5:
                    continue
                for ln in d["lines"]:
                    ox, oy = overlap(ln["bbox"], r)
                    if ox > 4 and oy > 0.4 * (ln["bbox"][3] - ln["bbox"][1]):
                        findings[sid].append(("HIDDEN", oid,
                            f"「{ln['text'].strip()[:20]}」が前面の {it['id']} に {ox:.0f}pt 隠れている", d))
                        break

        # 3) テキスト同士の衝突
        ids = list(drawn)
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                da, db = drawn[ids[a]], drawn[ids[b]]
                for la in da["lines"]:
                    for lb in db["lines"]:
                        ox, oy = overlap(la["bbox"], lb["bbox"])
                        h = min(la["bbox"][3] - la["bbox"][1], lb["bbox"][3] - lb["bbox"][1])
                        if ox > 1 and oy > 0.35 * h:
                            findings[sid].append(("COLLIDE", f"{ids[a]}×{ids[b]}",
                                f"「{la['text'].strip()[:18]}」と「{lb['text'].strip()[:18]}」が {oy:.0f}pt 重なり", None))
                            break
                    else:
                        continue
                    break
    return findings


def fmt(b):
    return "(" + ",".join(f"{v:.0f}" for v in b) + ")"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["report"])
    ap.add_argument("--deck", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    import pymupdf
    deck = json.load(open(a.deck))
    doc = pymupdf.open(a.pdf)
    f = analyze(deck, doc)
    lines, total = [], 0
    for s in deck["slides"]:
        sid = s["objectId"]
        seen = set()
        rows = []
        for kind, oid, msg, _ in f.get(sid, []):
            key = (kind, oid, msg)
            if key in seen:
                continue
            seen.add(key)
            rows.append(f"  [{kind:9}] {oid:<26} {msg}")
        if rows:
            total += len(rows)
            lines.append(f"{sid} ({len(rows)}件)")
            lines += rows
    lines.insert(0, f"検出 {total}件 / 問題のあるスライド {sum(1 for s in deck['slides'] if f.get(s['objectId']))}枚\n")
    txt = "\n".join(lines)
    if a.out:
        open(a.out, "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
