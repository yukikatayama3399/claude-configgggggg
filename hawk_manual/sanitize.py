"""画面キャプチャの個人情報・実データをサンプル表記に置き換える。

OCR（tesseract jpn+eng）で文字の位置を拾い、REPLACE のルールに当たった語を
周囲の背景色で塗りつぶして、サンプル表記を描き込む。

    python3 sanitize.py in.png out.png            # 1枚
    python3 sanitize.py in.png out.png --debug    # 置き換えた箇所を赤枠で示した確認用画像も出す

ルールを足すときは REPLACE に (正規表現, 置き換え後) を追加する。
"""
import argparse
import os
import re
import subprocess
import tempfile
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

FONT = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
FONT_FALLBACK = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"

# (正規表現, 置き換え後)。上から順に評価し、行の中で当たった部分だけを置き換える
# OCR の読み違い（i/l/1、a/e 等）も拾えるよう少し緩めに書く
REPLACE = [
    (r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "hoge@example.com"),
    (r"yuk\S{0,3}kat\w{1,4}ma\S*fout\S*", "hoge@example.com"),
    (r"yuk[il1|]?[._]?kat[a-z]{1,3}ma", "hoge_user"),
    (r"katayama", "hoge"),
    (r"Fre[ae]k\s*Out\s*HAWK\s*S[ae]les", "サンプル株式会社"),
    (r"freakout-hawk-sales", "sample-workspace"),
    (r"act_\d{6,}", "act_000000000000"),
    (r"\b\d{12,}\b", "000000000000"),
    (r"片山\s*優希|片山", "サンプル 太郎"),
    # 社員名は人ごとに別のサンプル名にする（一覧で見たとき同じ名前が並ばないように）
    (r"Aya\s*Sug\w*", "Sample User A"),
    (r"Tomoyuki\s*Sato", "Sample User B"),
    (r"Hiroshi\s*Okada", "Sample User C"),
    (r"Shin\s*Takemura", "Sample User D"),
    (r"Yugo", "Sample User E"),
    (r"岩田\s*弥和", "サンプル 次郎"),
    (r"中西\s*秀之", "サンプル 花子"),
    (r"田染\s*康行", "サンプル 三郎"),
    (r"杉浦", "サンプル"),
]
RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sanitize_rules.json")


def extra_rules(screen_id: str) -> list[tuple[str, str]]:
    """sanitize_rules.json の画面別ルール（代理店名のサンプル化など）。"""
    import json
    try:
        rules = json.load(open(RULES_FILE))
    except OSError:
        return []
    return [tuple(r) for r in rules.get(screen_id, [])]


