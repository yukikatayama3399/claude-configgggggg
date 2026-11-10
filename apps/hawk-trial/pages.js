// 入口まわりの画面（申込・ログイン・サインアップ・利用規約・管理）。server.js から呼ぶ。
const TERMS_VERSION = "2026-11-10-draft";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const LOGO = `<svg viewBox="0 0 40 40" width="34" height="34" aria-hidden="true"><circle cx="20" cy="20" r="19" fill="#0f5132"/><path d="M9 24c4-7 10-11 18-12-3 2-5 4-6 7 3-1 6-1 9 0-5 1-8 3-10 7-2-2-6-3-11-2z" fill="#fff"/><circle cx="27" cy="15.5" r="1.3" fill="#0f5132"/></svg>`;

const CSS = `
:root{--bg:#f6f7f9;--card:#fff;--ink:#1f2328;--sub:#646b74;--line:#e3e6ea;--green:#1aa86b;--green-d:#128556;--red:#d1344b;--chip:#eef1f4}
@media (prefers-color-scheme:dark){:root{--bg:#14171b;--card:#1d2126;--ink:#e8eaed;--sub:#a1a8b1;--line:#30363d;--chip:#262b31}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Hiragino Sans","Noto Sans JP","Yu Gothic UI",system-ui,sans-serif;line-height:1.7}
a{color:var(--green-d)}header{display:flex;align-items:center;gap:10px;padding:14px 20px;background:var(--card);border-bottom:1px solid var(--line)}
header b{font-size:22px;letter-spacing:.04em}.badge{font-size:12px;background:#fff3cd;color:#7a5600;border-radius:99px;padding:2px 10px;font-weight:700}
main{max-width:520px;margin:32px auto;padding:0 16px}main.wide{max-width:1100px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px;margin-bottom:16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:22px 0 6px}p.lead{color:var(--sub);margin:0 0 18px}
label{display:block;font-size:13px;font-weight:700;margin:14px 0 4px}input[type=text],input[type=email],input[type=password],textarea{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;font:inherit;background:var(--card);color:var(--ink)}
input[readonly]{background:var(--chip)}textarea{min-height:70px}
.check{display:flex;gap:8px;align-items:flex-start;font-size:14px;margin:10px 0}.check input{margin-top:5px}
.req{color:var(--red);font-size:11px;font-weight:700;margin-left:4px}.opt{color:var(--sub);font-size:11px;margin-left:4px}
button,.btn{display:inline-block;border:0;border-radius:8px;padding:11px 18px;font:inherit;font-weight:700;cursor:pointer;background:var(--green);color:#fff;text-decoration:none}
button:hover,.btn:hover{background:var(--green-d)}button:disabled{opacity:.45;cursor:not-allowed}button.ghost{background:var(--chip);color:var(--ink)}
.full{width:100%;margin-top:18px}.err{color:var(--red);font-size:13px;min-height:20px;margin-top:8px}.ok{color:var(--green-d)}
.steps{display:flex;gap:8px;margin:0 0 18px;padding:0;list-style:none;font-size:12px}.steps li{flex:1;text-align:center;padding:6px 4px;border-radius:8px;background:var(--chip);color:var(--sub)}.steps li.on{background:#dff5ea;color:#0f5132;font-weight:700}
.terms{max-height:260px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:12px 14px;font-size:13px;background:var(--bg)}
.terms h3{font-size:13px;margin:12px 0 2px}.muted{color:var(--sub);font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}th{color:var(--sub);font-weight:600}
.pill{font-size:11px;border-radius:99px;padding:1px 8px;background:var(--chip)}.pill.pending{background:#fff3cd;color:#7a5600}.pill.invited{background:#dbeafe;color:#1e40af}.pill.signed_up{background:#dff5ea;color:#0f5132}
pre{white-space:pre-wrap;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px;font-size:12px}
`;

function shell(title, body, { wide = false, script = "" } = {}) {
  return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title><style>${CSS}</style></head><body>
<header>${LOGO}<b>HAWK</b><span class="badge">トライアル</span></header>
<main class="${wide ? "wide" : ""}">${body}</main>
<script>
async function post(url, data){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});let j={};try{j=await r.json()}catch(e){}return {status:r.status,...j}}
${script}
</script></body></html>`;
}

const STEPS = (n) => `<ol class="steps"><li class="${n === 1 ? "on" : ""}">① お申込み</li><li class="${n === 2 ? "on" : ""}">② 招待メール</li><li class="${n === 3 ? "on" : ""}">③ アカウント作成</li><li class="${n === 4 ? "on" : ""}">④ ご利用開始</li></ol>`;

function landing() {
  return shell("HAWK トライアルのお申込み", `
