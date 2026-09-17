import doclib
def tables(content):
    out=[]
    for el in content:
        if 'table' in el:
            first=el['table']['tableRows'][0]['tableCells'][0]['content']
            t=''.join(doclib.ptext(p) for p in first if 'paragraph' in p).strip()
            out.append((t,el))
    return out
def find_table(content,key):
    for t,el in tables(content):
        if key in t: return el
    raise SystemExit('table not found '+key)
def cell_text(el,r,c):
    cell=el['table']['tableRows'][r]['tableCells'][c]
    return ''.join(doclib.ptext(p) for p in cell['content'] if 'paragraph' in p).rstrip('\n')
def set_cell(el,r,c,text):
    cell=el['table']['tableRows'][r]['tableCells'][c]
    ps=[p for p in cell['content'] if 'paragraph' in p]
    a=ps[0]['startIndex']; b=ps[-1]['endIndex']-1
    reqs=[]
    if b>a: reqs.append(doclib.dele(a,b))
    if text: reqs.append(doclib.ins(a,text))
    return a,reqs
