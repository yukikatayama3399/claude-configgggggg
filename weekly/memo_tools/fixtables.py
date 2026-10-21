#!/usr/bin/env python3
"""週報メモのタブで、gog docs write --markdown が書き損ねた表を作り直し、本番の書式に揃える。

gog は本文を書いた後に表を1つずつ作るため、Docs の書き込み上限(429)に当たると
「| 0. 共有事項 |」「|---|」が文字のまま残ったり、複数行の表が丸ごと消えたりする。
このスクリプトは md の表と本番タブの表を順番どおりに対応させ、下から順に
  - 1x1 の章見出し: 文字のまま残った2行を消して表を作り、濃灰背景・白14pt・HEADING_2
  - 複数行の表: 直前の行(アンカー)の後ろの空行に表を作って中身を入れ、本番のセル書式を写す
  - 既にある表(サイズ一致): 書式だけ写す
を行う。

env: DOC(週報メモID) TAB(タブID) MD(md のパス) PROD_JSON(本番 Docs JSON) PROD_TAB(本番タブID)
usage: python3 fixtables.py            # 実行
"""
import json, os, re, subprocess, sys, time

DOC = os.environ.get('DOC', '1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY')
TAB = os.environ['TAB']; MD = os.environ['MD']
PROD_JSON = os.environ['PROD_JSON']; PROD_TAB = os.environ['PROD_TAB']
STY = ('bold', 'fontSize', 'foregroundColor', 'italic')


def gws(args):
    for _ in range(8):
        r = subprocess.run(['gws'] + args, capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout) if r.stdout.strip() else {}
        out = r.stdout + r.stderr
        if '429' in out or 'RATE' in out.upper() or 'Quota' in out:
            time.sleep(65); continue
        raise SystemExit('ERR ' + out[-800:])
    raise SystemExit('rate limited')


def _find(tabs, tid):
    for t in tabs:
        if t['tabProperties']['tabId'] == tid:
            return t
        r = _find(t.get('childTabs', []), tid)
        if r:
            return r


def fetch():
    d = gws(['docs', 'documents', 'get', '--params', json.dumps({'documentId': DOC, 'includeTabsContent': True})])
    return _find(d['tabs'], TAB)['documentTab']['body']['content']


def upd(reqs):
    if reqs:
        gws(['docs', 'documents', 'batchUpdate', '--params', json.dumps({'documentId': DOC}), '--json', json.dumps({'requests': reqs})])
        time.sleep(2)


def T(e):
    return ''.join(x.get('textRun', {}).get('content', '') for x in e.get('paragraph', {}).get('elements', []))


def prodtables():
    d = json.load(open(PROD_JSON))
    return [e['table'] for e in _find(d['tabs'], PROD_TAB)['documentTab']['body']['content'] if 'table' in e]


def md_tables():
    md = open(MD).read().split('\n'); tabs = []; cur = None
    for l in md:
        if l.startswith('|'):
            cur = cur or []; cur.append(l)
        elif cur:
            tabs.append(cur); cur = None
    if cur:
        tabs.append(cur)
    res = []
    for t in tabs:
        rows = [r for r in t if not re.fullmatch(r'\|(-+\|)+', r.replace(' ', ''))]
        res.append([[c for c in r.strip()[1:-1].split(' | ')] for r in rows])
    return res


def parse_cell(s):
    s = s.strip().replace('<br>', '\n')
    out = ''; bold = []; links = []; strike = []; pos = 0
    pat = re.compile(r'\*\*(.+?)\*\*|~~(.+?)~~|\[([^\]]*)\]\(([^)]*)\)')
    for m in pat.finditer(s):
        out += s[pos:m.start()]
        st = len(out)
        if m.group(1) is not None or m.group(2) is not None:
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            mm = re.fullmatch(r'\[([^\]]*)\]\(([^)]*)\)', inner)
            if mm:
                out += mm.group(1); links.append((st, len(out), mm.group(2)))
            else:
                out += inner
            (bold if m.group(1) is not None else strike).append((st, len(out)))
        else:
            out += m.group(3); links.append((st, len(out), m.group(4)))
        pos = m.end()
    out += s[pos:]
    return out, bold, links, strike


