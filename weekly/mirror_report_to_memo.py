#!/usr/bin/env python3
"""本番「HAWK営業 - 定例会報告書」の当週タブを、書式ごと「【片山】週報メモ」t.0 へミラーする。

毎週水曜の HAWK週報 Routine（手順 4c）から実行する想定。
構成: (1) 週次アップデートヘッダ＋今週のハイライト
      (2) 6. お客様の声・フィードバック（週報共有用）… 既存内容を保全
      (3) 本番当週タブの写し（見出しレベル・表・箇条書きインデントを再現）

使い方:
  python3 weekly/mirror_report_to_memo.py --highlights highlights.txt [--source-tab 20260903]
  --highlights : 「■ 今週のハイライト」以下に入れる本文（・箇条書きのテキストファイル）
  --source-tab : 本番タブ名(YYYYMMDD)。省略時は日付名タブの最大値
  --feedback   : フィードバック節を差し替えるテキストファイル。省略時は現在の t.0 から保全
  --dry-run    : 書き込まずに構成だけ表示

前提: gws CLI がセットアップ済み（SessionStart フックで自動）。本番 Doc には書き込まない。
"""
import argparse
import json
import re
import subprocess
import sys

PROD_DOC = "1I7u2zNZTPl9tAo2SGalo35ElsDWu2MPpP6JgIYr8LCk"  # HAWK営業 - 定例会報告書
MEMO_DOC = "1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY"  # 【片山】週報メモ
MEMO_TAB = "t.0"
PLACEHOLDER = "@@TBL{}@@"


