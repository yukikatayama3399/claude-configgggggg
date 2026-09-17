import json, requests, time, os
CRED='/root/.config/gws/credentials.json'
_tok=None; _exp=0
def token():
    global _tok,_exp
    if _tok and time.time()<_exp-60: return _tok
    c=json.load(open(CRED))
    r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':c['client_id'],'client_secret':c['client_secret'],'refresh_token':c['refresh_token'],'grant_type':'refresh_token'},timeout=30)
    r.raise_for_status(); j=r.json(); _tok=j['access_token']; _exp=time.time()+j.get('expires_in',3600); return _tok
def get(pid):
    r=requests.get(f'https://slides.googleapis.com/v1/presentations/{pid}',headers={'Authorization':'Bearer '+token()},timeout=60)
    r.raise_for_status(); return r.json()
def batch(pid,reqs,label=''):
    if not reqs: return None
    r=requests.post(f'https://slides.googleapis.com/v1/presentations/{pid}:batchUpdate',headers={'Authorization':'Bearer '+token()},json={'requests':reqs},timeout=120)
    if r.status_code!=200:
        print('ERROR',label,r.status_code,r.text[:2000]); raise SystemExit(1)
    print(f'ok {label}: {len(reqs)} requests'); return r.json()

EMU=12700
def pt(v): return {'magnitude':v*EMU,'unit':'EMU'}
def rgb(hexs):
    h=hexs.lstrip('#'); return {'red':int(h[0:2],16)/255,'green':int(h[2:4],16)/255,'blue':int(h[4:6],16)/255}
def u16(s): return len(s.encode('utf-16-le'))//2

# colors
DG='#0f4a1b'; MG='#7e9464'; LG='#a9bc91'; PG='#d3dfc5'; BG='#f6f7f3'; YEL='#fff200'; TXT='#111111'; GRAY='#5e5e5e'; WHITE='#ffffff'; RED='#c83c14'

def text_style(size=None,color=None,bold=None,font=None,italic=None):
    st={}; fields=[]
    if size is not None: st['fontSize']=pt(size); fields.append('fontSize')
    if color is not None: st['foregroundColor']={'opaqueColor':{'rgbColor':rgb(color)}}; fields.append('foregroundColor')
    if bold is not None: st['bold']=bold; fields.append('bold')
    if italic is not None: st['italic']=italic; fields.append('italic')
    if font is not None: st['fontFamily']=font; fields.append('fontFamily')
    return st,','.join(fields)

def set_text(oid, runs, has_text=True, align=None, line_spacing=None, space_below=None):
    """runs: list of (text, dict(size,color,bold)) ; full text = concat. Replaces all text of shape."""
    if isinstance(runs,str): runs=[(runs,{})]
    reqs=[]
    if has_text: reqs.append({'deleteText':{'objectId':oid,'textRange':{'type':'ALL'}}})
    full=''.join(t for t,_ in runs)
    reqs.append({'insertText':{'objectId':oid,'insertionIndex':0,'text':full}})
    pos=0
    for t,st in runs:
        L=u16(t)
        if st and L>0:
            s,f=text_style(**st)
            reqs.append({'updateTextStyle':{'objectId':oid,'textRange':{'type':'FIXED_RANGE','startIndex':pos,'endIndex':pos+L},'style':s,'fields':f}})
        pos+=L
    ps={}; pf=[]
    if align: ps['alignment']=align; pf.append('alignment')
    if line_spacing: ps['lineSpacing']=line_spacing; pf.append('lineSpacing')
    if space_below is not None: ps['spaceBelow']=pt(space_below); pf.append('spaceBelow')
    if pf: reqs.append({'updateParagraphStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':ps,'fields':','.join(pf)}})
    return reqs

def delete(oids):
    return [{'deleteObject':{'objectId':o}} for o in oids]

_ctr=[0]
def nid(prefix='cx'):
    _ctr[0]+=1; return f'{prefix}_{int(time.time())%100000}_{_ctr[0]}'

