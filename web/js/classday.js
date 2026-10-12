// Class day (0.2.2): the instructor's Home. Setup until the class is ready, then one big "Start class" -- pick the
// class, tick today's plan (a lesson, leadership scenarios, live questions from any study card, videos), and run it
// from one run sheet: each item has its own button, the projector screens come back here when they end, and the
// plan is kept for the rest of the day on this computer. Listeners in JS (the page's policy blocks inline handlers).
'use strict';

const CD_KEY = 'cadetfoundry-classday';
const cdToday = () => new Date().toISOString().slice(0, 10);
const cdLoad = () => {
  try {
    const p = JSON.parse(localStorage.getItem(CD_KEY) || 'null');
    return p && p.date === cdToday() ? p : null;
  } catch (e) { return null; }
};
const cdSave = p => { try { localStorage.setItem(CD_KEY, JSON.stringify(p)); } catch (e) { } };
const cdClear = () => { try { localStorage.removeItem(CD_KEY); } catch (e) { } };
// A plan still being built (owner, 2026-10-12: leaving the screen lost everything ticked). Saved on every change; Home
// opens the planner again with it until Build or Cancel. Today only, like the plan itself.
const CD_DRAFT = 'cadetfoundry-classday-draft';
const cdDraftLoad = () => {
  try {
    const p = JSON.parse(localStorage.getItem(CD_DRAFT) || 'null');
    return p && p.date === cdToday() ? p : null;
  } catch (e) { return null; }
};
const cdDraftSave = p => { try { localStorage.setItem(CD_DRAFT, JSON.stringify(p)); } catch (e) { } };
const cdDraftClear = () => { try { localStorage.removeItem(CD_DRAFT); } catch (e) { } };
const CD_ICON = { lesson: '📋', scenario: '🗳️', question: '📡', video: '🎬', prompt: '💬', card: '🗂️' };
// Today's class runs in named steps (owner, 2026-10-11): Opening, Learn, Discuss, Engage, Assign, Close, then Progress.
const CD_PHASES = [['open', 'Opening', 'A question to get them thinking'], ['learn', 'Learn', 'Study cards and videos'],
  ['discuss', 'Discuss', 'Leadership scenarios — the class votes'], ['engage', 'Engage', 'Live questions'],
  ['assign', 'Assign', "Today's lesson"], ['close', 'Close', 'An exit question']];
const cdPhase = it => it.type === 'prompt' ? (it.id === 'close' ? 'close' : 'open')
  : ({ card: 'learn', video: 'learn', scenario: 'discuss', question: 'engage', lesson: 'assign' })[it.type] || 'learn';
// Suggested questions (the instructor can rewrite them). A different one each day.
const CD_OPENERS = ['Think of a leader you would follow anywhere. What is one thing they do that makes you trust them?',
  'What is the difference between being in charge and being a leader?',
  'When did someone\'s small act of respect make a difference to you?',
  'What is one thing a good teammate does that nobody notices?',
  'What does "lead by example" look like in this classroom?'];
const CD_CLOSERS = ['What is one thing from today you will use this week?',
  'What is one question you still have about today\'s topic?',
  'If you had to teach today\'s lesson to a new Cadet, what would you say first?'];
const cdDaily = list => list[Math.floor(Date.now() / 86400000) % list.length];

const homeForCadets = loaders.home;
loaders.home = async () => {
  if ((STATUS.kind || 'cadet') !== 'instructor') return homeForCadets();
  return classDayHome();
};

