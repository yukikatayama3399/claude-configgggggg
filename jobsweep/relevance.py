# -*- coding: utf-8 -*-
"""SNS広告運用求人かどうかの判定（唯一の品質ゲート）。

方針:
  優先度(S/A/B)は問わない。守るのは「SNS広告運用の求人が実在するか」だけ。
  媒体の検索はOR一致で大量のノイズを返す（求人ボックスで "SNS広告運用" が
  全国62,000件）ため、取り込み側のこのゲートで絞る。

精度上の要点:
  スニペット全文に対する単純な語の有無判定は、
  「応募条件: SEO・WEB広告運用・SNS運用の経験がある方」（実体は組込エンジニア派遣）
  のような求人を誤って通してしまう。そのため
    (1) タイトルの職種が明らかに別職種なら落とす
    (2) SNS語と広告語が「近接」していることを要求する
  の2段構えにする。
"""
import re
import unicodedata


def _norm(s: str) -> str:
    if not s:
        return ""
    return unicodedata.normalize("NFKC", s).lower()


# SNS(ソーシャル)を指す語
SNS = [
    "sns", "ソーシャルメディア", "ソーシャル広告",
    "instagram", "インスタグラム", "インスタ",
    "tiktok", "ティックトック",
    "facebook", "フェイスブック",
    "youtube", "ユーチューブ",
    "line広告", "line ads",
    "meta広告", "meta ads",
    "twitter", "x広告",
    "リール", "ショート動画広告",
]
# 広告そのものを指す語
AD = [
    "広告", "ad運用", "ads", "advertis", "出稿", "リスティング",
    "運用型広告", "web広告", "ウェブ広告", "ネット広告", "デジタル広告",
]
# 運用・実務を指す語（強＝広告運用の職務そのものを示唆する語）
OPS_CORE = [
    "運用", "配信", "入稿", "プランナー", "マーケ", "宣伝",
    "プロモーション", "集客", "グロース", "広報", "販促",
]
# 弱＝単独では職種を特定できない語（「経営コンサル」「事業責任者」等を拾ってしまう）
OPS_WEAK = [
    "オペレーション", "改善", "コンサル", "ディレク",
    "担当", "スペシャリスト", "マネージャ", "責任者",
]
OPS = OPS_CORE + OPS_WEAK

# タイトルに出たら別職種として落とす語（スニペットに何が書いてあっても落とす）
TITLE_NG = [
    # エンジニア・技術職
    "プログラマ", "エンジニア", "システムディレクター", "インフラ", "sier",
    "組み込み", "制御", "検査", "実験", "評価", "開発プロジェクトマネージャー",
    "サーバー構築", "ネットワーク",
    # 制作専業
    "webデザイナー", "web デザイナー", "グラフィックデザイナー", "イラストレーター",
    "コーダー", "ライター", "カメラマン", "動画編集",
    # 人材・管理・その他
    "人材コーディネーター", "キャリアアドバイザー", "リクルーター", "採用広報",
    "事業責任者", "新規事業立上げ", "オンラインスクール", "芸能マネージャー",
    "講師", "教室長", "店長", "販売スタッフ", "受付",
    # 対象外業種
    "看護", "介護", "保育", "調理", "美容師", "理容", "整体", "歯科",
    "ドライバー", "配送", "施工", "現場監督", "警備", "清掃", "工場",
    "薬剤師", "管理栄養", "セラピスト", "測量", "溶接", "電気工事",
]
FULLTIME = ["正社員", "正職員"]
# タイトル側に出る非正社員の表記（スタンバイは雇用形態を返さないためここで拾う）
TITLE_NOT_FULLTIME = [
    "パート", "アルバイト", "バイト", "派遣", "業務委託", "契約社員",
    "インターン", "新卒", "時給", "短期", "副業のみ",
]

# 近接判定の窓幅（文字数）
PROXIMITY_WINDOW = 40


def _hit(text: str, words) -> bool:
    return any(w in text for w in words)


def _positions(text: str, words):
    pos = []
    for w in words:
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            pos.append(i)
            start = i + 1
    return pos


def _proximate(text: str, a_words, b_words, window: int = PROXIMITY_WINDOW) -> bool:
    """a語とb語が window 文字以内に共起するか。"""
    pa, pb = _positions(text, a_words), _positions(text, b_words)
    if not pa or not pb:
        return False
    return any(abs(x - y) <= window for x in pa for y in pb)


def classify(title: str, snippet: str = "", employ_type: str = "") -> dict:
    """求人1件を判定する。

    tier:
      "strong" … SNS広告の運用実務であることがタイトル or 本文で近接確認できる
      "medium" … SNS語と広告語は揃うが近接が弱い
      "weak"   … SNS語+運用語のみ（広告出稿かは不明。既定では不採用）
      "reject" … 対象外
    """
    t = _norm(title)
    s = _norm(snippet)

    if not t.strip():
        return {"tier": "reject", "reason": "空タイトル"}
    if employ_type and not _hit(_norm(employ_type), FULLTIME):
        return {"tier": "reject", "reason": f"雇用形態:{employ_type}"}
    if _hit(t, TITLE_NG):
        return {"tier": "reject", "reason": "タイトルが別職種"}
    if _hit(t, TITLE_NOT_FULLTIME):
        return {"tier": "reject", "reason": "タイトルが非正社員"}

    title_sns = _hit(t, SNS)
    title_ad = _hit(t, AD)
    title_ops = _hit(t, OPS)
    title_ops_core = _hit(t, OPS_CORE)

    # 1) タイトル内でSNS×広告が近接 → 最も確実
    if _proximate(t, SNS, AD, window=25) and title_ops:
        return {"tier": "strong", "reason": "タイトルでSNS広告×運用"}
    if title_sns and title_ad:
        return {"tier": "strong", "reason": "タイトルにSNS語+広告語"}

    # 2) タイトルに広告/運用の軸があり、本文でSNS×広告が近接
    #    タイトル側が弱い運用語だけ（例:「経営コンサル募集」）の場合は採らない。
    if (title_ad or title_ops_core) and _proximate(s, SNS, AD):
        if title_ad:
            return {"tier": "strong", "reason": "本文でSNS広告近接(タイトルに広告語)"}
        return {"tier": "medium", "reason": "本文でSNS広告近接(タイトルにマーケ語)"}

    # 3) タイトルにSNS語はあるが広告語がない
    if title_sns and title_ops:
        if _proximate(s, SNS, AD):
            return {"tier": "medium", "reason": "タイトルSNS+運用、本文に広告"}
        return {"tier": "weak", "reason": "SNS+運用のみ(広告語なし)"}

    if title_sns:
        return {"tier": "weak", "reason": "SNS語のみ"}
    return {"tier": "reject", "reason": "SNS広告の軸なし"}


ACCEPT_TIERS = {"strong", "medium"}


def accepted(title: str, snippet: str = "", employ_type: str = "",
             accept_tiers=None) -> bool:
    tiers = ACCEPT_TIERS if accept_tiers is None else accept_tiers
    return classify(title, snippet, employ_type)["tier"] in tiers
