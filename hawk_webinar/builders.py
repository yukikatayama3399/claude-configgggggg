from slidekit import *

def header(page, slide, label, title, subtitle=None, title_size=28):
    """Set the small label (kept header element) and recreate accent bar + title (+subtitle)."""
    reqs=[]
    for el in slide.get('pageElements',[]):
        x,y,w,h=geo(el); t=text_of(el)
        if t and 'Confidential' not in t and ((y<30 and h<40) or x>=925):
            reqs+=set_text(el['objectId'],[(label,{})])
    _,r=shape(page,'RECTANGLE',43,40,7,43,fill=MG); reqs+=r
    _,r=shape(page,'TEXT_BOX',60,35,842,55,runs=title,size=title_size,color=TXT,bold=True); reqs+=r
    if subtitle:
        _,r=shape(page,'TEXT_BOX',62,91,828,41,runs=subtitle,size=13.5,color=GRAY,valign='TOP'); reqs+=r
    return reqs

def strip_body(slide):
    ids=[]
    for el in slide.get('pageElements',[]):
        x,y,w,h=geo(el)
        if x>=925: continue
        if 'image' in el and y>=470: continue
        if 'image' not in el and y<30 and h<40: continue
        ids.append(el['objectId'])
    return delete(ids)

# ---------- お悩み集計 ----------
SURVEY=[('運用業務の利益率を高めたい',7),('セールスと運用の連携（与件共有・提案リテラシー）',6),('運用できる専門人材が足りず、ノウハウも属人化',5),('設定・レポートなどの手作業が多く、負荷とミスが増えている',5),('AIツールの内製化・自社開発に限界を感じている',1)]
QUOTES=['「媒体知見の高い人材がおらず、その都度調べながら、なんとか運用している」','「AI化は必要だと思うが、リスクとの兼ね合いで踏み込めない。リソースも潤沢にない」','「AIエージェントで業務効率化がどこまでできるか。ビフォーアフターを知りたい」','「使用上の注意点・懸念点・セキュリティ対策を知りたい」']
def build_survey(page, slide, n=12, asof='9/16'):
    reqs=header(page,slide,'WHAT WE HEARD FROM YOU','事前アンケートで、こんなお悩みをお伺いしています',f'お申込時にいただいた回答（{asof}時点・{n}名）。本日は、このお悩みに沿ってお話しします。')
    _,r=shape(page,'TEXT_BOX',61,140,440,20,runs='現在お持ちの課題（複数選択）',size=11,color=MG,bold=True,font='Arial'); reqs+=r
    y=164
    mx=max(c for _,c in SURVEY)
    for lab,c in SURVEY:
        _,r=shape(page,'TEXT_BOX',61,y,300,44,runs=lab,size=12.5,color=TXT); reqs+=r
        bw=max(6,150*c/mx)
        _,r=shape(page,'RECTANGLE',366,y+12,bw,20,fill=DG if c==mx else MG); reqs+=r
        _,r=shape(page,'TEXT_BOX',366+bw+4,y+6,60,32,runs=[(f'{c}',{'size':16,'bold':True,'color':DG}),('名',{'size':11,'color':GRAY})],size=16,color=DG,bold=True,font='Arial'); reqs+=r
        y+=50
    _,r=shape(page,'TEXT_BOX',570,140,320,20,runs='Q&Aで聞きたいこと・日頃のお悩み（原文より抜粋）',size=11,color=MG,bold=True,font='Arial'); reqs+=r
    y=164
    for q in QUOTES:
        _,r=shape(page,'ROUND_RECTANGLE',570,y,320,60,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',582,y,298,60,runs=q,size=12,color=TXT); reqs+=r
        y+=68
    _,r=shape(page,'TEXT_BOX',61,440,829,24,runs='※ 回答は匿名化して集計しています。数字は当日朝の申込状況で更新します。',size=10,color=GRAY); reqs+=r
    reqs+=set_notes(slide,f'11:05。事前アンケートの集計（集客シート「集客状況」タブ、{asof}時点 n={n}）。数字は当日朝に再集計して更新する。読み上げず「利益率と、セールス連携が最多でした」とだけ言い、右の生声を1つ読む。「あなたのお悩みに沿って話す」テーラーメイド感を出すのが目的。30秒。')
    return reqs

# ---------- こんな毎日 ----------
PAINS=[('毎朝、日予算を手で直している','クライアントごとに管理画面を開いて、毎日。'),
       ('80を超える設定項目の選定が大変','1つ間違えれば、誤配信か予算超過。'),
       ('レポート作成に追われる','週末に作る。「次の提案」を考える時間が、残らない。'),
       ('熟練者がおらず、見よう見まねで運用している','疑問は、その都度調べながら。'),
       ('AIで効率化したいが、効果がイメージできない','どの業務が、どれだけ変わるのか。計算のしかたが分からない。'),
       ('運用が分かる人が辞めて、ノウハウが消える','引き継ぎ資料も、残らない。')]
def build_pains(page, slide):
    reqs=header(page,slide,'THE DAILY GRIND','こんな毎日が、続いていませんか？')
    xs=[61,342,623]; ys=[118,296]
    i=0
    for y in ys:
        for x in xs:
            h,b=PAINS[i]; i+=1
            _,r=shape(page,'ROUND_RECTANGLE',x,y,267,160,fill=BG); reqs+=r
            _,r=shape(page,'TEXT_BOX',x+16,y+12,235,60,runs=h,size=17,color=TXT,bold=True,valign='TOP'); reqs+=r
            _,r=shape(page,'TEXT_BOX',x+16,y+80,235,70,runs=b,size=13,color=GRAY,valign='TOP'); reqs+=r
    reqs+=set_notes(slide,'11:05。つかみ。読み上げず、1行ずつ「あるあるですよね」と間を取る。参加者の自分ゴト化が目的。見出しは課題ベースの言い回しに統一（2026-09-17）。「熟練者がおらず」「AIで効率化したいが」は事前アンケートの生声から追加。ここは30秒。')
    return reqs

# ---------- こう変わる ----------
CHANGES=[('手作業が多く、ミスが増える',[('運用4タスク 33.0h → 4.4h／月（−87%）。',1),('入稿1件 ',0),('30分 → 4分。',1),('予算超過・誤配信は ',0),('発生ゼロを維持',1)]),
         ('熟練者がいない・属人化している',[('メモを貼るだけで設定項目80超を自動生成。新人の立ち上げ ',0),('約3ヶ月 → 約1ヶ月',1)]),
         ('セールスと運用の連携',[('与件メモから見積が ',0),('2分',1),('。提案リードタイム ',0),('3営業日 → 当日',1)]),
         ('運用業務の利益率を高めたい',[('費用は月額固定。1人あたり担当案件 ',0),('5件 → 8件',1),('。人件費を増やさず取扱高を拡大',0)]),
         ('AI導入の効果がイメージできない',[('第2章で測定条件と内訳を全開示。貴社の人員・時間で',0),('投資対効果を個別に試算',1)])]
def build_changed(page, slide):
    reqs=header(page,slide,'WHAT CHANGED','そのお悩みは、こう変わりました','私たち自身の運用チーム（運用者5名）で実測した結果です。測り方は、第2章ですべて開示します。')
    y=146
    for pain,runs in CHANGES:
        _,r=shape(page,'ROUND_RECTANGLE',61,y,829,54,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',81,y,280,54,runs=pain,size=13.5,color=TXT,bold=True); reqs+=r
        _,r=shape(page,'TEXT_BOX',362,y,24,54,runs='▶',size=13,color=MG,font='Arial',align='CENTER'); reqs+=r
        rr=[(t,{'size':13.5,'bold':True,'color':DG} if b else {'size':12.5,'color':TXT}) for t,b in runs]
        _,r=shape(page,'TEXT_BOX',392,y,490,54,runs=rr,size=12.5,color=TXT); reqs+=r
        y+=60
    reqs+=set_notes(slide,'11:06。前のスライドのお悩みに1対1で答える。数字は第2章で回収するので、ここでは「変わった」ことだけ言う。読み上げは右列の太字だけ。数値は 2026-09-17 確定（たたき台を採用）。45秒。')
    return reqs

# ---------- レイヤー図 ----------
def build_layers(page):
    reqs=[]
    bands=[(146,DG,'HAWK が担う','ワークフローレイヤー',LG,WHITE,'#1c6b2a',WHITE,[['与件整理','見積もり','設計・設定'],['運用状況の確認','レポート・次アクション','媒体横断の予算管理']]),
           (246,PG,'媒体の自動化が担う','配信最適化レイヤー',GRAY,TXT,WHITE,TXT,[['Meta Advantage+','TikTok Smart+','Google P-MAX'],['オーディエンス','入札・予算配分','配信面・クリエイティブ']]),
           (346,BG,'配信基盤','媒体レイヤー',GRAY,TXT,WHITE,TXT,[['Instagram','Facebook','TikTok'],['LINEヤフー広告（今秋）']])]
    for y,fill,lab,title,labc,titc,chipf,chipt,rows in bands:
        _,r=shape(page,'ROUND_RECTANGLE',61,y,700,90,fill=fill); reqs+=r
        _,r=shape(page,'TEXT_BOX',81,y+8,190,20,runs=lab,size=10.5,color=labc,bold=True); reqs+=r
        _,r=shape(page,'TEXT_BOX',81,y+30,190,50,runs=title,size=17,color=titc,bold=True,valign='TOP'); reqs+=r
        for ri,row in enumerate(rows):
            cy=y+12+ri*38
            for ci,chip in enumerate(row):
                cx=280+ci*158
                _,r=shape(page,'ROUND_RECTANGLE',cx,cy,150,30,fill=chipf,outline=(PG,0.75) if chipf==WHITE else None); reqs+=r
                _,r=shape(page,'TEXT_BOX',cx,cy,150,30,runs=chip,size=11.5,color=chipt,bold=True,align='CENTER'); reqs+=r
    # bypass bracket: HAWK -> 媒体 directly
    _,r=line(page,761,191,880,191,color=DG,weight=3); reqs+=r
    _,r=line(page,880,191,880,391,color=DG,weight=3); reqs+=r
    _,r=line(page,880,391,765,391,color=DG,weight=3,arrow_end=True); reqs+=r
    _,r=shape(page,'TEXT_BOX',770,246,104,90,runs=[('HAWKは媒体へ\n直接入稿\n',{'size':11,'bold':True,'color':DG}),('自動最適化は\n通しません',{'size':10.5,'color':GRAY})],size=11,color=DG,bold=True,align='CENTER'); reqs+=r
    _,r=shape(page,'TEXT_BOX',61,444,829,28,runs=[('※ HAWKは各媒体の自動最適化を',{'size':13,'color':TXT,'bold':True}),('一切利用しません',{'size':13,'color':DG,'bold':True}),('。指定の入稿規定に即した配信設計を瞬時に実施します。',{'size':13,'color':TXT,'bold':True})],size=13,color=TXT,bold=True); reqs+=r
    return reqs

# ---------- ハブ図 ----------
def build_hub(page):
    reqs=[]
    # cycle arrows first (under boxes)
    for a in [(186,173,186,140,False),(186,140,765,140,False),(765,140,765,173,True),
              (765,307,765,400,False),(765,400,600,400,True),
              (350,400,186,400,False),(186,400,186,307,True)]:
        _,r=line(page,a[0],a[1],a[2],a[3],color=DG,weight=2.5,arrow_end=a[4]); reqs+=r
    for a in [(410,240,311,240),(540,240,640,240),(475,305,475,340)]:
        _,r=line(page,*a,color=MG,weight=1.5,dash='DASH'); reqs+=r
    boxes=[(61,173,250,134,'THINK ── 考える','与件メモを解釈し、見積もり・KPI・キャンペーン設計を自動生成'),
           (640,173,250,134,'RUN ── 動かす','キャンペーン・広告セット・広告を自動作成。日予算を毎日自動調整'),
           (350,340,250,120,'REVIEW ── 振り返る','実績とクリエイティブを分析し、インサイトレポートと次アクションを出力')]
    for x,y,w,h,t,b in boxes:
        _,r=shape(page,'ROUND_RECTANGLE',x,y,w,h,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+16,y+10,w-32,34,runs=t,size=18,color=TXT,bold=True); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+16,y+48,w-32,h-56,runs=b,size=12.5,color=GRAY,valign='TOP'); reqs+=r
    _,r=shape(page,'ELLIPSE',410,175,130,130,fill=DG); reqs+=r
    _,r=shape(page,'TEXT_BOX',410,175,130,130,runs=[('HAWK\n',{'size':22,'bold':True,'color':WHITE,'font':'Arial'}),('伴走型AIエージェント',{'size':9.5,'color':LG})],size=22,color=WHITE,bold=True,align='CENTER'); reqs+=r
    _,r=shape(page,'ROUND_RECTANGLE',372,126,206,28,fill=WHITE,outline=(MG,1)); reqs+=r
    _,r=shape(page,'TEXT_BOX',372,126,206,28,runs='各ステップに、人の確認ポイント',size=11,color=DG,bold=True,align='CENTER'); reqs+=r
    return reqs

# ---------- タスク別内訳（本番版 P15 用） ----------
BREAK=[('① 見積もり作成','3.0h → 0.2h','（−93%）'),('② キャンペーン設計・設定','8.0h → 1.0h','（−88%）'),('③ モニタリング・日予算調整','15.0h → 2.0h','（−87%）'),('④ レポート／次アクション作成','7.0h → 1.2h','（−83%）')]
def build_breakdown(page, y0=169):
    reqs=[]; y=y0
    for lab,num,pct in BREAK:
        _,r=shape(page,'ROUND_RECTANGLE',54,y,842,56,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',74,y,340,56,runs=lab,size=16,color=TXT,bold=True); reqs+=r
        _,r=shape(page,'TEXT_BOX',430,y,440,56,runs=[(num,{'size':22,'bold':True,'color':TXT,'font':'Arial'}),('　'+pct,{'size':16,'bold':True,'color':DG})],size=22,color=TXT,bold=True); reqs+=r
        y+=64
    _,r=shape(page,'TEXT_BOX',54,y+2,842,30,runs=[('合計 33.0h → 4.4h（',{'size':14,'bold':True,'color':TXT}),('−87%',{'size':14,'bold':True,'color':DG}),('）　※ 同一4タスク・1案件・月あたり。運用者5名・12案件の作業記録から再構成',{'size':11.5,'color':GRAY})],size=14,color=TXT,bold=True); reqs+=r
    return reqs

# ---------- 予備：デモ静止画 ----------
FALLBACK=[('A　入稿編','与件メモ → 見積 → 配信設計 → Metaへ入稿'),('B　運用編','キャンペーン構造／日予算自動調整／入札／クリエイティブON・OFF／参照キャンペーンの指標'),('C　レポート編','インサイトレポートを PowerPoint で出力')]
def build_fallback(page, slide):
    reqs=header(page,slide,'DEMO FALLBACK','（予備）デモ静止画：動画が再生できない場合に使用','録画が出ない場合はこのスライドで説明する。A／B／C の画面キャプチャを差し替えて配置。')
    xs=[61,342,623]
    for (h,b),x in zip(FALLBACK,xs):
        _,r=shape(page,'ROUND_RECTANGLE',x,146,267,290,fill=BG,outline=(MG,1,'DASH')); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+16,158,235,34,runs=h,size=17,color=TXT,bold=True); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+16,200,235,190,runs=[('画面キャプチャを配置\n\n',{'size':13,'color':GRAY,'bold':True}),(b,{'size':11.5,'color':GRAY})],size=13,color=GRAY,align='CENTER'); reqs+=r
    reqs+=set_notes(slide,'投影しない（予備）。杉浦さんの録画から A／B／C 各1枚のキャプチャを差し替える。動画が出ない場合はここに飛んで、A→B→C の順に口頭で説明する。')
    return reqs

