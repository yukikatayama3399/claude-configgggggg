"""スイープ全体の設定。

品質ゲートは「SNS広告運用の求人が実在するか」の1点のみ。
優先度(S/A/B)は判定に使わない。クエリはSNS広告運用の周辺から広げない。
"""

SPREADSHEET_ID = "1zOefPeDmOtPLRfNhs-8EZQWzKhYdu0wUxI0nvOMjqc0"
TAB_ALL = "全リスト"
TAB_FORM = "フォーム送信用"
TAB_LEDGER = "ledger"
TAB_SENT_DOMAIN = "_送信済ドメイン"

ACCOUNT = "yuki.katayama@fout.jp"

# --- 送信済み/除外の突合先（HIROGARU_フォーム入力シート_0817）-----------------
# 既に接触済み・除外済みのドメインが約12,300件ある。ここと突合しないと
# 「純増」に見えて実は既接触、という行が混ざる。
EXCLUDE_SPREADSHEET_ID = "1gYL-_-rM52JrWEtsL-Cx-Wv4BPjS49qg9g_n2xq8WqQ"
EXCLUDE_TAB_DOMAIN = "_除外ドメイン"
EXCLUDE_TAB_COMPANY = "除外リスト"

# --- 作業者が入力するタブ ---------------------------------------------------
# H列「入力状況」/ I列「担当者」を人が手で埋める。ここは実データなので
# 数式で生成してはいけない（数式にすると手入力できなくなる）。
# jobsweep は行の追加だけ行い、H列・I列には一切触れない。
WORK_SPREADSHEET_ID = EXCLUDE_SPREADSHEET_ID
WORK_TAB = "注力_最新SNS広告求人(自動追加)"

# 接触済み・接触禁止の企業名がある場所（タブ名, 会社名の列インデックス）
# 元は _取込元_SNS広告求人 の FILTER が COUNTIF で見ていた5つと同じ。
CONTACTED_SOURCES = [
    ("除外リスト", 1),                    # B列 企業名
    ("配信結果csv", 0),                   # A列 company_name
    ("全リスト", 0),                      # A列 企業名
    ("0814_注力_SNS系(624)", 0),          # A列 会社名
    ("0817_注力_WEB広告(1015)", 0),       # A列 会社名
]

# --- クエリ: SNS広告運用の中核のみ。ここを広げない ---------------------------
# 「Webマーケティング」「デジタルマーケティング」等の汎用語は意図的に除外。
CORE_QUERIES = [
    "SNS広告運用",
    "SNS広告",
    "Meta広告運用",
    "Instagram広告",
    "TikTok広告",
    "LINE広告運用",
    "Facebook広告運用",
    "X広告運用",
    "YouTube広告運用",
    "ソーシャル広告運用",
    "SNS運用 広告",
    "運用型広告 SNS",
]

# --- 地域: 東京・大阪は既に飽和しているため最後に回す -------------------------
PREFECTURES_PRIORITY = [
    "北海道", "宮城県", "福岡県", "愛知県", "広島県", "京都府", "兵庫県",
    "静岡県", "神奈川県", "埼玉県", "千葉県", "新潟県", "長野県", "岡山県", "熊本県",
    "沖縄県", "石川県", "群馬県", "栃木県", "茨城県", "三重県", "岐阜県", "滋賀県",
    "奈良県", "山口県", "愛媛県", "香川県", "鹿児島県", "長崎県", "大分県", "宮崎県",
    "佐賀県", "富山県", "福井県", "山梨県", "岩手県", "福島県", "青森県", "秋田県",
    "山形県", "和歌山県", "鳥取県", "島根県", "徳島県", "高知県",
]
# 最後に回す2つ
PREFECTURES_LAST = ["大阪府", "東京都"]
PREFECTURES = PREFECTURES_PRIORITY + PREFECTURES_LAST

# --- 収集の深さ ---------------------------------------------------------------
MAX_PAGES_REGION = 4      # 地域スライス1クエリあたりの最大ページ
MAX_PAGES_FRESH = 6       # 新着(24h)パスの最大ページ
REQUEST_INTERVAL_SEC = 1.5  # レート制限（媒体に負荷をかけない）
REQUEST_TIMEOUT_SEC = 30
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
