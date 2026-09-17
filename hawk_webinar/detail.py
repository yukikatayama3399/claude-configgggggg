import json,sys
d=json.load(open(sys.argv[1]))
pages=[int(x) for x in sys.argv[2].split(',')]
EMU=12700
def geo(el):
    t=el.get('transform',{}); s=el.get('size',{})
    w=s.get('width',{}).get('magnitude',0)*t.get('scaleX',1)/EMU
    h=s.get('height',{}).get('magnitude',0)*t.get('scaleY',1)/EMU
    return f"x={t.get('translateX',0)/EMU:.0f} y={t.get('translateY',0)/EMU:.0f} w={w:.0f} h={h:.0f}"
def style(te):
    st=te.get('textRun',{}).get('style',{})
    fs=st.get('fontSize',{}).get('magnitude'); c=st.get('foregroundColor',{}).get('opaqueColor',{}).get('rgbColor')
    col=None
    if c: col='#%02x%02x%02x'%tuple(int(round(c.get(k,0)*255)) for k in ('red','green','blue'))
    return f"{fs}pt {col} {'B' if st.get('bold') else ''} {st.get('fontFamily','')}"
def show(el,ind=' '):
    kind=[k for k in ('shape','image','table','elementGroup','line','video') if k in el][0]
    extra=''
    if kind=='shape':
        extra=el['shape'].get('shapeType','')
        fill=el['shape'].get('shapeProperties',{}).get('shapeBackgroundFill',{}).get('solidFill',{}).get('color',{}).get('rgbColor')
        if fill: extra+=' fill=#%02x%02x%02x'%tuple(int(round(fill.get(k,0)*255)) for k in ('red','green','blue'))
    print(f"{ind}{el['objectId']} {kind} {extra} {geo(el)}")
    if kind=='shape' and 'text' in el['shape']:
        for te in el['shape']['text'].get('textElements',[]):
            if 'textRun' in te:
                print(f"{ind}   [{style(te)}] {te['textRun']['content'].strip()[:80]!r}")
    if kind=='elementGroup':
        for ch in el['elementGroup']['children']: show(ch,ind+'   ')
print('pageSize',d['pageSize'])
for p in pages:
    s=d['slides'][p-1]
    print(f'\n##### P{p} {s["objectId"]} layout={s.get("slideProperties",{}).get("layoutObjectId")}')
    for el in s.get('pageElements',[]): show(el)