<div class="card">${STEPS(1)}
<h1>デモアカウントを申し込む</h1>
<p class="lead">依頼メモを貼るだけで、オーディエンス設計・見積り・配信設計まで AI が組み立てます。お申込み後、担当者から招待メールをお送りします。</p>
<form id="f">
<label>会社名<span class="req">必須</span></label><input type="text" name="company" autocomplete="organization" required>
<label>お名前<span class="req">必須</span></label><input type="text" name="name" autocomplete="name" required>
<label>メールアドレス<span class="req">必須</span></label><input type="email" name="email" autocomplete="email" required>
<label>ご相談内容<span class="opt">任意</span></label><textarea name="note" placeholder="例：TikTok の見積りを早く出したい"></textarea>
<div class="check"><input type="checkbox" id="agree" name="agree"><label for="agree" style="margin:0;font-weight:400">入力いただいた会社名・お名前・メールアドレスを、トライアルのご案内とご連絡のために利用することに同意します（<a href="/terms" target="_blank">取り扱いについて</a>）</label></div>
<button class="full" id="b" disabled>招待メールを申し込む</button><div class="err" id="e"></div>
</form></div>
<p class="muted" style="text-align:center">招待済みの方は <a href="/login">ログイン</a></p>
<div class="card" id="done" hidden><h1 class="ok">お申込みを受け付けました</h1><p>担当者が確認のうえ、<b id="em"></b> 宛てに招待メールをお送りします。メール内のリンクからアカウントを作成してください。</p></div>`,
  { script: `
const f=document.getElementById("f"),b=document.getElementById("b"),src=new URLSearchParams(location.search).get("src")||"";
document.getElementById("agree").onchange=e=>b.disabled=!e.target.checked;
f.onsubmit=async ev=>{ev.preventDefault();b.disabled=true;const d=Object.fromEntries(new FormData(f));d.agree=!!d.agree;d.source=src;
const r=await post("/api/request",d);if(!r.ok){document.getElementById("e").textContent=r.error||"送信できませんでした";b.disabled=false;return}
if(r.already){location.href="/login";return}
f.closest(".card").hidden=true;document.getElementById("em").textContent=d.email;document.getElementById("done").hidden=false};` });
}

function login() {
  return shell("HAWK トライアル ログイン", `
