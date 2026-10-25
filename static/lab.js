/* Challenge Lab, sharing controls, documents and reviewer dashboard.
   Loaded after the main script; hooks into its views instead of replacing them. */
const CRIT=[["correctness","Analysis & correctness"],["reasoning","Reasoning & trade-offs"],["understanding","Understanding (follow-ups)"],["debugging","Debugging & decisions"],["communication","Communication"]];
const fmt=d=>new Date(d).toLocaleString([], {dateStyle:"medium",timeStyle:"short"});
const live=c=>c.status==="issued"&&new Date(c.deadline_at)>Date.now();
const stateOf=c=>c.status==="reviewed"?"REVIEWED":c.status==="submitted"?"SUBMITTED":live(c)?"AVAILABLE":"EXPIRED";
const levelOf=c=>c.level||(c.review?"HUMAN-VERIFIED":c.auto?"AUTOMATED CHECK ONLY":"NOT SUBMITTED");
const lchip=l=>`<span class="pill" style="background:${l==="HUMAN-VERIFIED"?"#a8dcc0":l==="AUTOMATED CHECK ONLY"?"#f1e26a":"#ddd"}">${l}</span>`;
const failBox=(m)=>`<div class="warn">${esc(m)}</div>`;
const needLogin=()=>S.user&&S.user.role;

async function labLoad(){S.chsBusy=true;try{S.chs=await api("/challenges");S.chErr=""}catch(x){S.chs=[];S.chErr=x.message}S.chsBusy=false;render()}
async function recLoad(){try{S.rec=await api("/recruiter/candidates"+(S.recOpp?`?opportunity_id=${S.recOpp}`:""));S.recErr=""}catch(x){S.rec=[];S.recErr=x.message}render()}
function ensureChs(){if(S.chs===undefined&&!S.chsBusy&&S.user&&S.user.role==="student")labLoad()}

/* ---- hooks into the existing app ---- */
const _go=window.go;window.go=function(v,q){if(v!=="ch")clearInterval(S.tm);_go(v,q);if(v==="challenges"&&S.user.role==="student")labLoad();if(v==="rec")recLoad()};
const _chrome=window.chrome;window.chrome=function(){_chrome();const nav=$("nav");
 if(S.user.role==="student"){const b=nav.querySelector('[data-k="challenges"]');if(b)b.textContent="Challenge Lab";if(S.view==="ch"&&b)b.classList.add("on")}
 else{const b=nav.querySelector('[data-k="cands"]');if(b&&!nav.querySelector('[data-k="rec"]')){const n=b.cloneNode(true);n.dataset.k="rec";n.setAttribute("onclick","go('rec')");n.textContent="Compare";n.className=S.view==="rec"?"on":"";b.after(n)}}};
const _pm=window.profileModal;window.profileModal=function(){_pm();const box=$("modal").querySelector(".box");
 if(S.user.role==="student")box.insertAdjacentHTML("beforeend",`<p><button class="btn alt" onclick="sharingModal()">SHARING &amp; PRIVACY</button><button class="btn alt" onclick="docsModal()">MY DOCUMENTS</button></p>`)};
const _ev=window.evidence;window.evidence=function(){ensureChs();const p=P();
 return[..._ev().filter(e=>e.type!=="CHALLENGE RESULT"),...(p.documents||[]).map(d=>({type:"DOCUMENT",status:"UPLOADED",title:`${d.name} (${d.kind})`})),
  ...(S.chs||[]).filter(c=>c.status!=="issued").map(c=>({type:"CHALLENGE",status:c.review?"HUMAN-VERIFIED":"SUBMITTED · AUTOMATED CHECK ONLY",title:`${c.title} — ${c.skill}`}))]};
const _pc=window.pageContent;window.pageContent=function(i){const r=_pc(i);if(PAGES[i][0]!=="challenges")return r;ensureChs();
 return[`<div class="display">Challenge<br>Lab</div><p class="mono">Timed projects, scored on a rubric</p><button class="btn" onclick="go('challenges')">OPEN CHALLENGE LAB</button>`,
  (S.chs||[]).length?S.chs.slice(0,4).map(chCard).join(""):emp("OPEN CHALLENGE LAB","go('challenges')")]};
