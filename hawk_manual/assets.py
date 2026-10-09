"""スライドに貼る画像（ロゴ・画面スクショ）の素材置き場を管理する。

素材置き場 = config.json の assets_presentation_id（自動管理用の Google スライド）。
画像は1枚ずつ「page_<key>」スライドに「asset_<key>」として置き、代替テキストに出典 ref を記録する。
他人のデッキが消えても取説が壊れないよう、生成時は必ずここから画像を引く。

ref の書式（サイトマップ「スクショ」列）:
  slides:<presentationId>/<slideObjectId>  … そのスライドで一番大きい画像
  drive:<fileId>                          … Drive の画像ファイル
スクショ用フォルダに「S-15_xxx.png」のように画面IDで始まるファイルを置くと、
そちらが優先され、サイトマップの「スクショ」列も drive:<fileId> に書き換わる。
"""
import json
import pathlib
import re
import subprocess

from gws import call, read_tab
from schema import TABS

CFG_PATH = pathlib.Path(__file__).parent / "config.json"


def _largest_image_url(pid: str, slide_id: str) -> str:
    page = call("slides.presentations.pages.get", {"presentationId": pid, "pageObjectId": slide_id})
    best, area = "", 0
    for e in page.get("pageElements", []):
        if "image" in e:
            s, t = e["size"], e.get("transform", {})
            w = s["width"]["magnitude"] * t.get("scaleX", 1) / 12700
            a = s["width"]["magnitude"] * t.get("scaleX", 1) * s["height"]["magnitude"] * t.get("scaleY", 1)
            if w < 200:  # ロゴ・アイコンは画面キャプチャとみなさない
                continue
            if a > area:
                best, area = e["image"]["contentUrl"], a
    return best


def _drive_image_url(file_id: str) -> str:
    meta = call("drive.files.get", {"fileId": file_id, "fields": "thumbnailLink", "supportsAllDrives": True})
    link = meta.get("thumbnailLink", "")
    return re.sub(r"=s\d+$", "=s1600", link)


def resolve(ref: str) -> str:
    kind, _, rest = ref.partition(":")
    if kind == "slides":
        pid, _, sid = rest.partition("/")
        return _largest_image_url(pid, sid)
    if kind == "drive":
        return _drive_image_url(rest)
    raise ValueError(f"unknown ref: {ref}")


def pick_up_screenshot_folder(cfg: dict) -> int:
    """スクショ用フォルダの画像をサイトマップの「スクショ」列に反映する。反映件数を返す。"""
    folder = cfg.get("screenshot_folder_id")
    if not folder:
        return 0
    out = subprocess.run(["gog", "--account", cfg["account"], "-j", "drive", "ls", "--parent", folder],
                         capture_output=True, text=True, check=True)
    files = {}
    for f in sorted(json.loads(out.stdout).get("files", []), key=lambda f: f.get("modifiedTime", "")):
        m = re.match(r"(S-\d+)", f["name"])
        if m and f.get("mimeType", "").startswith("image/"):
            files[m.group(1)] = f["id"]  # 同じ画面IDが複数あれば新しい方
    sid = cfg["master_sheet_id"]
    rows = call("sheets.spreadsheets.values.get", {"spreadsheetId": sid, "range": "サイトマップ!A1:Z"}).get("values", [])
    col = chr(ord("A") + TABS["サイトマップ"].index("スクショ"))
    updates = []
    for n, r in enumerate(rows[1:], start=2):
        if r and r[0] in files:
            ref = f"drive:{files[r[0]]}"
            cur = r[TABS["サイトマップ"].index("スクショ")] if len(r) > TABS["サイトマップ"].index("スクショ") else ""
            if cur != ref:
                updates.append({"range": f"サイトマップ!{col}{n}", "values": [[ref]]})
    if updates:
        call("sheets.spreadsheets.values.batchUpdate", {"spreadsheetId": sid},
             {"valueInputOption": "RAW", "data": updates})
    return len(updates)


def sync(cfg: dict) -> dict[str, str]:
    """サイトマップのスクショ ref を素材置き場へ取り込み、{key: contentUrl} を返す。"""
    pid = cfg["assets_presentation_id"]
    pres = call("slides.presentations.get", {"presentationId": pid})
    have = {}  # key -> (ref, contentUrl)
    for s in pres.get("slides", []):
        for e in s.get("pageElements", []):
            if e["objectId"].startswith("asset_") and "image" in e:
                have[e["objectId"][6:]] = (e.get("description", ""), e["image"]["contentUrl"])
    want = {r["画面ID"]: r["スクショ"] for r in read_tab(cfg["master_sheet_id"], "サイトマップ") if r.get("スクショ")}
    req = []
    for key in have:
        if not key.startswith("logo_") and key not in want:  # サイトマップから外れた素材は消す
            req.append({"deleteObject": {"objectId": f"page_{key}"}})
    for key, ref in want.items():
        if key in have and have[key][0] == ref:
            continue
        try:
            url = resolve(ref)
        except Exception as e:  # 参照切れは生成を止めずに飛ばす
            print(f"  素材 {key}: 取得失敗 {ref} ({e})")
            continue
        if not url:
            print(f"  素材 {key}: 画像が見つからない {ref}")
            continue
        if key in have:
            req.append({"deleteObject": {"objectId": f"page_{key}"}})
        req += [{"createSlide": {"objectId": f"page_{key}"}},
                {"createImage": {"objectId": f"asset_{key}", "url": url, "elementProperties": {"pageObjectId": f"page_{key}"}}},
                {"updatePageElementAltText": {"objectId": f"asset_{key}", "title": key, "description": ref}}]
    for i in range(0, len(req), 30):
        call("slides.presentations.batchUpdate", {"presentationId": pid}, {"requests": req[i:i + 30]})
    if req:
        print(f"  素材置き場: {len([r for r in req if 'createImage' in r])} 枚を取り込み")
        pres = call("slides.presentations.get", {"presentationId": pid})
    urls, sizes = {}, {}
    for s in pres.get("slides", []):
        for e in s.get("pageElements", []):
            if e["objectId"].startswith("asset_") and "image" in e:
                key = e["objectId"][6:]
                urls[key] = e["image"]["contentUrl"]
                sz, t = e["size"], e.get("transform", {})
                sizes[key] = (sz["width"]["magnitude"] * t.get("scaleX", 1), sz["height"]["magnitude"] * t.get("scaleY", 1))
    return {"urls": urls, "sizes": sizes}
