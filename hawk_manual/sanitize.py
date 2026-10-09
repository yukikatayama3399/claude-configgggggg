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
    (r"[\w.+-]+@\s?(f[o0]ut|freakout)\w*", "hoge@example.com"),  # OCR がドメインのドットを落とした場合
    (r"yuk\S{0,3}kat\w{1,4}ma\S*fout\S*", "hoge@example.com"),
    (r"yuk[il1|]?[._]?kat[a-z]{1,3}m[a-z]?", "hoge_user"),
    (r"katayama", "hoge"),
    (r"Fre[ae]k\s*Out\s*HAWK\s*S[ae]les", "サンプル株式会社"),
    (r"freakout-hawk-sales", "sample-workspace"),
    (r"act_\d{6,}", "act_000000000000"),
    # ピクセルタグの noscript 行。ID が URL の途中にあり語の切れ目が無いので、URL ごと書き直す
    (r"\S*facebook\S*/tr\S*", 'src="https://www.facebook.com/tr?id=000000000000&ev=PageView&noscript=1"'),
    (r"(?<!\d)\d{12,}(?!\d)", "000000000000"),  # ピクセルID・ポートフォリオID 等（前後に文字が付いていても拾う）
    (r"片山\s*優希|片山", "サンプル 太郎"),
    # 社員名は人ごとに別のサンプル名にする（一覧で見たとき同じ名前が並ばないように）
    (r"Aya\s*Sug\w*", "Sample User A"),
    (r"Tomoyuki\s*Sato", "Sample User B"),
    (r"Hiroshi\s*Okada", "Sample User C"),
    (r"Shin\s*Takemura", "Sample User D"),
    (r"Yugo", "Sample User E"),
    (r"岩田\s*弥和", "サンプル 次郎"),
    (r"中西\s*秀之", "サンプル 花子"),
    (r"田\S?\s*康\s*行", "サンプル 三郎"),  # OCR が「染」を落とすことがある
    (r"杉浦", "サンプル"),
]
RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sanitize_rules.json")


def _rules() -> dict:
    import json
    try:
        return json.load(open(RULES_FILE))
    except OSError:
        return {}


def extra_rules(screen_id: str) -> list[tuple[str, str]]:
    """sanitize_rules.json の画面別ルール（代理店名のサンプル化など）。"""
    return [tuple(r) for r in _rules().get(screen_id, [])]


def _tesseract(im: Image.Image, scale: float = 1.0, dy: int = 0, dx: int = 0) -> list[dict]:
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
        lines[(c[2], c[3], c[4])].append((c[11], (x + dx, y + dy, x + dx + w, y + dy + h)))
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
    # 暗幕の下に沈んだ小さい文字（モーダル背後の「担当者」欄など）は、拡大してから明暗を広げると読める
    # 横長の帯のままだと読めないので、アカウント表示のある右側だけを切り出す
    x0 = int(band.width * 0.75)
    right = band.crop((x0, 0, band.width, band.height))
    big = right.resize((right.width * 4, right.height * 4), Image.LANCZOS)
    lines += _tesseract(ImageOps.autocontrast(big, cutoff=1), scale=4, dx=x0)
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


def _far(c, bg) -> bool:
    return sum((a - b) ** 2 for a, b in zip(c, bg)) > 40 ** 2