async function classDayHome() {
  const body = $('#homeBody');
  if (!body.innerHTML.trim()) body.innerHTML = '<p class="faint">Loading your class…</p>';
  const lock = await api('/api/lock');
  const name = (lock.current && lock.current.name) || '';
  const ov = await api('/api/instructor/overview');
  if (ov.error) {                                  // signed in, but the class records are locked: the Class PIN, right here
    body.innerHTML = `<h2>Hi${name ? ', ' + esc(name) : ''}</h2>
      <div class="card" style="border-color:var(--tan)"><h3>🔐 Open your class</h3>
        <p>Type the <b>Class PIN</b> (the one you made when you set up Cadet Foundry) to open your class for today.</p>
        <div class="row" style="flex-wrap:wrap;gap:8px"><input id="cdPin" type="password" inputmode="numeric" maxlength="12" placeholder="Class PIN"
          aria-label="Class PIN" style="flex:1;min-width:160px;font-size:20px;letter-spacing:.2em"><button class="btn primary" id="cdPinGo">Open</button></div>
        <p class="faint" id="cdPinMsg" role="alert"></p></div>`;
    const go = async () => {
      const r = await api('/api/instructor/unlock', { admin: $('#cdPin').value });
      if (r.ok) classDayHome(); else $('#cdPinMsg').textContent = r.error;
    };
    $('#cdPinGo').addEventListener('click', go);
    $('#cdPin').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    $('#cdPin').focus();
    return;
  }
  if (!lock.terms_ok) {                            // set up before the terms existed, or the terms changed: ask once
    body.innerHTML = `<h2>Hi${name ? ', ' + esc(name) : ''}</h2>
      <div class="card" style="border-color:var(--tan)"><h3>📄 Terms of use and Privacy notice</h3>
        <p>Cadet Foundry now has plain-English <a href="#" data-legal="terms">Terms of use</a> and a <a href="#" data-legal="privacy">Privacy notice</a>.
          The short version: it's a free community project, it isn't official, and your Cadets' data stays on this computer.</p>
        <label style="display:flex;gap:10px;align-items:flex-start;margin:8px 0">
          <input type="checkbox" id="cdAgree" style="width:24px;height:24px;flex:none;margin-top:2px">
          <span>I've read and agree to the Terms of use and the Privacy notice.</span></label>
        <button class="btn primary" id="cdAgreeGo">Continue</button><p class="faint" id="cdAgreeMsg" role="alert"></p></div>`;
    $('#cdAgreeGo').addEventListener('click', async () => {
      if (!$('#cdAgree').checked) { $('#cdAgreeMsg').textContent = 'Tick the box to agree first.'; return; }
      const r = await api('/api/terms/accept', {});
      if (r.error) { $('#cdAgreeMsg').textContent = r.error; return; }
      classDayHome();
    });
    return;
  }
  const plan = cdLoad();
  classDayActive = !!plan;
  body.innerHTML = `<h2>Hi${name ? ', ' + esc(name) : ''}</h2><div id="cdUsb"></div><div id="cdSetup"></div><div id="cdMain"></div>
    <div class="card"><h3>More tools</h3><div class="tiles" style="margin:0">
      <button class="tile" data-cdgo="class"><span>👥</span>Class<small>Cadets, units, ranks</small></button>
      <button class="tile" data-cdgo="lessons"><span>📋</span>Lessons<small>Write and assign</small></button>
      <button class="tile" data-cdgo="present"><span>🖥️</span>Present<small>Scenarios, live questions</small></button>
      <button class="tile" data-cdgo="reports"><span>📊</span>Reports<small>How they're doing</small></button>
      ${lock.sample ? '' : '<button class="tile" id="cdSample"><span>🧪</span>Sample class<small>See it with made-up Cadets</small></button>'}</div>
      <p class="faint" id="cdSampleMsg" role="status"></p></div>`;
  body.querySelectorAll('[data-cdgo]').forEach(b => b.addEventListener('click', () => { openView('instructor'); loaders.instructor(b.dataset.cdgo); }));
  usbHomeCards($('#cdUsb'), lock);
  if ($('#cdSample')) $('#cdSample').addEventListener('click', () => startSample($('#cdSample'), $('#cdSampleMsg')));
  const ready = await classSetup($('#cdSetup'), ov, classDayHome, { compactWhenReady: true });
  const main = $('#cdMain');
  const draft = cdDraftLoad();
  if (draft) return planner(main, ov, { ...draft, resumed: true });   // pick up where they left off
  if (plan) return runSheet(main, plan, ov);
  main.innerHTML = `<button class="btn primary" id="cdStart" style="width:100%;min-height:72px;font-size:24px;margin:4px 0 16px">▶ Start class</button>
    ${ready ? '' : '<p class="faint" style="margin-top:-8px">You can plan class now; finish the setup steps above before Cadets join.</p>'}`;
  $('#cdStart').addEventListener('click', () => planner(main, ov));
}

