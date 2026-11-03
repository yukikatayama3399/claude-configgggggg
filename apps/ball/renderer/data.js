// 仮データ（裏側をつなぐまでの見本）。中身は 2026-11-03 時点の実データを要約した例で、細部は事実と違うことがある。
// 本番ではここが Slack / Gmail / Messenger / カレンダーの取り込み結果に置き換わる。
window.BALL_DATA = (function () {
  const SHEET = "https://docs.google.com/spreadsheets/d/1iyhwVNhN_HJNdIBL_pREhrhBdQu2it5ktFOYq-DDm_w/edit";
  const SLACK = "https://app.slack.com/client";
  const GMAIL = "https://mail.google.com/mail/u/0/#inbox";
  const CAL = "https://calendar.google.com/calendar/r/week";
  const t = (title, url, sim) => ({ title, url, sim });

  const projects = {
    hawk: { name: "HAWK", color: "var(--p-hawk)" },
    uuum: { name: "UUUM・ビルコム", color: "var(--p-uuum)" },
    alpaka: { name: "alpaka", color: "var(--p-alpaka)" },
    in: { name: "社内", color: "var(--p-in)" },
    me: { name: "個人", color: "var(--p-me)" },
    none: { name: "未分類", color: "var(--muted)" },
  };

  const items = [
    {
      id: "iwata", sec: "me", proj: "hawk", src: "slack", ago: "2日前",
      title: "提案ステータス記入・過去案件の状態確認（岩田さん）", sub: "#hawk-sales-private",
      chips: [["定例 11/5 15:00 まで", "warn"]],
      feed: [
        ["prog", "3 tools · シート読込: 過去_提案ステータス / Gmail 検索 / Gemini メモ 6件"],
        ["ai", "岩田さんの依頼は2つです。定例前の提案ステータス記入と、過去の全案件の状態確認。\n\n10月に動いた12社のうち、シートが古いままの7社を、送ったメールと Gemini メモから埋める案を作りました（まだ書き込んでいません）。\n\n・ビジョン様：トライアル延長 → 11/2 OK\n・朝日コネクト様：10/30 商談。11/5 に確認メール\n・リックコミュニケーションズ様：コンペ結果待ち\n・viviON様：オンボーディング延期。再設定が必要\n・gaaboo様：トライアル終了。振り返り未実施\n\n右のブラウザにシートを開いています。これで記入して、スレッドに返信の下書きを入れますか。"],
        ["me", "それで。viviONは11月中に再設定って書いといて"],
        ["prog", "1 tool · シート記入の準備（7セル）"],
        ["ai", "viviON様は「11月中に再設定」にしました。スレッドに返信の下書きを入れています。右上の「スレッド」から確認して送れます。"],
      ],
      memo: "定例で話すこと\n・viviON 再設定日を決める\n・gaaboo 振り返りを今週中に\n・ビジョン 継続の条件",
      thread: { kind: "slack", ch: "#hawk-sales-private", ws: "FreakOut",
        msgs: [["#8E44AD", "岩田 美和", "11/2 10:12", "@片山 定例前に、提案ステータスへの記入と、過去全案件のコンディション確認をお願いします！", ""]],
        draft: "岩田さん\n遅くなりました、提案ステータス更新しました。\n・10月に動いた12社のうち7社を更新\n・viviON様は11月中に再設定予定\n・gaaboo様は振り返り未実施のため今週中に設定します\n定例でご確認お願いします。" },
      tabs: [t("HAWKアタックリスト", SHEET, "sheet"), t("Slack", SLACK, "slack")],
    },
    {
      id: "leads", sec: "me", proj: "hawk", src: "slack", ago: "6日前", pinned: true,
      title: "ウェビナー後リード65件の振り分け（中西さん）", sub: "#hawk-marketing",
      chips: [["cc 4人", "them"]],
      feed: [
        ["prog", "2 tools · シート読込: 共催ウェビナー_参加者 / HAWK企業マスタ"],
        ["ai", "65件を、HAWK企業マスタの業態と規模で3つに分けました。\n\nA：今週アポ打診　9件\nB：お礼＋資料　31件\nC：ナーチャリング　25件\n\nA の9件には個別のお礼メール下書きを作れます。作りますか。"],
      ],
      memo: "A の9件は FO 指名の4社を含む。指名分は送付済み。",
      thread: { kind: "slack", ch: "#hawk-marketing", ws: "FreakOut",
        msgs: [["#2E86C1", "中西 秀之", "10/28 18:40", "@片山 @座安 @小瀬 @木伏\nウェビナー後のリード65件、振り分けて休み明けに対応お願いします 🙏", "👀 3"]],
        draft: "中西さん\n振り分けました。\nA 9件（片山で打診）/ B 31件（お礼＋資料）/ C 25件（ナーチャリング）\nシートの担当列を更新しています。" },
      tabs: [t("共催ウェビナー_参加者", "https://docs.google.com/spreadsheets/", "leads"), t("Slack", SLACK, "slack")],
    },
    {
      id: "msgr", sec: "me", proj: "hawk", src: "msgr", ago: "2日前",
      title: "メッセンジャー：紹介したい会社の件（例）", sub: "Facebook メッセンジャー",
      chips: [["2日 未返信", "warn"]],
      feed: [
        ["prog", "1 tool · Messenger の未読を確認（3件）"],
        ["ai", "メッセンジャーの未読は3件で、返事が必要なのは1件です。\n来週お茶しながら紹介したい会社がある、という連絡なので、日程の候補を3つ入れた返信を下書きしました。\n\n候補はカレンダーの空きから取っています。\n・11/10（月）16:00〜\n・11/12（水）17:00〜\n・11/13（木）11:00〜\n\nメッセンジャーは右で開いているので、そのまま送れます。"],
      ],
      memo: "", thread: null,
      tabs: [t("Messenger", "https://www.facebook.com/messages/t/", "messenger")],
    },
    {
      id: "haru", sec: "me", proj: "uuum", src: "slack", ago: "10/16",
      title: "春さん：rawデータ活用と媒体の縛りへの回答", sub: "DM · 相手の発言で止まっている",
      chips: [["18日", "warn"]],
      feed: [["ai", "10/16 の春さんの質問に返していません。媒体ごとの規約を確認してから答える必要があります。\n\nまず「確認して金曜までに返します」と一次返信だけ入れますか。調べる方は、このボールのまま私が進めます。"]],
      memo: "確認すること\n・Meta / TikTok のrawデータ持ち出し条件\n・UUUM 側で使いたい粒度",
      thread: { kind: "slack", ch: "春 大介", ws: "DM",
        msgs: [["#D6336C", "春 大介", "10/16 19:22", "片山さん、rawデータって二次活用できます？媒体側の縛りがあるなら先に知っておきたくて", ""]],
        draft: "春さん\n返信が遅くなってすみません！\n媒体ごとに条件が違うので、確認して今週金曜までにまとめて返します。" },
      tabs: [t("Slack", SLACK, "slack"), t("Meta 広告 利用規約", "https://www.facebook.com/legal/terms", "doc")],
    },
    {
      id: "clabel", sec: "me", proj: "hawk", src: "gmail", ago: "昨日",
      title: "シーラベル様 打合せのお礼と登壇の段取り", sub: "11/2 12:00 の Gemini メモから",
      chips: [["お礼メール", "me"]],
      feed: [
        ["prog", "2 tools · Gemini メモ読込 / Gmail スレッド読込"],
        ["ai", "11/2 の打合せメモから、次の2点を拾いました。\n・2027年1月の共催オンライン選定会に、HAWK として登壇する方向\n・登壇者と概要を11月中に連絡する\n\nお礼メールを下書きしました。概要の叩き台はメモに入れています。"],
      ],
      memo: "登壇概要（叩き台）\n・テーマ：SNS広告の運用を AI エージェントに任せる\n・事例：共催ウェビナーで出した3社\n・時間：20分想定",
      thread: { kind: "gmail", subject: "【お伺い】広告サービス・営業×AIエージェント選定会へのご登壇について（HAWKにつきまして）",
        messages: [{ id: "mock-c1", from: "佐藤 亜弥 <aya.sato@clabel.co.jp>", to: "yuki.katayama@fout.jp", cc: "松山 為長 <matsuyama@clabel.co.jp>", date: "Wed, 28 Oct 2026 10:29 +0900",
          subject: "【お伺い】広告サービス・営業×AIエージェント選定会へのご登壇について（HAWKにつきまして）",
          body: "株式会社フリークアウト 片山 優希 様\n\nお世話になっております。株式会社シーラベルの佐藤です。\n来年2027年1月に「共催型オンライン選定会」の開催を予定しており、貴社にも是非ご参画いただきたくご連絡いたしました。\n\n企画書を添付いたします。一度オンラインでお話しさせていただけますと幸いです。",
          attachments: [{ filename: "広告サービス選定会_企画書.pdf", size: "2.1 MB" }] }],
        draft: "佐藤様、松山様\n\n本日はお時間をいただきありがとうございました。フリークアウトの片山です。\n1月の選定会、ぜひ登壇させていただければと思います。\n登壇者と概要は、11月中にあらためてご連絡いたします。\n\n引き続きよろしくお願いいたします。" },
      tabs: [t("Gmail", GMAIL, "gmail"), t("Gemini によるメモ", "https://drive.google.com/drive/recent", "gemini2")],
    },
    {
      id: "timerex", sec: "me", proj: "hawk", src: "slack", ago: "5日前",
      title: "TimeRex 登録とカレンダー修正（中西さん）", sub: "#hawk-marketing",
      chips: [["来週月曜まで", "me"]],
      feed: [["ai", "ウェビナーのフォロー用に TimeRex の予約ページを作り、カレンダーの【仮】枠を整理する依頼です。\n【仮】のまま残っている枠が今週3件あります。確定していない枠を外して、TimeRex の空きに戻しますか。"]],
      memo: "",
      thread: { kind: "slack", ch: "#hawk-marketing", ws: "FreakOut",
        msgs: [["#2E86C1", "中西 秀之", "10/30 17:05", "@片山 TimeRex 登録とカレンダー修正お願いします。来週月曜まででOKです", ""]],
        draft: "中西さん\nTimeRex 登録しました。カレンダーの仮枠も整理済みです。" },
      tabs: [t("TimeRex", "https://timerex.net/", "plain"), t("Google カレンダー", CAL, "cal")],
    },
    {
      id: "mercari", sec: "me", proj: "me", src: "web", ago: "3時間前",
      title: "メルカリ：取引メッセージへの返信（例）", sub: "通知メールから検出",
      chips: [["発送期限 明日", "me"]],
      feed: [["ai", "メルカリの取引メッセージに「発送してください」と入りました。発送期限は明日です。\n右のブラウザで取引画面を開いています。発送したら、ここで「完了」と言ってもらえればボールを閉じます。"]],
      memo: "", thread: null,
      tabs: [t("メルカリ", "https://jp.mercari.com/mypage/listings", "plain")],
    },
    {
      id: "shizu", sec: "ai", proj: "hawk", src: "form", ago: "今",
      title: "静鉄アド・パートナーズ 紹介申込の初動", sub: "#hawk_紹介受付 · 担当: 片山",
      chips: [["3/4 完了", "ai"]],
      feed: [
        ["prog", "hawk-inbound-lead · 4工程中3工程"],
        ["ai", "会社概要の Doc 作成、アタックリストへの行追加、カレンダーの仮押さえまで終わりました。いま初回メールを下書きしています。終わったら自分ボールに戻します。"],
      ],
      memo: "",
      thread: { kind: "slack", ch: "#hawk_紹介受付", ws: "FreakOut",
        msgs: [["#27AE60", "申込フォーム（bot）", "11/3 10:41", "HAWK紹介申込：株式会社静鉄アド・パートナーズ\n担当: @片山", ""]], draft: null },
      tabs: [t("会社概要 Doc", "https://docs.google.com/document/", "doc2")],
    },
    {
      id: "drafts", sec: "ai", proj: "in", src: "gmail", ago: "今",
      title: "Gmail 下書き140件の棚卸し", sub: "テンプレ営業文 52件を含む",
      chips: [["仕分け中", "ai"]],
      feed: [["ai", "下書きを「送る / 捨てる / テンプレにする」の3つに仕分けています。30日以上前のテンプレ営業文52件は「捨てる」を提案する予定です。仕分けが終わったら、まとめて確認してもらいます。"]],
      memo: "", thread: null,
      tabs: [t("Gmail - 下書き", "https://mail.google.com/mail/u/0/#drafts", "gmail")],
    },
    {
      id: "asahi", sec: "them", proj: "hawk", src: "gmail", ago: "",
      title: "朝日コネクト 秦様：検討状況", sub: "10/30 商談 · お礼送付済み",
      chips: [["待ち 4日", "them"]],
      feed: [["ai", "10/30 にお礼を送って返事を待っています。11/5 17:30 に確認メールの下書きを作って、自分ボールに戻します。"]],
      memo: "", thread: null,
      tabs: [t("Gemini によるメモ", "https://drive.google.com/drive/recent", "gemini"), t("Gmail", GMAIL, "gmail")],
    },
    {
      id: "rick", sec: "them", proj: "uuum", src: "gmail", ago: "",
      title: "リックコミュニケーションズ 樋口様：コンペ結果", sub: "インフルエンサーコンペ",
      chips: [["11/5 確認", "them"]],
      feed: [["ai", "コンペの結果待ちです。11/5 に結果を確認するリマインドを入れています。"]],
      memo: "", thread: null,
      tabs: [t("Gmail", GMAIL, "gmail")],
    },
    {
      id: "realtech", sec: "cal", proj: "hawk", src: "cal", time: "13:00",
      title: "【仮】リアルテックジャパン様 HAWKご説明", sub: "10/27 ウェビナー FO 指名", chips: [],
      feed: [
        ["prog", "hawk-shodan-prep · 予習ブリーフ"],
        ["ai", "13:00 の予習です。\n\n経緯：10/27 の共催ウェビナーで FO を指名。楳田様。\n状態：まだ【仮】のままで、先方からの確定連絡は来ていません。\n当日のゴール：トライアルのつなぎ込み日程を決める\n想定される質問：Meta 以外の媒体、料金の決まり方\n\n確定していないので、10時にリマインドを送りますか。下書きはできています。"],
      ],
      memo: "", thread: null,
      tabs: [t("Google カレンダー", CAL, "calev")],
    },
  ];

  const todayCal = [
    ["11:00", "【仮】小瀬さん紹介4社 HAWKご説明", null],
    ["13:00", "【仮】リアルテックジャパン様", "realtech"],
    ["14:00", "【仮】CARTA KNOT 鈴木様", null],
    ["17:00", "カクヤス杉田、平井連絡", null],
  ];
  const jobs = [
    ["run", "進行中", "リード65件の振り分け案 → 中西さん返信の下書き"],
    ["ok", "完了", "フォームの自動返信12件を既読に（人からの返信 0件）"],
    ["ok", "完了", "2段階認証の告知は送信済みと確認 → ボールを閉じました"],
  ];
  const closed = ["2段階認証の告知（杉浦さん）· 送信済み", "PAC×UUUM 明日のリマインド · 予定が終了"];

  return { projects, items, todayCal, jobs, closed };
})();