def _text_size(im: Image.Image, box, bg) -> int:
    """元の文字の大きさ（インクの縦幅）に合わせた字の大きさ。OCR の枠は漢字だと上下に膨らむので枠の高さは使わない。"""
    x0, y0, x1, y1 = (max(v, 0) for v in box)
    px = im.load()
    inked = [any(_far(px[x, y][:3], bg) for x in range(x0, min(x1, im.width), 2)) for y in range(y0, min(y1, im.height))]
    # 枠が上下の行にかかっていることがあるので、中央に最も近いインクの塊だけを測る
    runs, start = [], None
    for i, v in enumerate(inked + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    mid = len(inked) / 2
    ink = (min(runs, key=lambda r: 0 if r[0] <= mid <= r[1] else min(abs(r[0] - mid), abs(r[1] - mid)))
           if runs else None)
    ink = ink[1] - ink[0] if ink else (y1 - y0) * 0.7
    return max(min(int(ink * 1.1), int((y1 - y0) * 0.9)), 8)


def _free_right(im: Image.Image, box, bg) -> int:
    """枠の右側で、背景色だけが続く幅。置き換え後の文字が長いときはそこまではみ出してよい。"""
    x0, y0, x1, y1 = box
    px = im.load()
    x = max(x1, 0)
    while x < im.width - 1 and x - x1 < 400 and not any(_far(px[x, y][:3], bg) for y in range(max(y0, 0), min(y1, im.height))):
        x += 1
    return max(x - x1 - 6, 0)


def crop_chrome(im: Image.Image, bottom_ratio: float | None = None) -> Image.Image:
    """ブラウザのブックマークバー（上端の濃い帯）と macOS のメニューバー（下端の黒帯）を切り落とす。"""
    g = im.convert("L")
    w, h = g.size

    def mean(y):
        return sum(g.getpixel((x, y)) for x in range(0, w, max(w // 200, 1))) / len(range(0, w, max(w // 200, 1)))

    top = 0
    while top < h * 0.06 and mean(top) < 215:
        top += 1
    bottom = h
    while bottom > h * 0.9 and mean(bottom - 1) < 90:
        bottom -= 1
    if bottom_ratio:
        bottom = min(bottom, int(h * bottom_ratio))
    return im.crop((0, top, w, bottom)) if (top or bottom < h) else im


def trim_dark(im: Image.Image, margin: int = 10) -> Image.Image:
    """暗い余白を切り落とす（片山方針 2026-10-09: 裏の黒い部分はトリミング）。

    1) 四辺の黒帯（ウィンドウの影・黒い余白）を削る
    2) モーダル表示で背景が暗く沈んだ画面は、明るいモーダル部分だけを残す
    """
    g = im.convert("L")
    w, h = g.size
    px = g.load()

    def row_mean(y, x0=0, x1=None):
        xs = range(x0, x1 or w, max((x1 or w) // 300, 1))
        return sum(px[x, y] for x in xs) / len(xs)

    def col_mean(x, y0=0, y1=None):
        ys = range(y0, y1 or h, max((y1 or h) // 300, 1))
        return sum(px[x, y] for y in ys) / len(ys)

    t, b, l, r = 0, h, 0, w
    while t < h * 0.15 and row_mean(t) < 70:
        t += 1
    while b > h * 0.85 and row_mean(b - 1) < 70:
        b -= 1
    while l < w * 0.15 and col_mean(l, t, b) < 70:
        l += 1
    while r > w * 0.85 and col_mean(r - 1, t, b) < 70:
        r -= 1
    # 動画キャプチャの左右・上下の白い帯（ピラーボックス）も削る
    while l < w * 0.2 and col_mean(l, t, b) >= 253:
        l += 1
    while r > w * 0.8 and col_mean(r - 1, t, b) >= 253:
        r -= 1
    while t < h * 0.2 and row_mean(t, l, r) >= 253:
        t += 1
    while b > h * 0.8 and row_mean(b - 1, l, r) >= 253:
        b -= 1
    im, g = im.crop((l, t, r, b)), g.crop((l, t, r, b))
    w, h = g.size
    px = g.load()
    # 明るい（白い）部分の外接矩形を求める。行は「明るい画素が3割超」、列はその行の範囲で「5割超」
    step = 2
    bright = [[px[x, y] >= 236 for x in range(0, w, step)] for y in range(0, h, step)]
    def longest_run(idx, gap):  # 途切れ（gap 刻みまで）を許した最長の連続区間
        runs, cur = [], []
        for i in idx:
            if cur and i - cur[-1] > gap:
                runs.append(cur)
                cur = []
            cur.append(i)
        if cur:
            runs.append(cur)
        return max(runs, key=len) if runs else []

    # モーダルの中にも色の付いた部品があるので、行は高さの8%までの途切れを許す
    rows = longest_run([i for i, row in enumerate(bright) if sum(row) > 0.2 * len(row)], max(int(h / step * 0.08), 3))
    if rows:
        band = bright[rows[0]:rows[-1] + 1]
        cols = longest_run([j for j in range(len(bright[0])) if sum(row[j] for row in band) > 0.5 * len(band)],
                           max(int(w / step * 0.03), 3))
        if cols:
            box = (max(cols[0] * step - margin, 0), max(rows[0] * step - margin, 0),
                   min(cols[-1] * step + step + margin, w), min(rows[-1] * step + step + margin, h))
            area = (box[2] - box[0]) * (box[3] - box[1]) / (w * h)
            # 外側が暗く沈んでいる（= モーダルの背景）ときだけ切る
            outside = [px[x, y] for y in range(0, h, 6) for x in range(0, w, 6)
                       if not (box[0] <= x < box[2] and box[1] <= y < box[3])]
            if 0.08 < area < 0.95 and outside and sum(outside) / len(outside) < 205:
                im = im.crop(box)
    return im


def sanitize(src: str, dst: str, debug: bool = False, screen_id: str = "") -> list[str]:
    im = Image.open(src).convert("RGB")
    rules = _rules()
    crop = rules.get("_crop_bottom", {}).get(screen_id)
    cropped = crop_chrome(im, crop)
    top = rules.get("_crop_top", {}).get(screen_id)
    if top:  # 上端で見切れた行（ヘッダーのメールアドレス等）を落とす
        cropped = cropped.crop((0, int(cropped.height * top), cropped.width, cropped.height))
    if cropped is not im:
        im = cropped
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            im.save(f.name)
        src = f.name  # 以降の OCR は切り落とし後の画像で行う
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

    lines_all = ocr_lines(src)
    words_all = [(w, b) for ln in lines_all for w, b in ln["words"]]

    def extend_sides(box):
        """メールアドレスの左右に、別の語として読まれた断片（例: "yuki." や "jp"）がくっついていれば含める。"""
        x0, y0, x1, y1 = box
        h = y1 - y0
        changed = True
        while changed:
            changed = False
            for w, (a, b, c, d) in words_all:
                cy = (b + d) / 2
                if not (y0 <= cy <= y1 and re.fullmatch(r"[\w.\-]+", w)):
                    continue
                if x0 - 1.2 * h <= c <= x0 + 2 and a < x0:
                    x0, changed = a - 2, True
                elif x1 - 2 <= a <= x1 + 1.5 * h and c > x1 and len(w) <= 6:
                    x1, changed = c + 2, True
        return (x0, y0, x1, y1)

    for line in lines_all:
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
                if "@" in rep:
                    box = extend_sides(box)
                if overlaps(box):  # 全体読みとヘッダー読みで同じ所を拾った
                    continue
                done.append((m.start(), m.end()))
                bg, fg = _bg_and_fg(im, box)
                size = _text_size(im, box, bg)
                room = (box[2] - box[0]) + _free_right(im, box, bg)
                draw.rectangle(box, fill=bg)
                font = _font(size)
                while size > 8 and draw.textlength(rep, font=font) > room:
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
    # 画面別の固定領域。OCR で拾えない物（ロゴ、合成画像の継ぎ目）を座標で処理する。座標は画像の幅・高さに対する割合
    for x0, y0, x1, y1, *text in rules.get("_fill", {}).get(screen_id, []):
        box = (int(x0 * im.width), int(y0 * im.height), min(int(x1 * im.width), im.width - 1), min(int(y1 * im.height), im.height - 1))
        if box[1] >= box[3]:
            continue
        bg, fg = _bg_and_fg(im, box)
        draw.rectangle(box, fill=bg)
        if text:
            draw.text((box[0] + 1, box[1] + 1), text[0], fill=fg, font=_font(max(int((box[3] - box[1]) * 0.75), 8)))
        marks.append(box)
        log.append(f"（固定領域） -> {text[0] if text else '塗りつぶし'}")
    for x0, y0, x1, y1 in rules.get("_blur", {}).get(screen_id, []):
        box = (int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height))
        part = im.crop(box)
        small = part.resize((max(part.width // 8, 1), max(part.height // 8, 1)))
        im.paste(small.resize(part.size), box)
        marks.append(box)
        log.append("（固定領域） -> モザイク")
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