// Step 1 and 2: which class, and what's on today's plan.
async function planner(main, ov, prev) {
  main.innerHTML = '<p class="faint">Loading your lessons, scenarios and videos…</p>';
  const [ls, sc, qz, vd] = await Promise.all([api('/api/instructor/lessons'), api('/api/instructor/scenarios'),
    api('/api/instructor/quiz'), api('/api/videos')]);
  const lessons = ls.lessons || [], scenarios = sc.scenarios || [], cards = qz.cards || [], videos = vd.videos || [];
  const was = prev || {}, had = (t, id) => (was.items || []).some(i => i.type === t && i.id === id);
  let ready = false;
  const saveDraft = () => { if (ready && $('#cdBuild')) cdDraftSave(collect()); };
  let questions = (was.items || []).filter(i => i.type === 'question');
  const teach = (was.items || []).filter(i => i.type === 'card');
  const svcName = s => s === 'joint' ? 'All services' : (STATUS.services || {})[s] || s;
  const box = 'max-height:280px;overflow:auto;border:1px solid var(--line);border-radius:10px;padding:4px 10px';
  const pick = (type, id, label, sub, checked, kind = 'checkbox', name = '') => `<label style="display:flex;gap:10px;align-items:center;min-height:44px;cursor:pointer">
    <input type="${kind}" ${name ? `name="${name}"` : ''} data-cd="${type}" value="${esc(id)}" ${checked ? 'checked' : ''} style="width:22px;height:22px;flex:none">
    <span>${label}${sub ? ` <span class="faint">${sub}</span>` : ''}</span></label>`;
  main.innerHTML = `${was.resumed ? '<p class="faint" style="margin:0 0 8px">✎ Picked up where you left off — everything you ticked is still here.</p>' : ''}
    <div class="card" style="border-color:var(--tan)"><h3>▶ Start class</h3>
      <label for="cdUnit"><b>1. Which class?</b></label>
      ${ov.units.length ? `<select id="cdUnit">${ov.units.map(u => `<option value="${esc(u.id)}" ${u.id === was.unit ? 'selected' : ''}>${esc(u.name)}</option>`).join('')}</select>`
        : '<p class="faint">Make your class first (step 1 above). You can still plan today, and assign the lesson to everyone.</p>'}
      <p style="margin:18px 0 4px"><b>2. What's on today's plan?</b> <span class="faint">Class runs in this order. Tick anything — you can skip any step.</span></p></div>
    ${cdPromptCard('open', '💬 Opening', 'Put a question on the projector. Cadets think for a minute, then a few share.', was, CD_OPENERS)}
    <div class="card"><h3>🗂️ Learn — study cards to teach</h3>
      <p class="faint">Each card goes on the projector as a few slides, then a few check-on-learning questions.</p>
      <input id="cdTeachFind" placeholder="Search study cards (e.g. officer, salute, Navy ranks)" aria-label="Search study cards to teach">
      <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:6px"><select id="cdTeach" aria-label="Study card to teach" style="flex:3;min-width:200px"></select>
        <button class="btn" id="cdAddTeach">Add</button></div>
      <div id="cdTeachList" style="margin-top:8px"></div></div>
    <div class="card"><h3>🎬 Learn — videos</h3>
      <div style="${box}">${videos.map(v => pick('video', v.id, esc(v.title), `${esc(svcName(v.service))} · ${v.kind === 'youtube' ? 'YouTube (internet)' : v.local ? `${esc(v.length)} · plays offline` : 'not saved — needs internet'}`, had('video', v.id))).join('') || '<p class="faint">No videos.</p>'}</div></div>
    <div class="card"><h3>🗳️ Discuss — leadership scenarios</h3>
      <p class="faint">The class votes on their phones, then you reveal the discussion guidance. Your debrief notes stay on your screen.</p>
      <div style="${box}">${scenarios.map(s => pick('scenario', s.id, esc(s.title), esc(s.competency), had('scenario', s.id))).join('') || '<p class="faint">No scenarios.</p>'}</div></div>
    <div class="card"><h3>📡 Engage — live questions</h3>
      <p class="faint">Pick a study card. Its questions go on the projector one at a time; Cadets answer on their phones.</p>
      <input id="cdCardFind" placeholder="Search study cards (e.g. salute, ranks, core values)" aria-label="Search study cards">
      <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:6px"><select id="cdCard" aria-label="Study card" style="flex:3;min-width:200px"></select>
        <select id="cdCount" aria-label="How many questions" style="flex:1;min-width:110px">${[1, 2, 3, 4, 5].map(n => `<option value="${n}" ${n === 3 ? 'selected' : ''}>${n} question${n === 1 ? '' : 's'}</option>`).join('')}</select>
        <button class="btn" id="cdAddQ">Add</button></div>
      <div id="cdQList" style="margin-top:8px"></div></div>
    <div class="card"><h3>📋 Assign — a lesson</h3>
      ${lessons.length ? `<div style="${box}">${pick('lesson', '', 'No lesson today', '', !(was.items || []).some(i => i.type === 'lesson'), 'radio', 'cdLesson')}
        ${lessons.map(l => pick('lesson', l.id, esc(l.title), [l.let_level && `${STATUS.level_label || 'Year'} ${l.let_level}`, l.questions.length && `${l.questions.length} questions`].filter(Boolean).map(esc).join(' · '), had('lesson', l.id), 'radio', 'cdLesson')).join('')}</div>`
        : `<p class="faint">No lessons yet. Add Cadet Foundry's starter lessons — ready to assign, built from cited study cards — or write your own.</p>
           <button class="btn small primary" id="cdStarters">📦 Add the starter lessons</button>`}
      <button class="btn small" id="cdNewLesson" style="margin-top:8px">＋ Write a new lesson</button></div>
    ${cdPromptCard('close', '🚪 Close', 'An exit question on the projector before the bell.', was, CD_CLOSERS)}
    <div class="row" style="gap:8px;flex-wrap:wrap;margin-bottom:20px"><button class="btn primary" id="cdBuild" style="flex:1;min-height:56px;font-size:19px">Build today's class →</button>
      <button class="btn" id="cdCancel">Cancel</button></div><p class="faint" id="cdMsg" role="alert"></p>`;
  const fillCards = () => {
    const f = $('#cdCardFind').value.trim().toLowerCase();
    const list = cards.filter(c => c.questions && (!f || c.title.toLowerCase().includes(f))).slice(0, 200);
    $('#cdCard').innerHTML = list.map(c => `<option value="${esc(c.id)}">${esc(c.title)} (${c.questions})</option>`).join('') || '<option value="">No cards match</option>';
  };
  const drawQ = () => {
    $('#cdQList').innerHTML = questions.map((q, i) => `<div class="row" style="justify-content:space-between;gap:8px;margin:4px 0;flex-wrap:nowrap">
      <span>📡 ${esc(q.title)} <span class="faint">${esc(q.sub)}</span></span><button class="btn small" data-cdrmq="${i}" aria-label="Remove">✕</button></div>`).join('');
    $('#cdQList').querySelectorAll('[data-cdrmq]').forEach(b => b.addEventListener('click', () => { questions.splice(Number(b.dataset.cdrmq), 1); drawQ(); }));
    saveDraft();
  };
  const fillTeach = () => {
    const f = $('#cdTeachFind').value.trim().toLowerCase();
    const list = cards.filter(c => !f || c.title.toLowerCase().includes(f)).slice(0, 200);
    $('#cdTeach').innerHTML = list.map(c => `<option value="${esc(c.id)}">${esc(c.title)}</option>`).join('') || '<option value="">No cards match</option>';
  };
  const drawTeach = () => {
    $('#cdTeachList').innerHTML = teach.map((c, i) => `<div class="row" style="justify-content:space-between;gap:8px;margin:4px 0;flex-wrap:nowrap">
      <span>🗂️ ${esc(c.title)}</span><button class="btn small" data-cdrmt="${i}" aria-label="Remove">✕</button></div>`).join('');
    $('#cdTeachList').querySelectorAll('[data-cdrmt]').forEach(b => b.addEventListener('click', () => { teach.splice(Number(b.dataset.cdrmt), 1); drawTeach(); }));
    saveDraft();
  };
  fillTeach(); drawTeach();
  $('#cdTeachFind').addEventListener('input', fillTeach);
  $('#cdAddTeach').addEventListener('click', () => {
    const c = cards.find(x => x.id === $('#cdTeach').value);
    if (c && !teach.some(x => x.id === c.id)) { teach.push({ type: 'card', id: c.id, title: c.title, sub: 'Study card · slides on the projector' }); drawTeach(); }
  });
  fillCards(); drawQ();
  $('#cdCardFind').addEventListener('input', fillCards);
  $('#cdAddQ').addEventListener('click', async () => {
    const id = $('#cdCard').value;
    if (!id) return;
    const d = await api('/api/instructor/quiz?card=' + encodeURIComponent(id));
    const n = Number($('#cdCount').value);
    const fresh = (d.questions || []).filter(q => !(q.edit || {}).hidden && !questions.some(x => x.id === q.id)).slice(0, n);
    questions = questions.concat(fresh.map(q => ({ type: 'question', id: q.id, title: (q.edit || {}).q || q.q, sub: d.card.title })));
    drawQ();
  });
  $('#cdNewLesson').addEventListener('click', () => { openView('instructor'); loaders.instructor('lessons'); });
  if ($('#cdStarters')) $('#cdStarters').addEventListener('click', async () => {
    $('#cdStarters').disabled = true;
    $('#cdStarters').textContent = 'Adding…';
    const r = await api('/api/instructor/lessons/starter', {});
    if (r.error) { $('#cdMsg').textContent = r.error; $('#cdStarters').disabled = false; return; }
    planner(main, ov, collect());                   // what's ticked so far, now with lessons to pick from
  });
  function collect() {
    const items = [];
    const prompt = id => {
      const on = $(`#cdP-${id}`).checked, text = $(`#cdT-${id}`).value.trim();
      if (on && text) items.push({ type: 'prompt', id, title: text, sub: id === 'open' ? 'Opening question — on the projector' : 'Exit question — on the projector' });
    };
    prompt('open');
    items.push(...teach);
    main.querySelectorAll('[data-cd="video"]:checked').forEach(x => {
      const v = videos.find(y => y.id === x.value); items.push({ type: 'video', id: v.id, title: v.title, sub: v.kind === 'youtube' ? 'YouTube (internet)' : v.length });
    });
    main.querySelectorAll('[data-cd="scenario"]:checked').forEach(x => {
      const s = scenarios.find(y => y.id === x.value);
      items.push({ type: 'scenario', id: s.id, title: s.title, sub: s.competency, debrief: s.debrief });
    });
    items.push(...questions);
    const lid = (main.querySelector('[data-cd="lesson"]:checked') || {}).value;
    const lesson = lid && lessons.find(l => l.id === lid);
    if (lesson) items.push({ type: 'lesson', id: lid, title: lesson.title, sub: 'Assign it; Cadets find it on their Home screen' });
    prompt('close');
    return { date: cdToday(), unit: $('#cdUnit') ? $('#cdUnit').value : '', items };
  }
  $('#cdCancel').addEventListener('click', () => { cdDraftClear(); classDayHome(); });
  // one handler each (assigned, not added): an earlier planner on this page must never save its old lists
  main.onchange = saveDraft;                          // ticks, the class, the prompts' boxes
  main.oninput = e => { if (/^cdT-/.test(e.target.id)) saveDraft(); };   // the prompts' text
  ready = true;
  saveDraft();
  $('#cdBuild').addEventListener('click', () => {
    const { items } = collect();
    if (!items.length) { $('#cdMsg').textContent = 'Tick at least one thing for today — a question, a study card, a video, a scenario, a live question or a lesson.'; return; }
    const keep = Object.fromEntries((was.items || []).filter(i => i.done).map(i => [i.type + ':' + i.id, true]));
    items.forEach(i => { if (keep[i.type + ':' + i.id]) i.done = true; });
    const plan = { date: cdToday(), unit: $('#cdUnit') ? $('#cdUnit').value : '', items };
    cdSave(plan);
    cdDraftClear();
    classDayActive = true;
    runSheet(main, plan, ov);
    window.scrollTo(0, 0);
  });
}

