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
    raise ValueError(f"unknown ref: {ref}")


def resolve_drive_images(cfg: dict, refs: dict[str, str]) -> dict[str, str]:
    """drive: の画像を Slides に取り込めるURLにする。

    非公開の Drive 画像は Slides API から直接読めない（Access forbidden）。公開設定にはせず、
    画像を pptx にまとめて Google スライドへ変換し、変換後の画像URL（署名付き）を使う。
    一時スライドは呼び出し側が取り込み後に消す。戻り値 {key: url}、一時スライドIDは "__tmp__"。
    """
    if not refs:
        return {}
    import tempfile
    from pptx import Presentation
    from pptx.util import Emu
    with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).parent) as tmp:
        prs = Presentation()
        prs.slide_width, prs.slide_height = Emu(9144000), Emu(5143500)
        keys = []
        for key, ref in refs.items():
            name = f"{key}.png"
            subprocess.run(["gws", "drive", "files", "get", "-o", name, "--params",
                            json.dumps({"fileId": ref.split(":", 1)[1], "alt": "media", "supportsAllDrives": True})],
                           check=True, cwd=tmp, capture_output=True)
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.shapes.add_picture(str(pathlib.Path(tmp) / name), 0, 0, width=prs.slide_width)
            keys.append(key)
        pptx = pathlib.Path(tmp) / "import.pptx"
        prs.save(pptx)
        out = subprocess.run(["gog", "--account", cfg["account"], "-j", "drive", "upload", str(pptx),
                              "--convert-to", "slides", "--parent", cfg["folder_id"], "--name", "_素材取り込み用_一時"],
                             capture_output=True, text=True, check=True)
    res = json.loads(out.stdout)
    tmp_pid = (res.get("file") or res)["id"]
    pres = call("slides.presentations.get", {"presentationId": tmp_pid})
    urls = {"__tmp__": tmp_pid}
    for key, slide in zip(keys, pres["slides"]):
        imgs = [e for e in slide.get("pageElements", []) if "image" in e]
        if imgs:
            urls[key] = imgs[0]["image"]["contentUrl"]
    return urls


def _ls(cfg: dict, folder: str) -> list[dict]:
    out = subprocess.run(["gog", "--account", cfg["account"], "-j", "drive", "ls", "--parent", folder],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout).get("files", [])


def processed_folder(cfg: dict) -> str:
    """スクショ用フォルダの中の「加工済み（自動）」フォルダ。無ければ作る。"""
    if cfg.get("processed_folder_id"):
        return cfg["processed_folder_id"]
    for f in _ls(cfg, cfg["screenshot_folder_id"]):
        if f["mimeType"] == "application/vnd.google-apps.folder" and f["name"].startswith("加工済み"):
            fid = f["id"]
            break
    else:
        out = subprocess.run(["gog", "--account", cfg["account"], "-j", "drive", "mkdir", "加工済み（自動・触らない）",
                              "--parent", cfg["screenshot_folder_id"]], capture_output=True, text=True, check=True)
        fid = json.loads(out.stdout)["folder"]["id"]
    cfg["processed_folder_id"] = fid
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return fid


def upload_processed(cfg: dict, key: str, png: pathlib.Path, raw_id: str) -> str:
    """加工済み画像を「<画面ID>__<元ファイルID>.png」で保存し、その fileId を返す。"""
    out = subprocess.run(["gog", "--account", cfg["account"], "-j", "drive", "upload", str(png),
                          "--parent", processed_folder(cfg), "--name", f"{key}__{raw_id}.png"],
                         capture_output=True, text=True, check=True)
    res = json.loads(out.stdout)
    return (res.get("file") or res)["id"]


def pick_up_screenshot_folder(cfg: dict) -> int:
    """スクショ用フォルダの画像を伏せ字加工して、サイトマップの「スクショ」列に反映する。反映件数を返す。

    元画像はそのまま残し、加工済みを「加工済み（自動）」フォルダに置く。加工済みファイル名に
    元ファイルIDを入れておき、同じ元画像を二度加工しない。
    """
    folder = cfg.get("screenshot_folder_id")
    if not folder:
        return 0
    import tempfile
    from sanitize import sanitize
    done = {f["name"].split("__")[1].removesuffix(".png"): f["id"] for f in _ls(cfg, processed_folder(cfg))
            if "__" in f["name"]}
    files = {}
    for f in sorted(_ls(cfg, folder), key=lambda f: f.get("modifiedTime", "")):
        m = re.match(r"(S-\d+)", f["name"])
        if not (m and f.get("mimeType", "").startswith("image/")):
            continue
        if f["id"] not in done:  # 新しい元画像 → 落として加工してアップロード
            with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).parent) as tmp:
                subprocess.run(["gws", "drive", "files", "get", "-o", "raw.png", "--params",
                                json.dumps({"fileId": f["id"], "alt": "media", "supportsAllDrives": True})],
                               check=True, cwd=tmp, capture_output=True)
                out = pathlib.Path(tmp) / "clean.png"
                for line in sanitize(str(pathlib.Path(tmp) / "raw.png"), str(out), screen_id=m.group(1)):
                    print(f"  {m.group(1)}: {line}")
                done[f["id"]] = upload_processed(cfg, m.group(1), out, f["id"])
        files[m.group(1)] = done[f["id"]]  # 同じ画面IDが複数あれば新しい方
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
    todo = {k: r for k, r in want.items() if not (k in have and have[k][0] == r)}
    drive_urls = resolve_drive_images(cfg, {k: r for k, r in todo.items() if r.startswith("drive:")})
    for key, ref in todo.items():
        try:
            url = drive_urls[key] if ref.startswith("drive:") else resolve(ref)
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
    try:
        for i in range(0, len(req), 30):
            call("slides.presentations.batchUpdate", {"presentationId": pid}, {"requests": req[i:i + 30]})
    finally:
        if drive_urls.get("__tmp__"):
            call("drive.files.delete", {"fileId": drive_urls["__tmp__"], "supportsAllDrives": True})
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
