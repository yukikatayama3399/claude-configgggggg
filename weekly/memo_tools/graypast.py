#!/usr/bin/env python3
"""週報メモのタブで、前週の本番から変わっていない行を薄いグレーにする（今週足した行は黒のまま）。

env: DOC TAB  /  args: <前週本番の md> <今週の下書き md> [--apply] [--extra "黒のまま残す行" ...]
章見出し(1x1表)は触らない。「ステータス」で始まる表（商談ステータス表）は毎週列が増えるので黒のまま。
"""
import difflib, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('MD', '-'); os.environ.setdefault('PROD_JSON', '-'); os.environ.setdefault('PROD_TAB', '-')
from fixtables import fetch, upd, T, TAB

GRAY = {'color': {'rgbColor': {'red': 0.65, 'green': 0.65, 'blue': 0.65}}}


def norm(s):
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s).replace('**', '').replace('~~', '')
    s = re.sub(r'^[\s#>-]*', '', s)
    return re.sub(r'\s+', '', s)


def main():
    old_md, new_md = sys.argv[1], sys.argv[2]
    extra = [a for a in sys.argv[3:] if not a.startswith('--')]
    old = open(old_md).read().split('\n'); new = open(new_md).read().split('\n')
    added = set()
    for tag, a1, a2, b1, b2 in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag in ('replace', 'insert'):
            added |= {norm(l) for l in new[b1:b2] if norm(l) and not l.startswith('|')}
    added |= {norm(x) for x in extra}
    reqs = []; keep = []; gray = 0

    def para(p):
        nonlocal gray
        t = T(p)
        if not t.strip():
            return
        if norm(t) in added:
            keep.append(t.strip()[:60]); return
        gray += 1
        reqs.append({'updateTextStyle': {'range': {'startIndex': p['startIndex'], 'endIndex': p['endIndex'] - 1, 'tabId': TAB},
                                         'textStyle': {'foregroundColor': GRAY}, 'fields': 'foregroundColor'}})
    for e in fetch():
        if 'paragraph' in e:
            para(e)
        elif 'table' in e:
            tb = e['table']
            if tb['rows'] == 1 and tb['columns'] == 1:
                continue
            first = T(tb['tableRows'][0]['tableCells'][0]['content'][0]).strip()
            if first.startswith('ステータス'):
                continue
            for row in tb['tableRows']:
                for c in row['tableCells']:
                    for p in c['content']:
                        if 'paragraph' in p:
                            para(p)
    print('black(keep):', len(keep)); [print('  ', k) for k in keep]
    print('gray:', gray)
    if '--apply' in sys.argv:
        for i in range(0, len(reqs), 200):
            upd(reqs[i:i + 200])
        print('applied')


if __name__ == '__main__':
    main()
