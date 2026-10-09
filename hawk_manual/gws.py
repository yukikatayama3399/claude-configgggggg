"""gws (Google Workspace CLI) の薄いラッパー。"""
import json
import subprocess


def call(method: str, params: dict, body: dict | None = None) -> dict:
    """例: call("sheets.spreadsheets.get", {"spreadsheetId": sid})"""
    cmd = ["gws", *method.split("."), "--params", json.dumps(params, ensure_ascii=False)]
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"gws {method} failed: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout) if out.stdout.strip() else {}


def read_tab(spreadsheet_id: str, tab: str) -> list[dict]:
    """タブを読み、ヘッダー行をキーにした dict のリストで返す。"""
    res = call("sheets.spreadsheets.values.get",
               {"spreadsheetId": spreadsheet_id, "range": f"{tab}!A1:Z"})
    rows = res.get("values", [])
    if not rows:
        return []
    header = rows[0]
    # 先頭列（ID）が空の行は無視する。チェックボックス列があると空行も FALSE を返すため
    return [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows[1:] if r and r[0].strip()]
