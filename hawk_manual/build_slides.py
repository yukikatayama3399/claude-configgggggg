"""マスターシートからスライドを作り直す。

    python3 build_slides.py draft        # 下書き版: 全行（差戻し以外）。見え方の確認用
    python3 build_slides.py prod         # 本番版: 承認済 × 提供中 の行だけ
    python3 build_slides.py prod --lite  # 本番・簡易版: さらに「簡易版」チェックの行だけ
    python3 build_slides.py prod --archive  # 本番を作り直したあと PDF を日付付きで保存し版管理に記録

プレゼンは毎回「同じファイルの中身を全部差し替え」る。URL が変わらないので
お客様に配ったリンクはそのまま最新になる。初回だけ新規作成し config.json に ID を書き戻す。
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess

from gws import call, read_tab
from schema import APPROVED, CATEGORY_ORDER, RELEASED, REJECTED, SUPERSEDED

HERE = pathlib.Path(__file__).parent
CONFIG = HERE / "config.json"
JST = dt.timezone(dt.timedelta(hours=9))
MAX_LINES = 9  # 1枚に載せる箇条書きの上限。超えたら続きページに分ける

TITLES = {
    "draft": "【下書き】HAWK 機能取扱説明書",
    "prod": "HAWK 機能取扱説明書",
    "prod_lite": "HAWK 機能取扱説明書（簡易版）",
}


def load_rows(sid: str, mode: str, lite: bool) -> dict[str, list[dict]]:
    def keep(r: dict) -> bool:
        if mode == "draft":
            return r.get("承認") not in (REJECTED, SUPERSEDED)
        ok = r.get("承認") == APPROVED and r.get("提供状態", RELEASED) in (RELEASED, "")
        return ok and (not lite or r.get("簡易版", "").upper() == "TRUE")

    def latest_per_id(rows: list[dict], id_col: str) -> list[dict]:
        # 同じIDの行が複数あれば後ろ（新しい）を採用。仕様変更は同IDの新しい行として足す運用のため
        by_id: dict[str, dict] = {}
        for r in rows:
            by_id[r[id_col]] = r
        return list(by_id.values())

    out = {}
    for tab, id_col in (("機能一覧", "機能ID"), ("サイトマップ", "画面ID"), ("逆引き", "UCID"), ("更新履歴", None)):
        rows = read_tab(sid, tab)
        if tab == "更新履歴":
            out[tab] = [r for r in rows if mode == "draft" or r.get("反映状況") == APPROVED]
        elif tab == "サイトマップ":
            out[tab] = latest_per_id([r for r in rows if mode == "draft" or r.get("承認") == APPROVED], id_col)
        else:
            out[tab] = latest_per_id([r for r in rows if keep(r)], id_col)
    return out


class Deck:
    """Slides API のリクエストを溜めるだけのビルダー。"""

    def __init__(self):
        self.requests: list[dict] = []
        self.n = 0

    def _slide(self, layout: str, mapping: dict[str, str]) -> str:
        self.n += 1
        sid = f"g{self.n:03d}"
        self.requests.append({"createSlide": {
            "objectId": sid,
            "slideLayoutReference": {"predefinedLayout": layout},
            "placeholderIdMappings": [
                {"layoutPlaceholder": {"type": t, "index": 0}, "objectId": f"{sid}_{k}"}
                for k, t in mapping.items()],
        }})
        return sid

    def _text(self, oid: str, text: str):
        if text:
            self.requests.append({"insertText": {"objectId": oid, "text": text}})

    def title(self, title: str, subtitle: str):
        s = self._slide("TITLE", {"t": "CENTERED_TITLE", "s": "SUBTITLE"})
        self._text(f"{s}_t", title)
        self._text(f"{s}_s", subtitle)

    def section(self, title: str):
        s = self._slide("SECTION_HEADER", {"t": "TITLE"})
        self._text(f"{s}_t", title)

    def bullets(self, title: str, lines: list[str]):
        """箇条書き。多ければ続きページに分割する。行頭の全角スペース2個で1段下げ。"""
        chunks = [lines[i:i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)] or [[]]
        for i, chunk in enumerate(chunks):
            s = self._slide("TITLE_AND_BODY", {"t": "TITLE", "b": "BODY"})
            self._text(f"{s}_t", title + (f"（続き {i + 1}）" if i else ""))
            self._text(f"{s}_b", "\n".join(chunk))


def build(data: dict, mode: str, lite: bool) -> Deck:
    d = Deck()
    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    kind = "prod_lite" if lite else mode
    feats, screens, ucs, changes = data["機能一覧"], data["サイトマップ"], data["逆引き"], data["更新履歴"]

    d.title(TITLES[kind], f"{today} 時点 ／ 掲載機能 {len(feats)} 件")
    d.bullets("この資料の使い方", [
        "① 画面マップ … HAWK の画面構成と、どの画面から何ができるか",
        "② 機能一覧 … カテゴリ別に、できること・設定項目・目的",
        "③ 逆引き … 「こうしたい」から使う機能を探す",
        "④ 最近の更新 … 新しく使えるようになった機能",
        "このページは随時更新されます。リンクを開くと常に最新版が見られます。",
    ])

    if changes:
        recent = sorted(changes, key=lambda r: r.get("リリース日") or r.get("検知日"), reverse=True)[:12]
        d.bullets("最近の更新", [f"{r.get('リリース日') or r.get('検知日')}　{r['内容']}" for r in recent])

    if screens:
        d.section("① 画面マップ")
        lines = []
        for r in screens:
            depth = sum(1 for k in ("階層1", "階層2", "階層3") if r.get(k))
            label = r.get("画面名") or r.get(f"階層{depth}") or r["画面ID"]
            desc = r.get("この画面でやること", "")
            lines.append("　　" * max(depth - 1, 0) + label + (f" … {desc}" if desc else ""))
        d.bullets("画面マップ", lines)

    d.section("② 機能一覧")
    by_cat: dict[str, list[dict]] = {}
    for r in feats:
        by_cat.setdefault(r.get("カテゴリ") or "その他", []).append(r)
    order = [c for c in CATEGORY_ORDER if c in by_cat] + sorted(c for c in by_cat if c not in CATEGORY_ORDER)
    for cat in order:
        lines = []
        for r in by_cat[cat]:
            mark = "" if mode != "draft" or r.get("承認") == APPROVED else "［未承認］"
            lines.append(f"{mark}■ {r['機能名']}：{r.get('できること', '')}")
            if r.get("設定項目・選択肢"):
                lines.append(f"　　設定：{r['設定項目・選択肢']}")
            if r.get("何のため（目的）"):
                lines.append(f"　　目的：{r['何のため（目的）']}")
            if r.get("制約・注意"):
                lines.append(f"　　注意：{r['制約・注意']}")
        d.bullets(cat, lines)

    if ucs:
        d.section("③ 逆引き（やりたいこと → 機能）")
        names = {r["機能ID"]: r["機能名"] for r in feats}
        lines = []
        for r in ucs:
            ids = [i.strip() for i in re.split(r"[,、\s]+", r.get("使う機能ID", "")) if i.strip()]
            used = "、".join(names.get(i, i) for i in ids)
            lines.append(f"■ {r['やりたいこと']}")
            lines.append(f"　　→ {r.get('手順（概要）', '')}" + (f"（{used}）" if used else ""))
        d.bullets("逆引き", lines)
    return d


def ensure_presentation(cfg: dict, key: str, title: str) -> str:
    pid = cfg.get(key)
    if not pid:
        pid = call("slides.presentations.create", {}, {"title": title})["presentationId"]
        if cfg.get("folder_id"):
            subprocess.run(["gog", "--account", cfg["account"], "drive", "move", pid, "--parent", cfg["folder_id"]],
                           capture_output=True, check=True)
        cfg[key] = pid
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return pid


def replace_all(pid: str, deck: Deck):
    old = [s["objectId"] for s in call("slides.presentations.get", {"presentationId": pid}).get("slides", [])]
    # 古いスライドの objectId と衝突しないよう、今回分に接頭辞を付ける
    stamp = dt.datetime.now(JST).strftime("%H%M%S")
    raw = json.dumps(deck.requests, ensure_ascii=False)
    raw = re.sub(r'"(g\d{3}(?:_[a-z])?)"', lambda m: f'"v{stamp}{m.group(1)}"', raw)
    reqs = json.loads(raw) + [{"deleteObject": {"objectId": o}} for o in old]
    # コマンドライン引数の長さ制限があるので、約60KBずつ分けて送る
    batch, size = [], 0
    for r in reqs:
        n = len(json.dumps(r, ensure_ascii=False).encode())
        if batch and size + n > 60_000:
            call("slides.presentations.batchUpdate", {"presentationId": pid}, {"requests": batch})
            batch, size = [], 0
        batch.append(r)
        size += n
    if batch:
        call("slides.presentations.batchUpdate", {"presentationId": pid}, {"requests": batch})


def data_hash(data: dict) -> str:
    """掲載内容（行データ）のハッシュ。表紙の日付だけ変わった場合は同じ値になる。"""
    import hashlib
    return hashlib.sha1(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def last_archived_hash(sid: str, kind: str) -> str:
    rows = [r for r in read_tab(sid, "版管理") if r.get("種類") == kind]
    return rows[-1].get("メモ", "").removeprefix("hash:") if rows else ""


def archive(cfg: dict, pid: str, kind: str, n_rows: int, digest: str):
    stamp = dt.datetime.now(JST).strftime("%Y%m%d")
    pdf = HERE / f"{TITLES[kind]}_{stamp}.pdf"
    subprocess.run(["gws", "drive", "files", "export", "-o", str(pdf), "--params",
                    json.dumps({"fileId": pid, "mimeType": "application/pdf"})], check=True)
    link = ""
    if cfg.get("archive_folder_id"):
        up = subprocess.run(["gog", "--account", cfg["account"], "-j", "drive", "upload", str(pdf),
                             "--parent", cfg["archive_folder_id"]], capture_output=True, text=True, check=True)
        res = json.loads(up.stdout)
        link = (res.get("file") or res).get("webViewLink", "")
        pdf.unlink()
    call("sheets.spreadsheets.values.append",
         {"spreadsheetId": cfg["master_sheet_id"], "range": "版管理!A1", "valueInputOption": "RAW"},
         {"values": [[stamp, dt.datetime.now(JST).isoformat(timespec="minutes"), kind,
                      f"https://docs.google.com/presentation/d/{pid}/edit", link or str(pdf), n_rows, f"hash:{digest}"]]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["draft", "prod"])
    ap.add_argument("--lite", action="store_true")
    ap.add_argument("--archive", action="store_true")
    a = ap.parse_args()
    cfg = json.loads(CONFIG.read_text())
    kind = "prod_lite" if a.lite else a.mode
    data = load_rows(cfg["master_sheet_id"], a.mode, a.lite)
    deck = build(data, a.mode, a.lite)
    pid = ensure_presentation(cfg, f"{kind}_presentation_id", TITLES[kind])
    replace_all(pid, deck)
    print(f"{kind}: {deck.n} slides, {len(data['機能一覧'])} features")
    print(f"https://docs.google.com/presentation/d/{pid}/edit")
    if a.archive and a.mode == "prod":
        digest = data_hash(data)
        if digest == last_archived_hash(cfg["master_sheet_id"], kind):
            print("内容に変化なし。PDF 保存はスキップ")
        else:
            archive(cfg, pid, kind, len(data["機能一覧"]), digest)
            print("PDF を保存し版管理に記録")


if __name__ == "__main__":
    main()
