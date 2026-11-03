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
      ${srcIcon(i.src)}
      <span class="ct"><span class="t">${esc(i.title)}</span>
      <span class="m"><span class="proj"><span class="pd" style="background:${pj.color}"></span>${esc(pj.name)}</span>${esc(i.sub)}${i.ago ? ` · ${esc(i.ago)}` : ""}</span>
      ${i.chips.length ? `<span class="m">${i.chips.map((c) => `<span class="chip c-${c[1]}">${esc(c[0])}</span>`).join("")}</span>` : ""}</span></button>`;
  }
  function left() {
    const vis = items.filter((i) => !i.done && !i.hidden && (S.proj === "all" || i.proj === S.proj));
    const by = (s) => vis.filter((i) => i.sec === s);
    $("meCount").textContent = `自分ボール ${items.filter((i) => i.sec === "me" && !i.done && !i.hidden).length}`;
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
    // スレッドがあるボールは、まずスレッド（件名・本文・添付・下書き）を出す
    S.rmode = i.thread ? "thread" : "browser";
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
  function msgCard(m, open) {
    const q = trimQuote(m.body);
    const att = (m.attachments || []).map((a, k) => `<button type="button" class="att" data-msg="${esc(m.id)}" data-att="${k}" title="開く">📎 ${esc(a.filename)}<span>${esc(a.size)}</span></button>`).join("");
    return `<div class="mcard${open ? " open" : ""}">
      <div class="mhd"><b>${esc(nameOf(m.from))}</b><span>${esc(emailOf(m.from))}</span><time>${esc(m.date)}</time></div>
      <div class="mto">宛先 ${esc(m.to)}${m.cc ? `　CC ${esc(m.cc)}` : ""}</div>
      ${att ? `<div class="atts">${att}</div>` : ""}
      <div class="mb">${esc(q.text)}</div>
      ${q.trimmed ? `<div class="hint">（引用部分は省略。全文は「Gmail で開く」）</div>` : ""}
    </div>`;
  }
  function renderThread(i) {
    const t = i.thread;
    if (t.kind === "msgr") { renderMsgrThread(i); return; }
    if (t.kind === "slack") {
      $("thr").innerHTML = `<div class="thr"><h4>${t.ws === "DM" ? "DM: " : ""}${esc(t.ch)}${t.ws === "DM" ? "" : " のスレッド"}<span>${esc(t.ws)}</span></h4>
        ${t.msgs.map((m) => `<div class="sm"><span class="av" style="background:${m[0]}">${esc(m[1][0])}</span><div><div class="n">${esc(m[1])}<time>${esc(m[2])}</time></div><div class="x">${esc(m[3])}</div>${m[4] ? `<span class="react">${esc(m[4])}</span>` : ""}</div></div>`).join("")}
        ${t.draft ? draftBox(i, "slack") : ""}</div>`;
      bindDraft(i);
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
    $("thr").innerHTML = `<div class="thr">
      <div class="thd"><h4>${esc(subject)}</h4><button type="button" class="btn" id="openInGmail">Gmail で開く ↗</button></div>
      ${last ? msgCard(last, true) : ""}
      ${older.length ? `<details class="older"><summary>過去のやり取り（${older.length}件）</summary>${older.map((m) => msgCard(m, false)).join("")}</details>` : ""}
      ${draftBox(i, "gmail")}
    </div>`;
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
      <div class="thd"><h4>Messenger：${esc(t.name)}</h4><span><button type="button" class="btn" id="msgrReload">読み直す</button> <button type="button" class="btn" id="openInMsgr">Messenger で開く ↗</button></span></div>
      ${t.live && t.data ? `<div class="hint">${t.data.reachedTop ? "最初のメッセージまで読みました" : "直近から遡って読んでいます"}（${msgs.length}件）${more ? ` <button type="button" class="btn" id="msgrMore">もっと過去を読む</button>` : ""}</div>` : ""}
      ${t.error ? `<div class="empty">${esc(t.error)}</div>` : `<div class="bubs">${msgs.map((m, k) => `<div class="bubrow${m.mine ? " mine" : ""}">${
        m.image ? `<button type="button" class="bbimg" data-img="${k}" title="大きく開く"><img src="${esc(m.image)}" alt="写真" loading="lazy" referrerpolicy="no-referrer"></button>`
        : m.file ? `<button type="button" class="bb bbfile" data-file="${k}">${esc(m.text)}</button>`
        : `<div class="bb">${esc(m.text)}</div>`}</div>`).join("")}</div>`}
      ${draftBox(i, "msgr")}
    </div>`;
    $("msgrReload").onclick = () => { if (!t.live) return toast("見本の会話です"); t.data = null; t.error = null; renderMsgrThread(i); };
    if ($("msgrMore")) $("msgrMore").onclick = () => { t.steps = (t.steps || 4) + 10; t.data = null; t.error = null; renderMsgrThread(i); };
    $("openInMsgr").onclick = () => openConversationTab(i);
    // 写真は開けなかったら「📷 写真」の文字に差し替える。押すと右のブラウザで開く
    $("thr").querySelectorAll(".bbimg img").forEach((im) => (im.onerror = () => { const btn = im.parentElement; btn.className = "bb bbfile"; btn.textContent = "📷 写真（押すと開く）"; }));
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
    const saved = t.draftId ? `Gmail の下書きに保存済み` : kind === "msgr" ? "送るのは Messenger で Enter" : "まだ保存していません";
    const actions = kind === "gmail"
      ? `<span class="hint">AI は下書きまで。送るのは「送信」を押して確認したときだけ</span><span class="sp"></span><button type="button" class="btn" id="saveDraft">下書きに保存</button><button type="button" class="btn send" id="sendMail">送信…</button>`
      : kind === "msgr"
        ? `<button type="button" class="btn" id="copyDraft">コピー</button><span class="sp"></span><button type="button" class="btn" id="saveDraft">入力欄に入れる</button><button type="button" class="btn send" id="sendMsgr">送信…</button>`
        : `<span class="hint">見本です（Slack は下書きまで。投稿は自分のボタンで）</span><span class="sp"></span><button type="button" class="btn send" id="saveDraft">送信</button>`;
    return `<div class="draft"><div class="dh"><span>下書き（送るまで送信されません）</span><span id="draftState">${saved}</span></div>
      <textarea id="draftText" aria-label="下書き" placeholder="真ん中で「下書き書いて」と言うとここに入ります。直接書いても OK。">${esc(t.draft || "")}</textarea>
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
    return { draftId: t.draftId, replyToMessageId: lastOther.id, to: lastOther.from, cc, subject, body };
  }
  function bindDraft(i) {
    const t = i.thread, ta = $("draftText"), btn = $("saveDraft");
    if (!ta || !btn) return;
    ta.oninput = () => { t.draft = ta.value; if (t.kind === "gmail") $("draftState").textContent = t.draftId ? "変更あり（未保存）" : "まだ保存していません"; };
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
    const live = t.kind === "gmail" && t.live && IS_APP;
    btn.onclick = async () => {
      if (!live) return toast("見本なので保存・送信はしません");
      btn.disabled = true; $("draftState").textContent = "保存中…";
      const r = await window.ball.gmailDraft(replyFields(t, ta.value));
      btn.disabled = false;
      if (r.ok) { t.draftId = r.data.draftId || t.draftId; $("draftState").textContent = "Gmail の下書きに保存済み"; toast("Gmail の下書きに保存しました（送信はしていません）"); }
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
        <dl class="kv"><dt>宛先</dt><dd>${esc(f.to)}</dd>${f.cc ? `<dt>CC</dt><dd>${esc(f.cc)}</dd>` : ""}<dt>件名</dt><dd>${esc(f.subject)}</dd></dl>
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
  function applyMessenger(data) {
    lastMsgrData = data;
    msgrStatus(data);
    if (!data || data.status !== "ok") return;
    // 見本の Messenger ボールは本物が来たら外す
    const mock = items.find((x) => x.id === "msgr"); if (mock) mock.hidden = true;
    const want = new Map();
    data.convos.forEach((c, idx) => {
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
        sec: "me", proj: "none", src: "msgr", ago: c.time || "", msgr: true, msgrName: c.name, done: false, hidden: false,
        title: `Messenger：${c.name}`, sub: c.snippet ? c.snippet.slice(0, 40) : "Facebook メッセンジャー", chips,
      };
      if (!it) {
        it = Object.assign({ id, memo: "", activeTab: 0,
          thread: { kind: "msgr", live: true, href: c.href, name: c.name, draft: "" },
          feed: [["prog", "Messenger から自動で取り込み"], ["ai", `${c.name}さんとの会話です。${c.unread ? "未読があります。" : "相手の発言で止まっています。"}\n最後のメッセージ：${c.snippet || "（読み取れず）"}\n\n右に直近のやり取りを出しています。返信の段取りはここで相談できるようになります（Claude をつないだあと）。今は右の下書き欄に書いて「Messenger の入力欄に入れる」で送れます。`]],
          tabs: [{ title: `${c.name} - Messenger`, url: c.href, sim: "messenger", key: id + "-0" }] }, fields);
        items.unshift(it);
      } else {
        // 新しいメッセージが来ていたら、スレッドは読み直す
        if (it.sub !== fields.sub && it.thread) { it.thread.data = null; it.thread.error = null; }
        Object.assign(it, fields);
      }
    });
    left();
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
        sec: "me", proj: "none", src: "gmail", live: true, hidden: false, done: false,
        title: t.subject || "（件名なし）", sub: nameOf(t.from), ago: (t.date || "").slice(5, 16),
        chips: [[t.unread ? "未読" : "未返信", t.unread ? "warn" : "me"]].concat(t.count > 1 ? [[t.count + "通", "them"]] : []),
      };
      let it = items.find((x) => x.id === id);
      if (!it) {
        it = Object.assign({ id, memo: "", activeTab: 0,
          feed: [["prog", "Gmail から自動で取り込み"], ["ai", `${nameOf(t.from)}さんからのメールです。右にスレッドを出しています。\n\n返信の段取りはここで相談できるようになります（Claude をつないだあと）。今は右の下書き欄に直接書いて、Gmail の下書きに保存できます。`]],
          thread: { kind: "gmail", live: true, threadId: t.id, draft: "" },
          tabs: [{ title: "Gmail - このスレッド", url: gmailUrl(t.id), sim: "gmail", key: id + "-0" }] }, fields);
        items.unshift(it);
      } else Object.assign(it, fields);
    });
    // 一覧から消えた（＝返信した・アーカイブした）ものは閉じる
    items.filter((x) => x.live && x.src === "gmail" && !x.done && !ids.has(x.id)).forEach((x) => { x.done = true; D.closed.unshift(`Gmail: ${x.title.slice(0, 30)} · 返信済み`); });
    gmailAt = Date.now(); gmailCount = r.data.length;
    setFt("ft-gmail", `Gmail ${agoText(gmailAt)} · ${gmailCount}件`, "");
    left();
    if (!curItem() || curItem().hidden) { const first = items.find((x) => !x.hidden && !x.done && x.sec === "me"); if (first) select(first.id); }
  }
  $("ft-gmail").onclick = () => {
    if (!IS_APP) return toast("Gmail の取り込みはデスクトップアプリ版で動きます");
    if (!gmailErr) { toast("Gmail を読み込み直しています…"); return loadGmail(); }
    if (gmailErr.reason === "nogog") toast("この Mac に gog が入っていないか、場所が分かりません。ターミナルで gog --version を試してください");
    else toast("Gmail を読めませんでした：" + (gmailErr.message || "").slice(0, 300));
  };
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