def fill(tstart, cells, proto=None, protomap=None, para=None):
    tb = [e for e in fetch() if 'table' in e and e['startIndex'] == tstart][0]
    reqs = []
    order = [(r, c) for r in range(len(cells)) for c in range(len(cells[0]))][::-1]
    for r, c in order:
        idx = tb['table']['tableRows'][r]['tableCells'][c]['content'][0]['startIndex']
        txt, bold, links, strike = parse_cell(cells[r][c] if c < len(cells[r]) else '')
        if not txt.strip():
            txt = ''
        rng = lambda a, b: {'startIndex': idx + a, 'endIndex': idx + b, 'tabId': TAB}
        if txt:
            reqs.append({'insertText': {'text': txt, 'location': {'index': idx, 'tabId': TAB}}})
            if para:
                reqs.append({'updateParagraphStyle': {'range': rng(0, len(txt)), 'paragraphStyle': {'namedStyleType': para}, 'fields': 'namedStyleType'}})
        if proto is not None:
            pr, pc = protomap(r, c) if protomap else (r, c)
            if pr is not None and pr < len(proto['tableRows']) and pc < len(proto['tableRows'][pr]['tableCells']):
                pcell = proto['tableRows'][pr]['tableCells'][pc]
                bg = pcell.get('tableCellStyle', {}).get('backgroundColor')
                if bg and bg.get('color'):
                    reqs.append({'updateTableCellStyle': {'tableCellStyle': {'backgroundColor': bg}, 'fields': 'backgroundColor',
                                 'tableRange': {'tableCellLocation': {'tableStartLocation': {'index': tstart, 'tabId': TAB}, 'rowIndex': r, 'columnIndex': c}, 'rowSpan': 1, 'columnSpan': 1}}})
                rs = [x for p in pcell['content'] if 'paragraph' in p for x in p['paragraph']['elements'] if 'textRun' in x and x['textRun']['content'].strip()]
                if rs and txt:
                    ts = {k: v for k, v in rs[0]['textRun'].get('textStyle', {}).items() if k in ('fontSize', 'foregroundColor')}
                    if ts:
                        reqs.append({'updateTextStyle': {'range': rng(0, len(txt)), 'textStyle': ts, 'fields': ','.join(ts)}})
        for a, b in bold:
            reqs.append({'updateTextStyle': {'range': rng(a, b), 'textStyle': {'bold': True}, 'fields': 'bold'}})
        for a, b in strike:
            reqs.append({'updateTextStyle': {'range': rng(a, b), 'textStyle': {'strikethrough': True}, 'fields': 'strikethrough'}})
        for a, b, u in links:
            reqs.append({'updateTextStyle': {'range': rng(a, b), 'textStyle': {'link': {'url': u}}, 'fields': 'link'}})
    upd(reqs)


def idx_of(body, pred):
    for k, e in enumerate(body):
        if pred(e):
            return k
    raise SystemExit('anchor not found')


def table_after(body, k):
    for e in body[k:]:
        if 'table' in e:
            return e['startIndex']


def dedupe_before(tstart):
    body = fetch(); k = [i for i, e in enumerate(body) if 'table' in e and e['startIndex'] == tstart][0]
    a, b = body[k - 2], body[k - 1]
    if 'paragraph' in a and 'paragraph' in b and T(a) == '\n' and T(b) == '\n':
        upd([{'deleteContentRange': {'range': {'startIndex': a['startIndex'], 'endIndex': a['endIndex'], 'tabId': TAB}}}])
        return tstart - 1
    return tstart


def header(cells, proto):
    line = cells[0][0].strip()
    body = fetch()
    done = [e for e in body if 'table' in e and e['table']['rows'] == 1 and e['table']['columns'] == 1
            and T(e['table']['tableRows'][0]['tableCells'][0]['content'][0]).strip() == line]
    if done:   # 再実行時：作成済みの見出しは飛ばす
        return
    k = idx_of(body, lambda e: 'paragraph' in e and T(e).strip().strip('|').strip() == line and T(e).strip().startswith('|'))
    p1, p2 = body[k], body[k + 1]
    assert T(p2).strip() == '|---|', T(p2)
    s = p1['startIndex']
    upd([{'deleteContentRange': {'range': {'startIndex': s, 'endIndex': p2['endIndex'], 'tabId': TAB}}},
         {'insertTable': {'rows': 1, 'columns': 1, 'location': {'index': s, 'tabId': TAB}}}])
    t = dedupe_before(table_after(fetch(), k - 1))
    fill(t, cells, proto=proto, para='HEADING_2')
    print('header', line)


def anchor_line(mdlines, first_row):
    """md 上で表の直前にある、空でない非表行（アンカー）を返す。"""
    i = mdlines.index(first_row)
    j = i - 1
    while j >= 0 and not mdlines[j].strip():
        j -= 1
    while j > 0 and mdlines[j].startswith('|') and mdlines[j - 1].startswith('|'):
        j -= 1   # 直前が表なら、その表の1行目（章見出しの文字列）をアンカーにする
    return mdlines[j]


def norm(s):
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s).replace('**', '').replace('~~', '')
    s = re.sub(r'^[\s#>-]*', '', s)
    return re.sub(r'\s+', '', s)