<div class="card"><h1>ログイン</h1><p class="lead">招待メールから作成したアカウントでログインしてください。</p>
<form id="f"><label>メールアドレス</label><input type="email" name="email" autocomplete="email" required>
<label>パスワード</label><input type="password" name="password" autocomplete="current-password" required>
<button class="full">ログイン</button><div class="err" id="e"></div></form></div>
<p class="muted" style="text-align:center">アカウントをお持ちでない方は <a href="/">デモアカウントを申し込む</a></p>`,
  { script: `const f=document.getElementById("f");f.onsubmit=async ev=>{ev.preventDefault();const r=await post("/api/login",Object.fromEntries(new FormData(f)));if(r.ok)location.href="/app";else document.getElementById("e").textContent=r.error||"ログインできませんでした"};` });
}

const TERMS_BODY = `
<p class="muted">【たたき台・法務確認前】版: ${TERMS_VERSION}</p>
<h3>第1条（目的）</h3><p>本規約は、株式会社フリークアウト（以下「当社」）が提供する HAWK トライアル版（以下「本トライアル」）の利用条件を定めます。</p>
<h3>第2条（ご提供範囲と期間）</h3><p>本トライアルでは、与件メモの読み取り、オーディエンス設計、見積り、配信設計の作成機能をご利用いただけます。Meta・TikTok への配信連携、配信実績の取得、レポート出力はご利用いただけません。期間はアカウント作成日から当社が定める日数とし、期間満了後はご利用いただけなくなります。</p>
<h3>第3条（取得する情報と利用目的）</h3><p>当社は、お申込み・アカウント作成時に会社名、お名前、メールアドレスを取得し、また本トライアルで入力された内容（与件メモ等）を取り扱います。これらは、(1) アカウントの提供・本人確認、(2) トライアルに関するご連絡・サポート、(3) HAWK の正式なご利用に関するご案内、(4) サービス改善のための利用状況の把握、の目的に利用します。ご案内メールの受け取りは、アカウント作成画面で選択いただけます。</p>
<h3>第4条（AI による処理）</h3><p>本トライアルでは、入力された与件メモを AI（外部の AI サービスを含みます）で解析し、配信設計の案を作成します。AI の出力は参考案であり、正確性・完全性を保証しません。配信判断の前に必ずご自身でご確認ください。</p>
<h3>第5条（入力していただく内容について）</h3><p>個人を特定できる情報（顧客の氏名・連絡先等）や、第三者との契約で開示が禁じられている機密情報は入力しないでください。入力内容について必要な権限を有していることをご確認のうえご利用ください。</p>
<h3>第6条（禁止事項）</h3><p>法令・公序良俗に反する行為、本トライアルの運営を妨げる行為、アカウントの第三者への貸与・共有、競合サービスの開発等を目的とした利用、リバースエンジニアリングを禁止します。</p>
<h3>第7条（データの保存と削除）</h3><p>作成した与件・設計データは、原則としてご利用のブラウザ内に保存されます。アカウント情報は当社が管理し、削除をご希望の場合はご連絡ください。トライアル終了後、当社所定の期間経過後に削除します。</p>
<h3>第8条（免責）</h3><p>本トライアルは現状有姿で無償提供するものであり、当社は本トライアルの利用により生じた損害について、当社の故意または重過失による場合を除き責任を負いません。当社は予告なく本トライアルの内容を変更・中断・終了できるものとします。</p>
<h3>第9条（準拠法・管轄）</h3><p>本規約は日本法に準拠し、本トライアルに関する紛争は東京地方裁判所を第一審の専属的合意管轄裁判所とします。</p>`;

function terms() {
  return shell("HAWK トライアル 利用規約", `<div class="card"><h1>HAWK トライアル利用規約</h1>${TERMS_BODY}</div>`);
}

function signup({ email, name, company, token }) {
  return shell("HAWK トライアル アカウント作成", `
<div class="card">${STEPS(3)}
<h1>アカウントを作成</h1><p class="lead">パスワードを設定し、利用規約に同意するとすぐにご利用いただけます。</p>
<form id="f">
<label>メールアドレス</label><input type="email" value="${esc(email)}" readonly>
<label>会社名</label><input type="text" name="company" value="${esc(company)}">
<label>お名前</label><input type="text" name="name" value="${esc(name)}">
<label>パスワード<span class="req">必須</span><span class="opt">8文字以上</span></label><input type="password" name="password" autocomplete="new-password" minlength="8" required>
<label>パスワード（確認）<span class="req">必須</span></label><input type="password" name="password2" autocomplete="new-password" required>
<label>利用規約</label><div class="terms">${TERMS_BODY}</div>
<div class="check"><input type="checkbox" id="t1" name="agreeTerms"><label for="t1" style="margin:0;font-weight:400"><span class="req" style="margin:0 4px 0 0">必須</span>HAWK トライアル利用規約に同意します</label></div>
<div class="check"><input type="checkbox" id="t2" name="agreeEmail"><label for="t2" style="margin:0;font-weight:400"><span class="req" style="margin:0 4px 0 0">必須</span>メールアドレス等を、アカウント提供とトライアルに関するご連絡のために当社が取得・利用することに同意します</label></div>
<div class="check"><input type="checkbox" id="t3" name="marketing"><label for="t3" style="margin:0;font-weight:400"><span class="opt" style="margin:0 4px 0 0">任意</span>HAWK の新機能・セミナー等のご案内メールを受け取る</label></div>
<input type="hidden" name="token" value="${esc(token)}">
<button class="full" id="b" disabled>同意してアカウントを作成</button><div class="err" id="e"></div>
</form></div>`,
  { script: `
const f=document.getElementById("f"),b=document.getElementById("b");
const upd=()=>b.disabled=!(f.agreeTerms.checked&&f.agreeEmail.checked);f.agreeTerms.onchange=upd;f.agreeEmail.onchange=upd;
f.onsubmit=async ev=>{ev.preventDefault();const e=document.getElementById("e");
if(f.password.value!==f.password2.value){e.textContent="パスワードが一致しません";return}
b.disabled=true;const d={token:f.token.value,company:f.company.value,name:f.name.value,password:f.password.value,agreeTerms:f.agreeTerms.checked,agreeEmail:f.agreeEmail.checked,marketing:f.marketing.checked};
const r=await post("/api/signup",d);if(r.ok)location.href="/app";else{e.textContent=r.error||"作成できませんでした";upd()}};` });
}

function message(title, html) {
  return shell(title, `<div class="card"><h1>${esc(title)}</h1><p>${html}</p></div>`);
}

function admin({ gog, slack }) {
  return shell("HAWK トライアル 管理", `
