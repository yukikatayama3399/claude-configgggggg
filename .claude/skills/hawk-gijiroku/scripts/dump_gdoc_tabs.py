#!/usr/bin/env python3
"""Gemini 自動メモ等の Google Doc を「全タブ」テキスト化する。

gog docs cat は先頭タブしか出さないため、gws で includeTabsContent=true を付けて取り、
タブごとに <outdir>/tab_<tabId>.txt へ書き出す（表は ' | ' 区切りで1行化）。

使い方:
  python3 dump_gdoc_tabs.py <documentId or URL> [outdir]
"""
import json, os, re, subprocess, sys


def doc_id(s: str) -> str:
    m = re.search(r"/document/d/([A-Za-z0-9_-]+)", s)
    return m.group(1) if m else s


def para_text(p):
    return "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))


def body_text(body):
    out = []
    for el in body.get("content", []):
        if "paragraph" in el:
            out.append(para_text(el["paragraph"]))
        if "table" in el:
            for row in el["table"]["tableRows"]:
                cells = []
                for c in row["tableCells"]:
                    cells.append(" ".join(para_text(pp["paragraph"]).strip()
                                          for pp in c["content"] if "paragraph" in pp))
                out.append(" | ".join(cells) + "\n")
    return "".join(out)


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    did = doc_id(sys.argv[1])
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(outdir, exist_ok=True)
    raw = subprocess.check_output(
        ["gws", "docs", "documents", "get", "--params",
         json.dumps({"documentId": did, "includeTabsContent": True})])
    d = json.loads(raw)
    print("title:", d.get("title"))

    def walk(tabs, depth=0):
        for t in tabs:
            tp = t["tabProperties"]
            txt = body_text(t["documentTab"]["body"])
            fn = os.path.join(outdir, f"tab_{tp['tabId'].replace('.', '_')}.txt")
            with open(fn, "w") as f:
                f.write(txt)
            print("  " * depth + f"{tp['tabId']}\t{tp.get('title')}\t{len(txt)} chars\t-> {fn}")
            walk(t.get("childTabs", []), depth + 1)

    walk(d.get("tabs", []))


if __name__ == "__main__":
    main()