// The Opening and Close cards: a question for the projector, prefilled with today's suggestion.
function cdPromptCard(id, heading, help, was, list) {
  const prev = (was.items || []).find(i => i.type === 'prompt' && i.id === id);
  const on = prev ? true : !was.items;              // on by default for a new plan
  return `<div class="card"><h3>${heading}</h3><p class="faint">${help}</p>
    <label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" id="cdP-${id}" ${on ? 'checked' : ''} style="width:22px;height:22px">
      ${id === 'open' ? 'Open with a question' : 'Close with a question'}</label>
    <textarea id="cdT-${id}" rows="2" maxlength="300" aria-label="${id === 'open' ? 'Opening' : 'Exit'} question" style="width:100%">${esc(prev ? prev.title : cdDaily(list))}</textarea></div>`;
}

// Step 3: the run sheet -- today's plan in order (Opening, Learn, Discuss, Engage, Assign, Close), one button each.
function runSheet(main, plan, ov) {
  const unit = ov.units.find(u => u.id === plan.unit);
  const done = plan.items.filter(i => i.done).length;
  const label = { lesson: 'Assign', scenario: '▶ Present', question: '▶ Ask live', video: '▶ Play', prompt: '▶ Show', card: '▶ Show' };
  const order = CD_PHASES.map(p => p[0]);
  const items = plan.items.map((it, i) => ({ it, i })).sort((a, b) => order.indexOf(cdPhase(a.it)) - order.indexOf(cdPhase(b.it)) || a.i - b.i);
  const row = ({ it, i }) => `<div style="margin:10px 0;${it.done ? 'opacity:.6' : ''}"><div class="row" style="gap:10px;flex-wrap:nowrap">
        <span style="font-size:22px">${it.done ? '✅' : CD_ICON[it.type]}</span>
        <div style="flex:1;min-width:0"><b>${esc(it.title)}</b><div class="faint">${esc(it.sub || '')}${it.note ? ' · ' + esc(it.note) : ''}</div></div>
        <button class="btn ${it.done ? '' : 'primary'}" data-cdrun="${i}" style="white-space:nowrap">${it.done && it.type === 'lesson' ? 'Assigned' : label[it.type]}</button></div>
        ${it.type === 'scenario' && typeof debriefHtml === 'function' ? `<div style="margin-left:34px">${debriefHtml(it.debrief)}</div>` : ''}</div>`;
  const phases = CD_PHASES.map(([key, name, what]) => {
    const mine = items.filter(x => cdPhase(x.it) === key);
    return mine.length ? `<div style="margin-top:14px;border-top:1px solid var(--line);padding-top:8px"><div class="faint" style="letter-spacing:.12em;font-size:13px">${name.toUpperCase()} · ${esc(what)}</div>${mine.map(row).join('')}</div>` : '';
  }).join('');
  main.innerHTML = `<div class="card" style="border-color:var(--tan)">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px"><h3 style="margin:0">Today's class${unit ? ' — ' + esc(unit.name) : ''}</h3>
        <span class="faint">${done} of ${plan.items.length} done</span></div>
      <button class="btn primary" id="cdPresent" style="width:100%;min-height:64px;font-size:22px;margin:12px 0 4px">🖥️ ${plan.slide ? 'Resume' : 'Present'} today's class</button>
      <p class="faint" style="margin:0 0 8px">One slideshow for the projector. Next: the → key, Page Down or a presentation clicker · Back: ← · F: full screen · B: blank screen.</p>
      ${STATUS.sample ? '' : `<div class="row" style="gap:10px;margin:12px 0;flex-wrap:wrap"><span style="font-size:22px">📱</span>
        <div style="flex:1;min-width:200px"><b>Cadet phones: ${STATUS.lan ? 'On' : 'Off'}</b><div class="faint">${STATUS.lan
          ? 'Cadets can join from their phones and vote. Put the QR code on the projector so they can join.'
          : "You don't need phones: questions and scenarios run as a show of hands. Turn phones on if you want Cadets to vote and answer on them."}</div>
          <p class="faint" id="cdJoinMsg" role="status" style="margin:4px 0 0"></p></div>
        ${STATUS.lan ? '<button class="btn" id="cdJoin" style="white-space:nowrap">📱 Show the QR code</button>' : ''}
        <button class="btn ${STATUS.lan ? '' : 'primary'}" id="cdPhones" style="white-space:nowrap">${STATUS.lan ? 'Turn phones off' : 'Turn phones on'}</button></div>`}
      ${phases}
      <div style="margin-top:14px;border-top:1px solid var(--line);padding-top:8px"><div class="faint" style="letter-spacing:.12em;font-size:13px">PROGRESS · Who's done</div>
        <div class="row" style="gap:10px;margin:10px 0;flex-wrap:nowrap"><span style="font-size:22px">📈</span>
          <div style="flex:1;min-width:0"><b>See who finished today's work</b><div class="faint">Lesson scores and reflections, and the class report.</div></div>
          <button class="btn" id="cdProgress" style="white-space:nowrap">Open</button></div></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:14px"><button class="btn" id="cdEdit">✎ Change the plan</button>
        <button class="btn" id="cdEnd">Finish class</button></div><p class="faint" id="cdRunMsg" role="alert"></p></div>`;
  if ($('#cdJoin')) $('#cdJoin').addEventListener('click', () => window.open('/join', '_blank', 'noopener'));
  // Phones are the instructor's choice (owner, 2026-10-12): off by default; the page comes back on this same step.
  if ($('#cdPhones')) $('#cdPhones').addEventListener('click', () => switchClassroom(!STATUS.lan, $('#cdPhones'), $('#cdJoinMsg')));
  $('#cdPresent').addEventListener('click', () => presentDeck(plan, plan.slide || 0));
  $('#cdEdit').addEventListener('click', () => planner(main, ov, plan));
  $('#cdProgress').addEventListener('click', () => {
    openView('instructor');
    loaders.instructor(plan.items.some(i => i.type === 'lesson' && i.done) ? 'lessons' : 'reports');
  });
  $('#cdEnd').addEventListener('click', () => {
    const finish = () => { cdClear(); classDayActive = false; classDayHome(); };
    if (typeof classFeedbackForm !== 'function') {
      if (confirm('Finish today\'s class? The plan is cleared; everything Cadets did is already saved.')) finish();
      return;
    }
    // Finishing clears today's plan (everything Cadets did is already saved) -- after one quick, optional question.
    main.innerHTML = '<div id="cdFeedback"></div><p class="faint">Everything Cadets did today is already saved. Finishing clears today\'s plan.</p>';
    classFeedbackForm($('#cdFeedback'), finish, { skipLabel: 'Skip and finish' });
    $('#cdFeedback').querySelector('#cfSave').textContent = 'Save and finish';
    window.scrollTo(0, 0);
  });
  main.querySelectorAll('[data-cdrun]').forEach(b => b.addEventListener('click', () => runItem(plan, Number(b.dataset.cdrun), main, ov)));
}