DEMO_RUNS=[('A　入稿編\n',{'size':17,'bold':True,'color':WHITE}),('　与件メモ → 見積 → 配信設計 → Metaへ入稿\n',{'size':13.5,'color':WHITE,'bold':False}),
           ('B　運用編\n',{'size':17,'bold':True,'color':WHITE}),('　キャンペーン構造・日予算の自動調整・入札・クリエイティブ ON/OFF・指標\n',{'size':13.5,'color':WHITE,'bold':False}),
           ('C　レポート編\n',{'size':17,'bold':True,'color':WHITE}),('　インサイトレポートを PowerPoint で出力\n\n',{'size':13.5,'color':WHITE,'bold':False}),
           ('この3部を、録画（約5分）でご覧いただきます。',{'size':14,'color':LG,'bold':True})]
DEMO_NOTE='11:40頃。デモは録画を正とする（2026-09-17 決定。ライブはしない）。尺4〜5分、A→B→Cの3部構成。A 入稿編：与件メモ貼付→見積→配信設計→Metaへ入稿（広告マネージャで反映を確認）。B 運用編：キャンペーン／広告セット／広告の構造、広告セット単位の日予算自動調整ボタン、キャンペーン単位の予算設定、広告セット単位の入札設定、クリエイティブのON/OFF。過去の参照キャンペーンで CPC・CPE・CTR・25%視聴率・完全視聴率・完全視聴単価を確認（スコアは今後のキャンペーン対象なので飛ばす）。C レポート編：レポートのフォーマット紹介→PowerPoint出力（競合との最大差、省かない）。運用：ローカルに置いた動画を再生アプリで一時停止待機→動画ウィンドウを直接共有（ビデオクリップ最適化・音声共有ON）。1本版と3分割版（A/B/C）を持ち、質疑の「もう一度」は分割版で応える。話者は動画に合わせて口頭で説明（ナレーションは録画に入れない）。出ない場合は末尾の予備スライド（静止画）へ。'