<div class="card"><h1>トライアル申込の管理</h1>
<p class="muted">招待メールはこの画面から自動では送りません。「招待リンクを発行」→ ${gog ? "「Gmail 下書きを作る」で下書きを作成し、Gmail から送信してください" : "文面をコピーして、ご自身のメールから送信してください"}。Slack 通知: ${slack ? "あり" : "なし"}</p>
<table><thead><tr><th>申込日時</th><th>会社 / お名前</th><th>メール</th><th>経路・メモ</th><th>状態</th><th></th></tr></thead><tbody id="rq"></tbody></table></div>
<div class="card" id="mailbox" hidden><h2>招待メール</h2><div class="muted">宛先: <b id="mto"></b> ／ 件名: <b id="msub"></b></div><pre id="mbody"></pre>
<button id="copy" class="ghost">本文をコピー</button> <a id="mailto" class="btn" style="background:var(--chip);color:var(--ink)">メールアプリで開く</a> ${gog ? `<button id="draft">Gmail 下書きを作る</button>` : ""} <span id="mmsg" class="muted"></span></div>
<div class="card"><h2>登録済みアカウント</h2><table><thead><tr><th>登録日</th><th>会社 / お名前</th><th>メール</th><th>トライアル終了</th><th>案内メール</th><th>AI 読み取り</th></tr></thead><tbody id="us"></tbody></table></div>`,
  { wide: true, script: `
const L={pending:"招待待ち",invited:"招待済み",signed_up:"登録済み",revoked:"取消"};let cur=null;
const td=(t)=>{const x=document.createElement("td");x.textContent=t??"";return x};
const fmt=(s)=>s?new Date(s).toLocaleString("ja-JP",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"}):"";
async function load(){const r=await (await fetch("/api/admin/list")).json();const rq=document.getElementById("rq");rq.innerHTML="";
for(const x of r.requests){const tr=document.createElement("tr");tr.append(td(fmt(x.createdAt)),td(x.company+" / "+x.name),td(x.email),td([x.source,x.note].filter(Boolean).join(" ｜ ")));
const st=document.createElement("td");const p=document.createElement("span");p.className="pill "+x.status;p.textContent=L[x.status]||x.status;st.append(p);tr.append(st);
const act=document.createElement("td");if(x.status!=="signed_up"){const b=document.createElement("button");b.textContent=x.inviteToken?"招待メールを表示":"招待リンクを発行";b.onclick=()=>invite(x.id);act.append(b)}tr.append(act);rq.append(tr)}
const us=document.getElementById("us");us.innerHTML="";for(const u of r.users){const tr=document.createElement("tr");tr.append(td(fmt(u.createdAt)),td(u.company+" / "+u.name),td(u.email),td(fmt(u.trialEndsAt)),td(u.consent?.marketing?"受け取る":"—"),td((u.usage?.total||0)+"回"));us.append(tr)}}
async function invite(id){const r=await post("/api/admin/invite",{id});if(!r.ok)return alert(r.error||"失敗しました");cur=id;const m=r.mail;
mto.textContent=m.to;msub.textContent=m.subject;mbody.textContent=m.body;mailbox.hidden=false;mmsg.textContent="";
mailto.href="mailto:"+encodeURIComponent(m.to)+"?subject="+encodeURIComponent(m.subject)+"&body="+encodeURIComponent(m.body);mailbox.scrollIntoView({behavior:"smooth"});load()}
copy.onclick=async()=>{await navigator.clipboard.writeText(mbody.textContent);mmsg.textContent="コピーしました"};
const dr=document.getElementById("draft");if(dr)dr.onclick=async()=>{dr.disabled=true;mmsg.textContent="作成中…";const r=await post("/api/admin/draft",{id:cur});mmsg.textContent=r.ok?"Gmail に下書きを作成しました（未送信）。Gmail から送信してください":(r.error||"作成できませんでした");dr.disabled=false};
load();setInterval(load,30000);` });
}

module.exports = { landing, login, signup, terms, message, admin, TERMS_VERSION, LOGO, esc };
