#!/usr/bin/env python3
"""Google Slides の全スライドの文字（図形・表・グループ内）を標準出力に落とす。

使い方:
  python3 dump_slides_text.py <presentationId or URL> [...]
"""
import json, re, subprocess, sys


def pid(s: str) -> str:
    m = re.search(r"/presentation/d/([A-Za-z0-9_-]+)", s)
    return m.group(1) if m else s


def texts(el, out):
    if "shape" in el:
        t = el["shape"].get("text", {})
        s = "".join(e.get("textRun", {}).get("content", "") for e in t.get("textElements", []))
        if s.strip():
            out.append(s.strip())
    if "table" in el:
        for r in el["table"].get("tableRows", []):
            row = []
            for c in r.get("tableCells", []):
                s = "".join(e.get("textRun", {}).get("content", "")
                            for e in c.get("text", {}).get("textElements", []))
                row.append(s.strip().replace("\n", " / "))
            out.append(" | ".join(row))
    for ch in el.get("elementGroup", {}).get("children", []):
        texts(ch, out)


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    for arg in sys.argv[1:]:
        p = pid(arg)
        raw = subprocess.check_output(
            ["gws", "slides", "presentations", "get", "--params", json.dumps({"presentationId": p})])
        d = json.loads(raw)
        print(f"===== {d.get('title')} ({p}) =====")
        for i, s in enumerate(d.get("slides", []), 1):
            out = []
            for el in s.get("pageElements", []):
                texts(el, out)
            print(f"--- slide {i} ({s['objectId']}) ---")
            print("\n".join(out))


if __name__ == "__main__":
    main()