# ---------- お悩み集計（2枚分割版） ----------
def build_survey_issues(page, slide, n=12, asof='9/16'):
    reqs=header(page,slide,'WHAT WE HEARD FROM YOU','事前アンケートで、こんなお悩みをお伺いしています',f'お申込時にいただいた「現在お持ちの課題」（複数選択・{asof}時点・{n}名）。本日は、このお悩みに沿ってお話しします。')
    y=146; mx=max(c for _,c in SURVEY)
    for lab,c in SURVEY:
        top=(c==mx)
        _,r=shape(page,'ROUND_RECTANGLE',61,y,829,54,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',81,y,500,54,runs=lab,size=17,color=TXT,bold=True); reqs+=r
        bw=max(8,220*c/mx)
        _,r=shape(page,'RECTANGLE',590,y+15,bw,24,fill=DG if top else MG); reqs+=r
        _,r=shape(page,'TEXT_BOX',590+bw+6,y+6,80,42,runs=[(f'{c}',{'size':22,'bold':True,'color':DG if top else TXT}),('名',{'size':12,'color':GRAY})],size=22,color=DG,bold=True,font='Arial'); reqs+=r
        y+=60
    _,r=shape(page,'TEXT_BOX',61,448,829,22,runs='※ 回答は匿名化して集計しています。数字は当日朝の申込状況で更新します。',size=10,color=GRAY); reqs+=r
    reqs+=set_notes(slide,f'11:05。事前アンケートの集計（集客シート「集客状況」タブ、{asof}時点 n={n}）。数字は当日朝に再集計して更新する。読み上げず「利益率と、セールス連携が最多でした」とだけ言う。20秒。')
    return reqs

def build_survey_quotes(page, slide):
    reqs=header(page,slide,'WHAT WE HEARD FROM YOU','Q&Aで聞きたいこと・日頃のお悩みも、お伺いしています','お申込フォームの自由記述より抜粋（原文・匿名）。本日の質疑でも、ここからお答えします。')
    pos=[(61,146),(480,146),(61,300),(480,300)]
    for q,(x,y) in zip(QUOTES,pos):
        _,r=shape(page,'ROUND_RECTANGLE',x,y,410,140,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+14,y+4,40,50,runs='“',size=40,color=LG,bold=True,font='Arial'); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+24,y+22,370,110,runs=q.strip('「」'),size=16,color=TXT,bold=True); reqs+=r
    reqs+=set_notes(slide,'11:05。前のスライドの続き。4つのうち1つだけ読む（おすすめは「その都度調べながら、なんとか運用している」）。「これ、全部このあとの章で答えます」と言って次へ。「AIで効率化したいがイメージできない」は第2章、「セキュリティ・注意点」は第5章ガードレール＋質疑で回収。20秒。')
    return reqs

