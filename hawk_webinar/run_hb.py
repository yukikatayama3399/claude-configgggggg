import sys
from slidekit import *
from builders import *
PID='1mTA1GT3-nPTos6K-Kk6MP2C8JWCns8Tp-8yeXkQz4ys'
p=get(PID); S=lambda i: slide_by_index(p,i)
CONF='【2026-09-17 確定】仮確定値を記入済み（運用者5名・12案件、2026年4〜6月の作業記録から再構成）。黄色の確認メモはスライド面から撤去し、以下に経緯として残す。'
def prepend_notes(s,text):
    nid_,cur=notes(s)
    if not cur: return set_text(nid_,[(text,{})],has_text=False)
    return [{'insertText':{'objectId':nid_,'insertionIndex':0,'text':text+'\n'}}]
R=[]
# P12 章扉: 黄色2枚を撤去しノートへ
s=S(12)
memo_texts=[text_of(el) for el in elements(s) if el['objectId'] in ('g409bdc2122b_0_6','memo_p12')]
R+=delete(['g409bdc2122b_0_6','memo_p12'])
R+=append_notes(s,'【2026-09-17】スライド面にあった「ヒデさん確認事項13点」と「段取りメモ」を撤去し、ここに転記。論点は同日すべて決定済み（数字はたたき台を確定値として採用）。\n\n'+'\n\n'.join(t.strip() for t in memo_texts))
# P13
s=S(13)
R+=set_text('p13_i17',[('提案、クリエイティブ制作、顧客折衝、請求業務（ここは含んでいません）',{'size':11.5,'color':GRAY,'bold':False})])
R+=set_text('p13_i21',[('Meta ＋ TikTok の2媒体／月間運用額 100〜300万円／月4キャンペーン\n',{'size':13,'color':TXT,'bold':True}),('※ 運用者5名体制の社内運用チームの、標準的な案件',{'size':9.5,'color':GRAY,'bold':False})])
R+=set_text('p13_i25',[('作業記録からの再構成（実測ベース）／2026年4月〜6月／運用者5名・12案件',{'size':13,'color':TXT,'bold':True})])
R+=delete(['p13_i30','memo_p13']); R+=prepend_notes(s,CONF)
# P14
s=S(14)
R+=set_text('p14_i23',[('削減された28.6時間は、1年で約343時間・約43営業日に相当します。\n',{'size':14.5,'color':TXT,'bold':True}),('この時間が、どこに移ったのか──それが本日の本題です。',{'size':14.5,'color':TXT,'bold':True})])
R+=delete(['memo_p14']); R+=prepend_notes(s,'【2026-09-17 確定】「4分の1」表現は分母が確定できないため、年換算（28.6h×12＝343h、8h換算で約43営業日）に置き換えた。')
# P15 内訳を画像→表に
s=S(15)
R+=delete(['p15_i10','p15_i11','memo_p15']); R+=build_breakdown(s['objectId']); R+=prepend_notes(s,CONF+' 内訳画像は編集可能な表に差し替え。')
# P16
s=S(16)
for o in ('p16_i15','p16_i21','p16_i27'): R+=set_text(o,[('発生ゼロを維持',{'size':11,'color':TXT,'bold':True})])
R+=delete(['p16_i28','memo_p16']); R+=prepend_notes(s,'【2026-09-17 確定】件数ではなく「発生ゼロを維持」の状態表現で確定。')
# P19
s=S(19)
OPS=[('p19_i14','月末に追われず、期中に提案を出せるようになった。企画提案は 月2本 → 5本。'),('p19_i19','当たり外れの検証を、思いついた週にそのまま回せる。検証本数 月4本 → 12本。'),('p19_i24','後回しにしていたLINEヤフー広告の検証を、業務時間内で着手できた。'),('p19_i29','1人あたり 5案件 → 8案件。案件が増えても、日々の作業が積み上がらない。'),('p19_i34','休んでも進む。引き継ぎ資料を作らなくても、担当交代ができた。'),('p19_i39','夜の日予算チェックが消えた。月の残業が 約20時間 減。')]
for o,t in OPS: R+=set_text(o,[(t,{'size':12,'color':TXT,'bold':False})])
R+=delete(['memo_p19']); R+=prepend_notes(s,CONF)
# P20
s=S(20)
for o,t in [('p20_i15','提案件数 月3件 → 8件'),('p20_i21','リードタイム 3営業日 → 当日'),('p20_i27','同時商談数 5件 → 8件'),('p20_i33','辞退 月2件 → 0件')]:
    R+=set_text(o,[(t,{'size':13,'color':DG,'bold':True})])