async function runItem(plan, i, main, ov) {
  const it = plan.items[i], msg = t => { if ($('#cdRunMsg')) $('#cdRunMsg').textContent = t; };
  const mark = (note) => { it.done = true; if (note) it.note = note; cdSave(plan); };
  classDayActive = true;
  if (it.type === 'lesson') {
    if (it.done) return;
    const r = await api('/api/instructor/assign-lesson', { lesson: it.id, everyone: !plan.unit, units: plan.unit ? [plan.unit] : [], cadets: [], due: cdToday() });
    if (r.error) return msg(r.error);
    mark('assigned, due today');
    return runSheet(main, plan, ov);
  }
  if (it.type === 'card') {                       // jump into the slideshow at this card
    const slides = await buildDeck(plan);
    return presentDeck(plan, Math.max(0, slides.findIndex(s => s.item.type === 'card' && s.item.id === it.id)));
  }
  if (it.type === 'scenario') { mark(); return presentScenarios([it.id]); }
  if (it.type === 'prompt') { mark(); return projectorPrompt(it); }
  if (it.type === 'question') {
    const r = await api('/api/instructor/live-quiz', { action: 'start', id: it.id, mode: 'mc' });
    if (r.error) return msg(r.error);
    mark();
    return liveQuizMode();
  }
  if (it.type === 'video') {
    const d = await api('/api/videos');
    const v = (d.videos || []).find(x => x.id === it.id);
    if (!v) return msg('That video is no longer in the list.');
    mark();
    return projectorVideo(v);
  }
}

