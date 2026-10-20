#!/usr/bin/env python3
"""マイドライブ直下（受け皿）に置かれたファイルを、決まった置き場所へ振り分けるための CLI。

どこへ入れるかの判断は drive-inbox-sort スキル（.claude/skills/drive-inbox-sort/SKILL.md）が行い、
このスクリプトは「一覧・中身の確認・移動」を安全に実行するだけ。移動は既定でドライラン。

  python3 drive_inbox/drive_inbox.py inventory            # 直下の振り分け対象を JSON で出す
  python3 drive_inbox/drive_inbox.py peek <fileId>         # 中身の先頭を表示（判断材料）
  python3 drive_inbox/drive_inbox.py customers             # 10_顧客 の各社フォルダと 1_/2_/9_ の ID
  python3 drive_inbox/drive_inbox.py move <fileId> <DEST> [--name 新しい名前] [--apply]
  python3 drive_inbox/drive_inbox.py mkcustomer <社名> [--apply]

DEST は folders.json のキー（例: 02_顧客会議ログ / 50_会議メモ）か、フォルダ ID。

守っていること:
- 会議メモ・文字起こし・録音は共有ドライブへ移さない（move が拒否する）。片山ルール 2026-10-20。
- 共有ドライブへはフォルダごと移せない（Drive の仕様）ので、同じ構成を作って中身だけ移す。
- 移動先に同じ名前・同じ中身（md5）のファイルが既にあれば、移さずにマイドライブの「_削除候補」へ入れる。
- 共有ドライブからマイドライブへは戻せない（権限上）ので、迷うものは動かさずに報告に回す（判断はスキル側）。
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

CFG = json.loads((pathlib.Path(__file__).parent / "folders.json").read_text())
FOLDER = "application/vnd.google-apps.folder"
DELETE_BOX = "_削除候補"

MEMO_NAME = re.compile(r"Gemini によるメモ|^メモ - 「|文字起こし|Transcript|Recording|録音|ボイスメモ|音声メモ")
MEET_STAMP = re.compile(r" - \d{4}/\d{2}/\d{2} \d{1,2}:\d{2} JST")


def call(method: str, params: dict, body: dict | None = None, cwd: str | None = None) -> dict:
    cmd = ["gws", *method.split("."), "--params", json.dumps(params, ensure_ascii=False)]
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if out.returncode != 0:
        raise RuntimeError(f"gws {method} failed: {(out.stderr or out.stdout).strip()[-500:]}")
    return json.loads(out.stdout) if out.stdout.strip() else {}


def get(fid: str, fields: str = "id,name,mimeType,parents,driveId,size,md5Checksum,trashed") -> dict:
    return call("drive.files.get", {"fileId": fid, "supportsAllDrives": True, "fields": fields})


def children(fid: str, extra_q: str = "") -> list[dict]:
    q = f"'{fid}' in parents and trashed=false" + (f" and {extra_q}" if extra_q else "")
    items, token = [], None
    while True:
        p = {"q": q, "corpora": "allDrives", "supportsAllDrives": True, "includeItemsFromAllDrives": True,
             "pageSize": 1000, "fields": "nextPageToken,files(id,name,mimeType,size,md5Checksum,createdTime,modifiedTime)"}
        if token:
            p["pageToken"] = token
        r = call("drive.files.list", p)
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            return items


def resolve(dest: str) -> str:
    if dest == DELETE_BOX:
        return delete_box()
    return CFG["my"].get(dest) or CFG["shared"].get(dest) or dest


def is_shared(fid: str) -> bool:
    return bool(get(fid, "driveId").get("driveId"))


def is_meeting_memo(f: dict) -> bool:
    mt = f.get("mimeType", "")
    return bool(MEMO_NAME.search(f["name"]) or mt.startswith("audio/")
                or (mt.startswith("video/") and MEET_STAMP.search(f["name"])))


def delete_box() -> str:
    """マイドライブ直下の「_削除候補」。手でゴミ箱に入れられていたら作り直す。"""
    for f in children("root", f"mimeType='{FOLDER}'"):
        if f["name"] == DELETE_BOX:
            return f["id"]
    return call("drive.files.create", {"fields": "id"}, {"name": DELETE_BOX, "mimeType": FOLDER, "parents": ["root"]})["id"]


def emit(**kw) -> None:
    print(json.dumps(kw, ensure_ascii=False))


# ---------------------------------------------------------------- inventory / peek / customers

def cmd_inventory(_args) -> None:
    fixed = set(CFG["my"].values())
    out = []
    for f in children("root", "'me' in owners"):
        if f["id"] in fixed or f["name"] == DELETE_BOX:
            continue
        if f["mimeType"] == FOLDER and f["name"] in CFG["system_folders"]:
            continue
        f["meeting_memo"] = is_meeting_memo(f)
        f["empty_untitled"] = f["name"].startswith("無題") and int(f.get("size", 0) or 0) <= 1100
        if f["mimeType"] == FOLDER:
            f["children"] = len(children(f["id"]))
        out.append(f)
    print(json.dumps(sorted(out, key=lambda x: x["createdTime"]), ensure_ascii=False, indent=1))


def _office_text(path: pathlib.Path) -> str:
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return ""
    parts = [n for n in z.namelist() if re.match(r"(word/document|ppt/slides/slide\d+|xl/sharedStrings)\.xml$", n)]
    return " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore")) for n in sorted(parts))


def cmd_peek(args) -> None:
    f = get(args.id)
    mt, limit = f["mimeType"], args.chars
    with tempfile.TemporaryDirectory() as tmp:
        text = ""
        if mt in ("application/vnd.google-apps.document", "application/vnd.google-apps.presentation"):
            subprocess.run(["gws", "drive", "files", "export", "-o", "x.txt", "--params",
                            json.dumps({"fileId": args.id, "mimeType": "text/plain"})], cwd=tmp, capture_output=True)
            p = pathlib.Path(tmp, "x.txt")
            text = p.read_text("utf-8", "ignore") if p.exists() else ""
        elif mt == "application/vnd.google-apps.spreadsheet":
            subprocess.run(["gws", "drive", "files", "export", "-o", "x.csv", "--params",
                            json.dumps({"fileId": args.id, "mimeType": "text/csv"})], cwd=tmp, capture_output=True)
            p = pathlib.Path(tmp, "x.csv")
            text = p.read_text("utf-8", "ignore") if p.exists() else ""
        elif mt == FOLDER:
            text = "\n".join(c["name"] for c in children(args.id))
        elif not mt.startswith(("image/", "video/", "audio/")):
            subprocess.run(["gws", "drive", "files", "get", "-o", "x.bin", "--params",
                            json.dumps({"fileId": args.id, "alt": "media", "supportsAllDrives": True})],
                           cwd=tmp, capture_output=True)
            p = pathlib.Path(tmp, "x.bin")
            if p.exists():
                if mt == "application/pdf":
                    r = subprocess.run(["pdftotext", "-l", "3", str(p), "-"], capture_output=True, text=True)
                    text = r.stdout
                elif "openxmlformats" in mt:
                    text = _office_text(p)
                else:
                    text = p.read_bytes()[:limit * 3].decode("utf-8", "ignore")
    print(f"# {f['name']}  ({mt}, {f.get('size', '-')} bytes)")
    print(re.sub(r"[ \t]+", " ", text).strip()[:limit] or "（テキストなし：画像・動画などはファイル名と作成日で判断する）")


def cmd_customers(_args) -> None:
    for parent_key in ("10_顧客", "10_戦略的パートナーシップ"):
        for c in sorted(children(CFG["shared"][parent_key], f"mimeType='{FOLDER}'"), key=lambda x: x["name"]):
            subs = {s["name"]: s["id"] for s in children(c["id"], f"mimeType='{FOLDER}'")}
            emit(parent=parent_key, name=c["name"], id=c["id"], subfolders=subs)


# ---------------------------------------------------------------- move / mkcustomer

def _move_one(fid: str, dest: str, name: str | None, apply: bool) -> dict:
    f = get(fid)
    body = {"name": name} if name else {}
    if not apply:
        return {"plan": "move", "name": f["name"], "to": dest, "rename": name}
    r = call("drive.files.update", {"fileId": fid, "addParents": dest, "removeParents": ",".join(f.get("parents", [])),
                                    "supportsAllDrives": True, "fields": "id,name,parents"}, body)
    return {"moved": r["name"], "id": fid, "to": dest}


def _copy_structure(fid: str, dest: str, name: str | None, apply: bool) -> dict:
    """共有ドライブにはフォルダを移せないので、同名フォルダを作って中身を再帰的に移す。元フォルダは空のまま残す。"""
    src = get(fid)
    new_name = name or src["name"]
    if not apply:
        return {"plan": "copy-structure", "name": src["name"], "to": dest, "items": len(children(fid))}
    existing = [c for c in children(dest, f"mimeType='{FOLDER}'") if c["name"] == new_name]
    nf = existing[0]["id"] if existing else call("drive.files.create", {"supportsAllDrives": True, "fields": "id"},
                                                 {"name": new_name, "mimeType": FOLDER, "parents": [dest]})["id"]
    moved = 0
    for c in children(fid):
        if c["mimeType"] == FOLDER:
            _copy_structure(c["id"], nf, None, True)
        else:
            _move_one(c["id"], nf, None, True)
            moved += 1
    _move_one(fid, delete_box(), None, True)  # 空になった元フォルダは削除候補へ
    return {"copied_structure": new_name, "new_folder": nf, "moved_files": moved}


def cmd_move(args) -> None:
    dest = resolve(args.dest)
    f = get(args.id)
    shared = is_shared(dest)
    if shared and is_meeting_memo(f):
        emit(error="refused", reason="会議メモ・文字起こし・録音は共有ドライブへ移さない（マイドライブ 50_会議メモ へ）", name=f["name"])
        sys.exit(3)
    if f.get("md5Checksum"):
        for c in children(dest):
            if c["name"] == f["name"] and c.get("md5Checksum") == f["md5Checksum"]:
                emit(duplicate_of=c["id"], **_move_one(args.id, delete_box(), None, args.apply))
                return
    if f["mimeType"] == FOLDER and shared and not f.get("driveId"):
        emit(**_copy_structure(args.id, dest, args.name, args.apply))
    else:
        emit(**_move_one(args.id, dest, args.name, args.apply))


def cmd_mkcustomer(args) -> None:
    parent = CFG["shared"]["10_顧客"]
    folders = children(parent, f"mimeType='{FOLDER}'")
    key = re.sub(r"(株式会社|合同会社|有限会社|様|さん|\s)", "", args.name)
    for c in folders:
        if key and key in re.sub(r"^\d+_", "", c["name"]):
            emit(exists=c["name"], id=c["id"])
            return
    nums = [int(m.group(1)) for c in folders if (m := re.match(r"^(\d+)_", c["name"]))]
    new_name = f"{max(nums, default=0) + 1}_{args.name}"
    if not args.apply:
        emit(plan="mkcustomer", name=new_name)
        return
    cid = call("drive.files.create", {"supportsAllDrives": True, "fields": "id"},
               {"name": new_name, "mimeType": FOLDER, "parents": [parent]})["id"]
    subs = {}
    for s in ("1_議事録", "2_提案書", "9_契約書"):
        subs[s] = call("drive.files.create", {"supportsAllDrives": True, "fields": "id"},
                       {"name": s, "mimeType": FOLDER, "parents": [cid]})["id"]
    emit(created=new_name, id=cid, subfolders=subs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("inventory").set_defaults(fn=cmd_inventory)
    p = sp.add_parser("peek"); p.add_argument("id"); p.add_argument("--chars", type=int, default=1500); p.set_defaults(fn=cmd_peek)
    sp.add_parser("customers").set_defaults(fn=cmd_customers)
    p = sp.add_parser("move"); p.add_argument("id"); p.add_argument("dest"); p.add_argument("--name"); p.add_argument("--apply", action="store_true"); p.set_defaults(fn=cmd_move)
    p = sp.add_parser("mkcustomer"); p.add_argument("name"); p.add_argument("--apply", action="store_true"); p.set_defaults(fn=cmd_mkcustomer)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
