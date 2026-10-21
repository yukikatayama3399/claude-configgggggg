#!/usr/bin/env python3
"""Docs API の JSON（includeTabsContent=true）から、指定タブを markdown に変換する。

usage: doc2md.py <doc.json> <tabId> <out.md>
週報メモ下書き用。本番タブを gog docs write --markdown で写せる形にするのが目的なので、
見出し・太字・取り消し線・リンク・箇条書き（入れ子）・表だけを扱う。
"""
import json, sys

HEAD = {'TITLE': '#', 'SUBTITLE': '##', 'HEADING_1': '#', 'HEADING_2': '##',
        'HEADING_3': '###', 'HEADING_4': '####', 'HEADING_5': '#####', 'HEADING_6': '######'}


def find_tab(tabs, tid):
    for t in tabs:
        if t['tabProperties']['tabId'] == tid:
            return t
        r = find_tab(t.get('childTabs', []), tid)
        if r:
            return r


def runs(elements):
    out = ''
    for el in elements:
        if 'textRun' in el:
            tr = el['textRun']; txt = tr['content']; st = tr.get('textStyle', {})
            core = txt.rstrip('\n'); tail = txt[len(core):]
            if core.strip():
                if st.get('link', {}).get('url'):
                    core = f"[{core}]({st['link']['url']})"
                if st.get('strikethrough'):
                    core = f'~~{core}~~'
                if st.get('bold'):
                    core = f'**{core}**'
            out += core + tail
        elif 'richLink' in el:
            p = el['richLink'].get('richLinkProperties', {})
            out += f"[{p.get('title', '')}]({p.get('uri', '')})"
    return out


def para_md(p, lists, in_table=False):
    text = runs(p['elements']).rstrip('\n')
    style = p.get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT')
    if 'bullet' in p:
        lvl = p['bullet'].get('nestingLevel', 0)
        return '  ' * lvl + '- ' + text
    if style in HEAD and text.strip() and not in_table:
        return HEAD[style] + ' ' + text
    return text


def table_md(tb, lists):
    rows = []
    for row in tb['tableRows']:
        cells = []
        for c in row['tableCells']:
            ps = [para_md(x['paragraph'], lists, True) for x in c['content'] if 'paragraph' in x]
            v = '<br>'.join(p for p in ps if p.strip()) or '  '
            cells.append(' ' + v.replace('|', '／').replace('\n', '<br>') + ' ')
        rows.append('|' + '|'.join(cells) + '|')
    sep = '|' + '|'.join(['---'] * len(tb['tableRows'][0]['tableCells'])) + '|'
    return '\n'.join([rows[0], sep] + rows[1:])


def main(src, tid, out):
    d = json.load(open(src))
    tab = find_tab(d['tabs'], tid)
    doc = tab['documentTab']; lists = doc.get('lists', {})
    lines = []
    for el in doc['body']['content']:
        if 'paragraph' in el:
            lines.append(para_md(el['paragraph'], lists))
        elif 'table' in el:
            if lines and lines[-1] != '':
                lines.append('')
            lines.append(table_md(el['table'], lists))
            lines.append('')
    s = '\n'.join(lines).replace('****', '').replace('\x0b', '\n')
    open(out, 'w').write(s + '\n')


if __name__ == '__main__':
    main(*sys.argv[1:4])
