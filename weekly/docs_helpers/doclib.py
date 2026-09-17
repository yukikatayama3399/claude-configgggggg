import json, subprocess, sys
DOC="1I7u2zNZTPl9tAo2SGalo35ElsDWu2MPpP6JgIYr8LCk"
TAB="t.2boyn2a7oxux"
def fetch():
    out=subprocess.run(["gws","docs","documents","get","--params",json.dumps({"documentId":DOC,"includeTabsContent":True})],capture_output=True,text=True,check=True).stdout
    d=json.loads(out)
    def find(tabs):
        for t in tabs:
            if t['tabProperties']['tabId']==TAB: return t
            r=find(t.get('childTabs',[]))
            if r: return r
    return find(d['tabs'])['documentTab']['body']['content']
def ptext(el):
    return ''.join(e.get('textRun',{}).get('content','') for e in el['paragraph'].get('elements',[]))
def paras(content):
    out=[]
    for el in content:
        if 'paragraph' in el: out.append((el['startIndex'],el['endIndex'],ptext(el),el))
    return out
def find_para(ps, needle, nth=0, exact=False):
    hits=[p for p in ps if (p[2].rstrip('\n')==needle if exact else needle in p[2])]
    if len(hits)<=nth: raise SystemExit(f"NOT FOUND: {needle!r} (hits={len(hits)})")
    return hits[nth]
def batch(reqs):
    if not reqs: print("no requests"); return
    r=subprocess.run(["gws","docs","documents","batchUpdate","--params",json.dumps({"documentId":DOC}),"--json",json.dumps({"requests":reqs},ensure_ascii=False)],capture_output=True,text=True)
    print("rc",r.returncode); print(r.stdout[:600]); print(r.stderr[:2000])
    if r.returncode!=0: sys.exit(1)
def ins(idx,text): return {"insertText":{"location":{"tabId":TAB,"index":idx},"text":text}}
def dele(a,b): return {"deleteContentRange":{"range":{"tabId":TAB,"startIndex":a,"endIndex":b}}}