const _lf=window.leftFor,_rf=window.rightFor;
window.leftFor=function(){const v=S.view;const n=v==="challenges"&&S.user.role==="student"?labLeft():v==="ch"?chLeft():v==="rec"?recLeft():null;return n!==null?n:_lf()};
window.rightFor=function(){const v=S.view;const n=v==="challenges"&&S.user.role==="student"?labRight():v==="ch"?chRight():v==="rec"?recRight():null;return n!==null?n:_rf()};
window.candView=id=>fullPassport(id);
window.startCh=id=>openCh(id);

/* ---- student: challenge lab ---- */
function labLeft(){const l=S.chs||[],n=f=>l.filter(f).length;
 return`<div class="display">Challenge<br>Lab</div><p class="mono">Short timed projects. AI tools are allowed — you must explain and defend your work.</p>
 <p class="mono">${n(live)} available · ${n(c=>c.status==="submitted")} submitted · ${n(c=>c.status==="reviewed")} reviewed</p>
 <div class="doc"><b class="mono">New challenge</b><br><select id="lg_o" style="width:100%;padding:6px;margin:6px 0"><option value="">Based on my skills</option>${S.opps.map(o=>`<option value="${o.id}">${esc(o.title)} — ${esc(o.org)}</option>`).join("")}</select>
 <input id="lg_s" placeholder="Skill (optional, e.g. python)" style="width:100%;padding:6px"><button class="btn" id="lg_b" onclick="labGenerate()">GENERATE CHALLENGE</button></div>`}
function chCard(c){const t=new Date(c.deadline_at);return`<div class="doc" onclick="openCh('${c.id}')"><span class="pill">${stateOf(c)}</span>${lchip(levelOf(c))}<br><b>${esc(c.title)}</b><br><span class="mono">${esc(c.skill)} · ${c.limit} min · due ${fmt(t)}</span></div>`}
function labRight(){if(S.chs===undefined||S.chsBusy)return`<p class="mono">Loading…</p>`;if(S.chErr)return failBox("Could not load challenges: "+S.chErr);
 return S.chs.length?S.chs.map(chCard).join(""):`<div class="empty"><div class="display" style="font-size:26px">No challenges yet</div><p class="mono">Generate one from your skills or an opportunity.</p></div>`}
async function labGenerate(){const b=$("lg_b");b.disabled=true;b.textContent="GENERATING…";
 try{const c=await api("/challenges",{method:"POST",body:{opportunity_id:$("lg_o").value||null,skill:$("lg_s").value.trim()||null}});S.chs=[c,...(S.chs||[])];openCh(c.id)}
 catch(x){toast(x.message);b.disabled=false;b.textContent="GENERATE CHALLENGE"}}
async function openCh(id){try{S.chOpen=await api("/challenges/"+id);S.view="ch";chrome();render();clearInterval(S.tm);S.tm=setInterval(tick,1000);tick()}catch(x){toast(x.message)}}
function tick(){const e=$("cd");if(!e||S.view!=="ch"){clearInterval(S.tm);return}const c=S.chOpen,ms=new Date(c.deadline_at)-Date.now();
 e.textContent=c.status==="reviewed"?"REVIEWED":ms>0?`${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,"0")} LEFT`:"TIME UP"}
function chLeft(){const c=S.chOpen;if(!c)return"";const L=a=>a.map(x=>`<li>${esc(x)}</li>`).join("");
 return`<button class="btn" onclick="go('challenges')">← LAB</button><div class="mono">${esc(c.skill)} · ${c.source==="ai"?"AI-generated":"template"} · <b id="cd"></b></div><div class="display" style="font-size:32px">${esc(c.title)}</div><p>${esc(c.scenario)}</p>
 ${c.dataset?`<pre class="brief" style="background:#111;color:#a8dcc0;padding:8px;font-size:11px;white-space:pre-wrap">${esc(c.dataset)}</pre>`:""}
 <p class="mono">Constraints</p><ul>${L(c.constraints)}</ul><p class="mono">Deliverables</p><ul>${L(c.deliverables)}</ul>`}