def build_survey_issues_plain(page, slide, n=12, asof='9/16'):
    """グラフ・人数なし。お悩み文言だけを大きく。"""
    reqs=header(page,slide,'WHAT WE HEARD FROM YOU','事前アンケートで、こんなお悩みをお伺いしています',f'お申込時にいただいた「現在お持ちの課題」（{asof}時点・{n}名、多い順）。本日は、このお悩みに沿ってお話しします。')
    y=146
    for lab,c in SURVEY:
        _,r=shape(page,'ROUND_RECTANGLE',61,y,829,54,fill=BG); reqs+=r
        _,r=shape(page,'RECTANGLE',61,y+15,6,24,fill=DG); reqs+=r
        _,r=shape(page,'TEXT_BOX',85,y,790,54,runs=lab,size=22,color=TXT,bold=True); reqs+=r
        y+=60
    _,r=shape(page,'TEXT_BOX',61,448,829,22,runs='※ 回答は匿名化しています。',size=10,color=GRAY); reqs+=r
    reqs+=set_notes(slide,f'11:05。事前アンケートの「現在お持ちの課題」を多い順に並べたもの（集客シート「集客状況」タブ、{asof}時点 n={n}：利益率7／セールス連携6／人材5／手作業5／内製化1）。人数は出さず口頭で「利益率とセールス連携が最多でした」とだけ言う。当日朝に再集計して並び順を確認。20秒。')
    return reqs