// The opening or exit question on the projector: big type, nothing else, and a way back to the run sheet.
function projectorPrompt(it) {
  openView('classroom');
  const box = $('#classroomBody');
  box.innerHTML = `<div class="row" style="justify-content:space-between;gap:8px;flex-wrap:wrap">
      <span class="faint">CLASSROOM · ${it.id === 'close' ? 'EXIT QUESTION' : 'OPENING QUESTION'}</span><button class="btn small" id="ppBack">← Back to today's class</button></div>
    <h1 style="font-size:clamp(30px,5vw,60px);line-height:1.2;margin:8vh 0 4vh">${esc(it.title)}</h1>
    <p class="faint" style="font-size:20px">${it.id === 'close' ? 'Think about it, then share one answer before you go.' : 'Take a minute to think. Then we\'ll hear a few answers.'}</p>`;
  $('#ppBack').addEventListener('click', backFromClassroom);
}

// A video on the projector: big, with the official credit, and a way back to the run sheet.
function projectorVideo(v) {
  openView('classroom');
  const box = $('#classroomBody');
  const credit = v.kind === 'youtube' ? `${esc(v.channel)} — the service's official YouTube channel`
    : `Official video${v.credit ? ` by ${esc(v.credit)}` : ''}, ${esc(v.date || '')} · public domain · via DVIDS (dvidshub.net)`;
  box.innerHTML = `<div class="row" style="justify-content:space-between;gap:8px;flex-wrap:wrap">
      <span class="faint">CLASSROOM · VIDEO</span><button class="btn small" id="pvBack">← Back to today's class</button></div>
    <h1 style="font-size:clamp(24px,3.4vw,40px);margin:12px 0">${esc(v.title)}</h1>
    ${v.local ? `<video controls autoplay playsinline src="${esc(v.src)}" style="width:100%;max-height:72vh;background:#000;border-radius:10px"></video>`
      : `<div class="card"><p style="font-size:20px">${v.kind === 'youtube' ? 'This video is on YouTube. It opens in a new tab and needs internet.' : 'This video isn\'t saved on this computer yet, so it needs internet. Save the official videos once from Me → Add-ons.'}</p>
         <a class="btn primary" href="${esc(v.url)}" target="_blank" rel="noopener noreferrer">▶ Open the video</a></div>`}
    <p class="faint" style="margin-top:10px">${credit}</p>`;
  $('#pvBack').addEventListener('click', () => {
    const vid = box.querySelector('video'); if (vid) vid.pause();
    backFromClassroom();
  });
}