function chRight(){const c=S.chOpen;if(!c)return"";const own=S.user.role==="student",open=own&&c.status!=="reviewed"&&new Date(c.deadline_at)>Date.now();
 const hist=c.subs.map(s=>`<div class="doc"><span class="mono">Submission ${s.n} · ${fmt(s.at)}${s.ai_used?" · AI tools used":""}</span></div>`).join("");
 const form=open?`<p class="mono">Milestones completed</p>${c.milestones.map((m,i)=>`<label><input type="checkbox" class="cm" value="${esc(m)}" style="width:auto"> ${esc(m)}</label><br>`).join("")}
 <textarea id="ch_a" placeholder="Your solution" style="width:100%;height:90px;margin-top:6px"></textarea><textarea id="ch_r" placeholder="Your reasoning and trade-offs" style="width:100%;height:70px"></textarea>
 <label><input type="checkbox" id="ch_ai" style="width:auto"> I used AI tools</label><input id="ch_n" placeholder="How did you use them? (required if checked)" style="width:100%;padding:6px">
 <p class="mono">Follow-up questions</p>${c.followups.map((q,i)=>`<p>${esc(q)}</p><textarea class="cf" style="width:100%;height:50px"></textarea>`).join("")}
 <button class="btn" id="cs_b" onclick="submitLab()">${c.subs.length?"RESUBMIT":"SUBMIT"}</button>`:`<p class="mono">${own?"This challenge is closed for submissions.":""}</p>`;
 return`${hist}${c.auto?assessBox(c):""}${form}`}
function assessBox(c){const a=c.auto,r=c.review;
 return`<div class="brief"><span class="mono">${r?"HUMAN-VERIFIED by "+esc(r.reviewer):"AUTOMATED CHECK ONLY — NOT VERIFIED"}</span><table style="width:100%;font-size:12px">${CRIT.map(([k,l])=>`<tr><td>${l}</td><td>${r?r.scores[k]+"/4":a.scores[k]==null?"needs reviewer":a.scores[k]+"/4"}</td></tr>`).join("")}</table>
 <p class="mono">${r?`Rubric score ${r.pct}%`:`Partial score ${a.partial_pct??"—"}% (${a.facts_found}/${a.facts_total} data facts found)`}</p>${r?`<p><b>Reviewer feedback:</b> ${esc(r.feedback)}</p>`:`<p class="mono">${esc(a.note)}</p>`}</div>`}
async function submitLab(){const b=$("cs_b");b.disabled=true;
 const body={answer:$("ch_a").value.trim(),reasoning:$("ch_r").value.trim(),ai_used:$("ch_ai").checked,ai_notes:$("ch_n").value.trim(),followups:[...document.querySelectorAll(".cf")].map(x=>x.value.trim()),milestones:[...document.querySelectorAll(".cm:checked")].map(x=>x.value)};
 try{S.chOpen=await api(`/challenges/${S.chOpen.id}/submit`,{method:"POST",body});S.chs=undefined;toast("SUBMITTED — automated check only until a reviewer verifies it");render()}
 catch(x){toast(x.message.includes("least")||x.message.length<200?x.message:"Check your answers");b.disabled=false}}

/* ---- sharing & documents ---- */
async function sharingModal(){try{const r=await api("/consent"),c=r.consent;
 modal(`<h3>Sharing &amp; privacy</h3><p class="mono">Who may open your full Skill Passport?</p>
 ${[["private","Nobody (private)"],["applicants","Only organisers I applied to"],["reviewers","Any verified organiser, teacher or recruiter account"]].map(([v,l])=>`<label><input type="radio" name="cl" value="${v}" ${c.level===v?"checked":""} style="width:auto"> ${l}</label><br>`).join("")}
 <p><label><input type="checkbox" id="cd_d" ${c.documents?"checked":""} style="width:auto"> Share my uploaded documents</label><br><label><input type="checkbox" id="cd_c" ${c.challenges?"checked":""} style="width:auto"> Share my challenge results</label></p>
 <button class="btn" onclick="saveConsent()">SAVE</button><p class="mono">Recent views of your passport</p>${r.access_log.length?r.access_log.slice().reverse().map(l=>`<div class="mono">${esc(l.viewer)} · ${fmt(l.at)}</div>`).join(""):'<div class="mono">No one has viewed it yet.</div>'}`)}catch(x){toast(x.message)}}