def shape(page, kind, x,y,w,h, fill=None, outline=None, oid=None, runs=None, align='START', valign='MIDDLE', font='Meiryo', size=12, color=TXT, bold=False, line_spacing=None, inset=None):
    oid=oid or nid('sh')
    reqs=[{'createShape':{'objectId':oid,'shapeType':kind,'elementProperties':{'pageObjectId':page,'size':{'width':pt(w),'height':pt(h)},'transform':{'scaleX':1,'scaleY':1,'translateX':x*EMU,'translateY':y*EMU,'unit':'EMU'}}}}]
    sp={}; f=[]
    if fill: sp['shapeBackgroundFill']={'solidFill':{'color':{'rgbColor':rgb(fill)},'alpha':1}}; f.append('shapeBackgroundFill')
    else: sp['shapeBackgroundFill']={'propertyState':'NOT_RENDERED'}; f.append('shapeBackgroundFill')
    if outline: sp['outline']={'outlineFill':{'solidFill':{'color':{'rgbColor':rgb(outline[0])}}},'weight':pt(outline[1]),'dashStyle':outline[2] if len(outline)>2 else 'SOLID'}; f.append('outline')
    else: sp['outline']={'propertyState':'NOT_RENDERED'}; f.append('outline')
    sp['contentAlignment']=valign; f.append('contentAlignment')
    reqs.append({'updateShapeProperties':{'objectId':oid,'shapeProperties':sp,'fields':','.join(f)}})
    if runs is not None:
        if isinstance(runs,str): runs=[(runs,{})]
        full=''.join(t for t,_ in runs)
        reqs.append({'insertText':{'objectId':oid,'insertionIndex':0,'text':full}})
        base,bf=text_style(size=size,color=color,bold=bold,font=font)
        reqs.append({'updateTextStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':base,'fields':bf}})
        pos=0
        for t,st in runs:
            L=u16(t)
            if st and L>0:
                s,ff=text_style(**st)
                reqs.append({'updateTextStyle':{'objectId':oid,'textRange':{'type':'FIXED_RANGE','startIndex':pos,'endIndex':pos+L},'style':s,'fields':ff}})
            pos+=L
        ps={'alignment':align}; pf='alignment'
        if line_spacing: ps['lineSpacing']=line_spacing; pf+=',lineSpacing'
        reqs.append({'updateParagraphStyle':{'objectId':oid,'textRange':{'type':'ALL'},'style':ps,'fields':pf}})
    if inset is not None:
        pass
    return oid,reqs

def line(page,x1,y1,x2,y2,color=MG,weight=2,arrow_end=False,arrow_start=False,dash='SOLID',oid=None):
    oid=oid or nid('ln')
    dx=x2-x1; dy=y2-y1
    sx=1 if dx>=0 else -1; sy=1 if dy>=0 else -1
    w=abs(dx) if abs(dx)>0.01 else 0.01; h=abs(dy) if abs(dy)>0.01 else 0.01
    reqs=[{'createLine':{'objectId':oid,'lineCategory':'STRAIGHT','elementProperties':{'pageObjectId':page,'size':{'width':pt(w),'height':pt(h)},'transform':{'scaleX':sx,'scaleY':sy,'translateX':x1*EMU,'translateY':y1*EMU,'unit':'EMU'}}}}]
    lp={'lineFill':{'solidFill':{'color':{'rgbColor':rgb(color)}}},'weight':pt(weight),'dashStyle':dash}
    f='lineFill,weight,dashStyle'
    if arrow_end: lp['endArrow']='FILL_ARROW'; f+=',endArrow'
    if arrow_start: lp['startArrow']='FILL_ARROW'; f+=',startArrow'
    reqs.append({'updateLineProperties':{'objectId':oid,'lineProperties':lp,'fields':f}})
    return oid,reqs

# --- deck introspection helpers
def slide_by_index(pres,i): return pres['slides'][i-1]
def elements(slide):
    out=[]
    def walk(el):
        out.append(el)
        if 'elementGroup' in el:
            for ch in el['elementGroup']['children']: walk(ch)
    for el in slide.get('pageElements',[]): walk(el)
    return out
def text_of(el):
    if 'shape' in el and 'text' in el['shape']:
        return ''.join(te.get('textRun',{}).get('content','') for te in el['shape']['text'].get('textElements',[]))
    return ''
def geo(el):
    t=el.get('transform',{}); s=el.get('size',{})
    return (t.get('translateX',0)/EMU, t.get('translateY',0)/EMU, s.get('width',{}).get('magnitude',0)*t.get('scaleX',1)/EMU, s.get('height',{}).get('magnitude',0)*t.get('scaleY',1)/EMU)
def find(slide, substr):
    for el in elements(slide):
        if substr in text_of(el): return el['objectId']
    raise KeyError(substr)
def body_ids(slide, keep_y=30):
    """ids of body elements: everything except header (y<keep_y), sidebar (x>=925), images."""
    ids=[]
    for el in slide.get('pageElements',[]):
        x,y,w,h=geo(el)
        if 'image' in el: continue
        if x>=925: continue
        if y<keep_y and h<40: continue
        ids.append(el['objectId'])
    return ids
def notes(slide):
    np=slide['slideProperties']['notesPage']; nid_=np['notesProperties']['speakerNotesObjectId']
    txt=''
    for el in np['pageElements']:
        if el['objectId']==nid_: txt=text_of(el)
    return nid_,txt
def set_notes(slide,text):
    nid_,cur=notes(slide)
    return set_text(nid_,[(text,{})],has_text=bool(cur))
def append_notes(slide,text):
    nid_,cur=notes(slide)
    if not cur: return set_text(nid_,[(text,{})],has_text=False)
    return [{'insertText':{'objectId':nid_,'insertionIndex':u16(cur.rstrip('\n')),'text':'\n'+text}}]
