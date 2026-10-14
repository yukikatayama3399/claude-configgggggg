#!/usr/bin/env python3
"""初回打ち合わせアジェンダ（テンプレ）をコピーして、文字と画像を流し込む。

    python3 agenda/fill_agenda.py <config.json> [--out-dir DIR] [--template ID]

config.json の形は agenda/examples/pac_20261014.json を参照。
- text   : {"COMPANY": "株式会社〇〇", ...}  テンプレの {{KEY}} を置換する
- images : {"LOGO": {...}, "W1_PHOTO": {...}}  テンプレの {{KEY}} 画像枠に差し込む
    {"file": "path.svg|png|jpg"}                  ローカル画像（SVG は PNG に変換）
    {"url": "https://..."}                        Google から取得できる公開画像
    {"mshot": "https://site/page", "crop": [l, r, t, b]}
                                                  ページのスクショ（WordPress mshots 経由）
    {"icons": ["google.com", "yahoo.co.jp"]}      媒体アイコン（ファビコン）の 2 列グリッド
画像を指定しなかった枠は「写真」と書いた灰色の枠のまま残る。
最後に PDF を書き出して PNG に描画するので、必ず目で確認すること。
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi  # noqa: E402

TEMPLATE_ID = '1_v3W-u6awkmHMpL8DWU9RFFtDmsjvQcavkXw6oUK_6k'  # 【テンプレ】HAWK初回打ち合わせ アジェンダ
PT = 12700


def emu(v):
    return {'magnitude': v * PT, 'unit': 'EMU'}


def mshot_url(page):
    return 'https://s.wordpress.com/mshots/v1/' + urllib.parse.quote(page, safe='') + '?w=1024&h=768'


def image_size(path):
    """PNG / JPEG の縦横（取れなければ None）。"""
    try:
        from PIL import Image
        return Image.open(path).size
    except Exception:
        pass
    with open(path, 'rb') as f:
        head = f.read(24)
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', head[16:24])
    return None


def svg_to_png(svg, out):
    if shutil.which('rsvg-convert'):
        subprocess.check_call(['rsvg-convert', '-z', '10', '-o', out, svg])
        return out
    js = ("const {chromium}=require('playwright');(async()=>{"
          "const b=await chromium.launch({executablePath:process.env.PW_CHROMIUM||undefined});"
          "const p=await b.newPage({deviceScaleFactor:10});"
          "await p.goto('file://'+process.argv[1]);"
          "const r=await p.evaluate(()=>{const s=document.querySelector('svg').getBoundingClientRect();return{x:s.x,y:s.y,width:s.width,height:s.height}});"
          "await p.screenshot({path:process.argv[2],omitBackground:true,clip:r});await b.close();})();")
    env = dict(os.environ)
    env.setdefault('NODE_PATH', subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip())
    if os.path.exists('/opt/pw-browsers/chromium'):
        env.setdefault('PW_CHROMIUM', '/opt/pw-browsers/chromium')
    subprocess.check_call(['node', '-e', js, os.path.abspath(svg), os.path.abspath(out)], env=env)
    return out


def text_of(el):
    t = el.get('shape', {}).get('text')
    if not t:
        return ''
    return ''.join(r.get('textRun', {}).get('content', '') for r in t['textElements']).strip()


def bbox(el):
    tr, sz = el['transform'], el['size']
    return (tr.get('translateX', 0) / PT, tr.get('translateY', 0) / PT,
            sz['width']['magnitude'] * tr.get('scaleX', 1) / PT, sz['height']['magnitude'] * tr.get('scaleY', 1) / PT)


def create_image(oid, page, url, x, y, w, h, crop=None):
    reqs = [{'createImage': {'objectId': oid, 'url': url, 'elementProperties': {
        'pageObjectId': page, 'size': {'width': emu(w), 'height': emu(h)},
        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': x * PT, 'translateY': y * PT, 'unit': 'EMU'}}}}]
    if crop:
        l, r, t, b = crop
        reqs.append({'updateImageProperties': {'objectId': oid, 'imageProperties': {'cropProperties': {
            'leftOffset': l, 'rightOffset': r, 'topOffset': t, 'bottomOffset': b}}, 'fields': 'cropProperties'}})
    return reqs


def fit(box, aspect):
    x, y, w, h = box
    if not aspect:
        return box
    if w / h > aspect:
        nw = h * aspect
        return (x + (w - nw) / 2, y, nw, h)
    nh = w / aspect
    return (x, y + (h - nh) / 2, w, nh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('config')
    ap.add_argument('--template', default=TEMPLATE_ID)
    ap.add_argument('--out-dir', default='.')
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    base = os.path.dirname(os.path.abspath(a.config))

    pid = gapi.copy_file(a.template, cfg['title'], cfg.get('folder'))
    print('copied:', f'https://docs.google.com/presentation/d/{pid}/edit')

    # 1) 文字
    reqs = [{'replaceAllText': {'containsText': {'text': '{{%s}}' % k, 'matchCase': True}, 'replaceText': v}}
            for k, v in cfg.get('text', {}).items()]
    if reqs:
        gapi.batch(pid, reqs)

    # 2) 画像枠を探す
    pres = gapi.get_presentation(pid)
    slots = []  # (key, page, element)
    for s in pres['slides']:
        for e in s.get('pageElements', []):
            t = text_of(e)
            if t.startswith('{{') and t.endswith('}}'):
                slots.append((t[2:-2], s['objectId'], e))
    alltext = ' '.join(text_of(e) for s in pres['slides'] for e in s.get('pageElements', []))
    leftover = sorted({k for k in re.findall(r'\{\{(\w+)\}\}', alltext) if not k.endswith('_PHOTO') and k != 'LOGO'})
    if leftover:
        print('WARN: 未設定の文字:', ', '.join(leftover))

    images = cfg.get('images', {})
    tmp = tempfile.mkdtemp()
    shared = []  # (fileId, permId)
    file_urls = {}
    first, mshots, done_slots = [], [], []
    for n, (key, page, el) in enumerate(slots):
        spec = images.get(key)
        if key not in images and (key.endswith('_PHOTO') or key == 'LOGO'):
            first.append({'deleteText': {'objectId': el['objectId'], 'textRange': {'type': 'ALL'}}})
            first.append({'insertText': {'objectId': el['objectId'], 'text': '写真' if key != 'LOGO' else 'LOGO'}})
            continue
        if not spec:
            continue
        box = bbox(el)
        oid = f'img_{key.lower()}_{n}'
        if 'file' in spec:
            path = spec['file'] if os.path.isabs(spec['file']) else os.path.join(base, spec['file'])
            if path not in file_urls:
                if path.lower().endswith('.svg'):
                    path_png = svg_to_png(path, os.path.join(tmp, os.path.basename(path) + '.png'))
                else:
                    path_png = path
                mime = 'image/png' if path_png.lower().endswith('.png') else 'image/jpeg'
                fid = gapi.upload(path_png, mime)
                shared.append((fid, gapi.share_anyone(fid)))
                sz = image_size(path_png)
                file_urls[path] = (f'https://drive.google.com/uc?export=download&id={fid}', sz[0] / sz[1] if sz else None)
            url, aspect = file_urls[path]
            first += create_image(oid, page, url, *fit(box, aspect))
        elif 'url' in spec:
            first += create_image(oid, page, spec['url'], *box, crop=spec.get('crop'))
        elif 'mshot' in spec:
            mshots.append((oid, page, mshot_url(spec['mshot']), box, spec.get('crop')))
        elif 'icons' in spec:
            x, y, w, h = box
            icons = spec['icons']
            rows = (len(icons) + 1) // 2
            s = min((w - 24) / 2, (h - 8 - 7 * (rows - 1)) / rows)
            for i, d in enumerate(icons):
                ix = x + (w - (2 * s + 12)) / 2 + (i % 2) * (s + 12)
                iy = y + (h - (rows * s + 7 * (rows - 1))) / 2 + (i // 2) * (s + 7)
                first += create_image(f'{oid}_{i}', page,
                                      f'https://www.google.com/s2/favicons?domain={d}&sz=128', ix, iy, s, s)
            first.append({'updateShapeProperties': {'objectId': el['objectId'], 'shapeProperties': {
                'shapeBackgroundFill': {'solidFill': {'color': {'rgbColor': {'red': 1, 'green': 1, 'blue': 1}}}},
                'outline': {'outlineFill': {'solidFill': {'color': {'rgbColor': {'red': .8, 'green': .83, 'blue': .81}}}},
                            'weight': {'magnitude': .75, 'unit': 'PT'}}},
                'fields': 'shapeBackgroundFill.solidFill.color,outline.outlineFill.solidFill.color,outline.weight'}})
            first.append({'deleteText': {'objectId': el['objectId'], 'textRange': {'type': 'ALL'}}})
            continue
        done_slots.append(el['objectId'])

    try:
        if first:
            gapi.batch(pid, first)
        if mshots:
            # mshots は初回アクセスで「Generating Preview」画像を返す。一度読ませてから差し直す。
            gapi.batch(pid, [r for o, p, u, b, c in mshots for r in create_image(o + '_warm', p, u, *b)])
            time.sleep(30)
            reqs = [{'deleteObject': {'objectId': o + '_warm'}} for o, *_ in mshots]
            for o, p, u, b, c in mshots:
                reqs += create_image(o, p, u, *b, crop=c)
            gapi.batch(pid, reqs)
        if done_slots:
            gapi.batch(pid, [{'deleteObject': {'objectId': o}} for o in done_slots])
    finally:
        for fid, perm in shared:
            gapi.unshare(fid, perm)
            gapi.trash(fid)

    # 3) 目視確認用に PDF → PNG
    os.makedirs(a.out_dir, exist_ok=True)
    pdf = os.path.join(a.out_dir, 'agenda.pdf')
    gapi.export_pdf(pid, pdf)
    if shutil.which('pdftoppm'):
        subprocess.check_call(['pdftoppm', '-r', '80', '-png', pdf, os.path.join(a.out_dir, 'page')])
        print('rendered:', a.out_dir)
    print('done:', f'https://docs.google.com/presentation/d/{pid}/edit')


if __name__ == '__main__':
    main()