TIMELINE=[('11:10','なぜ、運用工数は減らないのか'),('11:17','自社案件の運用工数を、実測しました'),('11:25','工数が減っただけでは、何も変わりません'),('11:33','伴走型AIエージェント「HAWK」のご案内'),('11:40','デモ画面のご案内')]
def build_timeline(page, slide):
    reqs=header(page,slide,'TIMELINE','本日のタイムライン')
    y=126
    for t,title in TIMELINE:
        _,r=shape(page,'ROUND_RECTANGLE',61,y,829,58,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',81,y,110,58,runs=t,size=20,color=MG,bold=True,font='Arial'); reqs+=r
        _,r=shape(page,'TEXT_BOX',196,y,680,58,runs=title,size=26,color=TXT,bold=True); reqs+=r
        y+=64
    _,r=shape(page,'TEXT_BOX',81,y+2,809,24,runs='11:50〜 質疑応答（15分）。アンケート記述欄のご質問にも、後日回答します。',size=12,color=GRAY); reqs+=r
    reqs+=set_notes(slide,'タイムライン。章ごとに5行だけ（2026-09-17 簡略化）。「あと何分」が分かることで離脱を防ぐ。11:05〜11:10 はつかみ（お悩み・声・結果の先出し）で、このスライドはその最後に出す。質疑は11:50から15分。')
    return reqs

def build_pains_half(page, slide, part):
    """part=1: PAINS[0:3] / part=2: PAINS[3:6]。3タイル横並び、大きい文字。"""
    title='こんな毎日が、続いていませんか？' if part==1 else 'こんな悩みも、ありませんか？'
    reqs=header(page,slide,'THE DAILY GRIND',title)
    items=PAINS[0:3] if part==1 else PAINS[3:6]
    for (h,b),x in zip(items,[61,342,623]):
        _,r=shape(page,'ROUND_RECTANGLE',x,126,267,320,fill=BG); reqs+=r
        _,r=shape(page,'RECTANGLE',x+20,150,40,5,fill=MG); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+18,166,231,130,runs=h,size=24,color=TXT,bold=True,valign='TOP'); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+18,306,231,120,runs=b,size=16,color=GRAY,valign='TOP'); reqs+=r
    note=('11:05。つかみ1枚目。読み上げず、1枚ずつ「あるあるですよね」と間を取る。参加者の自分ゴト化が目的。15秒。' if part==1
          else '11:06。つかみ2枚目。「熟練者がおらず」「AIで効率化したいが」は事前アンケートの生声から。3つ目の「辞めてノウハウが消える」が第1章への伏線。15秒。')
    reqs+=set_notes(slide,note)
    return reqs