async function saveConsent(){try{await api("/consent",{method:"PUT",body:{level:document.querySelector("input[name=cl]:checked").value,documents:$("cd_d").checked,challenges:$("cd_c").checked}});closeM();toast("Sharing settings saved")}catch(x){toast(x.message)}}
function docsModal(){const d=P().documents||[];modal(`<h3>My documents</h3><p class="mono">PDF, DOCX or TXT up to 3 MB. Text is extracted and stored; shared only if you allow it.</p>
 <select id="dk"><option value="certificate">Certificate</option><option value="transcript">Transcript</option><option value="project">Project</option><option value="other">Other</option></select><input type="file" id="df" accept=".pdf,.docx,.txt"><button class="btn" onclick="uploadDoc()">UPLOAD</button>
 ${d.map(x=>`<div class="doc"><b>${esc(x.name)}</b> <span class="mono">${esc(x.kind)}</span> <button class="btn alt" onclick="delDoc('${x.id}')">DELETE</button></div>`).join("")||'<p class="mono">No documents yet.</p>'}`)}
async function uploadDoc(){const f=$("df").files[0];if(!f){toast("Choose a file first");return}const fd=new FormData();fd.append("file",f);fd.append("kind",$("dk").value);
 try{await api("/documents",{method:"POST",body:fd});S.profile=(await api("/profile")).profile;docsModal();render();toast("Document added")}catch(x){toast(x.message)}}
async function delDoc(id){try{await api("/documents/"+id,{method:"DELETE"});S.profile=(await api("/profile")).profile;docsModal();render()}catch(x){toast(x.message)}}

/* ---- recruiter: dashboard, passport, review, compare ---- */
function recLeft(){return`<div class="display">Candidate<br>dashboard</div><p class="mono">Only students who shared their passport appear. Similarity is not a talent ranking.</p>
 <select id="ro" style="width:100%;padding:6px" onchange="S.recOpp=this.value;S.cmp=[];recLoad()"><option value="">All sharing students</option>${S.opps.filter(o=>o.creator===S.user.id).map(o=>`<option value="${o.id}" ${S.recOpp===o.id?"selected":""}>${esc(o.title)}</option>`).join("")}</select>
 <button class="btn" onclick="recCompare()">COMPARE SELECTED (${(S.cmp||[]).length})</button><p class="mono">Select 2 to 3 candidates</p>`}
function recRight(){if(S.rec===undefined)return`<p class="mono">Loading…</p>`;if(S.recErr)return failBox(S.recErr);
 return S.rec.length?S.rec.map(c=>`<div class="doc"><label><input type="checkbox" style="width:auto" ${(S.cmp||[]).includes(c.id)?"checked":""} onchange="toggleCmp('${c.id}',this)"> <b>${esc(c.name)}</b></label> <span class="mono">${esc(c.field)}</span>${c.similarity!=null?` <span class="sim">${(c.similarity*100).toFixed(1)}%</span>`:""}${c.applied?' <span class="pill">APPLIED</span>':""}<br>
 ${c.skills.slice(0,6).map(s=>`<span class="pill">${esc(s)}</span>`).join("")}<br><span class="mono">${c.projects} projects</span> ${c.challenges.map(h=>`<button class="btn alt" onclick="viewCh('${h.id}')">${esc(h.skill)} · ${levelOf(h)}</button>`).join("")||'<span class="mono">no shared challenge results</span>'}<br><button class="btn" onclick="fullPassport('${c.id}')">VIEW PASSPORT</button></div>`).join(""):
 `<div class="empty"><div class="display" style="font-size:26px">No shared passports yet</div><p class="mono">Students appear here after they choose to share their Skill Passport.</p></div>`}
function toggleCmp(id,el){S.cmp=S.cmp||[];if(el.checked){if(S.cmp.length>=3){el.checked=false;toast("Compare up to 3 candidates");return}S.cmp.push(id)}else S.cmp=S.cmp.filter(x=>x!==id);document.querySelector(".btn[onclick='recCompare()']").textContent=`COMPARE SELECTED (${S.cmp.length})`}
function recCompare(){const sel=(S.rec||[]).filter(c=>(S.cmp||[]).includes(c.id));if(sel.length<2){toast("Select at least 2 candidates");return}
 const best=c=>{const h=c.challenges.filter(x=>x.review).sort((a,b)=>b.review.pct-a.review.pct)[0];return h};
 modal(`<h3>Side-by-side</h3><div style="overflow:auto"><table style="width:100%;font-size:12px;border-collapse:collapse"><tr><th></th>${sel.map(c=>`<th>${esc(c.name)}</th>`).join("")}</tr>
 <tr><td>Field</td>${sel.map(c=>`<td>${esc(c.field)}</td>`).join("")}</tr><tr><td>Profile similarity</td>${sel.map(c=>`<td>${c.similarity!=null?(c.similarity*100).toFixed(1)+"%":"—"}</td>`).join("")}</tr>
 <tr><td>Projects</td>${sel.map(c=>`<td>${c.projects}</td>`).join("")}</tr><tr><td>Skills</td>${sel.map(c=>`<td>${c.skills.map(esc).join(", ")}</td>`).join("")}</tr>
 <tr><td>Challenge status</td>${sel.map(c=>`<td>${c.challenges.map(h=>esc(h.skill)+": "+levelOf(h)).join("<br>")||"none shared"}</td>`).join("")}</tr>
 ${CRIT.map(([k,l])=>`<tr><td>${l}</td>${sel.map(c=>{const h=best(c);return`<td>${h?h.review.scores[k]+"/4 (human)":"—"}</td>`}).join("")}</tr>`).join("")}</table></div><p class="mono">Rubric rows show human-reviewed results only.</p>`)}