// One home for the class (usb_home.py, owner 2026-10-12): the computer or a USB drive, never both -- they don't sync.
function usbHomeCards(box, lock) {
  if (!box) return;
  const home = lock.home || {}, drives = lock.class_drives || [];
  let seen = false;
  try { seen = sessionStorage.getItem('cadetfoundry-usb-seen') === drives.join(','); } catch (e) { }
  if (drives.length && !seen) {                    // an installed copy, and the instructor's class drive is plugged in
    box.innerHTML = `<div class="card" style="border-color:var(--tan)"><h3>💾 Is your class on your USB drive?</h3>
      <p>A Cadet Foundry USB drive with a class on it is plugged in (${drives.map(esc).join(', ')}). <b>If you teach from that
        drive, open Cadet Foundry from there</b> — double-click <b>Start Cadet Foundry.bat</b> on the drive. Work you do here
        stays on this computer and won't be on the drive.</p>
      <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn primary" id="usbOpen">Open the drive</button>
        <button class="btn" id="usbHere">My class lives on this computer</button></div>
      <p class="faint" id="usbMsg" role="status"></p></div>`;
    $('#usbOpen').addEventListener('click', async () => {
      const r = await api('/api/instructor/open-folder', { path: drives[0] });
      $('#usbMsg').textContent = r.error || 'Opened. Close this window, then start Cadet Foundry from the drive.';
    });
    $('#usbHere').addEventListener('click', () => {
      try { sessionStorage.setItem('cadetfoundry-usb-seen', drives.join(',')); } catch (e) { }
      box.innerHTML = '';
    });
    return;
  }
  if (home.where === 'usb' && home.trusted == null) {   // running from the drive: back it up here? asked once per computer
    box.innerHTML = `<div class="card" style="border-color:var(--tan)"><h3>💾 Is this your own computer?</h3>
      <p>Your class lives on this USB drive (${esc(home.drive)}). If this is <b>your own</b> computer, Cadet Foundry keeps a
        backup copy of the class on it — so losing the drive doesn't mean losing your class. Not on a school or shared
        computer.</p>
      <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn primary" id="usbTrust">Yes — keep a backup here</button>
        <button class="btn" id="usbNo">No — school or shared computer</button></div><p class="faint" id="usbMsg" role="status"></p></div>`;
    const answer = async yes => {
      const r = await api('/api/instructor/usb/trust', { yes });
      box.innerHTML = r.error ? `<p class="faint">${esc(r.error)}</p>` : yes
        ? '<div class="card"><p>✅ Backups on. The newest five are kept on this computer — see 👤 Me.</p></div>' : '';
    };
    $('#usbTrust').addEventListener('click', () => answer(true));
    $('#usbNo').addEventListener('click', () => answer(false));
  }
}
