"""Google スライドを PDF に書き出す。

Drive の export は 10MB 程度で "too large" になるため、
一時コピーをページ範囲ごとに作って書き出し、pypdf で1本に結合する。
"""
import json
import pathlib
import subprocess
import tempfile

from gws import call

CHUNK = 12  # 1回に書き出すページ数


def export_pdf(pid: str, out: pathlib.Path, pages: range | None = None, account: str = "yuki.katayama@fout.jp") -> pathlib.Path:
    from pypdf import PdfWriter
    # 一時コピーは元ファイルの隣ではなく、マニュアル用フォルダ（自分のマイドライブ）に作る。
    # 共有ドライブの他人のフォルダだと、作ったコピーを消す権限が無いことがある
    cfg = json.load(open(pathlib.Path(__file__).with_name("config.json")))
    body = {"parents": [cfg["folder_id"]]} if cfg.get("folder_id") else {}
    slides = [s["objectId"] for s in call("slides.presentations.get", {"presentationId": pid, "fields": "slides(objectId)"})["slides"]]
    idx = list(pages) if pages is not None else list(range(len(slides)))
    writer = PdfWriter()
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        for k in range(0, len(idx), CHUNK):
            keep = set(idx[k:k + CHUNK])
            copy = call("drive.files.copy", {"fileId": pid, "supportsAllDrives": True}, {"name": f"_pdf_tmp_{k}", **body})["id"]
            try:
                cs = [s["objectId"] for s in call("slides.presentations.get", {"presentationId": copy, "fields": "slides(objectId)"})["slides"]]
                dels = [{"deleteObject": {"objectId": o}} for i, o in enumerate(cs) if i not in keep]
                for j in range(0, len(dels), 200):
                    call("slides.presentations.batchUpdate", {"presentationId": copy}, {"requests": dels[j:j + 200]})
                part = f"part_{k:04d}.pdf"
                subprocess.run(["gws", "drive", "files", "export", "-o", part, "--params",
                                json.dumps({"fileId": copy, "mimeType": "application/pdf"})],
                               check=True, cwd=tmp, capture_output=True)
                writer.append(str(pathlib.Path(tmp) / part))
            finally:
                call("drive.files.delete", {"fileId": copy, "supportsAllDrives": True})
    with open(out, "wb") as f:
        writer.write(f)
    return out
