import json,sys
def walk(el,path=''):
    if 'shape' in el and 'text' in el['shape']:
        s=''.join(te.get('textRun',{}).get('content','') for te in el['shape']['text'].get('textElements',[]))
        yield el['objectId'],s,el
    if 'table' in el:
        for r,row in enumerate(el['table'].get('tableRows',[])):
            for c,cell in enumerate(row.get('tableCells',[])):
                s=''.join(te.get('textRun',{}).get('content','') for te in cell.get('text',{}).get('textElements',[]))
                yield f"{el['objectId']}[{r},{c}]",s,cell
    if 'elementGroup' in el:
        for ch in el['elementGroup']['children']: yield from walk(ch)
d=json.load(open(sys.argv[1]))
for i,s in enumerate(d['slides'],1):
    for el in s.get('pageElements',[]):
        for oid,t,_ in walk(el):
            if '★' in t or 'ヒデさん' in t or '■' in t:
                print(f'P{i} {oid} len={len(t)} :: {t.strip()[:110].replace(chr(10)," / ")}')
