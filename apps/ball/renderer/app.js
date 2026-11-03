// BALL 画面の動き。Electron では右ペインに本物のブラウザ（webview）を出し、
// 普通のブラウザで開いたとき（プレビュー）は見本の画面を出す。
(function () {
  const D = window.BALL_DATA;
  const IS_APP = !!(window.ball && window.ball.isElectron);
  const IC = { slack: "SL", gmail: "GM", msgr: "MS", cal: "CA", form: "FM", doc: "DC", web: "WB" };
  const FAV = { slack: "#4A154B", gmail: "#C5221F", messenger: "#0866FF", sheet: "#1E8E3E", leads: "#1E8E3E", cal: "#1A73E8", calev: "#1A73E8", gemini: "#1F7A4D", gemini2: "#1F7A4D", doc: "#1F7A4D", doc2: "#1F7A4D", plain: "#8A94A3" };
  const items = D.items;
  items.forEach((it) => { it.activeTab = 0; it.tabs.forEach((t, k) => (t.key = it.id + "-" + k)); });
  let tabSeq = 100;
  const S = { proj: "all", cur: "iwata", ctab: "chat", rmode: "browser" };

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const curItem = () => items.find((x) => x.id === S.cur);
  const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  function toast(t) { const el = $("toast"); el.textContent = t; el.hidden = false; clearTimeout(toast.h); toast.h = setTimeout(() => (el.hidden = true), 2600); }

  document.body.classList.add(IS_APP ? "electron" : "web");
  if (IS_APP && window.ball.platform === "darwin") document.body.classList.add("mac");
  if (IS_APP) $("cap").hidden = true;

  // ---------- 上のバー ----------
  function ptabs() {
    const tabs = [["all", "すべて", "var(--chrome-muted)"], ...Object.entries(D.projects).map(([k, v]) => [k, v.name, v.color])];
    $("ptabs").innerHTML = tabs.map(([k, n, c]) => `<button type="button" data-p="${k}" aria-pressed="${S.proj === k}"><span class="pd" style="background:${c}"></span>${esc(n)}</button>`).join("");
    $("ptabs").querySelectorAll("button").forEach((b) => (b.onclick = () => { S.proj = b.dataset.p; ptabs(); left(); }));
  }

  // ---------- 左：ボール一覧 ----------
  function card(i) {
    const pj = D.projects[i.proj];
    return `<button type="button" class="card${i.sec === "me" ? " me" : ""}" data-id="${i.id}" aria-current="${S.cur === i.id}">
      <span class="ic s-${i.src}">${IC[i.src] || "··"}</span>
      <span class="ct"><span class="t">${esc(i.title)}</span>
      <span class="m"><span class="proj"><span class="pd" style="background:${pj.color}"></span>${esc(pj.name)}</span>${esc(i.sub)}${i.ago ? ` · ${esc(i.ago)}` : ""}</span>
      ${i.chips.length ? `<span class="m">${i.chips.map((c) => `<span class="chip c-${c[1]}">${esc(c[0])}</span>`).join("")}</span>` : ""}</span></button>`;
  }
  function left() {
    const vis = items.filter((i) => !i.done && (S.proj === "all" || i.proj === S.proj));
    const by = (s) => vis.filter((i) => i.sec === s);
    $("meCount").textContent = `自分ボール ${items.filter((i) => i.sec === "me" && !i.done).length}`;
    $("jobs").innerHTML = D.jobs.map((j) => `<div class="job"><b class="${j[0]}">${esc(j[1])}</b><span>${esc(j[2])}</span></div>`).join("");
    const sec = (t, list) => `<div class="sec"><div class="sech"><span>${t}</span><span class="n">${list.length}</span></div>${list.map(card).join("")}</div>`;
    let html = "";
    const pins = vis.filter((i) => i.pinned);
    if (pins.length) html += `<div class="sec"><div class="sech"><span>ピン留め</span></div>${pins.map(card).join("")}</div>`;
    html += sec("自分ボール", by("me").filter((i) => !i.pinned));
    html += sec("AI 作業中", by("ai"));
    html += sec("返事待ち（相手ボール）", by("them"));
    html += `<div class="sec"><div class="sech"><span>今日の予定</span><span class="n">${D.todayCal.length}</span></div>${D.todayCal.map((e) => `<button type="button" class="ev" ${e[2] ? `data-id="${e[2]}"` : "data-none='1'"} aria-current="${S.cur === e[2]}"><time>${e[0]}</time><span>${esc(e[1])}</span></button>`).join("")}</div>`;
    const closed = D.closed.concat(items.filter((i) => i.done).map((i) => i.title + " · 完了"));
    html += `<div class="sec"><div class="sech"><span>自動で閉じた</span><span class="n">${closed.length}</span></div><div class="closed">${closed.map((c) => `<s>${esc(c)}</s>`).join("")}</div></div>`;
    $("sections").innerHTML = html;
    $("sections").querySelectorAll("[data-id]").forEach((b) => (b.onclick = () => select(b.dataset.id)));
    $("sections").querySelectorAll("[data-none]").forEach((b) => (b.onclick = () => toast("この予定はまだ予習ブリーフを作っていません（見本）")));
  }

  function select(id) {
    S.cur = id;
    const i = curItem();
    S.rmode = i.thread && i.thread.draft ? S.rmode : "browser";
    left(); center(); right();
  }

  // ---------- 中：このボールの AI ----------
  function center() {
    const i = curItem(), pj = D.projects[i.proj];
    const ball = { me: ["自分ボール", "c-me"], ai: ["AI 作業中", "c-ai"], them: ["相手ボール", "c-them"], cal: ["今日の予定", "c-them"] }[i.sec];
    $("chHead").innerHTML = `<span class="proj"><span class="pd" style="background:${pj.color}"></span>${esc(pj.name)}</span><h2>${esc(i.title)}</h2><span class="chip ${ball[1]}">${ball[0]}</span>`;
    $("ct-chat").setAttribute("aria-pressed", S.ctab === "chat");
    $("ct-memo").setAttribute("aria-pressed", S.ctab === "memo");
    if (S.ctab === "chat") {
      $("feed").innerHTML = i.feed.map(([k, t]) => (k === "prog" ? `<div class="prog"><b>Progress</b>${esc(t)}</div>` : `<div class="bub ${k}">${esc(t)}</div>`)).join("");
    } else {
      $("feed").innerHTML = `<textarea class="memo" id="memoText" aria-label="メモ" placeholder="メモはまだありません。チャットで「メモに入れといて」と言うと AI が書きます。">${esc(i.memo)}</textarea>`;
      $("memoText").oninput = (e) => (i.memo = e.target.value);
    }
    $("feed").scrollTop = $("feed").scrollHeight;
    $("state").innerHTML = i.sec === "ai" ? `<b>作業中</b> 終わったら自分ボールに戻します` : `<b>待機中</b> あなたの番`;
  }

  // ---------- 右：ブラウザ / スレッド ----------
  const webviews = {}; // key -> <webview>
  function right() {
    const i = curItem();
    const hasThread = !!i.thread;
    $("m-thread").disabled = !hasThread;
    $("m-thread").title = hasThread ? "" : "このボールにはスレッドがありません";
    if (!hasThread) S.rmode = "browser";
    $("m-browser").setAttribute("aria-pressed", S.rmode === "browser");
    $("m-thread").setAttribute("aria-pressed", S.rmode === "thread");
    const showB = S.rmode === "browser";
    $("btabs").hidden = !showB; $("newtab").hidden = !showB; $("urlbar").hidden = !showB;
    $("thr").hidden = showB;
    $("webviews").hidden = !(showB && IS_APP);
    $("sim").hidden = !(showB && !IS_APP);
    if (showB) { renderTabs(); showTab(); } else { $("thr").innerHTML = thread(i.thread); bindSend($("thr")); }
  }
  function renderTabs() {
    const i = curItem();
    $("btabs").innerHTML = i.tabs.map((t, k) => `<button type="button" class="btab" data-k="${k}" aria-pressed="${k === i.activeTab}"><i class="fav" style="background:${FAV[t.sim] || FAV.plain}"></i><span>${esc(t.title)}</span><span class="x" data-close="${k}" aria-label="タブを閉じる">×</span></button>`).join("");
    $("btabs").querySelectorAll(".btab").forEach((b) => (b.onclick = (e) => {
      const c = e.target.closest("[data-close]");
      if (c) { closeTab(+c.dataset.close); return; }
      i.activeTab = +b.dataset.k; renderTabs(); showTab();
    }));
  }
  function activeTab() { const i = curItem(); return i.tabs[i.activeTab]; }
  function showTab() {
    const t = activeTab();
    $("urlInput").value = t ? t.url : "";
    if (IS_APP) {
      Object.values(webviews).forEach((w) => w.classList.add("off"));
      if (!t) return;
      let w = webviews[t.key];
      if (!w) {
        w = document.createElement("webview");
        w.setAttribute("partition", "persist:ball");
        w.setAttribute("allowpopups", "");
        w.src = t.url;
        w.addEventListener("page-title-updated", (e) => { t.title = e.title; if (activeTab() === t) renderTabs(); });
        const nav = (e) => { t.url = e.url; if (activeTab() === t) $("urlInput").value = e.url; };
        w.addEventListener("did-navigate", nav);
        w.addEventListener("did-navigate-in-page", (e) => { if (e.isMainFrame) nav(e); });
        webviews[t.key] = w;
        $("webviews").appendChild(w);
      }
      w.classList.remove("off");
    } else {
      $("sim").innerHTML = t ? `<div class="page">${pageOf(t)}</div>` : `<div class="empty">タブがありません。＋で開けます。</div>`;
    }
  }
  function openTab(url, title) {
    const i = curItem();
    const t = { title: title || hostOf(url), url, sim: "plain", key: i.id + "-n" + tabSeq++ };
    i.tabs.push(t); i.activeTab = i.tabs.length - 1; S.rmode = "browser"; right();
  }
  function closeTab(k) {
    const i = curItem(), t = i.tabs[k];
    if (IS_APP && webviews[t.key]) { webviews[t.key].remove(); delete webviews[t.key]; }
    i.tabs.splice(k, 1);
    i.activeTab = Math.max(0, Math.min(i.activeTab, i.tabs.length - 1));
    right();
  }
  function hostOf(u) { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; } }
  function toUrl(s) {
    s = s.trim();
    if (/^https?:\/\//i.test(s)) return s;
    if (/^[\w-]+(\.[\w-]+)+(\/.*)?$/.test(s)) return "https://" + s;
    return "https://www.google.com/search?q=" + encodeURIComponent(s);
  }
  function curWebview() { const t = activeTab(); return t && webviews[t.key]; }

  function thread(t) {
    if (t.kind === "slack") {
      return `<div class="thr"><h4>${t.ws === "DM" ? "DM: " : ""}${esc(t.ch)}${t.ws === "DM" ? "" : " のスレッド"}<span>${esc(t.ws)}</span></h4>
        ${t.msgs.map((m) => `<div class="sm"><span class="av" style="background:${m[0]}">${esc(m[1][0])}</span><div><div class="n">${esc(m[1])}<time>${esc(m[2])}</time></div><div class="x">${esc(m[3])}</div>${m[4] ? `<span class="react">${esc(m[4])}</span>` : ""}</div></div>`).join("")}
        ${t.draft ? draftBox(t.draft, "slack") : ""}</div>`;
    }
    return `<div class="thr"><div class="mail"><div class="mh"><span class="s">${esc(t.subject)}</span><span>${esc(t.from)} → ${esc(t.to)} · ${esc(t.date)}</span></div><div class="mb">${esc(t.body)}</div></div>${draftBox(t.draft, "gmail")}</div>`;
  }
  function draftBox(d, kind) {
    return `<div class="draft"><div class="dh"><span>AI 下書き（送るまで送信されません）</span><span>破棄</span></div>
      <div class="tool"><span>B</span><span>I</span><span>S</span><span>link</span><span>•</span><span>1.</span></div>
      <textarea aria-label="下書き">${esc(d)}</textarea>
      <div class="df">${kind === "gmail" ? `<button type="button" class="btn" data-send>Gmail の下書きに保存</button>` : `<span>＋ ☺ @</span>`}<span class="sp"></span><span>下書きを保存しています</span><button type="button" class="btn send" data-send>送信</button></div></div>`;
  }
  function bindSend(root) { root.querySelectorAll("[data-send]").forEach((b) => (b.onclick = () => toast("見本なので送信しません。裏側をつなぐと、ここで初めて送られます"))); }

  // 見本ページ（プレビュー用。アプリでは本物のサイトが開く）
  function pageOf(t) {
    const k = t.sim;
    if (k === "sheet") {
      const rows = [["ビジョン", "トライアル", "10/27", "延長の可否", "延長 OK（11/2）→ 継続見込み", 1], ["朝日コネクト", "商談済み", "10/30", "検討状況の確認", "11/5 確認メール", 1], ["リックコミュニケーションズ", "提案中", "10/30", "コンペ結果待ち", "結果待ち（11/5 確認）", 1], ["viviON", "オンボーディング", "10/14", "日程再設定", "11月中に再設定", 1], ["gaaboo", "トライアル終了", "10/22", "振り返り", "振り返り未実施 → 今週設定", 1], ["PAC", "紹介済み", "10/28", "UUUM・alpaka 紹介", "紹介済み", 1], ["AJIMA", "振り返り済み", "10/19", "本申込", "判断待ち", 1], ["LIVEDGE", "商談予定", "11/2", "11/11 商談", "", 0]];
      return `<div class="sheettitle"><i></i>HAWKアタックリスト <span class="hint">/ 過去_提案ステータス</span></div><div class="legend"><i></i>AI の更新案（まだ書き込んでいません）</div>
        <div class="gridwrap"><table><thead><tr><th>会社</th><th>ステージ</th><th>最終接点</th><th>次のアクション</th><th>状態（11/4 更新案）</th></tr></thead><tbody>${rows.map((r) => `<tr><td><b>${r[0]}</b></td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td class="${r[5] ? "new" : ""}">${r[4]}</td></tr>`).join("")}</tbody></table></div>`;
    }
    if (k === "leads") {
      const rows = [["A", "FO 指名", "4", "送付済み"], ["A", "業態一致・中規模以上", "5", "今週アポ打診"], ["B", "業態一致・小規模", "31", "お礼＋資料"], ["C", "業態外", "25", "ナーチャリング"]];
      return `<div class="sheettitle"><i></i>共催ウェビナー_参加者（10/27）</div><div class="gridwrap"><table><thead><tr><th>区分</th><th>条件</th><th>件数</th><th>対応</th></tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c, j) => `<td class="${j === 3 ? "new" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    if (k === "messenger") {
      return `<div class="ms"><div class="ml">
        <div class="mc on"><span class="av" style="background:#E67E22">K</span><div style="min-width:0"><b>K さん（例）</b><div class="p">来週どこかでお茶しませんか？</div></div><i class="u"></i></div>
        <div class="mc"><span class="av" style="background:#16A085">T</span><div style="min-width:0"><b>T さん（例）</b><div class="p">了解です！ありがとうございます</div></div><span></span></div>
        <div class="mc"><span class="av" style="background:#7F8C8D">M</span><div style="min-width:0"><b>M さん（例）</b><div class="p">資料見ました</div></div><span></span></div>
        </div><div class="mv"><div class="mvh">K さん（例）</div><div class="mvb">
        <div class="mm">片山さん、来週どこかでお茶しませんか？紹介したい会社があって</div>
        <div class="mm">SNS 広告まわりで困ってるところです</div>
        <div class="mm dr">ありがとうございます！ぜひ。\n11/10（月）16時〜、11/12（水）17時〜、11/13（木）11時〜あたりどうでしょう？\n（AI 下書き · 未送信）</div>
        </div><div class="mvi">Aa　メッセージを入力</div></div></div>`;
    }
    if (k === "gemini" || k === "gemini2") {
      const a = k === "gemini";
      return `<div class="doc"><h5>${a ? "朝日コネクト・HAWK" : "シーラベル様 × HAWK"} - Gemini によるメモ</h5><span class="hint">${a ? "2026/10/30 14:00" : "2026/11/02 12:00"} · 自動生成</span>
        <h6>概要</h6><p>${a ? "HAWK の機能と2週間トライアルの流れを説明。秦様から運用体制についての質問あり。" : "2027年1月の共催オンライン選定会について、登壇の方向性と進め方を相談。"}</p>
        <h6>次のステップ</h6><ul><li>[片山] ${a ? "検討状況を11/5に確認する" : "登壇者と概要を11月中に連絡する"}</li><li>[${a ? "秦" : "佐藤"}] ${a ? "社内で体制を確認する" : "当日の進行案を共有する"}</li></ul></div>`;
    }
    if (k === "doc2") return `<div class="doc"><h5>株式会社静鉄アド・パートナーズ 会社概要</h5><span class="hint">hawk-inbound-lead が作成中</span><h6>基本情報</h6><p>所在地・事業内容・主要取引先を整理中</p><h6>HAWK との接点</h6><p>紹介パートナー申込（11/3）</p></div>`;
    if (k === "calev") return `<div class="calv"><div class="tt"><i></i>[オンライン社外]【仮】リアルテックジャパン様（楳田様）／HAWKご説明</div><dl class="kv"><dt>日時</dt><dd>11/4（火）13:00〜14:00</dd><dt>経緯</dt><dd>10/27 共催ウェビナー FO 指名</dd><dt>状態</dt><dd><span class="chip c-warn">先方未確定</span></dd><dt>資料</dt><dd>HAWK_共催ウェビナー_20261027.pdf</dd></dl></div>`;
    if (k === "cal") return `<div class="calv"><div class="tt"><i></i>今週の【仮】枠</div><dl class="kv"><dt>11/4 11:00</dt><dd>小瀬さん紹介4社 HAWKご説明（候補3）</dd><dt>11/4 14:00</dt><dd>CARTA KNOT 鈴木様（候補3）</dd><dt>11/6 13:30</dt><dd>小瀬さん紹介4社（候補4）</dd></dl></div>`;
    return `<div class="ph"><b>${esc(hostOf(t.url))}</b><span>デスクトップアプリでは、ここにログインしたままの本物の ${esc(hostOf(t.url))} が開きます。</span><span class="hint">${esc(t.url)}</span></div>`;
  }

  // ---------- 全体図 ----------
  function overview(show) { $("ov").hidden = !show; if (show) $("ovStart").focus(); else store.set("ball.seenOverview", "1"); }

  // ---------- イベント ----------
  $("ct-chat").onclick = () => { S.ctab = "chat"; center(); };
  $("ct-memo").onclick = () => { S.ctab = "memo"; center(); };
  $("ct-done").onclick = () => { const i = curItem(); i.done = true; toast("完了にしました。本番ではカレンダーの予定に ✅ を付けます"); const next = items.find((x) => !x.done && x.sec === "me"); if (next) select(next.id); else left(); };
  $("m-browser").onclick = () => { S.rmode = "browser"; right(); };
  $("m-thread").onclick = () => { S.rmode = "thread"; right(); };
  $("newtab").onclick = () => openTab("https://www.google.com/", "新しいタブ");
  $("urlbar").onsubmit = (e) => {
    e.preventDefault();
    const url = toUrl($("urlInput").value);
    const t = activeTab();
    if (!t) { openTab(url); return; }
    t.url = url;
    if (IS_APP && webviews[t.key]) webviews[t.key].loadURL(url); else { t.title = hostOf(url); t.sim = "plain"; renderTabs(); showTab(); }
  };
  $("navBack").onclick = () => { const w = curWebview(); if (w && w.canGoBack()) w.goBack(); };
  $("navFwd").onclick = () => { const w = curWebview(); if (w && w.canGoForward()) w.goForward(); };
  $("navReload").onclick = () => { const w = curWebview(); if (w) w.reload(); else toast("見本ページです"); };
  $("navOut").onclick = () => { const t = activeTab(); if (!t) return; if (IS_APP) window.ball.openExternal(t.url); else window.open(t.url, "_blank"); };
  $("comp").onsubmit = (e) => {
    e.preventDefault();
    const t = $("compText").value.trim(); if (!t) return;
    const i = curItem();
    i.feed.push(["me", t], ["ai", "了解です。（見本なので、ここでは返事の例だけ出しています。裏側をつなぐと、このボールの中身を知った Claude が実際に作業します）"]);
    $("compText").value = ""; S.ctab = "chat"; center();
  };
  $("compText").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); $("comp").requestSubmit(); } });
  $("addForm").onsubmit = (e) => {
    e.preventDefault();
    const t = $("addInput").value.trim(); if (!t) return;
    const it = { id: "n" + Date.now(), sec: "me", proj: "in", src: "doc", title: t, sub: "手入力", chips: [["新規", "me"]], ago: "今", feed: [["ai", "ボールにしました。関係するスレッドや予定があれば紐づけます。"]], memo: "", thread: null, tabs: [{ title: "新しいタブ", url: "https://www.google.com/", sim: "plain" }], activeTab: 0 };
    it.tabs[0].key = it.id + "-0";
    items.unshift(it); $("addInput").value = ""; select(it.id);
  };
  $("bantoForm").onsubmit = (e) => { e.preventDefault(); const t = $("bantoInput").value.trim(); if (!t) return; D.jobs.unshift(["run", "進行中", t + " → 振り先を判断中"]); $("bantoInput").value = ""; left(); };
  $("ovBtn").onclick = () => overview(true);
  $("ovStart").onclick = () => overview(false);
  $("ov").onclick = (e) => { if (e.target.id === "ov") overview(false); };
  $("leftToggle").onclick = () => $("cols").classList.toggle("noleft");

  // 中と右の境目をドラッグで動かす
  (function () {
    const sp = $("split"); let x0, w0;
    const saved = parseInt(store.get("ball.centerW") || "", 10);
    if (saved) document.documentElement.style.setProperty("--center-w", saved + "px");
    sp.addEventListener("pointerdown", (e) => { x0 = e.clientX; w0 = $("center").getBoundingClientRect().width; sp.setPointerCapture(e.pointerId); sp.classList.add("drag"); document.body.style.userSelect = "none"; $("webviews").style.pointerEvents = "none"; });
    sp.addEventListener("pointermove", (e) => { if (x0 == null) return; const w = Math.max(340, Math.min(760, w0 + e.clientX - x0)); document.documentElement.style.setProperty("--center-w", w + "px"); });
    sp.addEventListener("pointerup", () => { if (x0 == null) return; x0 = null; sp.classList.remove("drag"); document.body.style.userSelect = ""; $("webviews").style.pointerEvents = ""; store.set("ball.centerW", parseInt(getComputedStyle(document.documentElement).getPropertyValue("--center-w"), 10)); });
  })();

  // キーボード
  document.addEventListener("keydown", (e) => {
    const m = e.metaKey || e.ctrlKey;
    if (e.key === "Escape" && !$("ov").hidden) overview(false);
    if (!m) return;
    if (e.key === "l") { e.preventDefault(); S.rmode = "browser"; right(); $("urlInput").select(); }
    else if (e.key === "t") { e.preventDefault(); $("newtab").click(); }
    else if (e.key === "w" && S.rmode === "browser") { e.preventDefault(); closeTab(curItem().activeTab); }
    else if (e.key === "1") { e.preventDefault(); $("leftToggle").click(); }
    else if (e.key === "k") { e.preventDefault(); $("addInput").focus(); }
  });
  // webview からのポップアップは新しいタブで開く
  if (IS_APP) window.ball.onOpenTab((url) => openTab(url));

  ptabs(); select("iwata");
  if (!store.get("ball.seenOverview")) overview(true);
})();