def gws(*args, json_in=None):
    cmd = ["gws"] + list(args)
    if json_in is not None:
        cmd += ["--json", json.dumps(json_in, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"gws failed: {' '.join(cmd[:4])}...\n{r.stderr[:2000]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def get_doc(doc_id):
    return gws("docs", "documents", "get", "--params",
               json.dumps({"documentId": doc_id, "includeTabsContent": True}))


def batch(doc_id, requests):
    return gws("docs", "documents", "batchUpdate", "--params",
               json.dumps({"documentId": doc_id}), json_in={"requests": requests})


def u16len(s):
    return len(s.encode("utf-16-le")) // 2


def para_text(p):
    return "".join(r.get("textRun", {}).get("content", "") for r in p.get("elements", []))


def cell_text(cell):
    parts = []
    for el in cell.get("content", []):
        if "paragraph" in el:
            parts.append(para_text(el["paragraph"]).rstrip("\n"))
    return "\n".join(parts).strip("\n")


def find_tab(doc, tab_id=None, title=None):
    def walk(tabs):
        for t in tabs:
            tp = t["tabProperties"]
            if (tab_id and tp["tabId"] == tab_id) or (title and tp.get("title") == title):
                yield t
            yield from walk(t.get("childTabs", []))
    hits = list(walk(doc.get("tabs", [])))
    return hits[0] if hits else None


def latest_dated_tab(doc):
    best = None
    for t in doc.get("tabs", []):
        title = t["tabProperties"].get("title", "")
        if re.fullmatch(r"\d{8}", title) and (best is None or title > best):
            best = title
    return best


def parse_blocks(tab):
    """本番タブ → blocks: {kind:p,text,style} / {kind:table,rows,banner}"""
    blocks = []
    for el in tab["documentTab"]["body"]["content"]:
        if "paragraph" in el:
            p = el["paragraph"]
            txt = para_text(p).rstrip("\n")
            style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
            if "bullet" in p:
                lvl = p["bullet"].get("nestingLevel", 0)
                txt = "　" * lvl + "・" + txt
                style = "NORMAL_TEXT"
            blocks.append({"kind": "p", "text": txt, "style": style})
        elif "table" in el:
            tbl = el["table"]
            rows = [[cell_text(tc) for tc in tr["tableCells"]] for tr in tbl["tableRows"]]
            banner = tbl["rows"] == 1 and tbl["columns"] == 1
            blocks.append({"kind": "table", "rows": rows, "banner": banner})
    return blocks


def extract_feedback(tab):
    """現在の t.0 から「6. お客様の声…」〜写しセパレータ直前を保全する。"""
    lines, cap = [], False
    for el in tab["documentTab"]["body"]["content"]:
        if "paragraph" not in el:
            if cap:  # 写しセパレータ（バナー表）に到達
                break
            continue
        txt = para_text(el["paragraph"]).rstrip("\n")
        if txt.startswith("6. お客様の声"):
            cap = True
        if cap and (txt.startswith("━━━━━") or txt.startswith("以下、本番")):
            break
        if cap:
            lines.append(txt)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def compose(source_tab_name, highlights_lines, feedback_lines, prod_blocks, today):
    blocks = [
        {"kind": "p", "text": f"◆ 週次アップデート（{today} 水曜更新）", "style": "HEADING_2"},
        {"kind": "p", "text": "※このタブは毎週水曜に、本番「HAWK営業 - 定例会報告書」の"
                              f"当週タブ（{source_tab_name}）と同内容へ更新する運用。", "style": "NORMAL_TEXT"},
        {"kind": "p", "text": "", "style": "NORMAL_TEXT"},
        {"kind": "p", "text": "■ 今週のハイライト", "style": "HEADING_3"},
    ]
    for l in highlights_lines:
        blocks.append({"kind": "p", "text": l, "style": "NORMAL_TEXT"})
    blocks.append({"kind": "p", "text": "", "style": "NORMAL_TEXT"})
    for i, l in enumerate(feedback_lines):
        style = "HEADING_2" if i == 0 else ("HEADING_4" if l.startswith("■ ") else "NORMAL_TEXT")
        blocks.append({"kind": "p", "text": l, "style": style})
    blocks += [
        {"kind": "p", "text": "", "style": "NORMAL_TEXT"},
        {"kind": "table", "rows": [[f"以下、本番 定例会報告書 {source_tab_name} タブの写し（{today} 時点）"]],
         "banner": True},
        {"kind": "p", "text": "", "style": "NORMAL_TEXT"},
    ]
    blocks += prod_blocks
    blocks.append({"kind": "p", "text": "（写しここまで）", "style": "NORMAL_TEXT"})
    return blocks


def render(blocks, dry_run=False):
    # --- バッチA: 全消し → プレースホルダ入りテキスト挿入 + 段落スタイル ---
    memo = get_doc(MEMO_DOC)
    t0 = find_tab(memo, tab_id=MEMO_TAB)
    end = t0["documentTab"]["body"]["content"][-1]["endIndex"]

    lines, tables = [], []
    for b in blocks:
        if b["kind"] == "p":
            lines.append(b)
        else:
            ph = PLACEHOLDER.format(len(tables))
            tables.append(b)
            lines.append({"kind": "p", "text": ph, "style": "NORMAL_TEXT", "_tbl": len(tables) - 1})

    text = "\n".join(l["text"] for l in lines) + "\n"
    if dry_run:
        print(text)
        return

    reqs = []
    if end > 2:
        reqs.append({"deleteContentRange": {"range": {"tabId": MEMO_TAB, "startIndex": 1, "endIndex": end - 1}}})
    reqs.append({"insertText": {"location": {"tabId": MEMO_TAB, "index": 1}, "text": text}})

    # 段落スタイル（offset は UTF-16）
    offsets, pos = [], 1
    for l in lines:
        ln = u16len(l["text"])
        offsets.append((pos, pos + ln + 1, l))
        pos += ln + 1
    for start, endi, l in offsets:
        if l["style"] != "NORMAL_TEXT" and l["text"]:
            reqs.append({"updateParagraphStyle": {
                "range": {"tabId": MEMO_TAB, "startIndex": start, "endIndex": endi},
                "paragraphStyle": {"namedStyleType": l["style"]}, "fields": "namedStyleType"}})
    batch(MEMO_DOC, reqs)

    # --- バッチB: プレースホルダ → 空テーブル（後ろから） ---
    reqs = []
    for start, endi, l in reversed(offsets):
        if "_tbl" not in l:
            continue
        tbl = tables[l["_tbl"]]
        rows, cols = len(tbl["rows"]), max(len(r) for r in tbl["rows"])
        reqs.append({"deleteContentRange": {"range": {"tabId": MEMO_TAB, "startIndex": start, "endIndex": endi}}})
        reqs.append({"insertTable": {"location": {"tabId": MEMO_TAB, "index": start}, "rows": rows, "columns": cols}})
    if reqs:
        batch(MEMO_DOC, reqs)

    # --- バッチC: セルへ流し込み（後ろのセルから）＋ 見出し行/バナーは太字 ---
    memo = get_doc(MEMO_DOC)
    t0 = find_tab(memo, tab_id=MEMO_TAB)
    doc_tables = [el for el in t0["documentTab"]["body"]["content"] if "table" in el]
    if len(doc_tables) != len(tables):
        sys.exit(f"table count mismatch: doc={len(doc_tables)} model={len(tables)}")
    fills = []
    for el, model in zip(doc_tables, tables):
        for r, tr in enumerate(el["table"]["tableRows"]):
            for c, tc in enumerate(tr["tableCells"]):
                val = model["rows"][r][c] if c < len(model["rows"][r]) else ""
                if not val:
                    continue
                idx = tc["content"][0]["startIndex"]
                bold = model["banner"] or r == 0
                fills.append((idx, val, bold))
    reqs = []
    for idx, val, bold in sorted(fills, reverse=True):
        reqs.append({"insertText": {"location": {"tabId": MEMO_TAB, "index": idx}, "text": val}})
        if bold:
            reqs.append({"updateTextStyle": {
                "range": {"tabId": MEMO_TAB, "startIndex": idx, "endIndex": idx + u16len(val)},
                "textStyle": {"bold": True}, "fields": "bold"}})
    for i in range(0, len(reqs), 400):
        batch(MEMO_DOC, reqs[i:i + 400])
    print(f"done: {len(lines)} paragraphs, {len(tables)} tables")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-tab")
    ap.add_argument("--highlights", required=True)
    ap.add_argument("--feedback")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import datetime
    today = datetime.date.today().isoformat()

    prod = get_doc(PROD_DOC)
    tab_name = args.source_tab or latest_dated_tab(prod)
    src = find_tab(prod, title=tab_name)
    if not src:
        sys.exit(f"production tab not found: {tab_name}")

    highlights = [l.rstrip("\n") for l in open(args.highlights, encoding="utf-8")]
    if args.feedback:
        feedback = [l.rstrip("\n") for l in open(args.feedback, encoding="utf-8")]
    else:
        memo = get_doc(MEMO_DOC)
        feedback = extract_feedback(find_tab(memo, tab_id=MEMO_TAB))
        if not feedback:
            feedback = ["6. お客様の声・フィードバック（週報共有用）", ""]

    blocks = compose(tab_name, highlights, feedback, parse_blocks(src), today)
    render(blocks, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
