from slidekit import *
from builders import *
PID='1mTA1GT3-nPTos6K-Kk6MP2C8JWCns8Tp-8yeXkQz4ys'
p=get(PID); ids=[s['objectId'] for s in p['slides']]
if 'hb_survey' not in ids:
    batch(PID,[{'duplicateObject':{'objectId':'p5','objectIds':{'p5':'hb_survey'}}},
               {'duplicateObject':{'objectId':'p5','objectIds':{'p5':'hb_pains'}}},
               {'duplicateObject':{'objectId':'p5','objectIds':{'p5':'hb_changed'}}},
               {'duplicateObject':{'objectId':'p37','objectIds':{'p37':'hb_fallback'}}}],'dup')
    batch(PID,[{'updateSlidesPosition':{'slideObjectIds':['hb_survey'],'insertionIndex':1}}],'pos1')
    batch(PID,[{'updateSlidesPosition':{'slideObjectIds':['hb_pains'],'insertionIndex':2}}],'pos2')
    batch(PID,[{'updateSlidesPosition':{'slideObjectIds':['hb_changed'],'insertionIndex':3}}],'pos3')
p=get(PID); order=[s['objectId'] for s in p['slides']]
print([(i+1,o) for i,o in enumerate(order) if o.startswith('hb_')], 'total',len(order))
byid={s['objectId']:s for s in p['slides']}
R=[]
for sid,b in [('hb_survey',build_survey),('hb_pains',build_pains),('hb_changed',build_changed),('hb_fallback',build_fallback)]:
    s=byid[sid]; R+=strip_body(s); R+=b(sid,s)
# 送付版の新規3枚はノートを送付版向けに補足
R+=append_notes(byid['hb_survey'],'（送付版）投影版と同じ内容。送付時は当日朝の再集計値に更新して出す。')
print('requests',len(R))
for k in range(0,len(R),150): batch(PID,R[k:k+150],f'hb phase2 {k}')
