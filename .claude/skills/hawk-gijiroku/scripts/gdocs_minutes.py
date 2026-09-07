#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HAWK 議事録フォーマットで Google Doc を組版する。

参照フォーマット: 議事録_0901_リソースクリエイション様_ご利用後フィードバックヒアリング
  - Google の見出しスタイル(HEADING_n)は使わない。全段落 NORMAL_TEXT。
  - 段落インデントをマイナスにして本文幅をページ一杯まで広げる（文字視認率を上げる）。
      indentStart = indentFirstLine = -63.7795pt / indentEnd = -65.3228pt
  - 階層は記号で表現する：
      ══════   罫線（タイトルの上下）
      【…】議事録   タイトル（太字にしない）
      ■ …    大見出し（太字）
      ▶ …    小見出し（太字）
      ・…     箇条書き
      ［先方］／［当社］  ネクストアクションの主語
  - 箇条書きの間に空行は入れない（詰める）。空行は ■ セクションの前だけ。

入力はこの記法のプレーンテキスト。リンクは Markdown 風に [ラベル](URL) と書くと
ハイパーリンク化される（gdocs-hyperlink スキルの UTF-16 インデックス計算に準拠）。

使い方:
    python3 scripts/gdocs_minutes.py --doc-id <ID> --body body.txt [--keep]

    --keep を付けない限り、既存の本文は全削除してから流し込む（べき等）。
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile

INDENT_START = -63.77952755905512
INDENT_END = -65.32283464566933
LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
BOLD_PREFIXES = ('■', '▶')


def u16(s):
    """Docs API のインデックスは UTF-16 コード単位。len() では絵文字でズレる。"""
    return len(s.encode('utf-16-le')) // 2


def gws(service, *path, params=None, body=None):
    cmd = ['gws', service] + list(path)
    if params is not None:
        cmd += ['--params', json.dumps(params, ensure_ascii=False)]
    if body is not None:
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(body, f, ensure_ascii=False)
            tmp = f.name
        cmd += ['--json', open(tmp, encoding='utf-8').read()]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('gws failed: %s\n%s' % (' '.join(cmd[:4]), r.stderr or r.stdout))
    return json.loads(r.stdout) if r.stdout.strip() else {}


def body_end_index(doc):
    tabs = doc.get('tabs')
    content = tabs[0]['documentTab']['body']['content'] if tabs else doc['body']['content']
    return max(el.get('endIndex', 1) for el in content)


def parse(text):
    """行ごとに (表示テキスト, [(offset, ラベル, URL)]) へ分解する。"""
    out = []
    for raw in text.split('\n'):
        spans = []
        line = ''
        pos = 0
        for m in LINK_RE.finditer(raw):
            line += raw[pos:m.start()]
            spans.append((u16(line), m.group(1), m.group(2)))
            line += m.group(1)
            pos = m.end()
        line += raw[pos:]
        out.append((line, spans))
    while out and out[-1][0] == '':
        out.pop()
    return out


def build_requests(lines, start=1):
    inserts, styles, links = [], [], []
    cursor = start
    for line, spans in lines:
        text = line + '\n'
        inserts.append({'insertText': {'location': {'index': cursor}, 'text': text}})
        end = cursor + u16(text)
        if line.startswith(BOLD_PREFIXES):
            styles.append({'updateTextStyle': {
                'range': {'startIndex': cursor, 'endIndex': end - 1},
                'textStyle': {'bold': True}, 'fields': 'bold'}})
        for off, label, url in spans:
            s = cursor + off
            links.append({'updateTextStyle': {
                'range': {'startIndex': s, 'endIndex': s + u16(label)},
                'textStyle': {'link': {'url': url}}, 'fields': 'link'}})
        cursor = end

    # 全段落に共通の段落スタイル（本文幅をページ一杯まで広げる）
    layout = [{'updateParagraphStyle': {
        'range': {'startIndex': start, 'endIndex': cursor - 1},
        'paragraphStyle': {
            'namedStyleType': 'NORMAL_TEXT',
            'indentStart': {'magnitude': INDENT_START, 'unit': 'PT'},
            'indentFirstLine': {'magnitude': INDENT_START, 'unit': 'PT'},
            'indentEnd': {'magnitude': INDENT_END, 'unit': 'PT'},
        },
        'fields': 'namedStyleType,indentStart,indentFirstLine,indentEnd'}}]
    # 挿入位置のスタイルを引き継がないよう、まず全体を素の状態に戻してから太字を当てる
    reset = [{'updateTextStyle': {
        'range': {'startIndex': start, 'endIndex': cursor - 1},
        'textStyle': {'bold': False}, 'fields': 'bold'}}]
    return inserts + layout + reset + styles + links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--doc-id', required=True)
    ap.add_argument('--body', required=True, help='議事録記法のプレーンテキストファイル')
    ap.add_argument('--keep', action='store_true', help='既存本文を消さずに末尾へ追記する')
    a = ap.parse_args()

    doc = gws('docs', 'documents', 'get', params={'documentId': a.doc_id})
    end = body_end_index(doc)

    lines = parse(open(a.body, encoding='utf-8').read())
    if a.keep:
        requests = build_requests(lines, start=end - 1)
    else:
        requests = []
        if end > 2:
            requests.append({'deleteContentRange': {'range': {'startIndex': 1, 'endIndex': end - 1}}})
        requests += build_requests(lines, start=1)

    gws('docs', 'documents', 'batchUpdate',
        params={'documentId': a.doc_id}, body={'requests': requests})
    print('applied %d requests -> https://docs.google.com/document/d/%s/edit' % (len(requests), a.doc_id))


if __name__ == '__main__':
    main()
