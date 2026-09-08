#!/usr/bin/env python3
"""Markdown 議事録（Slack 下書きと同じ原稿）を Google Doc に「文字詰め」体裁で流し込む。

- **太字** → bold、■/【議事録】行 → 見出し（10.5pt bold・上余白7pt）、1行目 → 13pt bold
- 本文 9pt・段落間隔 0・行間 100%・余白 上下36pt/左右40pt
- 空行と '---' は捨てる、Markdown 表（| # | アクション | 担当 | 期限 |）は番号リストに変換
- URL は updateTextStyle で本物のハイパーリンクにする（インデックスは UTF-16 単位で計算）

使い方:
  gog --account <me> docs create "<タイトル>"        # → id を得る
  python3 minutes_to_gdoc.py <minutes.md> <documentId>   # 空の Doc に流し込む（index 1 から挿入）
"""
import json, re, subprocess, sys


def u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    md, doc = sys.argv[1], sys.argv[2]
    src = open(md).read().split("\n")
    lines = []
    for ln in src:
        if ln.strip() in ("", "---"):
            continue
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if cells[0] == "#" or set(cells[0]) <= set("-"):
                continue
            n, act, who, when = (cells + ["", "", ""])[:4]
            lines.append(f"{n}. 【{who}】{act}｜{when}")
            continue
        lines.append(ln)

    text, bold, heads, links = "", [], [], []
    cursor = 1
    for ln in lines:
        plain, pos = "", cursor
        for p in re.split(r"(\*\*.+?\*\*)", ln):
            if p.startswith("**") and p.endswith("**"):
                inner = p[2:-2]
                bold.append((pos + u16(plain), pos + u16(plain) + u16(inner)))
                plain += inner
            else:
                plain += p
        for m in re.finditer(r"https?://[^\s）」]+", plain):
            links.append((pos + u16(plain[: m.start()]), pos + u16(plain[: m.end()]), m.group()))
        if plain.startswith("■") or plain.startswith("【議事録】"):
            heads.append((pos, pos + u16(plain) + 1))
        text += plain + "\n"
        cursor += u16(plain) + 1
    end = cursor

    pt = lambda v: {"magnitude": v, "unit": "PT"}
    reqs = [{"insertText": {"location": {"index": 1}, "text": text}},
            {"updateDocumentStyle": {"documentStyle": {"marginTop": pt(36), "marginBottom": pt(36),
                                                       "marginLeft": pt(40), "marginRight": pt(40)},
                                     "fields": "marginTop,marginBottom,marginLeft,marginRight"}},
            {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": end},
                                 "textStyle": {"fontSize": pt(9)}, "fields": "fontSize"}},
            {"updateParagraphStyle": {"range": {"startIndex": 1, "endIndex": end},
                                      "paragraphStyle": {"spaceAbove": pt(0), "spaceBelow": pt(0), "lineSpacing": 100},
                                      "fields": "spaceAbove,spaceBelow,lineSpacing"}}]
    for s, e in bold:
        reqs.append({"updateTextStyle": {"range": {"startIndex": s, "endIndex": e},
                                         "textStyle": {"bold": True}, "fields": "bold"}})
    for s, e in heads:
        reqs.append({"updateTextStyle": {"range": {"startIndex": s, "endIndex": e - 1},
                                         "textStyle": {"bold": True, "fontSize": pt(10.5)}, "fields": "bold,fontSize"}})
        reqs.append({"updateParagraphStyle": {"range": {"startIndex": s, "endIndex": e},
                                              "paragraphStyle": {"spaceAbove": pt(7)}, "fields": "spaceAbove"}})
    first = lines[0].replace("**", "")
    reqs.append({"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 1 + u16(first)},
                                     "textStyle": {"fontSize": pt(13), "bold": True}, "fields": "fontSize,bold"}})
    for s, e, url in links:
        reqs.append({"updateTextStyle": {"range": {"startIndex": s, "endIndex": e},
                                         "textStyle": {"link": {"url": url}}, "fields": "link"}})

    r = subprocess.run(["gws", "docs", "documents", "batchUpdate", "--params",
                        json.dumps({"documentId": doc}), "--json", json.dumps({"requests": reqs}, ensure_ascii=False)],
                       capture_output=True, text=True)
    print(f"{len(lines)} lines / {u16(text)} u16 units / {len(reqs)} requests / {len(links)} links")
    print("OK" if r.returncode == 0 else f"FAILED\n{r.stderr[:800]}")
    print(f"https://docs.google.com/document/d/{doc}/edit")


if __name__ == "__main__":
    main()
