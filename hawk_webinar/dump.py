import json,sys
def texts(el):
    out=[]
    if 'shape' in el and 'text' in el['shape']:
        s=''.join(te.get('textRun',{}).get('content','') for te in el['shape']['text'].get('textElements',[]))
        if s.strip(): out.append(s.strip().replace('\n',' / '))
    if 'table' in el:
        for row in el['table'].get('tableRows',[]):
            cells=[]
            for c in row.get('tableCells',[]):
                s=''.join(te.get('textRun',{}).get('content','') for te in c.get('text',{}).get('textElements',[]))
                cells.append(s.strip().replace('\n',' '))
            out.append(' | '.join(cells))
    if 'elementGroup' in el:
        for ch in el['elementGroup'].get('children',[]): out+=texts(ch)
    if 'image' in el: out.append('[IMAGE]')
    if 'video' in el: out.append('[VIDEO]')
    return out
d=json.load(open(sys.argv[1]))
print('TITLE:',d.get('title'),'slides:',len(d['slides']))
for i,s in enumerate(d['slides'],1):
    print(f'\n===== P{i} ({s["objectId"]}) =====')
    for el in s.get('pageElements',[]):
        for t in texts(el): print(' -',t)
    np=s.get('slideProperties',{}).get('notesPage',{})
    for el in np.get('pageElements',[]):
        if el['objectId']==np.get('notesProperties',{}).get('speakerNotesObjectId'):
            for t in texts(el): print(' NOTE:',t)
