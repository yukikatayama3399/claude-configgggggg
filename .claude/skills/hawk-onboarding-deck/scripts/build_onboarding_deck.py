#!/usr/bin/env python3
"""HAWK オンボーディング資料をテンプレから生成する。

usage:
  python3 build_onboarding_deck.py spec.json            # 生成して URL を出力
  python3 build_onboarding_deck.py spec.json --dry-run  # 置換内容とカレンダーだけ表示

テンプレ（Google Slides）を Drive でコピーし、{{KEY}} を置換したうえで
カレンダーのスライド（角丸のマス 21 個）を spec の日付で塗り直す。
gws（Google Workspace CLI）が使える環境で動く。
"""
import datetime as dt
import json
import re
import subprocess
import sys

TEMPLATE_ID = "1yeE82wjfdoZk7zwcIa6sBSHH-d-k8quzdpIqFUbdJ5w"
WEEK = "月火水木金土日"
E = 12700  # EMU / pt

DARK = {"red": 0.106, "green": 0.369, "blue": 0.125}    # 開始日
MID = {"red": 0.263, "green": 0.627, "blue": 0.278}     # 中間MTG・最終日
REVIEW = {"red": 0.180, "green": 0.490, "blue": 0.196}  # 振り返り
PALE = {"red": 0.910, "green": 0.961, "blue": 0.914}    # 期間内
WHITE = {"red": 1, "green": 1, "blue": 1}               # 期間外
BORDER = {"red": 0.835, "green": 0.871, "blue": 0.839}
GRAY_TXT = {"red": 0.639, "green": 0.678, "blue": 0.643}


def gws(args, body=None):
    cmd = ["gws"] + args
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"gws failed: {' '.join(args[:3])}\n{r.stdout[:2000]}{r.stderr[:2000]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def d(s):
    return dt.date.fromisoformat(s)


def md(x):
    return f"{x.month}/{x.day}"


def mdw(x):
    return f"{x.month}/{x.day}（{WEEK[x.weekday()]}）"


def long_date(x):
    return f"{x.year}年{x.month}月{x.day}日（{WEEK[x.weekday()]}）"


def or_dates(ds, with_week=True):
    """[10/15, 10/16] -> 10/15（木）or 16（金）／ 月が違えば 10/31（金）or 11/3（月）"""
    out = []
    for i, x in enumerate(ds):
        if i and x.month == ds[0].month:
            out.append(f"{x.day}（{WEEK[x.weekday()]}）" if with_week else f"{x.day}")
        else:
            out.append(mdw(x) if with_week else md(x))
    return "or ".join(out) if with_week else " or ".join(out)


def build_values(spec):
    onb = spec["onboarding"]
    od = d(onb["date"])
    ts = spec.get("trial", {})
    t_start = d(ts.get("start", onb["date"]))
    t_end = d(ts["end"]) if ts.get("end") else t_start + dt.timedelta(days=13)
    mid = spec.get("mid_mtg", {})
    mid_dates = [d(x) for x in mid.get("dates", [])] or [t_start + dt.timedelta(days=7)]
    review = d(spec["review"]) if spec.get("review") else t_end - dt.timedelta(days=1)
    st = dt.datetime.strptime(onb["start"], "%H:%M")
    if len(mid_dates) == 1 and mid.get("time"):
        mid_txt = f"{mdw(mid_dates[0])}{mid['time']}〜"
        mid_short = f"{md(mid_dates[0])} {mid['time']}〜"
    else:
        mid_txt = or_dates(mid_dates)
        mid_short = or_dates(mid_dates, with_week=False)
    v = {
        "CLIENT": spec["client"],
        "ONB_DATE_LONG": long_date(od),
        "ONB_DATE": mdw(od),
        "ONB_TIME": f"{onb['start']}〜{onb['end']}",
        "T_START": onb["start"],
        "T_QA": (st + dt.timedelta(minutes=45)).strftime("%H:%M"),
        "T_STEP1": (st + dt.timedelta(minutes=3)).strftime("%H:%M"),
        "T_STEP2": (st + dt.timedelta(minutes=10)).strftime("%H:%M"),
        "T_STEP3": (st + dt.timedelta(minutes=30)).strftime("%H:%M"),
        "TRIAL_START": mdw(t_start),
        "TRIAL_END": mdw(t_end),
        "MID_MTG": mid_txt,
        "MID_MTG_SHORT": mid_short,
        "REVIEW": mdw(review),
        "REVIEW_SHORT": md(review),
        "PREV_MTG": md(d(spec["prev_mtg"])) if spec.get("prev_mtg") else "前回",
    }
    s = spec["summary"]
    for i, (lab, txt) in enumerate(s["situation"][:3], 1):
        v[f"SITU{i}_L"], v[f"SITU{i}"] = lab, txt
    for i, (t, b) in enumerate(s["issues"][:3], 1):
        v[f"ISSUE{i}_T"], v[f"ISSUE{i}_B"] = t, b
    for i, (lab, txt) in enumerate(s["expectations"][:3], 1):
        v[f"EXP{i}_L"], v[f"EXP{i}"] = lab, txt
    cal = {"start": t_start, "end": t_end, "mid": mid_dates, "mid_time": mid.get("time"),
           "review": review, "onb": od}
    return v, cal