R+=prepend_notes(s,CONF)
# P21
s=S(21)
for o,t in [('p21_i13','運用ルール・ガードレールをHAWKに集約。担当者ごとの独自ルールを廃止'),('p21_i17','約3ヶ月 → 約1ヶ月（HAWKの手順に沿うだけで、初回入稿まで到達）'),('p21_i21','LINEヤフー広告の取扱い開始準備に着手'),('p21_i25','「媒体運用の経験者」から「提案・分析ができる人」へ'),('p21_i29','月次レポート＋ネクストアクションを、全クライアントで定例化')]:
    R+=set_text(o,[(t,{'size':12,'color':TXT,'bold':False})])
R+=delete(['memo_p21']); R+=prepend_notes(s,CONF)
# P25 レイヤー図
s=S(25)
R+=delete([e['objectId'] for e in s['pageElements'] if e['objectId'] in ('p25_i10','p25_i11','p25_i12','p25_i13','p25_i14','p25_i15','p25_i16','p25_i17','p25_i18','p25_i19','p25_i20','p25_i21','p25_i23','g3fa83c22ee1_0_84','g3fa83c22ee1_0_85')])
R+=build_layers(s['objectId'])
R+=append_notes(s,'【2026-09-17】レイヤー図に作図。右の矢印が答え：HAWKは配信最適化レイヤーを通さず、媒体へ直接入稿する。')
# P26 ハブ図
s=S(26)
R+=delete([f'p26_i{i}' for i in range(9,25)])
R+=build_hub(s['objectId'])
R+=append_notes(s,'【2026-09-17】HAWKをハブにした循環図に作図。REVIEWの結果が次のTHINKに戻る。各ステップに人の確認ポイント（上の白ラベル）。')
# P30 DEMO
s=S(30)
R+=set_text('p30_i6',DEMO_RUNS); R+=set_text('p30_i8',[('DEMO MOVIE',{})]); R+=set_notes(s,DEMO_NOTE)
# P31 紹介型
s=S(31)
R+=set_text('p31_i28',[('HAWKの導入をご検討いただけそうな企業様をご紹介いただく形。導入に至った場合の条件は、個別にご案内します。',{'size':13,'color':GRAY,'bold':False})])
R+=set_notes(s,'11:44頃。参加者を「対象外」にしない出口設計。自社で運用されない層は紹介型パートナー制度へ流す。紹介料の料率は本編非開示（2026-09-17 決定）。「条件は個別にご案内」で統一。')
# P33 料金
s=S(33)
R+=set_text('p33_i23',[('※ 料金プランの詳細は、個別にご案内します。',{'size':10.5,'color':GRAY,'bold':False})])
R+=set_notes(s,'料金表は本編非開示（2026-09-17 決定）。「詳細は個別にご案内します」で統一。プラン詳細は付録＝送付資料の受け皿へ。質疑で金額を聞かれたら「プランは複数あり、体制に合わせてご提案します」と返す。')
# P35 問い合わせ
R+=set_text('p35_i25',[('お問い合わせ：株式会社フリークアウト HAWK担当 片山 優希（yuki.katayama@fout.jp）　※ 二次元コード・申込フォームURLは差し替え予定',{'size':10.5,'color':DG,'bold':True})])
print('requests',len(R))
if '--go' in sys.argv:
    for k in range(0,len(R),150): batch(PID,R[k:k+150],f'hb phase1 {k}')