def _tesseract(im: Image.Image, scale: float = 1.0, dy: int = 0) -> list[dict]:
    """tesseract の TSV を行単位にまとめる。座標は元画像の座標に戻す。"""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        im.save(f.name)
    try:
        tsv = subprocess.run(["tesseract", f.name, "-", "-l", "jpn+eng", "--psm", "11", "tsv"],
                             capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(f.name)
    lines = defaultdict(list)
    for row in tsv.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or not c[11].strip() or float(c[10]) < 10:
            continue
        x, y, w, h = (int(int(v) / scale) for v in c[6:10])
        lines[(c[2], c[3], c[4])].append((c[11], (x, y + dy, x + w, y + dy + h)))
    out = []
    for words in lines.values():
        words.sort(key=lambda t: t[1][0])
        out.append({"words": words})
    return out


def _binarize(im: Image.Image, scale: int, offset: int) -> Image.Image:
    big = im.resize((im.width * scale, im.height * scale))
    med = ImageStat.Stat(big).median[0]
    return big.point(lambda v: 0 if v < med - offset else 255)


def ocr_lines(path: str) -> list[dict]:
    """読み方を変えて何度か読み、結果を足し合わせる。
    モーダル表示中など画面が暗く沈んだキャプチャは、二値化しないと文字が読めない。"""
    gray = Image.open(path).convert("L")
    lines = _tesseract(ImageOps.autocontrast(gray, cutoff=2))
    band = gray.crop((0, 0, gray.width, int(gray.height * 0.09)))  # ヘッダー帯（アカウント表示）は念入りに
    for scale, off in ((3, 25), (3, 12), (2, 18)):
        lines += _tesseract(_binarize(band, scale, off), scale=scale)
    lines += _tesseract(_binarize(gray, 2, 25), scale=2)
    return lines


def _font(size: int):
    for p in (FONT, FONT_FALLBACK):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _bg_and_fg(im: Image.Image, box) -> tuple[tuple, tuple]:
    """枠のすぐ外側の画素の最頻色を背景、枠内で背景から最も遠い色を文字色とみなす。"""
    x0, y0, x1, y1 = box
    px = im.load()
    ring = []
    for x in range(max(x0 - 3, 0), min(x1 + 3, im.width)):
        for y in (max(y0 - 3, 0), min(y1 + 2, im.height - 1)):
            ring.append(px[x, y][:3])
    bg = max(set(ring), key=ring.count) if ring else (255, 255, 255)
    fg, dist = (60, 60, 60), -1
    for x in range(x0, x1, max((x1 - x0) // 30, 1)):
        for y in range(y0, y1, max((y1 - y0) // 8, 1)):
            c = px[x, y][:3]
            d = sum((a - b) ** 2 for a, b in zip(c, bg))
            if d > dist:
                fg, dist = c, d
    return bg, fg


def sanitize(src: str, dst: str, debug: bool = False, screen_id: str = "") -> list[str]:
    im = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(im)
    marks, log = [], []

    def overlaps(b):
        """既に置き換えた枠と半分以上重なっていれば同じ語とみなす。"""
        for m in marks:
            w = min(b[2], m[2]) - max(b[0], m[0])
            h = min(b[3], m[3]) - max(b[1], m[1])
            if w > 0 and h > 0 and w * h > 0.5 * min((b[2] - b[0]) * (b[3] - b[1]), (m[2] - m[0]) * (m[3] - m[1])):
                return True
        return False

    for line in ocr_lines(src):
        # 行の文字列と、文字位置 → 単語の対応を作る
        text, spans = "", []
        for w, box in line["words"]:
            if text and re.match(r"[A-Za-z0-9]", w) and re.search(r"[A-Za-z0-9]$", text):
                text += " "
            spans.append((len(text), len(text) + len(w), box))
            text += w
        done: list[tuple[int, int]] = []  # この行で置き換え済みの文字範囲
        for pat, rep in extra_rules(screen_id) + REPLACE:
            for m in re.finditer(pat, text, flags=0 if pat.startswith("^") else re.I):
                if any(a < m.end() and m.start() < b for a, b in done):
                    continue
                hit = [b for s, e, b in spans if s < m.end() and e > m.start()]
                if not hit:
                    continue
                box = (min(b[0] for b in hit) - 2, min(b[1] for b in hit) - 1,
                       max(b[2] for b in hit) + 2, max(b[3] for b in hit) + 1)
                if overlaps(box):  # 全体読みとヘッダー読みで同じ所を拾った
                    continue
                done.append((m.start(), m.end()))
                bg, fg = _bg_and_fg(im, box)
                draw.rectangle(box, fill=bg)
                size = max(int((box[3] - box[1]) * 0.78), 8)
                font = _font(size)
                while size > 8 and draw.textlength(rep, font=font) > (box[2] - box[0]) * 1.25:
                    size -= 1
                    font = _font(size)
                draw.text((box[0] + 1, box[1] + (box[3] - box[1] - size) // 2), rep, fill=fg, font=font)
                marks.append(box)
                log.append(f"{m.group(0)} -> {rep}")  # marks と同じ順で並ぶ
    # ヘッダーのアカウント表示は「名前（太字）／メールアドレス」の2段。名前を読み落としても
    # メールアドレスの真上の段をまとめて置き換える
    for box in [b for b, rep in zip(marks, log) if rep.endswith("hoge@example.com") and b[1] < im.height * 0.09]:
        h = box[3] - box[1]
        name = (box[0] - 2, max(box[1] - int(h * 1.45), 0), box[0] + int((box[2] - box[0]) * 0.75), box[1] - 1)
        if not any(m[1] <= name[1] + 2 and m[3] >= name[3] - 2 and m[0] <= name[2] and m[2] >= name[0]
                   for m in marks if m is not box):
            bg, fg = _bg_and_fg(im, name)
            draw.rectangle(name, fill=bg)
            size = max(int((name[3] - name[1]) * 0.8), 8)
            draw.text((name[0] + 1, name[1] + 1), "hoge_user", fill=fg, font=_font(size))
            marks.append(name)
            log.append("（メール上段の名前） -> hoge_user")
    im.save(dst)
    if debug:
        dbg = Image.open(dst).convert("RGB")
        d2 = ImageDraw.Draw(dbg)
        for b in marks:
            d2.rectangle(b, outline=(255, 0, 0), width=3)
        dbg.save(dst.replace(".png", "_debug.png"))
    return log


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--screen", default="", help="画面ID（sanitize_rules.json の画面別ルールを使う）")
    a = ap.parse_args()
    for line in sanitize(a.src, a.dst, a.debug, a.screen):
        print(line)