def day_status(x, c):
    """(塗り, 枠, 日付文字色, ラベル)"""
    if x < c["start"] or x > c["end"]:
        return WHITE, BORDER, GRAY_TXT, None
    if x == c["start"]:
        return DARK, DARK, WHITE, "開始\n本日" if x == c["onb"] else "開始"
    if x == c["review"]:
        return REVIEW, REVIEW, WHITE, "振り返り\n推奨日"
    if x == c["end"]:
        lab = "予備日\n最終日" if c["review"] == x - dt.timedelta(days=1) else "最終日"
        return MID, MID, WHITE, lab
    if x in c["mid"]:
        if len(c["mid"]) == 1:
            lab = f"中間MTG\n{c['mid_time']}〜" if c["mid_time"] else "中間MTG"
        else:
            lab = "中間MTG\n候補日"
        return MID, MID, WHITE, lab
    return PALE, PALE, DARK, None


def text_of(e):
    return "".join(t.get("textRun", {}).get("content", "") for t in e.get("shape", {}).get("text", {}).get("textElements", [])).strip()


def calendar_requests(pres, c):
    slide = None
    for s in pres["slides"]:
        cells = [e for e in s.get("pageElements", []) if e.get("shape", {}).get("shapeType") == "ROUND_RECTANGLE"]
        if len(cells) == 21:
            slide = s
            break
    if not slide:
        sys.exit("カレンダーのスライド（角丸のマス21個）が見つからない。テンプレが変わっていないか確認")
    els = slide["pageElements"]

    def geo(e):
        t = e["transform"]
        return (t.get("translateX", 0) / E, t.get("translateY", 0) / E,
                e["size"]["width"]["magnitude"] * t.get("scaleX", 1) / E,
                e["size"]["height"]["magnitude"] * t.get("scaleY", 1) / E)

    cells = sorted([e for e in els if e.get("shape", {}).get("shapeType") == "ROUND_RECTANGLE"],
                   key=lambda e: (round(geo(e)[1]), geo(e)[0]))
    boxes = [e for e in els if e.get("shape", {}).get("shapeType") == "TEXT_BOX"]
    monday = c["start"] - dt.timedelta(days=c["start"].weekday())
    R, preview = [], []
    for i, cell in enumerate(cells):
        x, y, w, h = geo(cell)
        day = monday + dt.timedelta(days=i)
        fill, line, tcol, label = day_status(day, c)
        R.append({"updateShapeProperties": {"objectId": cell["objectId"], "shapeProperties": {
            "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": fill}}},
            "outline": {"outlineFill": {"solidFill": {"color": {"rgbColor": line}}}}},
            "fields": "shapeBackgroundFill.solidFill.color,outline.outlineFill.solidFill.color"}})
        inside = [b for b in boxes if x - 6 <= geo(b)[0] <= x + w and y - 6 <= geo(b)[1] <= y + h]
        date_box = [b for b in inside if re.fullmatch(r"\d{1,2}/\d{1,2}", text_of(b))]
        for b in inside:
            if b not in date_box[:1]:
                R.append({"deleteObject": {"objectId": b["objectId"]}})
        style = {"fontFamily": "Noto Sans JP", "bold": True, "fontSize": {"magnitude": 14, "unit": "PT"},
                 "foregroundColor": {"opaqueColor": {"rgbColor": tcol}}}
        if date_box:
            b = date_box[0]["objectId"]
            R.append({"deleteText": {"objectId": b, "textRange": {"type": "ALL"}}})
            R.append({"insertText": {"objectId": b, "insertionIndex": 0, "text": md(day)}})
            R.append({"updateTextStyle": {"objectId": b, "textRange": {"type": "ALL"}, "style": style,
                                          "fields": "fontFamily,bold,fontSize,foregroundColor"}})
        if label:
            oid = f"onbcal_lab_{i:02d}"
            R.append({"createShape": {"objectId": oid, "shapeType": "TEXT_BOX", "elementProperties": {
                "pageObjectId": slide["objectId"],
                "size": {"width": {"magnitude": w - 12, "unit": "PT"}, "height": {"magnitude": 44, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x + 6, "translateY": y + 34, "unit": "PT"}}}})
            R.append({"insertText": {"objectId": oid, "text": label}})
            R.append({"updateTextStyle": {"objectId": oid, "textRange": {"type": "ALL"},
                                          "style": {**style, "fontSize": {"magnitude": 12, "unit": "PT"},
                                                    "foregroundColor": {"opaqueColor": {"rgbColor": WHITE}}},
                                          "fields": "fontFamily,bold,fontSize,foregroundColor"}})
        preview.append(f"{md(day):>5}{'['+label.replace(chr(10), '')+']' if label else ''}")
    return R, preview


def notes_requests(pres, notes):
    """社内向けの対応方針をサマリースライドのスピーカーノートに入れる（先方には見えない）"""
    if not notes:
        return []
    if isinstance(notes, list):
        notes = "\n".join("・" + x for x in notes)
    for s in pres["slides"]:
        if any("お伺いした内容のサマリー" in text_of(e) for e in s.get("pageElements", [])):
            np = s["slideProperties"]["notesPage"]
            nid = np["notesProperties"]["speakerNotesObjectId"]
            R = []
            if any(e["objectId"] == nid and text_of(e) for e in np.get("pageElements", [])):
                R.append({"deleteText": {"objectId": nid, "textRange": {"type": "ALL"}}})
            R.append({"insertText": {"objectId": nid, "insertionIndex": 0, "text": "【社内メモ・先方に見せない】\n" + notes}})
            return R
    return []


def main():
    spec = json.load(open(sys.argv[1]))
    dry = "--dry-run" in sys.argv
    v, cal = build_values(spec)
    if dry:
        for k, x in v.items():
            print(f"{{{{{k}}}}} -> {x}")
    name = spec.get("title") or f"【{spec.get('client_short', spec['client'])}様】HAWKオンボーディング資料_{spec['onboarding']['date'].replace('-', '')}"
    if dry:
        print("title:", name)
        pres = gws(["slides", "presentations", "get", "--params", json.dumps({"presentationId": TEMPLATE_ID})])
        _, prev = calendar_requests(pres, cal)
        for i in range(0, 21, 7):
            print(" ".join(prev[i:i + 7]))
        return
    body = {"name": name}
    if spec.get("folder_id"):
        body["parents"] = [spec["folder_id"]]
    new = gws(["drive", "files", "copy", "--params", json.dumps({"fileId": TEMPLATE_ID, "supportsAllDrives": True})], body)
    pid = new["id"]
    reqs = [{"replaceAllText": {"containsText": {"text": "{{" + k + "}}", "matchCase": True}, "replaceText": x}}
            for k, x in v.items()]
    res = gws(["slides", "presentations", "batchUpdate", "--params", json.dumps({"presentationId": pid})], {"requests": reqs})
    misses = [k for k, r in zip(v, res.get("replies", [])) if not r.get("replaceAllText", {}).get("occurrencesChanged")]
    pres = gws(["slides", "presentations", "get", "--params", json.dumps({"presentationId": pid})])
    left = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", json.dumps(pres, ensure_ascii=False))))
    creq, _ = calendar_requests(pres, cal)
    creq += notes_requests(pres, spec.get("internal_notes"))
    gws(["slides", "presentations", "batchUpdate", "--params", json.dumps({"presentationId": pid})], {"requests": creq})
    print(f"https://docs.google.com/presentation/d/{pid}/edit")
    if misses:
        print("テンプレに見つからなかったキー:", ", ".join(misses))
    if left:
        print("置換されずに残ったプレースホルダ:", ", ".join(left))


if __name__ == "__main__":
    main()