OPS_ITEMS=[('戦略・企画立案','月末に追われず、期中に提案を出せるようになった。企画提案は 月2本 → 5本。'),
           ('クリエイティブ改善のPDCA','当たり外れの検証を、思いついた週にそのまま回せる。検証本数 月4本 → 12本。'),
           ('新媒体の検証','後回しにしていたLINEヤフー広告の検証を、業務時間内で着手できた。'),
           ('担当案件数','1人あたり 5案件 → 8案件。案件が増えても、日々の作業が積み上がらない。'),
           ('属人化の解消','休んでも進む。引き継ぎ資料を作らなくても、担当交代ができた。'),
           ('労働時間','夜の日予算チェックが消えた。月の残業が 約20時間 減。')]
def build_ops_half(page, slide, part):
    title='運用担当者に起きたこと' if part==1 else '運用担当者に起きたこと（続き）'
    reqs=header(page,slide,'THE OPERATORS',title,'反復作業から解放された時間が、どこに移ったか。')
    items=OPS_ITEMS[0:3] if part==1 else OPS_ITEMS[3:6]
    base=0 if part==1 else 3
    for i,((h,b),x) in enumerate(zip(items,[61,342,623])):
        _,r=shape(page,'ROUND_RECTANGLE',x,146,267,310,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+18,160,60,34,runs=f'{base+i+1:02d}',size=18,color=MG,bold=True,font='Arial'); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+18,196,231,90,runs=h,size=24,color=TXT,bold=True,valign='TOP'); reqs+=r
        _,r=shape(page,'TEXT_BOX',x+18,296,231,150,runs=b,size=16,color=TXT,valign='TOP'); reqs+=r
    reqs+=set_notes(slide,('運用担当者の所感（前半3つ）。2026-09-17 に仮確定値で記入。差し替える場合は本文だけ変える。' if part==1 else '運用担当者の所感（後半3つ）。04 担当案件数 5→8 は「8倍にはならない」と整合させた数字。'))
    return reqs

