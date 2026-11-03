// BALL 画面の動き。Electron では右ペインに本物のブラウザ（webview）を出し、
// 普通のブラウザで開いたとき（プレビュー）は見本の画面を出す。
(function () {
  const D = window.BALL_DATA;
  const IS_APP = !!(window.ball && window.ball.isElectron);
  const LOGO = window.BALL_LOGOS || {};
  // ボールの出どころ → ロゴ（無いものは文字のアイコン）
  const SRC_LOGO = { slack: "slack", gmail: "gmail", msgr: "msgr", cal: "cal", form: "slack", doc: "doc" };
  const SRC_TEXT = { web: ["メ", "#E8340C"] };
  // ブラウザのタブ → ロゴ
  const SIM_LOGO = { slack: "slack", gmail: "gmail", messenger: "msgr", sheet: "sheet", leads: "sheet", cal: "cal", calev: "cal", gemini: "doc", gemini2: "doc", doc: "doc", doc2: "doc" };
  function srcIcon(src) {
    if (SRC_LOGO[src] && LOGO[SRC_LOGO[src]]) return `<span class="ic logo">${LOGO[SRC_LOGO[src]]}</span>`;
    const t = SRC_TEXT[src] || ["・", "#8A94A3"];
    return `<span class="ic" style="background:${t[1]}">${t[0]}</span>`;
  }
  function tabIcon(t) {
    let k = SIM_LOGO[t.sim];
    if (!k) {
      const h = hostOf(t.url);
      if (/mail\.google/.test(h)) k = "gmail";
      else if (/slack\.com/.test(h)) k = "slack";
      else if (/messenger\.com/.test(h)) k = "msgr";
      else if (/calendar\.google/.test(h)) k = "cal";
      else if (/docs\.google/.test(h)) k = /spreadsheets/.test(t.url) ? "sheet" : "doc";
      else if (/drive\.google/.test(h)) k = "drive";
      else if (/google\./.test(h)) k = "google";
    }
    if (k && LOGO[k]) return `<i class="fav logo">${LOGO[k]}</i>`;
    if (/mercari/.test(t.url)) return `<i class="fav" style="background:#E8340C"></i>`;
    return `<i class="fav"></i>`;
  }
  // アプリ版では見本のデータを出さない（本物と混ざって紛らわしいので）。最初は「はじめに」だけ置いて、読み込んだ本物を並べる
  if (IS_APP) {
    D.items.splice(0, D.items.length, {
      id: "home", hidden: true, sec: "me", proj: "none", src: "doc", title: "BALL", sub: "", chips: [], ago: "", memo: "", thread: null,
      feed: [["ai", "左の一覧からボールを選ぶと、ここでそのボールの相談ができます。\nGmail・Slack・Messenger・カレンダーは裏で読み込んでいます（状態は下の帯）。"]],
      tabs: [{ title: "Google", url: "https://www.google.com/", sim: "plain" }],
    });
    D.jobs = []; D.closed = []; D.todayCal = [];
  }
  const items = D.items;
  items.forEach((it) => { it.activeTab = 0; it.tabs.forEach((t, k) => (t.key = it.id + "-" + k)); });
  let tabSeq = 100;
  const S = { proj: "all", cur: IS_APP ? "home" : "iwata", ctab: "chat", rmode: "browser" };

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const curItem = () => items.find((x) => x.id === S.cur);
  const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  function toast(t) { const el = $("toast"); el.textContent = t; el.hidden = false; clearTimeout(toast.h); toast.h = setTimeout(() => (el.hidden = true), 2600); }

  document.body.classList.add(IS_APP ? "electron" : "web");
  if (IS_APP && window.ball.platform === "darwin") document.body.classList.add("mac");
  if (IS_APP) {
    $("cap").hidden = true;
    // 見本の表示（日付・稼働・同期・使用量・番頭）を本物に合わせる
    const d = new Date();
    $("today").textContent = `${d.getMonth() + 1}/${d.getDate()}（${"日月火水木金土"[d.getDay()]}）`;
    $("dateEn").textContent = d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }).toUpperCase();
    $("sync").hidden = true; $("usage").hidden = true; $("banto").hidden = true;
  }

  // ファイルを落としたときに、画面がそのファイルに移ってしまわないようにする（受け付けるのは下書き欄だけ）
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", (e) => e.preventDefault());

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
      ${srcIcon(i.src)}
      <span class="ct"><span class="t">${esc(i.title)}</span>
      <span class="m"><span class="proj"><span class="pd" style="background:${pj.color}"></span>${esc(pj.name)}</span>${esc(i.sub)}${i.ago ? ` · ${esc(i.ago)}` : ""}</span>
      ${i.chips.length ? `<span class="m">${i.chips.map((c) => `<span class="chip c-${c[1]}">${esc(c[0])}</span>`).join("")}</span>` : ""}</span></button>`;
  }
  // ---------- 並び順 ----------
  // メール・Slack・Messenger は受け取った時刻の新しい順（新着が上）。カレンダーの作業は、これから来る時刻の早い順
  function dateTime(str) { const d = new Date(String(str || "").replace(/^(\d{4}-\d{2}-\d{2}) /, "$1T")); return isNaN(d) ? 0 : d.getTime(); }
  function relTime(t) {
    t = String(t || "").trim();
    const m = t.match(/^(\d+)\s*(分|時間|日|週間|か月|ヶ月|年|m|h|d|w|y)/);
    if (m) { const n = +m[1], u = { "分": 60e3, m: 60e3, "時間": 3600e3, h: 3600e3, "日": 86400e3, d: 86400e3, "週間": 7 * 86400e3, w: 7 * 86400e3, "か月": 30 * 86400e3, "ヶ月": 30 * 86400e3, "年": 365 * 86400e3, y: 365 * 86400e3 }[m[2]]; return Date.now() - n * u; }
    const hm = t.match(/^(\d{1,2}):(\d{2})$/);
    if (hm) { const d = new Date(); d.setHours(+hm[1], +hm[2], 0, 0); return d.getTime(); }
    if (/たった今|now/i.test(t)) return Date.now();
    return 0;
  }
  const byNewest = (a, b) => (b.at || 0) - (a.at || 0);
  const byStart = (a, b) => (a.calStart < b.calStart ? -1 : a.calStart > b.calStart ? 1 : 0);
  function left() {
    const vis = items.filter((i) => !i.done && !i.hidden && (S.proj === "all" || i.proj === S.proj));
    const by = (s) => vis.filter((i) => i.sec === s);
    $("meCount").textContent = `自分ボール ${items.filter((i) => i.sec === "me" && !i.done && !i.hidden).length}`;
    $("jobs").innerHTML = D.jobs.map((j) => `<div class="job"><b class="${j[0]}">${esc(j[1])}</b><span>${esc(j[2])}</span></div>`).join("");
    const sec = (t, list) => `<div class="sec"><div class="sech"><span>${t}</span><span class="n">${list.length}</span></div>${list.map(card).join("")}</div>`;
    let html = "";
    const pins = vis.filter((i) => i.pinned);
    if (pins.length) html += `<div class="sec"><div class="sech"><span>ピン留め</span></div>${pins.map(card).join("")}</div>`;
    // カレンダーの作業は、時刻の早い順（時系列で片付けるので）。他のボールはこれまでどおりの順で、その下に並べる
    const mine = by("me").filter((i) => !i.pinned);
    const calMine = mine.filter((i) => i.calStart).sort(byStart);
    html += sec("自分ボール", mine.filter((i) => !i.calStart).sort(byNewest).concat(calMine));
    html += sec("AI 作業中", by("ai").sort(byNewest));
    if (by("notes").length) html += sec("会議メモ（議事録）", by("notes").sort(byNewest));
    html += sec("返事待ち（相手ボール）", by("them").sort(byNewest));
    const fyi = by("fyi").sort(byNewest);
    if (fyi.length) html += `<details class="sec fyi"${S.fyiOpen ? " open" : ""}><summary class="sech"><span>返事不要（AI 判断）</span><span class="n">${fyi.length}</span></summary>${fyi.map(card).join("")}</details>`;
    const liveCal = items.filter((x) => x.live && x.src === "cal" && x.sec === "cal" && !x.hidden && (S.proj === "all" || x.proj === S.proj));
    if (calLoaded) {
      const byDay = {};
      liveCal.forEach((x) => { (byDay[x.calDay] = byDay[x.calDay] || []).push(x); });
      Object.keys(byDay).sort().forEach((day) => {
        html += `<div class="sec"><div class="sech"><span>${day === todayStr() ? "今日の予定" : dayLabel(day) + "の予定"}</span><span class="n">${byDay[day].length}</span></div>${byDay[day].sort(byStart).map((x) => `<button type="button" class="ev" data-id="${x.id}" aria-current="${S.cur === x.id}"><time>${esc(x.calTime)}</time><span>${esc(x.title)}</span></button>`).join("")}</div>`;
      });
    } else {
      html += `<div class="sec"><div class="sech"><span>今日の予定</span><span class="n">${D.todayCal.length}</span></div>${D.todayCal.map((e) => `<button type="button" class="ev" ${e[2] ? `data-id="${e[2]}"` : "data-none='1'"} aria-current="${S.cur === e[2]}"><time>${e[0]}</time><span>${esc(e[1])}</span></button>`).join("")}</div>`;
    }
    const closed = D.closed.concat(items.filter((i) => i.done).map((i) => i.title + " · 完了"));
    html += `<div class="sec"><div class="sech"><span>自動で閉じた</span><span class="n">${closed.length}</span></div><div class="closed">${closed.map((c) => `<s>${esc(c)}</s>`).join("")}</div></div>`;
    $("sections").innerHTML = html;
    const fd = $("sections").querySelector("details.fyi"); if (fd) fd.ontoggle = () => (S.fyiOpen = fd.open);
    $("sections").querySelectorAll("[data-id]").forEach((b) => (b.onclick = () => select(b.dataset.id)));
    $("sections").querySelectorAll("[data-none]").forEach((b) => (b.onclick = () => toast("この予定はまだ予習ブリーフを作っていません（見本）")));
  }

  function select(id) {
    S.cur = id;
    const i = curItem();
    // スレッドがあるボールは、まずスレッド（件名・本文・添付・下書き）を出す
    S.rmode = i.thread ? "thread" : "browser";
    left(); center(); right();
  }

  // ---------- 中：このボールの AI ----------
  function center() {
    const i = curItem(), pj = D.projects[i.proj];
    loadChat(i);
    const ball = { me: ["自分ボール", "c-me"], ai: ["AI 作業中", "c-ai"], them: ["相手ボール", "c-them"], cal: ["予定", "c-them"], notes: ["会議メモ", "c-ai"] }[i.sec] || ["", "c-them"];
    $("chHead").innerHTML = `<span class="proj"><span class="pd" style="background:${pj.color}"></span>${esc(pj.name)}</span><h2>${esc(i.title)}</h2><span class="chip ${ball[1]}">${ball[0]}</span>`;
    $("ct-chat").setAttribute("aria-pressed", S.ctab === "chat");
    $("ct-memo").setAttribute("aria-pressed", S.ctab === "memo");
    if (S.ctab === "chat") {
      $("feed").innerHTML = feedHtml(i);
      bindLinks($("feed"));
    } else {
      $("feed").innerHTML = `<textarea class="memo" id="memoText" aria-label="メモ" placeholder="メモはまだありません。チャットで「メモに入れといて」と言うと AI が書きます。">${esc(i.memo)}</textarea>`;
      $("memoText").oninput = (e) => { i.memo = e.target.value; saveChat(i); };
    }
    $("feed").scrollTop = $("feed").scrollHeight;
    renderState(i);
  }
  function feedHtml(i) {
    const run = running[i.id];
    return i.feed.map(([k, t], n) => (k === "prog" ? `<div class="prog"><b>Progress</b>${esc(t)}</div>`
      : k === "ai" ? `<div class="bub ai rich${run && run.cur === n ? " live" : ""}">${t ? richBody(t) : `<span class="hint">考え中…</span>`}</div>`
      : k === "err" ? `<div class="bub ai err">${esc(t)}</div>`
      : `<div class="bub ${k}">${esc(t)}</div>`)).join("");
  }
  function renderState(i) {
    const run = running[i.id];
    $("state").innerHTML = run ? `<b>Claude が作業中</b> ${esc(run.note || "考えています…")}`
      : i.sec === "ai" ? `<b>作業中</b> 終わったら自分ボールに戻します` : `<b>待機中</b> あなたの番`;
    $("compSend").textContent = run ? "止める" : "送信";
    $("compSend").classList.toggle("stop", !!run);
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
    if (showB) { renderTabs(); showTab(); } else renderThread(i);
  }
  function renderTabs() {
    const i = curItem();
    $("btabs").innerHTML = i.tabs.map((t, k) => `<button type="button" class="btab" data-k="${k}" aria-pressed="${k === i.activeTab}">${tabIcon(t)}<span>${esc(t.title)}</span><span class="x" data-close="${k}" aria-label="タブを閉じる">×</span></button>`).join("");
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

  // ---------- スレッド表示 ----------
  const gmailUrl = (threadId) => "https://mail.google.com/mail/u/0/#all/" + threadId;
  const nameOf = (addr) => (String(addr || "").match(/^\s*"?([^"<]+?)"?\s*</) || [, addr || ""])[1].trim();
  const emailOf = (addr) => (String(addr || "").match(/<([^>]+)>/) || [, addr || ""])[1].trim();
  // 返信に付いてくる引用（「〜 wrote:」「>」以降）を切って、そのメールで新しく書かれた部分だけにする
  function trimQuote(body) {
    const lines = String(body || "").split(/\r?\n/);
    const cut = lines.findIndex((l) => /^\s*>/.test(l) || /^On .+wrote:\s*$/.test(l) || /^\d{4}年\d{1,2}月\d{1,2}日.+(<.+@.+>)?:?\s*$/.test(l.trim()) && /[:：]\s*$/.test(l.trim()) || /^-{5,}\s*(Original Message|Forwarded message)/i.test(l));
    const kept = (cut > 0 ? lines.slice(0, cut) : lines).join("\n").trim();
    return { text: kept || String(body || "").trim(), trimmed: cut > 0 };
  }
  // ---------- メール本文を見やすくする ----------
  // リンクはボタンに（改行で割れた長いリンクもつなぐ）、*見出し* は太字、[担当] の行は担当者つきのリストに、
  // 自分（Yuki Katayama / 片山）の担当は色付き。末尾のアンケート・住所・[image: …] は隠す
  const ME_RE = /Yuki Katayama|片山|katayama/i;
  function linkLabel(u) {
    try {
      const x = new URL(u), h = x.hostname.replace(/^www\./, "");
      if (h === "docs.google.com") return /\/spreadsheets\//.test(x.pathname) ? "📊 スプレッドシート" : /\/presentation\//.test(x.pathname) ? "📽 スライド" : /\/forms\//.test(x.pathname) ? "📝 フォーム" : "📄 Google ドキュメント";
      if (h === "forms.gle") return "📝 Google フォーム";
      if (h === "script.google.com") return "📝 Web フォーム（Google）";
      if (h === "drive.google.com") return "📁 Drive のファイル";
      if (h === "meet.google.com") return "🎥 Meet";
      if (h === "calendar.google.com" || (h === "google.com" && /calendar/.test(x.pathname))) return "📅 カレンダー";
      if (/slack\.com$/.test(h)) return "💬 Slack";
      if (/zoom\.us$/.test(h)) return "🎥 Zoom";
      return "🔗 " + h;
    } catch (e) { return "🔗 リンク"; }
  }
  function cleanBody(raw) {
    let t = String(raw || "").replace(/\r/g, "");
    t = t.replace(/<(https?:\/\/[^>]+)>/g, (m, u) => "<" + u.replace(/\s+/g, "") + ">");
    const cut = t.search(/このメールの内容はお役に立ちましたか|Was this (email|helpful)|Google LLC, 1600 Amphitheatre/);
    if (cut > 0) t = t.slice(0, cut);
    return t.replace(/\[image:[^\]]*\]/g, "").replace(/\n{3,}/g, "\n\n").trim();
  }
  // 本文のリンクを拾って、名前を付ける。
  //  - [名前](URL)（HTML メールの <a> と Slack の <URL|名前> はこの形にしてある）→ その名前
  //  - 「お申込フォーム：URL」のように同じ行の短い前置き → それ
  //  - URL だけの行 → 少し上の見出し（*■ お申込フォーム* / 【…】 など）
  // 返す t はリンクを \0番号\0 に置き換えた本文
  const PH = (k) => "\u0000" + k + "\u0000";
  const tidyLabel = (s) => String(s || "").replace(/\u0000\d+\u0000/g, "").replace(/^[\s*_~>＞■□●○◆◇▼▶・\-–—【\[]+|[\s*_~:：→】\]]+$/g, "").replace(/\s+/g, " ").trim();
  const isHeading = (s) => /^\s*[*＊]?\s*[■□●○◆◇▼▶【]/.test(s) || /^\s*\*[^*]+\*\s*$/.test(s);
  function parseLinks(raw) {
    const links = [];
    const t = cleanBody(raw).replace(/\[([^\]\n]{1,80})\]\((https?:\/\/[^)\s]+)\)|<(https?:\/\/[^>\s]+)>|(https?:\/\/[^\s<>"」）)]+)/g, (m, label, lu, a, b) => {
      if (lu) { links.push({ url: lu, label: label.trim() === lu ? "" : label.trim() }); return PH(links.length - 1); }
      const full = a || b, u = full.replace(/[.,、。]+$/, "");
      links.push({ url: u, label: "" });
      return PH(links.length - 1) + full.slice(u.length);
    });
    const lines = t.split("\n");
    lines.forEach((line, n) => {
      for (const m of line.matchAll(/\u0000(\d+)\u0000/g)) {
        const L = links[+m[1]]; if (L.label) continue;
        const before = line.slice(0, m.index);
        if (before.trim()) {
          // 同じ行の前置き。文になっている長いものは名前にしない
          const b = tidyLabel(before);
          if (b && b.length <= 24 && !/[。！？]$/.test(b)) L.label = b;
          continue;
        }
        // URL だけの行: 3行上までの見出し、なければ直前の短い行
        for (let p = n - 1, seen = 0; p >= 0 && seen < 3; p--) {
          if (!lines[p].trim()) continue; seen++;
          if (/\u0000\d+\u0000/.test(lines[p])) break;
          const c = tidyLabel(lines[p]);
          if (c && c.length <= 30 && (isHeading(lines[p]) || (seen === 1 && c.length <= 20 && !/[。、！？]/.test(c)))) { L.label = c; break; }
        }
      }
    });
    return { t, links };
  }
  function linkBtn(L) {
    const auto = linkLabel(L.url), icon = auto.split(" ")[0];
    const label = L.label ? icon + " " + L.label : auto;
    return `<button type="button" class="lnk" data-url="${esc(L.url)}" data-label="${esc(L.label || auto.replace(/^\S+\s/, ""))}" title="${esc(L.url)}\nクリックで別ウィンドウ / ⌘クリックで右のタブ">${esc(label)}<small>${esc(hostOf(L.url))}</small></button>`;
  }
  function richBody(raw) {
    const { t, links } = parseLinks(raw);
    const fill = (str) => esc(str).replace(/\u0000(\d+)\u0000/g, (m, k) => linkBtn(links[+k]));
    return t.split("\n").map((line) => {
      const plain = line.replace(/\u0000\d+\u0000/g, "").trim();
      if (/^\*[^*].*\*$/.test(plain)) return `<div class="bh">${esc(plain.replace(/^\*|\*$/g, ""))}</div>`;
      if (/^(推奨される次のステップ|次のステップ|Next steps|概要|詳細|まとめ)$/.test(plain)) return `<div class="bh">${esc(plain)}</div>`;
      const ai = line.match(/^\s*\[([^\]]+)\]\s*(.+)$/);
      if (ai) return `<div class="actl${ME_RE.test(ai[1]) ? " mine" : ""}"><span class="who">${esc(ai[1])}</span><span>${fill(ai[2])}</span></div>`;
      return line.trim() ? `<div class="ln">${fill(line)}</div>` : `<div class="gap"></div>`;
    }).join("");
  }
  // 会議メモの「次のステップ」から自分の担当を抜き出す
  function myActions(raw) {
    return cleanBody(raw).split("\n").map((l) => l.match(/^\s*\[([^\]]+)\]\s*(.+)$/)).filter((m) => m && ME_RE.test(m[1])).map((m) => m[2].replace(/<https?:[^>]+>/g, "").trim());
  }
  // ---------- 資料バー: スレッドに出てくる添付ファイルと Google のファイルを、古い順に横に並べる ----------
  const driveCache = {};
  const URL_RE = /<(https?:\/\/[^>\s]+)>|(https?:\/\/[^\s<>"」）)]+)/g;
  const gFileId = (u) => { const m = String(u).match(/\/(?:d|folders)\/([a-zA-Z0-9_-]{20,})/) || String(u).match(/[?&]id=([a-zA-Z0-9_-]{20,})/); return m ? m[1] : ""; };
  const isDocLink = (u) => /docs\.google\.com\/(document|spreadsheets|presentation|forms)|drive\.google\.com\/(file|open|drive\/folders)|forms\.gle\/|script\.google\.com\/[^?#]*macros\/|\.(pdf|pptx?|key|docx?|xlsx?|csv|zip)(\?|$)/i.test(u);
  function docIcon(name, mime, url) {
    const x = (String(name) + " " + String(mime) + " " + String(url)).toLowerCase();
    if (/presentation|\.pptx?\b|\.key\b|slides/.test(x)) return "📽";
    if (/spreadsheet|\.xlsx?\b|\.csv\b|sheet/.test(x)) return "📊";
    if (/\.pdf\b|application\/pdf/.test(x)) return "📕";
    if (/document|\.docx?\b|wordprocessing/.test(x)) return "📄";
    if (/image\/|\.(png|jpe?g|gif|heic)\b/.test(x)) return "🖼";
    if (/folder/.test(x)) return "📁";
    if (/forms|script\.google|フォーム/.test(x)) return "📝";
    return "📎";
  }
  const shortDate = (d) => { const t = typeof d === "number" ? new Date(d) : new Date(d); return isNaN(t) ? "" : `${t.getMonth() + 1}/${t.getDate()}`; };
  // スレッドの種類ごとに、出てきた順（古い→新しい）で集める
  function collectDocs(i) {
    const t = i.thread, docs = [], seen = new Set();
    const add = (d) => { const key = d.url || d.name + "|" + d.size; if (seen.has(key)) return; seen.add(key); docs.push(d); };
    const linksIn = (text, date) => { for (const L of parseLinks(text).links) if (isDocLink(L.url)) add({ kind: "link", url: L.url, gid: gFileId(L.url), name: L.label || "", date }); };
    if (t.kind === "gmail") {
      const msgs = t.live ? (t.data ? t.data.messages : []) : (t.messages || []);
      msgs.forEach((m) => {
        (m.attachments || []).forEach((a, k) => { if (!/\.ics$/i.test(a.filename)) add({ kind: "att", name: a.filename, size: a.size, mime: a.mimeType, date: m.date, att: a }); });
        linksIn(m.body, m.date);
      });
    } else if (t.kind === "slack" && t.live && t.data) {
      t.data.messages.forEach((m) => {
        const date = parseFloat(m.ts) * 1000;
        (m.files || []).forEach((f) => add({ kind: "link", url: f.url, name: f.name, mime: f.mimetype, date }));
        linksIn(m.text, date);
      });
    } else if (t.kind === "cal" && t.ev) {
      (t.ev.attachments || []).forEach((a) => add({ kind: "link", url: a.url, name: a.title, mime: a.mimeType, gid: gFileId(a.url) }));
      linksIn(t.ev.description || "");
    } else if (t.kind === "msgr") {
      const msgs = t.live ? (t.data ? t.data.messages : []) : (t.messages || []);
      msgs.forEach((m) => { if (m.file) add({ kind: "link", url: m.file, name: m.text.replace(/^📎\s*/, "") }); linksIn(m.text || ""); });
    }
    return docs;
  }
  function docsBarHtml(docs) {
    if (!docs.length) return "";
    return `<div class="docbar" role="list" aria-label="このスレッドの資料（古い順）"><span class="dbl">資料 ${docs.length}</span>${docs.map((d, k) => {
      const meta = d.gid && driveCache[d.gid];
      const name = (meta && meta.name) || d.name || linkLabel(d.url).replace(/^\S+\s/, "");
      const icon = docIcon(name, d.mime || (meta && meta.mimeType) || "", d.url || "");
      return `<button type="button" class="doc" role="listitem" data-doc="${k}" title="${esc(name)}${d.url ? "\n" + esc(d.url) : ""}"><span class="di">${icon}</span><span class="dn">${esc(name)}</span>${d.date ? `<span class="dd">${esc(shortDate(d.date))}</span>` : ""}</button>`;
    }).join("")}</div>`;
  }
  // 資料バーを出して、押したら開く。Google のファイル名が分かっていなければ gog で調べて差し替える
  function mountDocsBar(i, anchorSel) {
    const docs = collectDocs(i);
    const host = $("thr").querySelector(anchorSel);
    if (!host) return false;
    if (!docs.length) return true;
    host.insertAdjacentHTML("afterend", docsBarHtml(docs));
    bindDocsBar(i, docs);
    const need = [...new Set(docs.filter((d) => d.gid && !driveCache[d.gid]).map((d) => d.gid))];
    if (!need.length || !IS_APP || !window.ball.driveMeta) return true;
    window.ball.driveMeta(need).then((r) => {
      if (!r.ok) return;
      Object.assign(driveCache, r.data);
      const bar = $("thr").querySelector(".docbar");
      if (!bar || curItem() !== i) return;
      bar.outerHTML = docsBarHtml(docs);
      bindDocsBar(i, docs);
    });
    return true;
  }
  function bindDocsBar(i, docs) {
    const bar = $("thr").querySelector(".docbar"); if (!bar) return;
    bar.querySelectorAll("[data-doc]").forEach((b) => (b.onclick = (event) => {
      const d = docs[+b.dataset.doc];
      if (d.kind === "att") {
        if (!IS_APP || !i.thread.live) return toast("見本の添付ファイルです");
        toast("添付ファイルを開いています…");
        window.ball.gmailAttachment(d.att).then((r) => toast(r.ok ? "開きました" : "開けませんでした：" + r.error));
      } else openLink(d.url, (d.gid && driveCache[d.gid] && driveCache[d.gid].name) || d.name || linkLabel(d.url).replace(/^\S+\s/, ""), event);
    }));
  }
  // リンクは BALL と同じログインのまま別ウィンドウで開く（スレッドと下書きを見ながら中身を確かめられる）。⌘クリックなら右のタブで
  function openLink(url, title, ev) {
    if (ev && (ev.metaKey || ev.ctrlKey)) return openTab(url, title);
    if (IS_APP && window.ball.openPreview) window.ball.openPreview({ url, title });
    else window.open(url, "_blank", "noopener");
  }
  function bindLinks(root) { root.querySelectorAll(".lnk[data-url]").forEach((b) => (b.onclick = (e) => openLink(b.dataset.url, b.dataset.label, e))); }

  // 会議メモ: Gemini のメモ本体（Google ドキュメント）・文字起こし・録画へのリンクを一番上に出す。Claude に読ませて議事録にするため
  function notesDocs(msgs) {
    const out = [], seen = new Set();
    (msgs || []).forEach((m) => parseLinks(m.body).links.forEach((L) => {
      const u = L.url;
      if (!/docs\.google\.com\/document\/d\/|drive\.google\.com\/(file\/d|open)/.test(u)) return;
      const id = gFileId(u) || u; if (seen.has(id)) return; seen.add(id);
      out.push({ url: u, label: L.label && !/^(こちら|リンク|here)$/i.test(L.label) ? L.label : /drive\.google/.test(u) ? "録画・ファイル" : "会議メモ（ドキュメント）" });
    }));
    return out;
  }
  function notesBar(msgs) {
    const docs = notesDocs(msgs);
    return `<div class="notesbar"><span class="nbl">議事録の元</span>${docs.length ? docs.map((d) => linkBtn({ url: d.url, label: d.label }).replace('class="lnk"', 'class="lnk big"')).join("") : `<span class="hint">メモ本体へのリンクが見つかりませんでした（本文から作ります）</span>`}<span class="sp"></span><button type="button" class="btn send" id="notesToClaude" title="会議メモ（リンク先のドキュメントも）を Claude に読ませて、議事録をメモ欄に作ります">Claude で議事録にする</button></div>`;
  }
  function msgCard(m, open, full) {
    // 会議メモ（転送されたものも）は本文がまるごと大事なので、引用を省かない
    const q = full ? { text: String(m.body || "").trim(), trimmed: false } : trimQuote(m.body);
    const att = (m.attachments || []).map((a, k) => `<button type="button" class="att" data-msg="${esc(m.id)}" data-att="${k}" title="開く">📎 ${esc(a.filename)}<span>${esc(a.size)}</span></button>`).join("");
    return `<div class="mcard${open ? " open" : ""}">
      <div class="mhd"><b>${esc(nameOf(m.from))}</b><span>${esc(emailOf(m.from))}</span><time>${esc(m.date)}</time></div>
      <div class="mto">宛先 ${esc(m.to)}${m.cc ? `　CC ${esc(m.cc)}` : ""}</div>
      ${att ? `<div class="atts">${att}</div>` : ""}
      <div class="mb rich">${richBody(q.text)}</div>
      ${q.trimmed ? `<div class="hint">（引用部分は省略。全文は「Gmail で開く」）</div>` : ""}
    </div>`;
  }
  function renderThread(i) {
    const t = i.thread;
    if (t.kind === "msgr") { renderMsgrThread(i); return; }
    if (t.kind === "cal") { renderCalThread(i); return; }
    if (t.kind === "slack" && t.live) { renderSlackThread(i); return; }
    if (t.kind === "slack") {
      $("thr").innerHTML = `<div class="thr"><h4>${t.ws === "DM" ? "DM: " : ""}${esc(t.ch)}${t.ws === "DM" ? "" : " のスレッド"}<span>${esc(t.ws)}</span></h4>
        ${t.msgs.map((m) => `<div class="sm"><span class="av" style="background:${m[0]}">${esc(m[1][0])}</span><div><div class="n">${esc(m[1])}<time>${esc(m[2])}</time></div><div class="x rich">${richBody(m[3])}</div>${m[4] ? `<span class="react">${esc(m[4])}</span>` : ""}</div></div>`).join("")}
        ${t.draft ? draftBox(i, "slack") : ""}</div>`;
      bindLinks($("thr")); bindDraft(i);
      return;
    }
    // Gmail
    if (t.live && !t.data) {
      $("thr").innerHTML = `<div class="thr"><div class="empty">スレッドを読み込み中…</div></div>`;
      if (!t.loading) {
        t.loading = true;
        window.ball.gmailThread(t.threadId).then((r) => {
          t.loading = false;
          if (r.ok) t.data = r.data; else t.error = r.error;
          if (curItem() === i && S.rmode === "thread") renderThread(i);
        });
      }
      if (!t.error) return;
    }
    if (t.error) { $("thr").innerHTML = `<div class="thr"><div class="empty">スレッドを読めませんでした：${esc(t.error)}</div></div>`; return; }
    const msgs = t.live ? t.data.messages : t.messages;
    const last = msgs[msgs.length - 1];
    const older = msgs.slice(0, -1).reverse();
    const subject = (last && last.subject) || t.subject || i.title;
    const mine = i.notes ? [...new Set(msgs.flatMap((m) => myActions(m.body)))] : [];
    if (i.notes && t.live) { i.chips = [["議事録", "ai"]].concat(mine.length ? [[`自分の担当 ${mine.length}件`, "me"]] : []); if (mine.length) i.sec = "me"; }
    $("thr").innerHTML = `<div class="thr">
      <div class="thd"><h4>${esc(subject)}</h4><button type="button" class="btn" id="openInGmail">Gmail で開く ↗</button></div>
      ${i.ccWarn ? `<div class="ccwarn"><b>⚠ 送り先に注意</b>${esc(i.ccWarn)}</div>` : ""}
      ${i.notes ? notesBar(msgs) : ""}
      ${i.notes ? `<div class="mine-box"><b>${mine.length ? `自分の担当（${mine.length}件）` : "自分の担当はありませんでした"}</b>${mine.length ? `<ul>${mine.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}<span class="hint">議事録の清書は真ん中の Claude に頼めます</span></div>` : ""}
      ${last ? msgCard(last, true, !!i.notes) : ""}
      ${older.length ? `<details class="older"><summary>過去のやり取り（${older.length}件）</summary>${older.map((m) => msgCard(m, false, !!i.notes)).join("")}</details>` : ""}
      ${draftBox(i, "gmail")}
    </div>`;
    bindLinks($("thr"));
    mountDocsBar(i, ".notesbar") || mountDocsBar(i, ".thd");
    if ($("notesToClaude")) $("notesToClaude").onclick = () => {
      $("compText").value = "この会議の議事録を、いつも Claude で作っているのと同じやり方（メモリー・スキル・CLAUDE.md の決まり。顧客フォルダの 1_議事録 への格納、フォルダが無ければ作るところまで）で作って。会議メモのドキュメント（リンク先）も読んで。できたら議事録のリンクと要点をこのボールのメモにも入れて。";
      $("comp").requestSubmit();
    };
    if (i.notes && t.live) left();
    $("openInGmail").onclick = () => { const url = gmailUrl(t.threadId || ""); if (!t.threadId) return toast("見本のスレッドです"); const tab = i.tabs.find((x) => x.url === url); if (tab) { i.activeTab = i.tabs.indexOf(tab); S.rmode = "browser"; right(); } else openTab(url, "Gmail - このスレッド"); };
    $("thr").querySelectorAll(".att").forEach((b) => (b.onclick = () => {
      const m = msgs.find((x) => x.id === b.dataset.msg), a = m && m.attachments[+b.dataset.att];
      if (!a) return;
      if (!IS_APP || !t.live) return toast("見本の添付ファイルです");
      toast("添付ファイルを開いています…");
      window.ball.gmailAttachment(a).then((r) => toast(r.ok ? "開きました" : "開けませんでした：" + r.error));
    }));
    bindDraft(i);
  }
  // Messenger: 直近のやり取りを吹き出しで出し、下書きを会話の入力欄に入れる
  function renderMsgrThread(i) {
    const t = i.thread;
    if (t.live && !t.data && !t.error) {
      $("thr").innerHTML = `<div class="thr"><div class="empty">${esc(t.name)}さんとのやり取りを読み込み中…（過去へ遡って読んでいます）</div></div>`;
      if (!t.loading && IS_APP) {
        t.loading = true;
        window.ball.messengerThread({ href: t.href, name: t.name, steps: t.steps || 4 }).then((r) => {
          t.loading = false;
          if (r.ok && r.messages && r.messages.length) {
            t.data = r;
            // 会話を開いたあとの URL（/t/<番号>）を覚える。送信先の取り違えを防ぐのに使う
            if (/\/t\/[^/?#]+/.test(r.url || "")) { t.href = r.url; i.tabs.forEach((x) => { if (x.sim === "messenger") x.url = r.url; }); }
          } else t.error = r.ok ? `メッセージを読み取れませんでした（${r.rows || 0} 個）。「Messenger で開く」で見てください` : r.error;
          if (curItem() === i && S.rmode === "thread") renderMsgrThread(i);
        });
      }
      return;
    }
    const msgs = t.live ? (t.data ? t.data.messages : []) : t.messages;
    const more = t.live && t.data && !t.data.reachedTop;
    $("thr").innerHTML = `<div class="thr">
      <div class="thd"><h4>Messenger：${esc(t.name)}</h4><span><button type="button" class="btn" id="msgrMute" title="仕事と関係ない相手を BALL に出さないようにする">今後この相手を出さない</button> <button type="button" class="btn" id="msgrReload">読み直す</button> <button type="button" class="btn" id="openInMsgr">Messenger で開く ↗</button></span></div>
      ${t.live && t.data ? `<div class="hint">${t.data.reachedTop ? "最初のメッセージまで読みました" : "直近から遡って読んでいます"}（${msgs.length}件）${more ? ` <button type="button" class="btn" id="msgrMore">もっと過去を読む</button>` : ""}</div>` : ""}
      ${t.error ? `<div class="empty">${esc(t.error)}</div>` : `<div class="bubs">${msgs.map((m, k) => `<div class="bubrow${m.mine ? " mine" : ""}">${
        m.image ? `<button type="button" class="bbimg" data-img="${k}" title="大きく開く"><img ${/^data:/.test(m.image) ? `src="${esc(m.image)}"` : `data-msgr-src="${esc(m.image)}"`} alt="写真" loading="lazy" referrerpolicy="no-referrer"></button>`
        : m.file ? `<button type="button" class="bb bbfile" data-file="${k}">${esc(m.text)}</button>`
        : `<div class="bb rich">${richBody(m.text)}</div>`}</div>`).join("")}</div>`}
      ${draftBox(i, "msgr")}
    </div>`;
    bindLinks($("thr"));
    $("msgrReload").onclick = () => { if (!t.live) return toast("見本の会話です"); t.data = null; t.error = null; renderMsgrThread(i); };
    mountDocsBar(i, ".thd");
    $("msgrMute").onclick = () => { muteName(t.name); i.hidden = true; toast(`${t.name} は今後 BALL に出しません`); const next = items.find((x) => !x.hidden && !x.done && x.sec === "me"); if (next) select(next.id); else left(); };
    if ($("msgrMore")) $("msgrMore").onclick = () => { t.steps = (t.steps || 4) + 10; t.data = null; t.error = null; renderMsgrThread(i); };
    $("openInMsgr").onclick = () => openConversationTab(i);
    // 写真は開けなかったら「📷 写真」の文字に差し替える。押すと右のブラウザで開く
    const photoFail = (im) => { const btn = im.parentElement; btn.className = "bb bbfile"; btn.textContent = "📷 写真（押すと開く）"; };
    $("thr").querySelectorAll(".bbimg img").forEach((im) => (im.onerror = () => photoFail(im)));
    // 写真は Messenger にログインした BALL の中から取ってくる
    $("thr").querySelectorAll("img[data-msgr-src]").forEach((im) => {
      if (!IS_APP || !window.ball.messengerImage) { im.src = im.dataset.msgrSrc; return; }
      window.ball.messengerImage(im.dataset.msgrSrc).then((r) => { if (r && r.ok) im.src = r.data; else photoFail(im); });
    });
    $("thr").querySelectorAll("[data-img]").forEach((b) => (b.onclick = () => openTab(msgs[+b.dataset.img].image, "写真")));
    $("thr").querySelectorAll("[data-file]").forEach((b) => (b.onclick = () => openTab(msgs[+b.dataset.file].file, msgs[+b.dataset.file].text.replace(/^📎\s*/, ""))));
    if (t.live && t.data) { const bx = $("thr").querySelector(".bubs"); if (bx && bx.lastElementChild) bx.lastElementChild.scrollIntoView({ block: "nearest" }); }
    bindDraft(i);
  }
  function openConversationTab(i) {
    const url = i.thread.href || (i.tabs[0] && i.tabs[0].url);
    let tab = i.tabs.find((x) => x.url === url);
    if (!tab) { tab = { title: `${i.thread.name} - Messenger`, url, sim: "messenger", key: i.id + "-c" + tabSeq++ }; i.tabs.unshift(tab); }
    i.activeTab = i.tabs.indexOf(tab); S.rmode = "browser"; right();
    return tab;
  }
  const normName = (x) => String(x || "").replace(/[\s　・、,]/g, "").toLowerCase();
  // 会話を右のブラウザで開き、入力欄に下書きを入れる。send=true のときだけ Enter まで押す（本人が確認ボタンを押した場合のみ）
  function insertIntoMessenger(i, text, { send = false, done } = {}) {
    if (!IS_APP || !i.thread.live) return toast("見本なので入れません。アプリ版では会話の入力欄に入ります");
    const t = i.thread;
    if (send && !/\/t\/[^/?#]+/.test(t.href || "")) return toast("この会話の場所（URL）が分からないので送信できません。「入力欄に入れる」を使って、Messenger で送ってください");
    const tab = openConversationTab(i);
    const w = webviews[tab.key];
    // 入力欄に入れる前に、開いている会話の名前が相手と一致するかを確かめる
    const js = `(function(t){var h=(document.querySelector('[role="main"] h1, [role="main"] h2')||{}).innerText||document.title||"";var b=document.querySelector('[role="textbox"][contenteditable="true"]');if(!b)return {ok:false,h:h};b.focus();document.execCommand('insertText',false,t);return {ok:true,h:h};})(${JSON.stringify(text)})`;
    const check = `(function(){var h=(document.querySelector('[role="main"] h1, [role="main"] h2')||{}).innerText||document.title||"";return h;})()`;
    let tries = 0;
    const attempt = async () => {
      try {
        const header = await w.executeJavaScript(check);
        const match = header && normName(header).includes(normName(t.name).slice(0, 6));
        if (!match) {
          if (++tries < 10) return setTimeout(attempt, 1000);
          return toast(send ? "開いている会話の相手が一致しなかったので、送信を止めました" : "会話が開けませんでした。下書きをコピーして貼ってください");
        }
        const r = await w.executeJavaScript(js);
        if (!r.ok) { if (++tries < 10) return setTimeout(attempt, 1000); return toast("入力欄が見つかりませんでした。下書きをコピーして貼ってください"); }
        if (!send) return toast("入力欄に入れました。内容を確認して Enter で送ってください");
        w.focus();
        w.sendInputEvent({ type: "keyDown", keyCode: "Enter" });
        w.sendInputEvent({ type: "char", keyCode: "\r" });
        w.sendInputEvent({ type: "keyUp", keyCode: "Enter" });
        toast(`${t.name}さんに送信しました`);
        if (done) done();
      } catch (e) { if (++tries < 10) setTimeout(attempt, 1000); }
    };
    setTimeout(attempt, 1500);
  }
  function draftBox(i, kind) {
    const t = i.thread;
    if (kind === "slacklive") return slackComposerHtml(t);
    const saved = t.aiDraft ? `AI が入れた下書きです（未保存・未送信） <button type="button" class="lnkbtn" id="discardDraft">破棄</button>` : t.draftId ? `Gmail の下書きに保存済み` : kind === "msgr" ? "送るのは Messenger で Enter" : "まだ保存していません";
    const actions = kind === "gmail"
      ? `<button type="button" class="sbt" id="gAdd" title="ファイルを添付（ドラッグ＆ドロップ・⌘V の貼り付けも可）">📎</button><input type="file" id="gFile" multiple hidden><span class="hint">送るのは「送信…」で確認したときだけ</span><span class="sp"></span><button type="button" class="btn" id="saveDraft">下書きに保存</button><button type="button" class="btn send" id="sendMail">送信…</button>`
      : kind === "msgr"
        ? `<button type="button" class="btn" id="copyDraft">コピー</button><span class="sp"></span><button type="button" class="btn" id="saveDraft">入力欄に入れる</button><button type="button" class="btn send" id="sendMsgr">送信…</button>`
      : kind === "slacklive"
        ? `<button type="button" class="btn" id="copyDraft">コピー</button><span class="hint">AI は下書きまで。送るのは「送信…」で確認したときだけ</span><span class="sp"></span><button type="button" class="btn send" id="saveDraft">送信…</button>`
        : `<span class="hint">見本です（Slack は下書きまで。投稿は自分のボタンで）</span><span class="sp"></span><button type="button" class="btn send" id="saveDraft">送信</button>`;
    let head = "";
    if (kind === "gmail" && t.live && t.data) {
      const f = replyFields(t, "");
      head = `<div class="mhead"><div class="rmode"><button type="button" class="btn" id="rOne" title="差出人だけに返す">↩ 返信</button><button type="button" class="btn" id="rAll" title="宛先・CC の全員に返す">↩↩ 全員に返信</button></div><label>To<input id="dTo" value="${esc(f.to)}" spellcheck="false"></label><label>Cc<input id="dCc" value="${esc(f.cc)}" placeholder="Cc（カンマ区切り）" spellcheck="false"></label><div class="msub">件名 ${esc(f.subject)}</div></div>`;
    }
    return `<div class="draft${kind === "gmail" ? " gcomp" : ""}" id="${kind === "gmail" ? "gcomp" : "dbox"}"><div class="dh"><span>下書き（送るまで送信されません）</span><span id="draftState">${saved}</span></div>${head}
      <textarea id="draftText" aria-label="下書き" placeholder="真ん中で「下書き書いて」と言うとここに入ります。直接書いても OK。">${esc(t.draft || "")}</textarea>
      ${kind === "gmail" ? `<div class="satt" id="gAtt"></div>` : ""}
      <div class="df">${actions}</div>
      <div class="confirm" id="sendConfirm" hidden></div></div>`;
  }
  // 返信の宛先を決める: 最後に相手から来たメールの差出人へ。CC は元の宛先と CC（自分と差出人を除く）
  function replyFields(t, body) {
    const msgs = t.data.messages, last = msgs[msgs.length - 1];
    const me = /yuki\.katayama@fout\.jp/i;
    const lastOther = [...msgs].reverse().find((m) => !me.test(m.from)) || last;
    const cc = [lastOther.to, lastOther.cc].join(",").split(",").map((s) => s.trim()).filter((s) => s && !me.test(s) && emailOf(s) !== emailOf(lastOther.from)).join(", ");
    const subject = /^re[:：]/i.test(last.subject) ? last.subject : "Re: " + last.subject;
    return { draftId: t.draftId, replyToMessageId: lastOther.id, to: t.to != null ? t.to : lastOther.from, cc: t.cc != null ? t.cc : cc, subject, body,
      files: (t.files || []).map((f) => ({ name: f.name, data: f.data })) };
  }
  // ---------- メールの下書き欄: 宛先・CC を直せる、ファイルを付けられる ----------
  function bindGmailComposer(i, ta) {
    const t = i.thread; t.files = t.files || [];
    const box = $("gcomp"), att = $("gAtt");
    if (!box || !att) return;
    const dirty = () => { if ($("draftState")) $("draftState").textContent = t.draftId ? "変更あり（未保存）" : "まだ保存していません"; };
    if ($("dTo")) $("dTo").oninput = (e) => { t.to = e.target.value; dirty(); };
    if ($("rOne")) $("rOne").onclick = () => { const f0 = (t.to = null, t.cc = null, replyFields(t, "")); t.to = f0.to; t.cc = ""; $("dTo").value = t.to; $("dCc").value = ""; dirty(); toast("差出人だけに返します"); };
    if ($("rAll")) $("rAll").onclick = () => { t.to = null; t.cc = null; const f0 = replyFields(t, ""); t.to = f0.to; t.cc = f0.cc; $("dTo").value = t.to; $("dCc").value = t.cc; dirty(); toast("全員に返します（CC を確かめてください）"); };
    if ($("dCc")) $("dCc").oninput = (e) => { t.cc = e.target.value; dirty(); };
    const draw = () => {
      att.innerHTML = t.files.map((f, k) => `<span class="schip">${f.preview ? `<img src="${f.preview}" alt="">` : `<span class="fi">${fileIcon({ filetype: f.name.split(".").pop(), mimetype: f.type })}</span>`}<span class="fn"><b>${esc(f.name)}</b><span>${esc(sizeText(f.size))}</span></span><button type="button" data-rm="${k}" aria-label="外す">×</button></span>`).join("");
      att.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { const f = t.files.splice(+b.dataset.rm, 1)[0]; if (f && f.preview) URL.revokeObjectURL(f.preview); draw(); dirty(); }));
    };
    const add = async (list) => {
      for (const f of list) {
        if (f.size > 25 * 1024 * 1024) { toast(`${f.name} は大きすぎます（Gmail は 25MB まで）`); continue; }
        t.files.push({ name: f.name || "image.png", type: f.type || "application/octet-stream", size: f.size, data: await f.arrayBuffer(), preview: /^image\//.test(f.type) ? URL.createObjectURL(f) : "" });
      }
      draw(); dirty();
    };
    draw();
    $("gAdd").onclick = () => $("gFile").click();
    $("gFile").onchange = () => { add([...$("gFile").files]); $("gFile").value = ""; };
    ta.addEventListener("paste", (e) => { const fs = [...((e.clipboardData && e.clipboardData.files) || [])]; if (fs.length) { e.preventDefault(); add(fs); } });
    box.addEventListener("dragover", (e) => { e.preventDefault(); box.classList.add("drop"); });
    box.addEventListener("dragleave", (e) => { if (!box.contains(e.relatedTarget)) box.classList.remove("drop"); });
    box.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); box.classList.remove("drop"); add([...((e.dataTransfer && e.dataTransfer.files) || [])]); });
  }

  // ---------- Slack のメンション ----------
  // 下書きでは「@名前」で見せ、送る直前に Slack の本物のメンション（<@ID>）に直す。
  // 候補はスレッドの発言者・メンションされている人 → チャンネルのメンバー（最初の @ で読み込む）
  function slackPeople(t) {
    const seen = new Set();
    return [...((t.data && t.data.people) || []), ...(t.people || [])].filter((p) => p && p.id && p.name && !seen.has(p.id) && seen.add(p.id));
  }
  function toSlackMentions(t, text) {
    let out = String(text || "");
    for (const p of slackPeople(t).sort((a, b) => b.name.length - a.name.length)) out = out.split("@" + p.name).join(`<@${p.id}>`);
    return out;
  }
  function bindMention(i, ta) {
    const t = i.thread;
    let box = null, sel = 0, matches = [], loading = false;
    const close = () => { if (box) box.remove(); box = null; };
    const query = () => { const m = ta.value.slice(0, ta.selectionStart).match(/(^|[\s　(（「、。])@([^\s@　]{0,30})$/); return m ? m[2] : null; };
    const loadMembers = () => {
      if (t.people || loading || !IS_APP || !window.ball.slackPeople) return;
      loading = true;
      window.ball.slackPeople({ channel: t.channel }).then((r) => { loading = false; t.people = r.ok ? r.people : []; if (document.activeElement === ta) update(); });
    };
    const update = () => {
      const q = query();
      if (q == null) return close();
      loadMembers();
      const ql = q.toLowerCase().replace(/\s/g, "");
      matches = slackPeople(t).filter((p) => p.name.toLowerCase().replace(/\s/g, "").includes(ql)).slice(0, 8);
      if (!matches.length && !loading) return close();
      sel = Math.max(0, Math.min(sel, matches.length - 1));
      if (!box) { box = document.createElement("div"); box.className = "mention"; box.setAttribute("role", "listbox"); ta.parentElement.appendChild(box); }
      box.innerHTML = matches.map((p, k) => `<button type="button" role="option" data-k="${k}" aria-selected="${k === sel}">@${esc(p.name)}</button>`).join("") + (loading ? `<span class="hint">メンバーを読み込み中…</span>` : "");
      box.querySelectorAll("button").forEach((b) => (b.onmousedown = (e) => { e.preventDefault(); pick(+b.dataset.k); }));
    };
    const pick = (k) => {
      const p = matches[k]; if (!p) return;
      const pos = ta.selectionStart, before = ta.value.slice(0, pos).replace(/@([^\s@　]{0,30})$/, "@" + p.name + " ");
      ta.value = before + ta.value.slice(pos);
      ta.selectionStart = ta.selectionEnd = before.length;
      t.draft = ta.value; saveChat(i); close(); ta.focus();
    };
    ta.addEventListener("input", () => { sel = 0; update(); });
    ta.addEventListener("keydown", (e) => {
      if (!box || e.isComposing || !matches.length) { if (box && e.key === "Escape") close(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % matches.length; update(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = (sel - 1 + matches.length) % matches.length; update(); }
      else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); pick(sel); }
      else if (e.key === "Escape") close();
    });
    ta.addEventListener("blur", () => setTimeout(close, 150));
  }
  function bindDraft(i) {
    const t = i.thread, ta = $("draftText"), btn = $("saveDraft");
    if (!ta || !btn) return;
    if ($("discardDraft")) $("discardDraft").onclick = () => { t.draft = ""; t.aiDraft = false; saveChat(i); renderThread(i); toast("AI の下書きを消しました"); };
    ta.oninput = () => { t.draft = ta.value; t.aiDraft = false; saveChat(i); if (t.kind === "gmail") $("draftState").textContent = t.draftId ? "変更あり（未保存）" : "まだ保存していません"; };
    if (t.kind === "slack" && t.live) {
      bindMention(i, ta);
      bindSlackComposer(i, ta);
      const cp = $("copyDraft");
      if (cp) cp.onclick = () => navigator.clipboard.writeText(ta.value).then(() => toast("コピーしました"), () => { ta.select(); toast("選択しました。⌘C でコピーしてください"); });
      // 送信は2段階: 「送信…」→ 送り先と本文を確認 →「この内容で送信」を本人が押したときだけ。送り先はチャンネルとスレッドで決まるので取り違えない
      btn.onclick = () => {
        if (!IS_APP) return toast("見本なので送信しません");
        if (!ta.value.trim() && !(t.files || []).length) return toast("下書きが空です");
        const where = t.threadTs ? `${t.where} のスレッド` : t.where;
        const box = $("sendConfirm");
        const ments = slackPeople(t).filter((p) => ta.value.includes("@" + p.name)).map((p) => p.name);
        const nf = (t.files || []).length;
        box.innerHTML = `<b>${esc(where)}に、この内容で送信しますか？</b>${ments.length ? `<div class="hint">メンション（通知が届きます）: ${esc(ments.join("、"))}</div>` : ""}${nf ? `<div class="hint">添付 ${nf} 件: ${esc(t.files.map((f) => f.name).join("、"))}</div>` : ""}<div class="mb sx" style="max-height:160px;overflow:auto">${slackHtml(ta.value, { emoji: (t.data && t.data.emoji) || {}, people: slackPeople(t), selfName: (t.data && t.data.selfName) || "" })}</div>
          <div class="crow"><span class="sp"></span><button type="button" class="btn" id="sendCancel">やめる</button><button type="button" class="btn send" id="sendGo">この内容で送信</button></div>`;
        box.hidden = false;
        $("sendCancel").onclick = () => { box.hidden = true; };
        $("sendGo").onclick = async () => {
          $("sendGo").disabled = true; $("sendGo").textContent = "送信中…";
          $("sendGo").textContent = (t.files || []).length ? "ファイルを送っています…" : "送信中…";
          const r = await window.ball.slackSend({ channel: t.channel, threadTs: t.threadTs, text: toSlackText(t, ta.value), files: (t.files || []).map((f) => ({ name: f.name, type: f.type, data: f.data })) });
          if (r.ok) { box.hidden = true; t.draft = ""; ta.value = ""; (t.files || []).forEach((f) => f.preview && URL.revokeObjectURL(f.preview)); t.files = []; t.aiDraft = false; toast("送信しました"); i.done = true; D.closed.unshift(`Slack: ${i.title.slice(0, 30)} · 返信済み`); left(); }
          else { $("sendGo").disabled = false; $("sendGo").textContent = "この内容で送信"; toast("送信できませんでした：" + r.error); }
        };
      };
      return;
    }
    if (t.kind === "msgr") {
      const cp = $("copyDraft");
      if (cp) cp.onclick = () => navigator.clipboard.writeText(ta.value).then(() => toast("コピーしました"), () => { ta.select(); toast("選択しました。⌘C でコピーしてください"); });
      btn.onclick = () => { if (!ta.value.trim()) return toast("下書きが空です"); insertIntoMessenger(i, ta.value); };
      // 送信も2段階: 「送信…」→ 相手と本文を確認 →「この内容で送信」を本人が押したときだけ
      const sb = $("sendMsgr");
      if (sb) sb.onclick = () => {
        if (!t.live || !IS_APP) return toast("見本なので送信しません");
        if (!ta.value.trim()) return toast("下書きが空です");
        const box = $("sendConfirm");
        box.innerHTML = `<b>${esc(t.name)}さんに、この内容で送信しますか？</b><div class="mb" style="max-height:120px;overflow:auto">${esc(ta.value)}</div>
          <div class="crow"><span class="hint">送る前に、開いた会話の相手が ${esc(t.name)}さんか確かめます</span><span class="sp"></span><button type="button" class="btn" id="sendCancel">やめる</button><button type="button" class="btn send" id="sendGo">この内容で送信</button></div>`;
        box.hidden = false;
        $("sendCancel").onclick = () => { box.hidden = true; };
        $("sendGo").onclick = () => {
          box.hidden = true;
          const text = ta.value;
          insertIntoMessenger(i, text, { send: true, done: () => { t.draft = ""; i.done = true; D.closed.unshift(`Messenger: ${t.name} · 送信済み`); left(); } });
        };
      };
      return;
    }
    if (t.kind === "gmail") bindGmailComposer(i, ta);
    const live = t.kind === "gmail" && t.live && IS_APP;
    btn.onclick = async () => {
      if (!live) return toast("見本なので保存・送信はしません");
      btn.disabled = true; $("draftState").textContent = "保存中…";
      const r = await window.ball.gmailDraft(replyFields(t, ta.value));
      btn.disabled = false;
      if (r.ok) { t.aiDraft = false; t.draftId = r.data.draftId || t.draftId; $("draftState").textContent = "Gmail の下書きに保存済み"; toast("Gmail の下書きに保存しました（送信はしていません）"); }
      else { $("draftState").textContent = "保存できませんでした"; toast("保存できませんでした：" + r.error); }
    };
    // 送信は2段階: 「送信…」で宛先・件名を確認 →「この内容で送信」を本人が押したときだけ送る
    const sendBtn = $("sendMail");
    if (!sendBtn) return;
    sendBtn.onclick = () => {
      if (!live) return toast("見本なので送信しません");
      if (!ta.value.trim()) return toast("下書きが空です");
      const f = replyFields(t, ta.value), box = $("sendConfirm");
      box.innerHTML = `<b>この内容で送信しますか？</b>
        <dl class="kv"><dt>宛先</dt><dd>${esc(f.to)}</dd>${f.cc ? `<dt>CC</dt><dd>${esc(f.cc)}</dd>` : ""}<dt>件名</dt><dd>${esc(f.subject)}</dd>${f.files.length ? `<dt>添付</dt><dd>${esc((t.files || []).map((x) => x.name).join("、"))}</dd>` : ""}</dl>
        <div class="crow"><span class="sp"></span><button type="button" class="btn" id="sendCancel">やめる</button><button type="button" class="btn send" id="sendGo">この内容で送信</button></div>`;
      box.hidden = false;
      $("sendCancel").onclick = () => { box.hidden = true; };
      $("sendGo").onclick = async () => {
        $("sendGo").disabled = true; $("sendGo").textContent = "送信中…";
        const r = await window.ball.gmailSend(replyFields(t, ta.value));
        if (r.ok) {
          box.hidden = true; t.draftId = null; t.draft = ""; ta.value = "";
          $("draftState").textContent = "送信しました";
          toast("送信しました");
          i.done = true; D.closed.unshift(`Gmail: ${i.title.slice(0, 30)} · 送信済み`); left();
        } else {
          $("sendGo").disabled = false; $("sendGo").textContent = "この内容で送信";
          toast("送信できませんでした：" + r.error);
        }
      };
    };
  }

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
  // ---------- 真ん中の Claude（Mac の Claude Code をボールごとの会話として呼ぶ） ----------
  // 送信の絶対ルール: Claude には送信の手段が無い。返信は右の下書き欄に入るだけで、送るのは片山さんのボタン。
  // 会話はボールごとに続く（Claude Code の --resume）。会話・メモ・下書きはこの Mac の中にだけ保存する
  var running = {};   // ballId -> { reqId, cur（いま書いている吹き出しの位置）, note, hash }
  var chatStore = null;
  const CHAT_KEY = "ball.chat.v1";
  const PERMS = { "いつもどおり": "full", "読むだけ": "read" };
  const MODEL_KEYS = { "Opus 5.5": "opus", "Sonnet 5.5": "sonnet" };
  let claudeState = null; // { ok, version, error, cwd }
  let lastInit = null;    // 直近の会話で読み込まれたスキル・コネクタ
  function chats() {
    if (!chatStore) { try { chatStore = JSON.parse(localStorage.getItem(CHAT_KEY) || "{}") || {}; } catch (e) { chatStore = {}; } }
    return chatStore;
  }
  function saveChat(i) {
    const st = chats();
    st[i.id] = { sid: i.claudeSid || "", feed: i.feed.slice(-200), memo: i.memo || "", draft: (i.thread && i.thread.draft) || "", aiDraft: !!(i.thread && i.thread.aiDraft), ctx: i.ctxHash || "", at: Date.now() };
    const keys = Object.keys(st);
    if (keys.length > 400) keys.sort((a, b) => (st[a].at || 0) - (st[b].at || 0)).slice(0, keys.length - 400).forEach((k) => delete st[k]);
    try { localStorage.setItem(CHAT_KEY, JSON.stringify(st)); } catch (e) { /* 保存できなくても会話は続けられる */ }
  }
  function loadChat(i) {
    if (i._chat) return; i._chat = true;
    const c = chats()[i.id]; if (!c) return;
    if (c.feed && c.feed.length) i.feed = c.feed;
    i.claudeSid = c.sid || ""; i.ctxHash = c.ctx || "";
    if (c.memo && !i.memo) i.memo = c.memo;
    if (i.thread && c.draft && !i.thread.draft) { i.thread.draft = c.draft; i.thread.aiDraft = !!c.aiDraft; }
  }
  const hashOf = (s) => { let h = 5381; for (let k = 0; k < s.length; k++) h = ((h << 5) + h + s.charCodeAt(k)) | 0; return (h >>> 0).toString(36) + ":" + s.length; };
  const cut = (s, n) => { s = String(s || ""); return s.length > n ? s.slice(0, n) + `…（以下 ${s.length - n} 文字省略）` : s; };
  const jstToday = () => { const d = new Date(Date.now() + 9 * 3600e3); return `${d.toISOString().slice(0, 10)}（${"日月火水木金土"[d.getUTCDay()]}）`; };

  // ボールの中身を Claude に渡す形にする。スレッド部分（大きい）と、メモ・下書き（よく変わる）は分けて持つ
  function threadText(i) {
    const t = i.thread; if (!t) return "（スレッドなし）";
    if (t.kind === "gmail") {
      const msgs = t.live ? (t.data ? t.data.messages : null) : t.messages;
      if (!msgs) return t.error ? `（スレッドを読めませんでした: ${t.error}）` : "（スレッドは未読み込み）";
      return `Gmail スレッド（id: ${t.threadId || "見本"}、古い順）\n` + msgs.map((m) => `--- ${m.date}\n差出人: ${m.from}\n宛先: ${m.to}${m.cc ? "\nCC: " + m.cc : ""}\n件名: ${m.subject}${(m.attachments || []).length ? "\n添付: " + m.attachments.map((a) => a.filename).join(", ") : ""}\n\n${cut(i.notes ? m.body : trimQuote(m.body).text, i.notes ? 30000 : 8000)}`).join("\n\n");
    }
    if (t.kind === "slack") {
      if (t.live) {
        if (!t.data) return t.error ? `（読めませんでした: ${t.error}）` : "（未読み込み）";
        const ppl = slackPeople(t).map((p) => p.name);
        return `Slack ${t.where}${t.threadTs ? " のスレッド" : ""}（古い順）\n` + (ppl.length ? `メンションできる人（下書きに「@名前」と書けば、送るときに本物のメンションになります）: ${ppl.map((n) => "@" + n).join(" ")}\n` : "") + t.data.messages.map((m) => `--- ${new Date(parseFloat(m.ts) * 1000).toLocaleString("ja-JP")} ${m.name}${m.mine ? "（片山）" : ""}\n${m.text}${m.files.length ? "\n添付: " + m.files.map((f) => f.name).join(", ") : ""}${m.reactions.length ? "\nリアクション: " + m.reactions.map((r) => `:${r.name}:${r.mine ? "(自分)" : ""}`).join(" ") : ""}`).join("\n");
      }
      return `Slack ${t.ch}（見本）\n` + t.msgs.map((m) => `--- ${m[2]} ${m[1]}\n${m[3]}`).join("\n");
    }
    if (t.kind === "msgr") {
      const msgs = t.live ? (t.data ? t.data.messages : null) : t.messages;
      if (!msgs) return t.error ? `（読めませんでした: ${t.error}）` : "（未読み込み）";
      return `Messenger ${t.name}さんとの会話（古い順・時刻は取れていません）\n` + msgs.map((m) => `${m.mine ? "片山" : t.name}: ${m.image ? "（写真）" : m.text}`).join("\n");
    }
    if (t.kind === "cal") {
      const e = t.ev || {};
      return `予定: ${e.summary}\n日時: ${e.start} 〜 ${e.end}\n場所: ${e.location || "-"}\n主催: ${e.organizer || "-"}\n参加者: ${(e.attendees || []).map((a) => `${a.name}(${a.status || "?"})`).join(", ")}\nMeet: ${e.meet || "-"}\n説明:\n${cut(e.description, 6000)}`;
    }
    return "（スレッドなし）";
  }
  function ballParts(i) {
    const pj = D.projects[i.proj] || {};
    const src = { gmail: "Gmail", slack: "Slack", msgr: "Messenger", cal: "カレンダー" }[i.src] || (i.thread && i.thread.kind) || "手入力";
    const head = [`ボール: ${i.title}`, `出どころ: ${src}`, pj.name ? `分類: ${pj.name}` : "", i.sub ? `補足: ${i.sub}` : "", (i.chips || []).length ? `状態: ${i.chips.map((c) => c[0]).join(" / ")}` : "", i.notes ? "種類: 会議メモ（Gemini）" : ""].filter(Boolean).join("\n");
    let extra = "";
    if (i.notes && i.thread && i.thread.kind === "gmail") {
      const msgs = i.thread.live ? (i.thread.data ? i.thread.data.messages : []) : i.thread.messages;
      const nd = notesDocs(msgs);
      if (nd.length) extra = "\n会議メモの元（docs_read で読めます）:\n" + nd.map((d) => `・${d.label}: ${d.url}`).join("\n");
    }
    return { body: head + extra + "\n\n" + cut(threadText(i), 90000), memo: i.memo || "", draft: (i.thread && i.thread.draft) || "" };
  }
  function buildPrompt(i, text, perm) {
    const p = ballParts(i);
    const hBody = hashOf(p.body), hSide = hashOf(p.memo + "\u0001" + p.draft);
    const [oldBody, oldSide] = String(i.ctxHash || "").split("|");
    const permLine = `今の権限: ${$("perm").value}`;
    let pre = "";
    if (!i.claudeSid || oldBody !== hBody) {
      pre = `<ball>\n今日: ${jstToday()}\n${permLine}\n\n${p.body}\n\n今のメモ:\n${p.memo || "（なし）"}\n\n今の下書き欄:\n${p.draft || "（空）"}\n</ball>\n\n`;
    } else if (oldSide !== hSide) {
      pre = `<ball_update>\n${permLine}\n今のメモ:\n${p.memo || "（なし）"}\n\n今の下書き欄:\n${p.draft || "（空）"}\n</ball_update>\n\n`;
    } else pre = `（${permLine}）\n\n`;
    return { prompt: pre + text, hash: hBody + "|" + hSide };
  }
  // 送る前に、まだ読んでいないスレッドを読んでおく（Claude が中身を知った状態で答えられるように）
  async function ensureThread(i) {
    const t = i.thread; if (!t || !t.live || t.data || t.loading || !IS_APP) return;
    try {
      if (t.kind === "gmail") { const r = await window.ball.gmailThread(t.threadId); if (r.ok) t.data = r.data; }
      else if (t.kind === "slack") { const r = await window.ball.slackThread({ channel: t.channel, threadTs: t.threadTs }); if (r.ok) t.data = r; }
      else if (t.kind === "msgr") { const r = await window.ball.messengerThread({ href: t.href, name: t.name, steps: t.steps || 4 }); if (r.ok && r.messages && r.messages.length) t.data = r; }
    } catch (e) { /* 読めなくても、分かっている範囲で答える */ }
  }
  const TOOL_LABEL = {
    gmail_search: (a) => `Gmail を検索：${a.query || ""}`, gmail_read_thread: () => "メールのスレッドを読む",
    calendar_events: (a) => `カレンダーを見る（${a.days || 7}日分）`, drive_search: (a) => `Drive を検索：${a.query || ""}`,
    docs_read: () => "ドキュメントを読む", sheets_read: (a) => `シートを読む：${a.range || ""}`, sheets_write: (a) => `シートに記入：${a.range || ""}`,
    ball_set_draft: () => "下書き欄に入れる（未送信）", ball_set_memo: () => "メモに書く",
  };
  let feedTick = 0;
  function refreshFeed(i) {
    if (curItem() !== i || S.ctab !== "chat") return;
    if (feedTick) return;
    feedTick = requestAnimationFrame(() => {
      feedTick = 0;
      if (curItem() !== i || S.ctab !== "chat") return;
      const f = $("feed"), atBottom = f.scrollHeight - f.scrollTop - f.clientHeight < 80;
      f.innerHTML = feedHtml(i); bindLinks(f);
      if (atBottom) f.scrollTop = f.scrollHeight;
      renderState(i);
    });
  }
  async function askClaude(i, text) {
    const perm = PERMS[$("perm").value] || "full", model = MODEL_KEYS[$("model").value] || "opus";
    i.feed.push(["me", text]);
    const run = running[i.id] = { reqId: null, cur: null, note: "ボールの中身を読んでいます…" };
    S.ctab = "chat"; center();
    await ensureThread(i);
    const { prompt, hash } = buildPrompt(i, text, perm);
    run.hash = hash; run.note = "考えています…"; refreshFeed(i);
    const r = await window.ball.claudeAsk({ ballId: i.id, sessionId: i.claudeSid || "", prompt, model, perm });
    if (!r.ok) { delete running[i.id]; i.feed.push(["err", "Claude を呼べませんでした：" + r.error]); saveChat(i); center(); return; }
    run.reqId = r.reqId;
    if (run.stopAsked) window.ball.claudeStop(r.reqId);
  }
  function onClaudeEvent(ev) {
    const i = items.find((x) => x.id === ev.ballId), run = running[ev.ballId];
    if (!i || !run || (run.reqId && run.reqId !== ev.reqId)) return;
    if (ev.type === "start") { if (ev.sessionId) i.claudeSid = ev.sessionId; lastInit = ev; }
    else if (ev.type === "delta") {
      if (run.cur == null) { i.feed.push(["ai", ""]); run.cur = i.feed.length - 1; }
      i.feed[run.cur][1] += ev.text; run.note = "書いています…";
    } else if (ev.type === "tool") {
      run.cur = null;
      const label = (TOOL_LABEL[ev.name] || (() => ev.name))(ev.input || {});
      i.feed.push(["prog", label]); run.note = label;
    } else if (ev.type === "toolError") {
      i.feed.push(["prog", "うまくいきませんでした：" + String(ev.text || "").slice(0, 160)]);
    } else if (ev.type === "done" || ev.type === "error") {
      delete running[i.id];
      if (ev.sessionId) i.claudeSid = ev.sessionId;
      (ev.denied || []).forEach((d) => i.feed.push(["prog", "許可していない道具なので止めました：" + d]));
      if (ev.stopped) i.feed.push(["prog", "止めました"]);
      else if (ev.type === "error" || ev.isError) {
        const msg = String(ev.error || "エラー");
        // 会話が見つからない（Claude Code 側で消えた）ときは、次は新しい会話で始める
        if (/No conversation found|session.*not found|--resume/i.test(msg)) { i.claudeSid = ""; i.ctxHash = ""; }
        i.feed.push(["err", "Claude でエラーになりました：" + msg.slice(0, 600)]);
      } else i.ctxHash = run.hash;
      // 空の吹き出しは消す
      i.feed = i.feed.filter(([k, t]) => !(k === "ai" && !t));
      saveChat(i);
      if (curItem() === i) center(); else left();
      return;
    }
    refreshFeed(i);
  }
  // Claude の道具のうち、画面の中身を変えるもの（下書き欄・メモ）
  function onClaudeTool(req, reply) {
    const i = items.find((x) => x.id === req.ballId);
    if (!i) return reply({ ok: false, error: "このボールはもう一覧にありません" });
    const a = req.args || {};
    if (req.name === "ball_set_draft") {
      const text = String(a.text || "").trim();
      if (!text) return reply({ ok: false, error: "下書きが空です" });
      const t = i.thread;
      if (!t || t.kind === "cal") {
        i.memo = (i.memo ? i.memo.replace(/\s+$/, "") + "\n\n" : "") + "【下書き】\n" + text; saveChat(i);
        if (curItem() === i && S.ctab === "memo") center();
        return reply({ ok: true, text: "このボールには返信先のスレッドが無いので、メモ欄に【下書き】として入れました（送信はしていません）" });
      }
      t.draft = text; t.aiDraft = true;
      if (t.kind === "gmail") { if (a.to) t.to = String(a.to); if (a.cc != null && a.cc !== "") t.cc = String(a.cc); }
      saveChat(i);
      if (curItem() === i) { S.rmode = "thread"; right(); }
      const where = t.kind === "gmail" ? "Gmail の返信" : t.kind === "msgr" ? "Messenger の返信" : "Slack の返信";
      return reply({ ok: true, text: `${where}の下書き欄に入れました。まだ送信していません（Gmail の下書きにも未保存）。送るのは片山さんが確認してからです。` });
    }
    if (req.name === "ball_set_memo") {
      const text = String(a.text || "");
      i.memo = a.mode === "replace" ? text : (i.memo ? i.memo.replace(/\s+$/, "") + "\n\n" : "") + text;
      saveChat(i);
      if (curItem() === i && S.ctab === "memo") center();
      return reply({ ok: true, text: "メモ欄に書きました" });
    }
    reply({ ok: false, error: "知らない道具です" });
  }
  async function checkClaude() {
    if (!IS_APP || !window.ball.claudeStatus) { setFt("ft-claude", "Claude 見本（アプリ版でつながります）", "mock"); return; }
    setFt("ft-claude", "Claude 確認中…", "mock");
    claudeState = await window.ball.claudeStatus();
    if (claudeState.ok) setFt("ft-claude", "Claude つながっています", "");
    else setFt("ft-claude", "Claude: 見つかりません（押して詳細）", "ng");
  }
  $("ft-claude").onclick = () => {
    if (!IS_APP) return toast("真ん中の Claude はデスクトップアプリ版でつながります");
    if (claudeState && !claudeState.ok) return showInfo("Claude（Claude Code）が見つかりません", claudeState.error + "\n\nターミナルで次が動けば OK です:\n  claude --version\n\nclaude が別の場所にあるなら、BALL_CLAUDE=<claude のパス> npm start で起動してください。", "もう一度確かめる", checkClaude);
    const skills = lastInit ? lastInit.skills.filter((x) => !/^(session-start-hook|update-config|verify|debug|code-review|simplify|batch|fewer-permission-prompts|doctor|loop|claude-api|workflow-authoring|run|run-skill-generator|plugin-authoring|design|design-sync|slides|dataviz|artifact-|cowork-plugin)/.test(x)) : [];
    const tri = triageOff() ? "止めています" : `動いています（判断 ${judgeStat.n}件${judgeStat.err ? `・直近のエラー: ${judgeStat.err}` : ""}）`;
    showInfo("真ん中の Claude", `巡回の判断: ${tri}\n新しく来たメール・Slack・Messenger を Claude が見て、返信が要るか・どの案件か・どのボールの続きかを決めます\n\nClaude Code ${claudeState ? claudeState.version : ""}（${claudeState ? claudeState.path : ""}）
作業フォルダ: ${(lastInit && lastInit.cwd) || (claudeState && claudeState.cwd) || ""}

・いつもの Claude Code と同じ CLAUDE.md・メモリー・スキル（アカウントのスキルも）・ルーティン・コネクタ・gog で動きます。ボールごとに会話が続きます
・許可の判断は Claude Code の auto モード（危ない操作は自動で止まる）と、普段の許可設定のとおりです
・止めてあるもの（送信の絶対ルール）: メールの送信・返信・転送、Slack の投稿・リアクション、カレンダーの招待・変更・出欠の返事、Drive の共有。送るのは右の「送信…」を自分で押したときだけです
${lastInit ? `\n直近の会話で読み込まれたもの:\n・スキル ${skills.length} 個: ${skills.join(", ")}\n・コネクタ: ${lastInit.mcp.join(", ") || "なし"}` : "\n（一度話しかけると、読み込まれたスキルとコネクタがここに出ます）"}`,
      triageOff() ? "巡回の判断を再開する" : "巡回の判断を止める", () => { try { localStorage.setItem("ball.triage.off", triageOff() ? "0" : "1"); } catch (e) {} toast(triageOff() ? "巡回の判断を止めました" : "巡回の判断を再開しました"); $("infoDlg").hidden = true; queueJudge(); });
  };
  if (IS_APP && window.ball.onClaude) { window.ball.onClaude(onClaudeEvent); window.ball.onClaudeTool(onClaudeTool); }
  checkClaude();

  // ---------- 巡回の判断: 新しく来たものだけ Claude に見てもらう ----------
  // 返信が要るか・どの案件か・どのボールの続きか・一言の要約と次にやること・CC の注意。
  // 返事が要らないものは消さずに「返事不要（AI 判断）」にまとめる。判断はこの Mac に覚えておき、同じものは二度聞かない
  const JUDGE_KEY = "ball.judged.v1";
  let judgedStore = null, judging = false, judgeTimer = 0, judgeStat = { n: 0, at: 0, err: "" };
  const judged = () => { if (!judgedStore) { try { judgedStore = JSON.parse(localStorage.getItem(JUDGE_KEY) || "{}") || {}; } catch (e) { judgedStore = {}; } } return judgedStore; };
  const saveJudged = () => { const st = judged(), ks = Object.keys(st); if (ks.length > 1500) ks.slice(0, ks.length - 1500).forEach((k) => delete st[k]); try { localStorage.setItem(JUDGE_KEY, JSON.stringify(st)); } catch (e) { /* 覚えられなくても動く */ } };
  const triageOff = () => { try { return localStorage.getItem("ball.triage.off") === "1"; } catch (e) { return false; } };
  const judgeKey = (x) => x.id + "|" + (x.origTitle || x.title) + "|" + x.sub;
  const KIND_CHIP = { reply: ["返信が要る", "me"], todo: ["作業あり", "me"], fyi: ["読むだけ", "them"], done: ["片付き済み", "them"] };
  function applyJudged(x) {
    if (x.title !== x.aiTitle) x.origTitle = x.title; // 読み込み直しで件名が元に戻っていたら、そちらが元の件名
    const j = judged()[judgeKey(x)];
    if (!j) return false;
    x.judged = j;
    x.aiTitle = j.title || x.origTitle;
    x.title = x.aiTitle;
    if ((x.proj === "none" || !x.proj) && j.project && D.projects[j.project]) x.proj = j.project;
    const target = j.mergeInto && items.find((y) => y.id === j.mergeInto);
    const chips = (x.chips || []).filter((c) => !c.ai);
    const kc = KIND_CHIP[j.kind]; if (kc) { const c = kc.slice(); c.ai = true; chips.unshift(c); }
    if (target) { const c = [`続き: ${target.title.slice(0, 14)}`, "them"]; c.ai = true; chips.push(c); }
    x.chips = chips;
    if (j.kind === "fyi" || j.kind === "done") x.sec = "fyi";
    x.ccWarn = j.ccWarning || "";
    if (!x.judgedFeed && !x.claudeSid) {
      x.judgedFeed = true;
      x.feed.push(["prog", "巡回で判断（AI）"], ["ai", `${j.summary}${j.next ? `\n次にやること: ${j.next}` : ""}${j.ccWarning ? `\n⚠ ${j.ccWarning}` : ""}${target ? `\n（「${target.title}」の続きです）` : ""}`]);
    }
    return true;
  }
  function judgeText(x) {
    const ai = (x.feed || []).find((f) => f[0] === "ai");
    return cut((ai ? ai[1] : "").replace(/右にスレッド[\s\S]*$/, "").replace(/返信はここで頼めます[\s\S]*$/, ""), 600);
  }
  function queueJudge() {
    let changed = false;
    items.forEach((x) => { if (x.live && applyJudged(x)) changed = true; });
    if (changed) left();
    if (!IS_APP || !window.ball.claudeJudge || triageOff() || (claudeState && !claudeState.ok)) return;
    clearTimeout(judgeTimer);
    judgeTimer = setTimeout(runJudge, 6000);
  }
  async function runJudge() {
    if (judging) return;
    items.forEach((x) => { if (x.title !== x.aiTitle) x.origTitle = x.title; });
    const todo = items.filter((x) => x.live && ["gmail", "slack", "msgr"].includes(x.src) && !x.done && !x.hidden && !judged()[judgeKey(x)]).slice(0, 6);
    if (!todo.length) return;
    judging = true;
    setFt("ft-claude", `Claude 巡回の判断中…（${todo.length}件）`, "");
    const batch = todo.map((x) => ({ key: judgeKey(x), source: { gmail: "Gmail", slack: "Slack", msgr: "Messenger" }[x.src], title: x.origTitle || x.title, from: x.sub, text: judgeText(x), notes: !!x.notes }));
    const balls = items.filter((x) => !x.done && !x.hidden && !todo.includes(x) && x.id !== "home").slice(0, 80).map((x) => ({ id: x.id, title: x.title, project: x.proj }));
    const r = await window.ball.claudeJudge({ items: batch, balls, model: MODEL_KEYS[$("model").value] || "opus" });
    judging = false;
    if (!r.ok) {
      judgeStat.err = r.error; judgeStat.fails = (judgeStat.fails || 0) + 1;
      setFt("ft-claude", "Claude: 巡回の判断でエラー（押して詳細）", "ng");
      // 3回続けて失敗するまでは、少し待って取り直す
      if (judgeStat.fails < 3) judgeTimer = setTimeout(runJudge, 60000);
      return;
    }
    judgeStat.fails = 0;
    const st = judged();
    for (const j of r.items) if (j && j.key && batch.some((b) => b.key === j.key)) st[j.key] = { ...j, at: Date.now() };
    // 答えが返ってこなかったものも、同じものを何度も聞かないように印を付ける
    for (const b of batch) if (!st[b.key]) st[b.key] = { key: b.key, kind: "reply", project: "none", title: "", summary: "", next: "", mergeInto: "", ccWarning: "", at: Date.now(), missing: true };
    saveJudged();
    judgeStat = { n: judgeStat.n + batch.length, at: Date.now(), err: "" };
    todo.forEach((x) => applyJudged(x));
    left(); if (todo.includes(curItem())) { center(); right(); }
    setFt("ft-claude", `Claude つながっています · 判断 ${judgeStat.n}件`, "");
    if (items.some((x) => x.live && ["gmail", "slack", "msgr"].includes(x.src) && !x.done && !x.hidden && !judged()[judgeKey(x)])) judgeTimer = setTimeout(runJudge, 3000);
  }

  $("comp").onsubmit = (e) => {
    e.preventDefault();
    const i = curItem();
    const run = running[i.id];
    if (run) { run.stopAsked = true; if (run.reqId) window.ball.claudeStop(run.reqId); run.note = "止めています…"; renderState(i); return; }
    const t = $("compText").value.trim(); if (!t) return;
    $("compText").value = "";
    if (!IS_APP || !window.ball.claudeAsk) {
      i.feed.push(["me", t], ["ai", "了解です。（ブラウザ版の見本なので、返事の例だけ出しています。デスクトップアプリ版では、このボールの中身を知った Claude が実際に答えます）"]);
      S.ctab = "chat"; center(); return;
    }
    if (claudeState && !claudeState.ok) { i.feed.push(["me", t], ["err", "Claude（Claude Code）が見つかりません。下のステータス行の「Claude」を押すと確かめ方が出ます"]); center(); return; }
    askClaude(i, t);
  };
  $("compText").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); $("comp").requestSubmit(); } });
  $("addForm").onsubmit = (e) => {
    e.preventDefault();
    const t = $("addInput").value.trim(); if (!t) return;
    const it = { id: "n" + Date.now(), at: Date.now(), sec: "me", proj: "in", src: "doc", title: t, sub: "手入力", chips: [["新規", "me"]], ago: "今", feed: [["ai", "ボールにしました。関係するスレッドや予定があれば紐づけます。"]], memo: "", thread: null, tabs: [{ title: "新しいタブ", url: "https://www.google.com/", sim: "plain" }], activeTab: 0 };
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

  // ---------- Messenger の取り込み（アプリ版のみ） ----------
  // 未読 → 自分ボール。既読でも相手の発言で止まっている上位の会話 → 自分ボール（既読・未返信）。
  // 自分が最後に返した会話はボールにしない。前回ボールだったものが返信済みになったら自動で閉じる。
  function agoText(ms) { const m = Math.round((Date.now() - ms) / 60000); return m < 1 ? "たった今" : m + "分前"; }
  function msgrStatus(data) {
    const el = $("ft-msgr");
    el.classList.remove("mock", "ng");
    let text;
    if (!data) { text = "Messenger 読み取り準備中"; el.classList.add("mock"); }
    else if (data.status === "login") { text = "Messenger: 読み取り画面でログインが必要（押す →「読み取り画面を見る」）"; el.classList.add("ng"); }
    else if (data.status === "away") { text = "Messenger: " + (data.note || "Messenger 以外のページにいます"); el.classList.add("mock"); }
    else if (data.status === "nolist") { text = data.note ? "Messenger: " + data.note : "Messenger: 会話一覧が読めません（右で Messenger を開いて押す）"; el.classList.add("ng"); }
    else text = `Messenger ${agoText(data.at)} · 会話${data.convos.length}件・未読${data.convos.filter((c) => c.unread).length}`;
    el.querySelector("span").textContent = text;
  }
  let lastMsgrData = null;
  // 仕事と関係ない相手は出さない。最初から外すもの + 「今後この相手を出さない」で足したもの（この Mac に保存）
  const MUTE_DEFAULT = [/nu\s*star/i, /voyage\w*\s*poker/i];
  const mutedNames = () => { try { return JSON.parse(store.get("ball.msgrMute") || "[]"); } catch (e) { return []; } };
  const isMuted = (name) => MUTE_DEFAULT.some((re) => re.test(name || "")) || mutedNames().includes(name);
  function muteName(name) { const l = mutedNames(); if (!l.includes(name)) l.push(name); store.set("ball.msgrMute", JSON.stringify(l)); }
  function applyMessenger(data) {
    lastMsgrData = data;
    msgrStatus(data);
    if (!data || data.status !== "ok") return;
    // 見本の Messenger ボールは本物が来たら外す
    const mock = items.find((x) => x.id === "msgr"); if (mock) mock.hidden = true;
    const want = new Map();
    data.convos.filter((c) => !isMuted(c.name)).forEach((c, idx) => {
      if (c.unread || (!c.mine && idx < 8)) want.set("m-" + c.id, c);
    });
    // 返信済みになったものは閉じる
    items.filter((x) => x.msgr && !x.done && !want.has(x.id)).forEach((x) => {
      x.done = true; D.closed.unshift(`Messenger: ${x.msgrName} · 返信済み`);
    });
    want.forEach((c, id) => {
      let it = items.find((x) => x.id === id);
      const chips = [[c.unread ? "未読" : "既読・未返信", c.unread ? "warn" : "me"]];
      if (c.time) chips.push([c.time, "them"]);
      const fields = {
        sec: "me", proj: "none", src: "msgr", ago: c.time || "", at: relTime(c.time), msgr: true, msgrName: c.name, done: false, hidden: false,
        title: `Messenger：${c.name}`, sub: c.snippet ? c.snippet.slice(0, 40) : "Facebook メッセンジャー", chips,
      };
      if (!it) {
        it = Object.assign({ id, memo: "", activeTab: 0,
          thread: { kind: "msgr", live: true, href: c.href, name: c.name, draft: "" },
          feed: [["prog", "Messenger から自動で取り込み"], ["ai", `${c.name}さんとの会話です。${c.unread ? "未読があります。" : "相手の発言で止まっています。"}\n最後のメッセージ：${c.snippet || "（読み取れず）"}\n\n右に直近のやり取りを出しています。返信はここで頼めます（例:「返信の下書き書いて」）。下書きは右の下書き欄に入り、送るのは自分です。`]],
          tabs: [{ title: `${c.name} - Messenger`, url: c.href, sim: "messenger", key: id + "-0" }] }, fields);
        items.unshift(it);
      } else {
        // 新しいメッセージが来ていたら、スレッドは読み直す
        if (it.sub !== fields.sub && it.thread) { it.thread.data = null; it.thread.error = null; }
        Object.assign(it, fields);
      }
    });
    left();
    queueJudge();
  }
  // エラーの中身などを出す小さな画面（コピーできる）
  function showInfo(title, text, actionLabel, action) {
    let el = $("infoDlg");
    if (!el) { el = document.createElement("div"); el.id = "infoDlg"; el.className = "ov"; document.body.appendChild(el); el.onclick = (e) => { if (e.target === el) el.hidden = true; }; }
    el.innerHTML = `<div class="ovc" role="dialog" aria-modal="true" style="max-width:720px"><h2>${esc(title)}</h2>
      <pre id="infoText" style="white-space:pre-wrap;font-family:var(--f-mono);font-size:11.5px;background:var(--soft);border-radius:8px;padding:12px;max-height:50vh;overflow:auto;margin:0">${esc(text)}</pre>
      <div class="ovf"><span class="hint">ログイン情報（トークン）は含まれていません。このままコピーして Claude に送ってください</span><span>${actionLabel ? `<button type="button" class="btn" id="infoAct">${esc(actionLabel)}</button> ` : ""}<button type="button" class="btn" id="infoCopy">コピー</button> <button type="button" class="btn dark" id="infoClose">閉じる</button></span></div></div>`;
    el.hidden = false;
    $("infoClose").onclick = () => (el.hidden = true);
    $("infoCopy").onclick = () => navigator.clipboard.writeText(text).then(() => toast("コピーしました"), () => toast("選択して ⌘C でコピーしてください"));
    if (actionLabel) $("infoAct").onclick = () => { el.hidden = true; action(); };
  }

  // Messenger 読み取りの診断（名前・本文は含まない）。コピーして送ってもらう用
  function showMsgrDiag(data) {
    const info = { status: data.status, convos: (data.convos || []).length, unread: (data.convos || []).filter((c) => c.unread).length, mine: (data.convos || []).filter((c) => c.mine).length, note: data.note || "", diag: data.diag || null };
    const text = JSON.stringify(info, null, 1);
    let el = $("diag");
    if (!el) {
      el = document.createElement("div"); el.id = "diag"; el.className = "ov";
      el.innerHTML = `<div class="ovc" role="dialog" aria-modal="true" aria-labelledby="diagTitle" style="max-width:720px">
        <h2 id="diagTitle">Messenger 読み取りの診断</h2>
        <p class="hint">名前やメッセージの中身は入っていません。画面の作りだけです。うまく読めないときは、これをコピーして Claude に送ってください。「読み取り画面を見る」で、裏で開いている Messenger の画面をそのまま見られます（PIN の入力やログインが出ていたら、そこで済ませてください。閉じるとまた見えなくなります）。</p>
        <pre id="diagText" style="white-space:pre-wrap;font-family:var(--f-mono);font-size:11.5px;background:var(--soft);border-radius:8px;padding:12px;max-height:50vh;overflow:auto;margin:0"></pre>
        <div class="ovf"><span class="hint">右のブラウザで Messenger の一覧を開いて下の帯を押すと、そのページを読むように切り替わります</span><span><button type="button" class="btn" id="diagShow">読み取り画面を見る</button> <button type="button" class="btn" id="diagCopy">コピー</button> <button type="button" class="btn dark" id="diagClose">閉じる</button></span></div></div>`;
      document.body.appendChild(el);
      el.onclick = (e) => { if (e.target === el) el.hidden = true; };
      $("diagClose").onclick = () => (el.hidden = true);
      // 透明にしている読み取り画面を見えるようにする（PIN 入力やログインが出ていないか確認・操作できる。閉じると透明に戻る）
      $("diagShow").onclick = () => { el.hidden = true; if (IS_APP) window.ball.messengerShow(); else toast("アプリ版で使えます"); };
      $("diagCopy").onclick = () => {
        const tx = $("diagText").textContent;
        navigator.clipboard.writeText(tx).then(() => toast("コピーしました"), () => { const r = document.createRange(); r.selectNodeContents($("diagText")); getSelection().removeAllRanges(); getSelection().addRange(r); toast("選択しました。⌘C でコピーしてください"); });
      };
    }
    $("diagText").textContent = text;
    el.hidden = false;
  }

  // ---------- Gmail の取り込み（アプリ版のみ・Mac の gog 経由） ----------
  // 受信トレイで「最後のメールが自分以外の人から」のスレッドを自分ボールにする。返信すると次の取り込みで閉じる。
  function setFt(id, text, cls) {
    const el = $(id); if (!el) return;
    el.classList.remove("mock", "ng"); if (cls) el.classList.add(cls);
    el.querySelector("span").textContent = text;
  }
  // ---------- Slack の取り込み（アプリ版のみ・BALL の中でログインした Slack から） ----------
  // 自分宛てメンションと、相手の発言で止まっている DM → 自分ボール。
  // 自分が返信した・✅ など完了のスタンプを押した → 閉じる。👍 など了解のスタンプ → 「了解済み」で残す
  let slackData = null;
  const slackAgo = (ms) => { const h = (Date.now() - ms) / 3600e3; return h < 1 ? Math.max(1, Math.round(h * 60)) + "分前" : h < 24 ? Math.round(h) + "時間前" : Math.round(h / 24) + "日前"; };
  // 一覧の件名や引用用に、リンクの書式（[名前](URL)）と *太字* の記号を落とす
  const flat = (s) => String(s || "").replace(/\[([^\]\n]+)\]\((https?:[^)\s]+)\)/g, "$1").replace(/(^|\s)\*([^*\n]+)\*/g, "$1$2");
  function applySlack(data) {
    slackData = data;
    if (data.status === "login") return setFt("ft-slack", "Slack: 読み取り画面でログインが必要（押す）", "ng");
    if (data.status !== "ok") return setFt("ft-slack", "Slack: エラー（" + String(data.error || "").replace(/^[\w.]+:\s*/, "").slice(0, 60) + "）押して詳細", "ng");
    items.filter((x) => x.src === "slack" && !x.live).forEach((x) => (x.hidden = true));
    const ids = new Set();
    data.items.forEach((m) => {
      const id = "s-" + m.channel + "-" + m.ts; ids.add(id);
      const where = m.kind === "dm" ? (m.channelName ? m.channelName : `${m.userName}さんとの DM`) : `#${m.channelName}`;
      const chips = [];
      if (m.state === "ack") chips.push([`${m.unsureEmoji ? "スタンプ" : "了解"}済み :${m.emoji}:`, "them"]);
      else chips.push([m.kind === "dm" ? "DM・未返信" : "未返信", "me"]);
      chips.push([slackAgo(m.at), "them"]);
      const fields = {
        sec: "me", proj: "none", src: "slack", live: true, hidden: false, done: false, at: m.at || 0,
        title: `${m.userName}：${flat(m.text).replace(/\s+/g, " ").slice(0, 34)}`, sub: where, ago: "", chips,
      };
      let it = items.find((x) => x.id === id);
      if (!it) {
        it = Object.assign({ id, memo: "", activeTab: 0,
          feed: [["prog", "Slack から自動で取り込み"], ["ai", `${where} で ${m.userName}さんから${m.kind === "dm" ? "の DM" : "メンション"}です。${m.state === "ack" ? `\n:${m.emoji}: を押してあるので返信は済み扱いです。作業が残っていれば、ここで片付けます。` : ""}\n\n「${flat(m.text).slice(0, 120)}」\n\n右にスレッドを出しています。返信の下書きはここで頼めます。下書きは右の下書き欄に入り、送るのは「送信…」で確認したときだけです。`]],
          thread: { kind: "slack", live: true, channel: m.channel, threadTs: m.threadTs, ts: m.ts, where, permalink: m.permalink, draft: "" },
          tabs: m.permalink ? [{ title: "Slack", url: m.permalink, sim: "slack", key: id + "-0" }] : [{ title: "Slack", url: "https://app.slack.com/client", sim: "slack", key: id + "-0" }] }, fields);
        items.unshift(it);
      } else { Object.assign(it, fields); }
    });
    // 一覧から消えた（返信した・完了のスタンプを押した）ものは閉じる
    items.filter((x) => x.live && x.src === "slack" && !x.done && !ids.has(x.id)).forEach((x) => { x.done = true; D.closed.unshift(`Slack: ${x.title.slice(0, 30)} · 返信済み`); });
    const n = data.items.length, dm = data.items.filter((x) => x.kind === "dm").length;
    setFt("ft-slack", `Slack ${agoText(data.at)} · メンション${n - dm}・DM${dm}${data.warn ? "（DM 一覧は読めず・押して詳細）" : ""}`, data.warn ? "mock" : "");
    queueJudge();
    left();
  }
  // ---------- Slack のスレッドを、本物の Slack に近い見た目で出す ----------
  // 書式（*太字* _斜体_ ~取り消し~ `コード` ```ブロック``` > 引用）・絵文字（標準とカスタム）・メンション・画像のサムネイル・ファイル
  const STD_EMOJI = {
    "+1": "👍", thumbsup: "👍", "-1": "👎", thumbsdown: "👎", pray: "🙏", bow: "🙇", "man-bowing": "🙇‍♂️", "woman-bowing": "🙇‍♀️", "person_bowing": "🙇",
    smile: "😄", smiley: "😃", grinning: "😀", laughing: "😆", satisfied: "😆", joy: "😂", rofl: "🤣", sweat_smile: "😅", blush: "😊", wink: "😉", relaxed: "☺️",
    heart_eyes: "😍", kissing_heart: "😘", yum: "😋", sunglasses: "😎", thinking_face: "🤔", thinking: "🤔", neutral_face: "😐", expressionless: "😑", smirk: "😏",
    unamused: "😒", sweat: "😓", pensive: "😔", confused: "😕", upside_down_face: "🙃", astonished: "😲", flushed: "😳", scream: "😱", cry: "😢", sob: "😭",
    disappointed: "😞", worried: "😟", angry: "😠", rage: "😡", triumph: "😤", sleepy: "😪", sleeping: "😴", mask: "😷", innocent: "😇", partying_face: "🥳",
    pleading_face: "🥺", hugging_face: "🤗", hugs: "🤗", face_with_rolling_eyes: "🙄", zany_face: "🤪", shushing_face: "🤫", exploding_head: "🤯", star_struck: "🤩",
    eyes: "👀", eye: "👁️", white_check_mark: "✅", heavy_check_mark: "✔️", ballot_box_with_check: "☑️", x: "❌", o: "⭕", warning: "⚠️", no_entry: "⛔", question: "❓",
    exclamation: "❗", bangbang: "‼️", ok_hand: "👌", ok: "🆗", clap: "👏", raised_hands: "🙌", muscle: "💪", wave: "👋", point_up: "☝️", point_right: "👉", point_left: "👈",
    point_down: "👇", v: "✌️", handshake: "🤝", fist: "✊", punch: "👊", writing_hand: "✍️", tada: "🎉", confetti_ball: "🎊", sparkles: "✨", star: "⭐", star2: "🌟",
    fire: "🔥", "100": "💯", heart: "❤️", hearts: "♥️", blue_heart: "💙", green_heart: "💚", yellow_heart: "💛", purple_heart: "💜", broken_heart: "💔", rocket: "🚀",
    bulb: "💡", memo: "📝", pencil: "📝", pencil2: "✏️", calendar: "📆", date: "📅", clock: "🕐", hourglass: "⌛", alarm_clock: "⏰", mega: "📣", loudspeaker: "📢",
    bell: "🔔", email: "📧", envelope: "✉️", phone: "☎️", iphone: "📱", computer: "💻", chart_with_upwards_trend: "📈", chart_with_downwards_trend: "📉", bar_chart: "📊",
    moneybag: "💰", money_with_wings: "💸", yen: "💴", gift: "🎁", trophy: "🏆", medal: "🏅", crown: "👑", coffee: "☕", beer: "🍺", beers: "🍻", sushi: "🍣", ramen: "🍜",
    sunny: "☀️", cloud: "☁️", umbrella: "☔", zap: "⚡", snowflake: "❄️", rainbow: "🌈", seedling: "🌱", cherry_blossom: "🌸", sweat_drops: "💦", dash: "💨", zzz: "💤",
    boom: "💥", collision: "💥", speech_balloon: "💬", thought_balloon: "💭", arrow_right: "➡️", arrow_left: "⬅️", arrow_up: "⬆️", arrow_down: "⬇️", repeat: "🔁",
    link: "🔗", paperclip: "📎", pushpin: "📌", round_pushpin: "📍", mag: "🔍", lock: "🔒", key: "🔑", hammer: "🔨", wrench: "🔧", gear: "⚙️", package: "📦",
    car: "🚗", taxi: "🚕", train: "🚆", airplane: "✈️", house: "🏠", office: "🏢", japan: "🗾", jp: "🇯🇵", ghost: "👻", skull: "💀", robot_face: "🤖", see_no_evil: "🙈",
    raising_hand: "🙋", man_raising_hand: "🙋‍♂️", woman_raising_hand: "🙋‍♀️", ok_woman: "🙆", ok_man: "🙆‍♂️", no_good: "🙅", information_desk_person: "💁",
    dog: "🐶", cat: "🐱", pig: "🐷", panda_face: "🐼", bear: "🐻", hatching_chick: "🐣", tiger: "🐯", sob_cat: "😿", heavy_plus_sign: "➕", heavy_minus_sign: "➖",
  };
  function slackEmoji(name, ctx) {
    const base = name.replace(/::skin-tone-\d$/, "");
    const custom = ctx.emoji && ctx.emoji[base];
    if (custom) return `<img class="semoji" src="${esc(custom)}" alt=":${esc(base)}:" title=":${esc(base)}:" referrerpolicy="no-referrer">`;
    if (STD_EMOJI[base]) return `<span class="semoji u" title=":${esc(base)}:">${STD_EMOJI[base]}</span>`;
    return `<span class="semoji t">:${esc(base)}:</span>`;
  }
  function slackHtml(raw, ctx) {
    const out = [];
    String(raw || "").split(/```/).forEach((seg, k) => {
      if (k % 2) { out.push(`<pre class="scode">${esc(seg.replace(/^\n|\n$/g, ""))}</pre>`); return; }
      const ph = [];
      const keep = (h) => { ph.push(h); return "\u0001" + (ph.length - 1) + "\u0001"; };
      let t = seg
        .replace(/\[([^\]\n]{1,120})\]\((https?:\/\/[^)\s]+)\)/g, (m, l, u) => keep(`<button type="button" class="slink" data-url="${esc(u)}" data-label="${esc(l)}" title="${esc(u)}">${esc(l)}</button>`))
        .replace(/https?:\/\/[^\s<>"」）)]+/g, (u) => { const v = u.replace(/[.,、。]+$/, ""); return keep(`<button type="button" class="slink" data-url="${esc(v)}" data-label="${esc(hostOf(v))}" title="${esc(v)}">${esc(v.length > 70 ? v.slice(0, 68) + "…" : v)}</button>`) + u.slice(v.length); })
        .replace(/`([^`\n]+)`/g, (m, c) => keep(`<code class="sc">${esc(c)}</code>`));
      t = esc(t);
      // メンション（自分宛ては黄色）
      const names = [...(ctx.people || []).map((p) => p.name), ctx.selfName].filter(Boolean).sort((a, b) => b.length - a.length);
      for (const n of names) t = t.split(esc("@" + n)).join(keep(`<span class="smen${n === ctx.selfName ? " me" : ""}">@${esc(n)}</span>`));
      t = t.replace(/@(here|channel|everyone)\b/g, (m) => keep(`<span class="smen me">${m}</span>`));
      // 書式
      const edge = "(^|[\\s(（「『、。!！?？:：])";
      t = t.replace(new RegExp(edge + "\\*([^*\\n]+)\\*(?=$|[\\s)）」』、。!！?？.,:：])", "g"), "$1<b>$2</b>")
        .replace(new RegExp(edge + "_([^_\\n]+)_(?=$|[\\s)）」』、。!！?？.,:：])", "g"), "$1<i>$2</i>")
        .replace(new RegExp(edge + "~([^~\\n]+)~(?=$|[\\s)）」』、。!！?？.,:：])", "g"), "$1<s>$2</s>")
        .replace(/:([a-z0-9_+'-]+(?:::skin-tone-\d)?):/gi, (m, n) => slackEmoji(n, ctx));
      // 引用（> で始まる行）
      t = t.split("\n").map((line) => (/^&gt;\s?/.test(line) ? `<span class="squote">${line.replace(/^&gt;\s?/, "")}</span>` : line)).join("\n");
      t = t.replace(/\u0001(\d+)\u0001/g, (m, n) => ph[+n]);
      out.push(`<span class="stext">${t}</span>`);
    });
    return out.join("");
  }
  const fileIcon = (f) => (/pdf/.test(f.filetype + f.mimetype) ? "📕" : /presentation|pptx?|key/.test(f.filetype + f.mimetype) ? "📽" : /sheet|xlsx?|csv/.test(f.filetype + f.mimetype) ? "📊" : /word|docx?|gdoc/.test(f.filetype + f.mimetype) ? "📄" : /video|mp4|mov/.test(f.filetype + f.mimetype) ? "🎬" : /zip/.test(f.filetype) ? "🗜" : "📎");
  const sizeText = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : n > 1024 ? Math.round(n / 1024) + " KB" : n ? n + " B" : "");
  function slackMsgsHtml(t) {
    const d = t.data, ctx = { emoji: d.emoji || {}, people: slackPeople(t), selfName: d.selfName || "" };
    let prev = null;
    return d.messages.map((m, k) => {
      const at = parseFloat(m.ts) * 1000;
      const cont = prev && prev.user === m.user && m.user && at - parseFloat(prev.ts) * 1000 < 5 * 60e3 && !m.files.length === !prev.files.length;
      prev = m;
      const when = new Date(at), hm = when.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
      const av = m.avatar ? `<img class="sav" src="${esc(m.avatar)}" alt="" referrerpolicy="no-referrer" loading="lazy">` : `<span class="sav ini" style="background:${m.mine ? "#1E7B4E" : "#4A154B"}">${esc((m.name || "?")[0])}</span>`;
      const files = m.files.map((f, j) => (f.thumb && /^image\/|pdf|video/.test(f.mimetype + f.filetype)
        ? `<button type="button" class="simg" data-msg="${k}" data-file="${j}" title="${esc(f.name)}（押すと大きく開く）"><img data-slack-src="${esc(f.thumb)}" alt="${esc(f.name)}"${f.w && f.h ? ` style="aspect-ratio:${f.w}/${f.h}"` : ""}>${/image\//.test(f.mimetype) ? "" : `<span class="simg-cap">${fileIcon(f)} ${esc(f.name)}</span>`}</button>`
        : `<button type="button" class="sfile" data-msg="${k}" data-file="${j}" title="${esc(f.name)}"><span class="fi">${fileIcon(f)}</span><span class="fn"><b>${esc(f.title || f.name)}</b><span>${esc([f.pretty || f.filetype.toUpperCase(), sizeText(f.size)].filter(Boolean).join(" · "))}</span></span></button>`)).join("");
      const reacts = m.reactions.map((r) => `<span class="sreact${r.mine ? " mine" : ""}" title=":${esc(r.name)}:">${slackEmoji(r.name, ctx)}<b>${r.count}</b></span>`).join("");
      return `<div class="smsg${cont ? " cont" : ""}${m.ts === t.ts ? " hl" : ""}">
        <div class="sl">${cont ? `<time class="st2">${esc(hm)}</time>` : av}</div>
        <div class="sb">${cont ? "" : `<div class="sn"><b>${esc(m.name)}</b><time title="${esc(when.toLocaleString("ja-JP"))}">${esc(when.toLocaleString("ja-JP", { month: "numeric", day: "numeric" }))} ${esc(hm)}</time></div>`}
          ${m.text ? `<div class="sx">${slackHtml(m.text, ctx)}${m.edited ? `<span class="sedit">（編集済み）</span>` : ""}</div>` : ""}
          ${files ? `<div class="sfiles">${files}</div>` : ""}
          <div class="sreacts">${reacts}<button type="button" class="sadd" title="スタンプを付ける（自分で押したときだけ付きます）">😀＋</button></div>
          ${m.replyCount && !t.threadTs ? `<div class="sreply">${m.replyCount} 件の返信</div>` : ""}
        </div></div>`;
    }).join("");
  }
  // 画像は BALL の中の Slack のログインで取ってきて差し込む（取れなければファイルの札にする）
  function loadSlackImages(root, t) {
    root.querySelectorAll("img[data-slack-src]").forEach((im) => {
      const url = im.dataset.slackSrc;
      if (!IS_APP || !window.ball.slackImage) return;
      window.ball.slackImage(url).then((r) => {
        if (r && r.ok) { im.src = r.data; im.removeAttribute("data-slack-src"); return; }
        const b = im.closest(".simg"); if (!b) return;
        const f = t.data.messages[+b.dataset.msg].files[+b.dataset.file];
        b.outerHTML = `<button type="button" class="sfile" data-msg="${b.dataset.msg}" data-file="${b.dataset.file}"><span class="fi">${fileIcon(f)}</span><span class="fn"><b>${esc(f.title || f.name)}</b><span>${esc([f.pretty, sizeText(f.size)].filter(Boolean).join(" · "))}</span></span></button>`;
        bindSlackFiles(root, t);
      });
    });
  }
  function bindSlackFiles(root, t) {
    root.querySelectorAll(".simg[data-file], .sfile[data-file]").forEach((b) => (b.onclick = (e) => {
      const f = t.data.messages[+b.dataset.msg].files[+b.dataset.file];
      const url = /^image\//.test(f.mimetype) ? (f.download || f.url) : (f.url || f.download);
      if (url) openLink(url, f.name, e);
    }));
    root.querySelectorAll(".slink[data-url]").forEach((b) => (b.onclick = (e) => openLink(b.dataset.url, b.dataset.label, e)));
  }

  // ---------- 絵文字を選ぶ小窓（入力欄の 😀 と、スタンプを付ける 😀＋ で共通） ----------
  let emojiAllCache = null;
  const RECENT_KEY = "ball.emoji.recent";
  const recentEmoji = () => { try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (e) { return []; } };
  const pushRecent = (n) => { try { localStorage.setItem(RECENT_KEY, JSON.stringify([n, ...recentEmoji().filter((x) => x !== n)].slice(0, 24))); } catch (e) { /* 覚えられなくても動く */ } };
  function emojiPicker(anchor, ctx, onPick) {
    document.querySelectorAll(".epick").forEach((x) => x.remove());
    const box = document.createElement("div");
    box.className = "epick";
    box.innerHTML = `<input type="search" placeholder="絵文字を探す（例: ok, pray, ryoukai）" aria-label="絵文字を探す"><div class="eg" role="listbox"></div>`;
    document.body.appendChild(box);
    const r = anchor.getBoundingClientRect();
    box.style.left = Math.max(8, Math.min(window.innerWidth - 340, r.left)) + "px";
    box.style.top = (r.top > 340 ? r.top - 330 : r.bottom + 6) + "px";
    const all = () => Object.assign({}, emojiAllCache || {}, ctx.emoji || {});
    const draw = (q) => {
      q = String(q || "").trim().toLowerCase();
      const custom = Object.keys(all());
      const names = q
        ? [...new Set([...custom, ...Object.keys(STD_EMOJI)])].filter((n) => n.includes(q)).slice(0, 96)
        : [...new Set([...recentEmoji(), ...Object.keys(ctx.emoji || {}), "white_check_mark", "+1", "pray", "bow", "eyes", "ok_hand", "raised_hands", "clap", "tada", "joy", "sob", "sweat_smile", "fire", "100", "muscle", "heart", "thinking_face", "memo", "rocket", "sparkles"])].slice(0, 48);
      const c2 = { emoji: all() };
      box.querySelector(".eg").innerHTML = names.map((n) => `<button type="button" data-n="${esc(n)}" title=":${esc(n)}:">${slackEmoji(n, c2)}</button>`).join("") || `<span class="hint">見つかりません</span>`;
      box.querySelectorAll(".eg button").forEach((b) => (b.onmousedown = (e) => { e.preventDefault(); pushRecent(b.dataset.n); box.remove(); onPick(b.dataset.n); }));
    };
    const inp = box.querySelector("input");
    inp.oninput = () => draw(inp.value);
    inp.onkeydown = (e) => { if (e.key === "Escape") box.remove(); if (e.key === "Enter") { const b = box.querySelector(".eg button"); if (b) b.dispatchEvent(new MouseEvent("mousedown")); } };
    draw("");
    setTimeout(() => inp.focus(), 0);
    const off = (e) => { if (!box.contains(e.target) && e.target !== anchor) { box.remove(); document.removeEventListener("mousedown", off, true); } };
    document.addEventListener("mousedown", off, true);
    if (!emojiAllCache && IS_APP && window.ball.slackEmojiAll) window.ball.slackEmojiAll().then((x) => { if (x && x.ok) { emojiAllCache = x.emoji; if (document.body.contains(box)) draw(inp.value); } });
  }

  // ---------- Slack の入力欄 ----------
  function slackComposerHtml(t) {
    const tool = [["b", "<b>B</b>", "太字（⌘B）"], ["i", "<i>I</i>", "斜体（⌘I）"], ["s", "<s>S</s>", "取り消し線（⌘⇧X）"], ["|"], ["link", "🔗", "リンク（⌘⇧U）"], ["ol", "1.", "番号付きリスト"], ["ul", "•", "箇条書き"], ["|"], ["quote", "❝", "引用"], ["code", "&lt;/&gt;", "コード"], ["block", "{ }", "コードブロック"]];
    return `<div class="draft scomp" id="scomp">
      <div class="dh"><span>下書き（送るまで送信されません）</span><span id="draftState">${t.aiDraft ? `AI が入れた下書きです（未送信） <button type="button" class="lnkbtn" id="discardDraft">破棄</button>` : "ファイルはドラッグ＆ドロップ・貼り付けでも付けられます"}</span></div>
      <div class="stool" role="toolbar" aria-label="書式">${tool.map((x) => (x[0] === "|" ? `<i class="ssep"></i>` : `<button type="button" data-fmt="${x[0]}" title="${x[2]}">${x[1]}</button>`)).join("")}</div>
      <textarea id="draftText" aria-label="下書き" placeholder="真ん中で「下書き書いて」と言うとここに入ります。直接書いても OK（@ でメンション）">${esc(t.draft || "")}</textarea>
      <div class="sprev" id="sPrev" hidden></div>
      <div class="satt" id="sAtt"></div>
      <div class="df">
        <button type="button" class="sbt" id="sAdd" title="ファイルを添付（ドラッグ＆ドロップ・⌘V の貼り付けも可）">＋</button><input type="file" id="sFile" multiple hidden>
        <button type="button" class="sbt" id="sAa" title="送ったときの見え方" aria-pressed="false">Aa</button>
        <button type="button" class="sbt" id="sEmo" title="絵文字">😀</button>
        <button type="button" class="sbt" id="sAt" title="メンション">@</button>
        <span class="hint">送るのは「送信…」で確認したときだけ</span><span class="sp"></span>
        <button type="button" class="btn" id="copyDraft">コピー</button><button type="button" class="btn send" id="saveDraft">送信…</button>
      </div>
      <div class="confirm" id="sendConfirm" hidden></div></div>`;
  }
  // 選んだところを書式で囲む / 行の頭に付ける
  function fmtWrap(ta, a, b, ph) {
    const s0 = ta.selectionStart, s1 = ta.selectionEnd, v = ta.value, sel = v.slice(s0, s1) || ph;
    ta.value = v.slice(0, s0) + a + sel + b + v.slice(s1);
    ta.selectionStart = s0 + a.length; ta.selectionEnd = s0 + a.length + sel.length;
  }
  function fmtLines(ta, kind) {
    const v = ta.value, s0 = v.lastIndexOf("\n", ta.selectionStart - 1) + 1, e = v.indexOf("\n", ta.selectionEnd), s1 = e < 0 ? v.length : e;
    const lines = v.slice(s0, s1).split("\n").map((l, k) => (kind === "ol" ? `${k + 1}. ` : kind === "ul" ? "• " : "> ") + l.replace(/^(\d+\.\s|•\s|>\s?)/, ""));
    const out = lines.join("\n");
    ta.value = v.slice(0, s0) + out + v.slice(s1);
    ta.selectionStart = s0; ta.selectionEnd = s0 + out.length;
  }
  function applyFmt(ta, k) {
    if (k === "b") fmtWrap(ta, "*", "*", "太字");
    else if (k === "i") fmtWrap(ta, "_", "_", "斜体");
    else if (k === "s") fmtWrap(ta, "~", "~", "取り消し");
    else if (k === "code") fmtWrap(ta, "`", "`", "コード");
    else if (k === "block") fmtWrap(ta, "```\n", "\n```", "コード");
    else if (k === "link") {
      const s0 = ta.selectionStart, s1 = ta.selectionEnd, sel = ta.value.slice(s0, s1);
      if (/^https?:\/\/\S+$/.test(sel)) return;
      const label = sel || "リンクの文字", ins = `[${label}](https://)`;
      ta.value = ta.value.slice(0, s0) + ins + ta.value.slice(s1);
      ta.selectionStart = s0 + label.length + 3; ta.selectionEnd = s0 + ins.length - 1;   // https:// のところを選んだ状態にする
    } else fmtLines(ta, k);
    ta.dispatchEvent(new Event("input")); ta.focus();
  }
  // 送る前の本文: @名前 → 本物のメンション、[文字](URL) → Slack のリンク
  function toSlackText(t, text) {
    return toSlackMentions(t, text).replace(/\[([^\]\n]{1,120})\]\((https?:\/\/[^)\s]+)\)/g, (m, l, u) => `<${u}|${l.replace(/[|>]/g, " ")}>`);
  }
  function bindSlackComposer(i, ta) {
    const t = i.thread;
    t.files = t.files || [];
    const box = $("scomp"), att = $("sAtt"), prev = $("sPrev");
    const ctx = () => ({ emoji: (t.data && t.data.emoji) || {}, people: slackPeople(t), selfName: (t.data && t.data.selfName) || "" });
    const drawAtt = () => {
      att.innerHTML = t.files.map((f, k) => `<span class="schip">${f.preview ? `<img src="${f.preview}" alt="">` : `<span class="fi">${fileIcon({ filetype: f.name.split(".").pop(), mimetype: f.type })}</span>`}<span class="fn"><b>${esc(f.name)}</b><span>${esc(sizeText(f.size))}</span></span><button type="button" data-rm="${k}" aria-label="外す">×</button></span>`).join("");
      att.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { const f = t.files.splice(+b.dataset.rm, 1)[0]; if (f && f.preview) URL.revokeObjectURL(f.preview); drawAtt(); }));
    };
    const addFiles = async (list) => {
      for (const f of list) {
        if (f.size > 100 * 1024 * 1024) { toast(`${f.name} は大きすぎます（100MB まで）`); continue; }
        t.files.push({ name: f.name || "image.png", type: f.type || "application/octet-stream", size: f.size, data: await f.arrayBuffer(), preview: /^image\//.test(f.type) ? URL.createObjectURL(f) : "" });
      }
      drawAtt();
    };
    drawAtt();
    box.querySelectorAll("[data-fmt]").forEach((b) => (b.onmousedown = (e) => { e.preventDefault(); applyFmt(ta, b.dataset.fmt); }));
    ta.addEventListener("keydown", (e) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      const k = e.key.toLowerCase();
      if (k === "b") { e.preventDefault(); applyFmt(ta, "b"); }
      else if (k === "i") { e.preventDefault(); applyFmt(ta, "i"); }
      else if (k === "x" && e.shiftKey) { e.preventDefault(); applyFmt(ta, "s"); }
      else if (k === "u" && e.shiftKey) { e.preventDefault(); applyFmt(ta, "link"); }
    });
    $("sAdd").onclick = () => $("sFile").click();
    $("sFile").onchange = () => { addFiles([...$("sFile").files]); $("sFile").value = ""; };
    ta.addEventListener("paste", (e) => { const fs = [...((e.clipboardData && e.clipboardData.files) || [])]; if (fs.length) { e.preventDefault(); addFiles(fs); } });
    box.addEventListener("dragover", (e) => { e.preventDefault(); box.classList.add("drop"); });
    box.addEventListener("dragleave", (e) => { if (!box.contains(e.relatedTarget)) box.classList.remove("drop"); });
    box.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); box.classList.remove("drop"); addFiles([...((e.dataTransfer && e.dataTransfer.files) || [])]); });
    const showPrev = () => { prev.innerHTML = ta.value.trim() ? slackHtml(ta.value, ctx()) : `<span class="hint">（空です）</span>`; };
    $("sAa").onclick = () => { const on = prev.hidden; prev.hidden = !on; $("sAa").setAttribute("aria-pressed", on); if (on) showPrev(); };
    ta.addEventListener("input", () => { if (!prev.hidden) showPrev(); });
    $("sEmo").onclick = () => emojiPicker($("sEmo"), ctx(), (n) => { fmtWrap(ta, "", "", ""); const p = ta.selectionStart; ta.value = ta.value.slice(0, p) + `:${n}: ` + ta.value.slice(p); ta.selectionStart = ta.selectionEnd = p + n.length + 3; ta.dispatchEvent(new Event("input")); ta.focus(); });
    $("sAt").onclick = () => { const p = ta.selectionStart, pre = ta.value.slice(0, p); const ins = (pre && !/\s$/.test(pre) ? " " : "") + "@"; ta.value = pre + ins + ta.value.slice(p); ta.selectionStart = ta.selectionEnd = p + ins.length; ta.focus(); ta.dispatchEvent(new Event("input")); };
  }

  // ---------- スタンプ（リアクション）: 片山さんが押したときだけ付ける・外す ----------
  function bindSlackReactions(i, root) {
    const t = i.thread;
    const ctx = () => ({ emoji: (t.data && t.data.emoji) || {} });
    const apply = async (m, name, remove) => {
      if (!IS_APP || !window.ball.slackReact) return toast("見本なので付けられません");
      const r = await window.ball.slackReact({ channel: t.channel, ts: m.ts, name, remove });
      if (!r.ok) return toast("スタンプを付けられませんでした：" + r.error);
      const ex = m.reactions.find((x) => x.name === name);
      if (remove) { if (ex) { ex.count--; ex.mine = false; if (ex.count <= 0) m.reactions.splice(m.reactions.indexOf(ex), 1); } }
      else if (ex) { ex.count++; ex.mine = true; } else m.reactions.push({ name, count: 1, mine: true });
      if (!remove && t.data.emoji && emojiAllCache && emojiAllCache[name]) t.data.emoji[name] = emojiAllCache[name];
      toast(remove ? "スタンプを外しました" : `:${name}: を付けました`);
      renderSlackThread(i);
      window.ball.slackScan && window.ball.slackScan(); // ボールの状態（了解済み・完了）を付け直す
    };
    root.querySelectorAll(".smsg").forEach((el, k) => {
      const m = t.data.messages[k];
      const add = el.querySelector(".sadd");
      if (add) add.onclick = () => emojiPicker(add, ctx(), (n) => apply(m, n, false));
      el.querySelectorAll(".sreact").forEach((b, j) => (b.onclick = () => { const r = m.reactions[j]; apply(m, r.name, r.mine); }));
    });
  }

  function renderSlackThread(i) {
    const t = i.thread;
    if (!t.data && !t.error) {
      $("thr").innerHTML = `<div class="thr"><div class="empty">${esc(t.where)} のやり取りを読み込み中…</div></div>`;
      if (!t.loading) {
        t.loading = true;
        window.ball.slackThread({ channel: t.channel, threadTs: t.threadTs }).then((r) => {
          t.loading = false;
          if (r.ok) t.data = r; else t.error = r.error;
          if (curItem() === i && S.rmode === "thread") renderSlackThread(i);
        });
      }
      return;
    }
    $("thr").innerHTML = `<div class="thr">
      <div class="thd"><h4>${esc(t.where)}${t.threadTs ? " のスレッド" : ""}</h4><span><button type="button" class="btn" id="slackReload">読み直す</button>${t.permalink ? ` <button type="button" class="btn" id="slackOpen">Slack で開く ↗</button>` : ""}</span></div>
      ${t.error ? `<div class="empty">読めませんでした：${esc(t.error)}</div>` : `<div class="smsgs">${slackMsgsHtml(t)}</div>`}
      ${draftBox(i, "slacklive")}
    </div>`;
    $("slackReload").onclick = () => { t.data = null; t.error = null; renderSlackThread(i); };
    mountDocsBar(i, ".thd");
    if ($("slackOpen")) $("slackOpen").onclick = () => openTab(t.permalink, "Slack");
    if (t.data) { const box = $("thr").querySelector(".smsgs"); bindSlackFiles(box, t); loadSlackImages(box, t); bindSlackReactions(i, box); }
    bindDraft(i);
  }
  $("ft-slack").onclick = () => {
    if (!IS_APP) return toast("Slack の取り込みはデスクトップアプリ版で動きます");
    if (slackData && slackData.status === "ok" && slackData.warn) { showInfo("Slack：DM の一覧を読めませんでした", slackData.warn, "読み直す", () => { toast("Slack を読み込み直しています…"); window.ball.slackScan(); }); return; }
    if (slackData && slackData.status === "error") { showInfo("Slack 読み取りのエラー", slackData.error || "", "読み取り画面を見る", () => window.ball.slackShow()); return; }
    if (!slackData || slackData.status !== "ok") { toast("読み取り画面を開きます。Slack にログインしてから閉じてください"); window.ball.slackShow(); return; }
    toast("Slack を読み込み直しています…"); window.ball.slackScan();
  };
  if (IS_APP && window.ball.onSlack) {
    window.ball.onSlack(applySlack);
    window.ball.slackLast().then((d) => { if (d) applySlack(d); else setFt("ft-slack", "Slack 読み取り準備中", "mock"); });
  }

  // ---------- カレンダーの取り込み（アプリ版のみ・Mac の gog 経由・読み取りのみ） ----------
  // [作業] の予定 → 自分ボール。それ以外 → 「今日の予定」「明日の予定」。予定は押すと右に詳細が出る
  let calLoaded = false, calAt = 0, calErr = null;
  const todayStr = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const dayLabel = (d) => { const t = todayStr(); const tm = new Date(Date.parse(t) + 86400e3).toISOString().slice(0, 10); return d === tm ? "明日" : d.slice(5).replace("-", "/"); };
  const hhmm = (iso) => (iso && iso.length > 10 ? iso.slice(11, 16) : "終日");
  const STATUS_JA = { accepted: "出席", declined: "欠席", tentative: "未定", needsAction: "未回答", organizer: "主催" };
  async function loadCalendar() {
    const r = await window.ball.calendarEvents(2);
    if (!r.ok) { calErr = r.error; setFt("ft-cal", "カレンダー: 読み込みエラー（押して再読込）", "ng"); return; }
    calErr = null; calLoaded = true; calAt = Date.now();
    items.filter((x) => x.src === "cal" && !x.live).forEach((x) => (x.hidden = true));
    const ids = new Set();
    r.data.forEach((e) => {
      const id = "c-" + e.id + "-" + e.start.slice(0, 10); ids.add(id);
      const isBall = e.isWork && !/今日の5件/.test(e.summary);
      const day = e.start.slice(0, 10);
      const fields = {
        sec: isBall ? "me" : "cal", proj: "none", src: "cal", live: true, hidden: false,
        title: isBall ? e.summary.replace(/^\[作業[^\]]*\]\s*/, "") : e.summary,
        sub: isBall ? `カレンダーの作業 · ${dayLabel(day) === "明日" ? "明日" : day === todayStr() ? "今日" : dayLabel(day)} ${hhmm(e.start)}` : `${hhmm(e.start)}〜${hhmm(e.end)}`,
        ago: "", calDay: day, calTime: e.allDay ? "終日" : hhmm(e.start), calStart: e.start,
        chips: isBall ? [[day === todayStr() ? "今日" : dayLabel(day), "me"]] : [],
      };
      let it = items.find((x) => x.id === id);
      if (!it) {
        it = Object.assign({ id, memo: "", activeTab: 0, done: false,
          feed: [["prog", "カレンダーから自動で取り込み"], ["ai", isBall ? `カレンダーに入れていた作業です（${hhmm(e.start)}〜）。右に予定の中身を出しています。` : `${hhmm(e.start)} の予定です。右に参加者や説明を出しています。\n商談なら、予習のブリーフはここで頼めます（例:「この商談の予習して」）。`]],
          thread: { kind: "cal", live: true, ev: e },
          tabs: e.htmlLink ? [{ title: "Google カレンダー", url: e.htmlLink, sim: "calev", key: id + "-0" }] : [] }, fields);
        items.push(it);
      } else { Object.assign(it, fields); it.thread.ev = e; }
    });
    // 予定が消えた・過去になったものは隠す
    items.filter((x) => x.live && x.src === "cal" && !ids.has(x.id)).forEach((x) => (x.hidden = true));
    setFt("ft-cal", `カレンダー ${agoText(calAt)} · ${r.data.length}件`, "");
    left();
  }
  function renderCalThread(i) {
    const e = i.thread.ev;
    if (!e) { $("thr").innerHTML = `<div class="thr"><div class="empty">見本の予定です</div></div>`; return; }
    const when = e.allDay ? `${e.start.slice(5).replace("-", "/")} 終日` : `${e.start.slice(5, 10).replace("-", "/")} ${hhmm(e.start)}〜${hhmm(e.end)}`;
    $("thr").innerHTML = `<div class="thr">
      <div class="thd"><h4>${esc(e.summary)}</h4><span>${e.meet ? `<button type="button" class="btn send" id="calMeet">Meet に入る</button> ` : ""}${e.htmlLink ? `<button type="button" class="btn" id="calOpen">カレンダーで開く ↗</button>` : ""}</span></div>
      <div class="calv"><dl class="kv">
        <dt>日時</dt><dd>${esc(when)}</dd>
        ${e.location ? `<dt>場所</dt><dd>${esc(e.location)}</dd>` : ""}
        ${e.organizer ? `<dt>主催</dt><dd>${esc(e.organizerSelf ? "自分" : e.organizer)}</dd>` : ""}
        ${e.myStatus ? `<dt>自分</dt><dd>${esc(STATUS_JA[e.myStatus] || e.myStatus)}</dd>` : ""}
        ${e.attendees.length ? `<dt>参加者</dt><dd>${e.attendees.map((a) => `${esc(a.self ? "自分" : a.name)}<span class="hint">（${esc(STATUS_JA[a.status] || a.status || "")}）</span>`).join("、")}</dd>` : ""}
      </dl></div>
      ${e.description ? `<div class="mcard open"><div class="mb rich">${richBody(e.description)}</div></div>` : ""}
    </div>`;
    bindLinks($("thr"));
    mountDocsBar(i, ".thd");
    if ($("calMeet")) $("calMeet").onclick = () => (IS_APP ? window.ball.openExternal(e.meet) : window.open(e.meet, "_blank"));
    if ($("calOpen")) $("calOpen").onclick = () => openTab(e.htmlLink, "Google カレンダー");
  }
  $("ft-cal").onclick = () => { if (!IS_APP) return toast("カレンダーの取り込みはデスクトップアプリ版で動きます"); toast(calErr ? "読み込み直しています…（前回のエラー：" + calErr.slice(0, 80) + "）" : "カレンダーを読み込み直しています…"); loadCalendar(); };

  let gmailErr = null, gmailAt = 0, gmailCount = 0;
  async function loadGmail() {
    const st = await window.ball.gmailStatus();
    if (!st.ok) {
      gmailErr = st;
      setFt("ft-gmail", st.reason === "nogog" ? "Gmail: gog が見つかりません（押して確認）" : "Gmail: gog の認証エラー（押して確認）", "ng");
      return;
    }
    const r = await window.ball.gmailInbox();
    if (!r.ok) { gmailErr = { reason: "error", message: r.error }; setFt("ft-gmail", "Gmail: 読み込みエラー（押して確認）", "ng"); return; }
    gmailErr = null;
    // 本物が読めたら見本の Gmail ボールは隠す
    items.filter((x) => x.src === "gmail" && !x.live).forEach((x) => (x.hidden = true));
    const ids = new Set();
    [...r.data].reverse().forEach((t) => {
      const id = "g-" + t.id; ids.add(id);
      const fields = {
        sec: t.notes ? "notes" : "me", proj: "none", src: "gmail", live: true, hidden: false, done: false,
        title: t.notes ? "議事録：" + (t.subject || "").replace(/^(Fwd|FW)[:：]\s*/i, "").replace(/^(メモ|共有されたドキュメント)[:：]\s*/, "").replace(/^「|」.*$|（\d{4}年.*$/g, "").replace(/\s*-\s*\d{4}\/\d{2}\/\d{2}.*$/, "") : (t.subject || "（件名なし）"),
        sub: nameOf(t.from), ago: (t.date || "").slice(5, 16), at: dateTime(t.date), notes: !!t.notes,
        chips: t.notes ? [["議事録", "ai"]] : [[t.unread ? "未読" : "未返信", t.unread ? "warn" : "me"]].concat(t.count > 1 ? [[t.count + "通", "them"]] : []),
      };
      let it = items.find((x) => x.id === id);
      if (!it) {
        it = Object.assign({ id, memo: "", activeTab: 0,
          feed: t.notes
            ? [["prog", "会議メモ（Gemini）を自動で取り込み"], ["ai", `会議のメモです。右に要点と、自分（Yuki Katayama）の担当を色付きで出しています。リンクはボタンから開けます。\n\n議事録への清書や担当の整理はここで頼めます（例:「議事録にしてメモに入れといて」）。`]]
            : [["prog", "Gmail から自動で取り込み"], ["ai", `${nameOf(t.from)}さんからのメールです。右にスレッドを出しています。\n\n返信はここで頼めます（例:「丁寧めに返信の下書き書いて」）。下書きは右の下書き欄に入り、Gmail への保存も送信も自分のボタンです。`]],
          thread: { kind: "gmail", live: true, threadId: t.id, draft: "" },
          tabs: [{ title: "Gmail - このスレッド", url: gmailUrl(t.id), sim: "gmail", key: id + "-0" }] }, fields);
        items.unshift(it);
      } else Object.assign(it, fields);
    });
    // 一覧から消えた（＝返信した・アーカイブした）ものは閉じる
    items.filter((x) => x.live && x.src === "gmail" && !x.done && !ids.has(x.id)).forEach((x) => { x.done = true; D.closed.unshift(`Gmail: ${x.title.slice(0, 30)} · 返信済み`); });
    gmailAt = Date.now(); gmailCount = r.data.length;
    setFt("ft-gmail", `Gmail ${agoText(gmailAt)} · ${gmailCount}件`, "");
    queueJudge();
    left();
    if (!curItem() || curItem().hidden) { const first = items.find((x) => !x.hidden && !x.done && x.sec === "me"); if (first) select(first.id); }
  }
  $("ft-gmail").onclick = () => {
    if (!IS_APP) return toast("Gmail の取り込みはデスクトップアプリ版で動きます");
    if (!gmailErr) { toast("Gmail を読み込み直しています…"); return loadGmail(); }
    if (gmailErr.reason === "nogog") toast("この Mac に gog が入っていないか、場所が分かりません。ターミナルで gog --version を試してください");
    else toast("Gmail を読めませんでした：" + (gmailErr.message || "").slice(0, 300));
  };
  if (IS_APP && window.ball.calendarEvents) {
    window.ball.gmailStatus().then((st) => { if (st.ok) loadCalendar(); else setFt("ft-cal", "カレンダー: gog の準備が必要", "ng"); });
    setInterval(() => { loadCalendar(); }, 5 * 60 * 1000);
    setInterval(() => { if (calAt && !calErr) setFt("ft-cal", `カレンダー ${agoText(calAt)}`, ""); }, 60000);
  }
  if (IS_APP && window.ball.gmailStatus) {
    loadGmail();
    setInterval(loadGmail, 3 * 60 * 1000);
    setInterval(() => { if (gmailAt && !gmailErr) setFt("ft-gmail", `Gmail ${agoText(gmailAt)} · ${gmailCount}件`, ""); }, 30000);
  }

  $("ft-msgr").onclick = () => {
    if (!IS_APP) { toast("Messenger の読み取りはデスクトップアプリ版で動きます"); return; }
    // 右のブラウザで Messenger の会話を開いていれば、そのページを読み取りに使う
    const t = S.rmode === "browser" && activeTab();
    if (t && /^https:\/\/(www\.)?(facebook\.com\/messages|messenger\.com)/.test(t.url)) {
      window.ball.messengerUseUrl(t.url);
      $("ft-msgr").querySelector("span").textContent = "Messenger: このページで読み直しています…";
      toast("右に開いている Messenger のページを読むように切り替えました");
      return;
    }
    if (lastMsgrData) { showMsgrDiag(lastMsgrData); return; }
    toast("右のブラウザで Messenger の会話一覧を開いてから、もう一度ここを押してください");
    window.ball.messengerShow();
  };
  if (IS_APP && window.ball.onMessenger) {
    window.ball.onMessenger(applyMessenger);
    window.ball.messengerLast().then((d) => { if (d) applyMessenger(d); else msgrStatus(null); });
    setInterval(() => { if (lastMsgrData) msgrStatus(lastMsgrData); }, 30000);
  }

  ptabs(); select("iwata");
  if (!store.get("ball.seenOverview")) overview(true);
})();