async function fullPassport(id){try{const p=await api(`/students/${id}/passport`);
 modal(`<div class="mono">Skill Passport</div><div class="display" style="font-size:32px">${esc(p.name)}</div><p class="mono">${esc(p.field)}</p>${p.bio?`<p>${esc(p.bio)}</p>`:""}
 <p>${p.skills.map(s=>`<span class="stamp">${esc(s)}</span>`).join("")||"No skills listed."}</p>
 ${p.projects.map(x=>`<div class="doc"><b>${esc(x.title)}</b><br>${esc(x.description||"")}<br><span class="mono">${esc(x.tech||"")}</span></div>`).join("")}
 ${p.achievements.map(x=>`<div class="doc"><b>${esc(x.title)}</b> <span class="mono">${esc(x.kind||"")} · SELF-REPORTED</span></div>`).join("")}
 ${p.links.map(x=>`<div class="doc"><span class="pill">${esc(x.kind)}</span><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${esc(x.url)}</a></div>`).join("")}
 ${(p.documents||[]).map(d=>`<div class="doc"><span class="pill">DOCUMENT</span><b>${esc(d.name)}</b> <span class="mono">${esc(d.kind)}</span><br><span class="mono">${esc(d.excerpt.slice(0,240))}</span></div>`).join("")}
 <p class="mono">Challenge results</p>${(p.challenges||[]).map(h=>`<div class="doc" onclick="viewCh('${h.id}')">${lchip(levelOf(h))} <b>${esc(h.title)}</b> <span class="mono">${esc(h.skill)}</span></div>`).join("")||'<p class="mono">None shared.</p>'}`)}catch(x){toast(x.message)}}
async function viewCh(id){try{const c=await api("/challenges/"+id),rv=c.review;
 modal(`<div class="mono">${esc(c.skill)} · ${lchip(levelOf(c))}</div><div class="display" style="font-size:28px">${esc(c.title)}</div><p>${esc(c.scenario)}</p>
 ${c.subs.map(s=>`<div class="doc"><span class="mono">Submission ${s.n} · ${fmt(s.at)} · AI tools: ${s.ai_used?"yes — "+esc(s.ai_notes):"no"}</span><p><b>Solution</b><br>${esc(s.answer)}</p><p><b>Reasoning</b><br>${esc(s.reasoning)}</p>${c.followups.map((q,i)=>`<p class="mono">${esc(q)}</p><p>${esc(s.followups[i]||"")}</p>`).join("")}</div>`).join("")}
 ${c.auto?assessBox(c):""}${S.user.role==="creator"?`<p class="mono">Reviewer rubric (0–4)</p>${CRIT.map(([k,l])=>`<label>${l} <select id="rv_${k}">${[0,1,2,3,4].map(n=>`<option ${rv&&rv.scores[k]===n?"selected":""}>${n}</option>`).join("")}</select></label><br>`).join("")}<textarea id="rv_f" placeholder="Feedback for the student" style="width:100%;height:60px">${rv?esc(rv.feedback):""}</textarea><button class="btn" onclick="sendReview('${c.id}')">SAVE REVIEW</button>`:""}`)}catch(x){toast(x.message)}}
async function sendReview(id){try{await api(`/challenges/${id}/review`,{method:"POST",body:{scores:Object.fromEntries(CRIT.map(([k])=>[k,+$("rv_"+k).value])),feedback:$("rv_f").value.trim()}});toast("Review saved — marked HUMAN-VERIFIED");closeM();recLoad()}catch(x){toast(x.message)}}