# ---------- 送付版（本番版）用: 1枚に情報量多め ----------
def build_survey_dense(page, slide, n=12, asof='9/16'):
    reqs=header(page,slide,'WHAT WE HEARD FROM YOU','事前アンケートで、こんなお悩みをお伺いしています',f'お申込時にいただいた回答（{asof}時点・{n}名）。本日は、このお悩みに沿ってお話しします。')
    _,r=shape(page,'TEXT_BOX',61,140,440,20,runs='現在お持ちの課題（複数選択・多い順）',size=11,color=MG,bold=True,font='Arial'); reqs+=r
    y=164
    for lab,c in SURVEY:
        _,r=shape(page,'ROUND_RECTANGLE',61,y,480,46,fill=BG); reqs+=r
        _,r=shape(page,'RECTANGLE',61,y+12,5,22,fill=DG); reqs+=r
        _,r=shape(page,'TEXT_BOX',80,y,455,46,runs=lab,size=14,color=TXT,bold=True); reqs+=r
        y+=52
    _,r=shape(page,'TEXT_BOX',570,140,320,20,runs='Q&Aで聞きたいこと・日頃のお悩み（原文より抜粋）',size=11,color=MG,bold=True,font='Arial'); reqs+=r
    y=164
    for q in QUOTES:
        _,r=shape(page,'ROUND_RECTANGLE',570,y,320,60,fill=BG); reqs+=r
        _,r=shape(page,'TEXT_BOX',582,y,298,60,runs=q,size=12,color=TXT); reqs+=r
        y+=68
    _,r=shape(page,'TEXT_BOX',61,440,829,24,runs='※ 回答は匿名化しています。',size=10,color=GRAY); reqs+=r
    reqs+=set_notes(slide,f'（送付版）事前アンケートの集計と自由記述抜粋を1枚に。投影版では2枚に分けている。{asof}時点 n={n}（利益率7／セールス連携6／人材5／手作業5／内製化1）。送付時は当日朝の再集計値に更新。')
    return reqs

def build_ops_dense(page, slide):
    reqs=header(page,slide,'THE OPERATORS','運用担当者に起きたこと','反復作業から解放された時間が、どこに移ったか。')
    xs=[61,342,623]; ys=[146,306]; i=0
    for y in ys:
        for x in xs:
            h,b=OPS_ITEMS[i]; i+=1
            _,r=shape(page,'ROUND_RECTANGLE',x,y,267,150,fill=BG); reqs+=r
            _,r=shape(page,'TEXT_BOX',x+16,y+12,40,28,runs=f'{i:02d}',size=15,color=MG,bold=True,font='Arial'); reqs+=r
            _,r=shape(page,'TEXT_BOX',x+56,y+12,200,28,runs=h,size=15,color=TXT,bold=True); reqs+=r
            _,r=shape(page,'TEXT_BOX',x+16,y+48,235,96,runs=b,size=13,color=TXT,valign='TOP'); reqs+=r
    reqs+=set_notes(slide,'【2026-09-17 確定】運用担当者の所感6枠に仮確定値を記入（サンプル文を昇格）。送付版は1枚、投影版は2枚に分割。差し替える場合は本文だけ変える。')
    return reqs
