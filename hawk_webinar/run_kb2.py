from slidekit import *
from builders import *
PID='1WdSjAJttmgzPQHgH_OAlxhCKY1RBrCqeE4xBzIHUyM0'
p=get(PID); n=len(p['slides'])
ids=[s['objectId'] for s in p['slides']]
if 'kb_survey' not in ids:
    batch(PID,[{'duplicateObject':{'objectId':'kb_ns0001','objectIds':{'kb_ns0001':'kb_survey'}}},
               {'duplicateObject':{'objectId':'kb_ns0001','objectIds':{'kb_ns0001':'kb_changed'}}},
               {'duplicateObject':{'objectId':'kb_ns0800','objectIds':{'kb_ns0800':'kb_fallback'}}}],'dup')
    batch(PID,[{'updateSlidesPosition':{'slideObjectIds':['kb_survey'],'insertionIndex':1}}],'pos1')
    batch(PID,[{'updateSlidesPosition':{'slideObjectIds':['kb_changed'],'insertionIndex':3}}],'pos2')
    p=get(PID); n=len(p['slides'])
    batch(PID,[{'updateSlidesPosition':{'slideObjectIds':['kb_fallback'],'insertionIndex':n}}],'pos3')
p=get(PID)
order=[s['objectId'] for s in p['slides']]
print([ (i+1,o) for i,o in enumerate(order) if o in ('kb_survey','kb_ns0001','kb_changed','kb_fallback')])
byid={s['objectId']:s for s in p['slides']}
R=[]
for sid,builder in [('kb_survey',build_survey),('kb_ns0001',build_pains),('kb_changed',build_changed),('kb_fallback',build_fallback)]:
    s=byid[sid]
    R+=strip_body(s)
    R+=builder(sid,s)
print('requests',len(R))
for k in range(0,len(R),150): batch(PID,R[k:k+150],f'kb phase2 {k}')