def multi(cells, proto, anchor, protomap=None):
    body = fetch()
    if anchor.startswith('|'):   # 直前も表（章見出し）: 文字のまま残った |---| の次の空行
        k = idx_of(body, lambda e: 'paragraph' in e and T(e).strip().strip('|').strip() == anchor.strip().strip('|').strip()) + 1
    else:
        k = idx_of(body, lambda e: 'paragraph' in e and norm(T(e)) == norm(anchor) and norm(T(e)))
    B = body[k + 1]
    if T(B) != '\n':   # 空行がなければ作る
        upd([{'insertText': {'text': '\n', 'location': {'index': B['startIndex'], 'tabId': TAB}}}])
        body = fetch(); B = body[k + 1]
    upd([{'insertTable': {'rows': len(cells), 'columns': len(cells[0]), 'location': {'index': B['startIndex'], 'tabId': TAB}}}])
    t = table_after(fetch(), k)
    fill(t, cells, proto=proto, protomap=protomap)
    print('multi', cells[0][:2])


def style_only(tb_el, proto):
    reqs = []; ts0 = tb_el['startIndex']
    for r, row in enumerate(tb_el['table']['tableRows']):
        for c, cell in enumerate(row['tableCells']):
            if r >= len(proto['tableRows']) or c >= len(proto['tableRows'][r]['tableCells']):
                continue
            pcell = proto['tableRows'][r]['tableCells'][c]
            bg = pcell.get('tableCellStyle', {}).get('backgroundColor')
            if bg and bg.get('color'):
                reqs.append({'updateTableCellStyle': {'tableCellStyle': {'backgroundColor': bg}, 'fields': 'backgroundColor',
                             'tableRange': {'tableCellLocation': {'tableStartLocation': {'index': ts0, 'tabId': TAB}, 'rowIndex': r, 'columnIndex': c}, 'rowSpan': 1, 'columnSpan': 1}}})
            rs = [x for p in pcell['content'] if 'paragraph' in p for x in p['paragraph']['elements'] if 'textRun' in x and x['textRun']['content'].strip()]
            s = cell['content'][0]['startIndex']; e = cell['content'][-1]['endIndex'] - 1
            if rs and e > s:
                st = {k: v for k, v in rs[0]['textRun'].get('textStyle', {}).items() if k in ('fontSize', 'foregroundColor')}
                if st:
                    reqs.append({'updateTextStyle': {'range': {'startIndex': s, 'endIndex': e, 'tabId': TAB}, 'textStyle': st, 'fields': ','.join(st)}})
    upd(reqs); print('styled existing table', len(reqs))


def tidy_headers():
    """章見出しの後に本番どおり空行を入れ、その空行の箇条書きを外す。"""
    body = fetch(); ins = []
    for i, e in enumerate(body):
        if 'table' in e and e['table']['rows'] == 1 and e['table']['columns'] == 1:
            if T(body[i + 1]) != '\n':
                ins.append(body[i + 1]['startIndex'])
    upd([{'insertText': {'text': '\n', 'location': {'index': s, 'tabId': TAB}}} for s in sorted(ins, reverse=True)])
    body = fetch(); fix = []
    for i, e in enumerate(body):
        if 'table' in e and e['table']['rows'] == 1:
            n = body[i + 1]
            if T(n) == '\n' and 'bullet' in n.get('paragraph', {}):
                fix.append(n)
    upd([{'deleteParagraphBullets': {'range': {'startIndex': n['startIndex'], 'endIndex': n['endIndex'], 'tabId': TAB}}} for n in fix])


def main():
    mt = md_tables(); pt = prodtables()
    mdlines = open(MD).read().split('\n')
    if len(mt) != len(pt):
        print(f'warn: md tables {len(mt)} != prod tables {len(pt)}; proto is matched by shape')
    body = fetch()
    existing = [e for e in body if 'table' in e]
    for mi in range(len(mt) - 1, -1, -1):
        cells = mt[mi]
        R, C = len(cells), len(cells[0])
        proto = pt[mi] if mi < len(pt) else None
        if proto is not None and (proto['rows'], proto['columns']) != (R, C) and not (R == proto['rows']):
            cand = [p for p in pt if (p['rows'], p['columns']) == (R, C)]
            proto = cand[0] if cand else proto
        protomap = (lambda r, c, pc=proto['columns']: (r, min(c, pc - 1))) if proto else None
        ex = [e for e in existing if (e['table']['rows'], e['table']['columns']) == (R, C) and not (R == 1 and C == 1)]
        if ex:
            style_only(ex[0], proto); existing.remove(ex[0]); continue
        if R == 1 and C == 1:
            header(cells, proto)
        else:
            row0 = [l for l in mdlines if l.startswith('|') and l.strip()[1:-1].split(' | ') == cells[0]][0]
            multi(cells, proto, anchor_line(mdlines, row0), protomap)
    tidy_headers()
    body = fetch()
    print('tables', sum(1 for e in body if 'table' in e), 'literal', sum(1 for e in body if 'paragraph' in e and T(e).startswith('|')))


if __name__ == '__main__':
    main()
