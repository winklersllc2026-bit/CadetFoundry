// Leadership scenarios (Phase 5). Cadets: the Lead tab -- live classroom vote, scenarios, leadership log.
// Instructors: scenarios, each Cadet's log, and classroom mode for the projector. Phone-first; listeners in JS
// (the page's security policy blocks inline handlers).
'use strict';

const ORIGIN = { practice: 'Practice scenario — not official curriculum', instructor: 'From your instructor' };
const LETTERS = 'ABCD';
let livePoll = null;

const block = (title, text) => text ? `<div style="margin-top:10px"><b>${title}</b><div style="white-space:pre-wrap">${esc(text)}</div></div>` : '';

// ── Cadet: Lead tab ──
loaders.lead = async () => {
  const body = $('#leadBody');
  const cadet = STATUS.kind === 'cadet';
  const [list, liveNow, quizNow] = await Promise.all([api('/api/scenarios'), cadet ? api('/api/live') : {}, cadet ? api('/api/live/quiz') : {}]);
  body.innerHTML = `<h2>Lead</h2><div id="liveQuizBox"></div><div id="liveBox"></div>
    <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
      <p class="faint" style="margin:0">Real situations a Cadet leader meets. Choose, see what happens, and reflect.</p>
      ${STATUS.kind === 'cadet' ? '<button class="btn small" id="myLog">📓 My leadership log</button>' : ''}</div>
    ${list.scenarios.map(s => `<button class="btn" data-sc="${esc(s.id)}" style="display:block;width:100%;text-align:left;margin:8px 0">
      <b>${esc(s.title)}</b><br><span class="faint">${esc(s.competency)} · ${esc(ORIGIN[s.origin] || '')}${s.done ? ` · done ${s.done}×` : ''}</span></button>`).join('')}`;
  body.querySelectorAll('[data-sc]').forEach(b => b.addEventListener('click', () => openScenario(b.dataset.sc)));
  if ($('#myLog')) $('#myLog').addEventListener('click', showMyLog);
  showLive(liveNow);
  showLiveQuiz(quizNow);
  clearInterval(livePoll);
  if (cadet) livePoll = setInterval(async () => {
    if (!$('#lead').classList.contains('on')) { clearInterval(livePoll); return; }
    try {
      if ($('#liveBox')) showLive(await api('/api/live'));
      if ($('#liveQuizBox')) showLiveQuiz(await api('/api/live/quiz'));
    } catch (e) { clearInterval(livePoll); }
  }, 5000);
};

function showLive(lv) {
  const box = $('#liveBox');
  if (!box) return;
  if (!lv || !lv.scenario) { box.innerHTML = ''; return; }
  const sc = lv.scenario, key = sc.id + ':' + lv.my_vote + ':' + lv.revealed;
  if (box.dataset.key === key) return;                       // don't redraw (and lose focus) every 5 seconds
  box.dataset.key = key;
  box.innerHTML = `<div class="card" style="border-color:var(--tan)"><h3>🗳️ Classroom vote</h3>
    <b>${esc(sc.title)}</b><p style="white-space:pre-wrap">${esc(sc.situation)}</p>
    ${sc.choices.map((c, i) => `<button class="btn ${lv.my_vote === i ? 'primary' : ''}" data-vote="${i}" style="display:block;width:100%;text-align:left;margin:6px 0">
      <b>${LETTERS[i]}.</b> ${esc(c)}</button>`).join('')}
    <p class="faint">Your vote is anonymous — your instructor sees only the totals.${lv.my_vote != null ? ' You can change it until the discussion.' : ''}</p></div>`;
  box.querySelectorAll('[data-vote]').forEach(b => b.addEventListener('click', async () => {
    const r = await api('/api/live/vote', { choice: Number(b.dataset.vote) });
    if (!r.error) showLive(await api('/api/live'));
  }));
}

// The live pop quiz: one answer each, graded by Cadet Foundry; the answer shows only after the instructor reveals it.
const LQ_RESULT = { right: '✅ Right!', close: '🟡 Close — check the wording below.', wrong: '❌ Not this time.' };
function showLiveQuiz(lq) {
  const box = $('#liveQuizBox');
  if (!box) return;
  if (!lq || !lq.id) { box.innerHTML = ''; box.dataset.key = ''; return; }
  const key = lq.id + ':' + lq.answered + ':' + lq.revealed;
  if (box.dataset.key === key) return;                       // don't redraw (and lose typing) every 5 seconds
  box.dataset.key = key;
  let inner;
  if (lq.revealed) {
    inner = `${lq.answered ? `<p style="font-size:18px"><b>${LQ_RESULT[lq.verdict] || ''}</b></p>` : '<p class="faint">You didn’t answer this one.</p>'}
      <div class="card"><b>Answer:</b> ${esc(lq.answer)}</div>`;
  } else if (lq.answered) {
    inner = '<p>✅ Answer received. Your result shows when your instructor reveals the answer.</p>';
  } else if (lq.mode === 'mc') {
    inner = lq.choices.map((c, i) => `<button class="btn" data-lqc="${i}" style="display:block;width:100%;text-align:left;margin:6px 0"><b>${LETTERS[i]}.</b> ${esc(c)}</button>`).join('');
  } else {
    inner = `<label for="lqText" class="faint">Type your answer</label><input id="lqText" maxlength="500" autocomplete="off">
      <button class="btn primary" id="lqSend" style="margin-top:8px">Send</button>`;
  }
  box.innerHTML = `<div class="card" style="border-color:var(--tan)"><h3>🎯 Live question</h3>
    <p style="font-size:18px">${esc(lq.q)}</p>${inner}<p class="faint" id="lqMsg" role="alert"></p>
    <p class="faint">One answer each. Your instructor sees only how many got it right — never who. A miss here is just something to learn.</p></div>`;
  const send = async body => {
    const r = await api('/api/live/quiz/answer', body);
    if (r.error) { $('#lqMsg').textContent = r.error; return; }
    showLiveQuiz(r);
  };
  box.querySelectorAll('[data-lqc]').forEach(b => b.addEventListener('click', () => send({ choice: lq.choices[Number(b.dataset.lqc)] })));
  if ($('#lqSend')) {
    $('#lqSend').addEventListener('click', () => send({ answer: $('#lqText').value }));
    $('#lqText').addEventListener('keydown', e => { if (e.key === 'Enter') send({ answer: $('#lqText').value }); });
  }
}

async function openScenario(id) {
  const body = $('#leadBody');
  const sc = await api('/api/scenario?id=' + encodeURIComponent(id));
  if (sc.error) return;
  body.innerHTML = `<button class="btn small" id="scBack">← Lead</button>
    <h2 style="margin-top:12px">${esc(sc.title)}</h2><p class="faint">${esc(sc.competency)} · ${esc(ORIGIN[sc.origin] || '')}</p>
    <div class="card"><div style="white-space:pre-wrap">${esc(sc.situation)}</div></div>
    <h3>What do you do?</h3>
    ${sc.choices.map((c, i) => `<button class="btn" data-ch="${i}" style="display:block;width:100%;text-align:left;margin:8px 0"><b>${LETTERS[i]}.</b> ${esc(c)}</button>`).join('')}
    <div id="scOut"></div>`;
  $('#scBack').addEventListener('click', () => loaders.lead());
  body.querySelectorAll('[data-ch]').forEach(b => b.addEventListener('click', async () => {
    body.querySelectorAll('[data-ch]').forEach(x => { x.classList.toggle('primary', x === b); x.disabled = true; });
    const ex = await api('/api/scenario/choose', { id, choice: Number(b.dataset.ch) });
    if (ex.error) return;
    const cadet = STATUS.kind === 'cadet';
    $('#scOut').innerHTML = `<div class="card" style="border-color:var(--tan)"><h3>What happened</h3>
        <div style="white-space:pre-wrap">${esc(ex.outcome)}</div>
        ${block('What worked', ex.strengths)}${block('What to watch for', ex.weaknesses)}
        ${ex.principles.length ? `<div style="margin-top:10px"><b>Leadership principles</b><ul style="margin:4px 0;padding-left:20px">${ex.principles.map(p => `<li>${esc(p)}</li>`).join('')}</ul></div>` : ''}
        ${block('Other ways to approach it', ex.alternatives)}</div>
      ${cadet ? `<div class="card"><h3>Your leadership log</h3>
        <label for="scWhy">Why did you choose this?</label><textarea id="scWhy" rows="2" style="width:100%"></textarea>
        <label for="scRefl">${esc(sc.reflection)}</label><textarea id="scRefl" rows="3" style="width:100%"></textarea>
        <label for="scLearn">What I learned</label><textarea id="scLearn" rows="2" style="width:100%"></textarea>
        <button class="btn primary" id="scSave" style="width:100%;margin-top:10px">Save to my leadership log</button>
        <p class="faint" id="scMsg" role="alert"></p></div>` : ''}`;
    if (!cadet) return;
    $('#scSave').addEventListener('click', async () => {
      const r = await api('/api/scenario/log', { id, choice: Number(b.dataset.ch), reasoning: $('#scWhy').value,
        reflection: $('#scRefl').value, learned: $('#scLearn').value });
      if (r.error) { $('#scMsg').textContent = r.error; return; }
      $('#scOut').insertAdjacentHTML('beforeend', `<div class="card"><b>Saved to your leadership log.</b> Here's how each choice plays out:
        ${r.all_outcomes.map((o, i) => `<div style="border-top:1px solid var(--line);margin-top:10px;padding-top:8px"><b>${LETTERS[i]}. ${esc(o.decision)}</b>
          <div style="white-space:pre-wrap">${esc(o.outcome)}</div></div>`).join('')}</div>`);
      $('#scSave').remove();
    });
  }));
}

async function showMyLog() {
  const body = $('#leadBody');
  const r = await api('/api/leadership-log');
  body.innerHTML = `<button class="btn small" id="logBack">← Lead</button><h2 style="margin-top:12px">📓 My leadership log</h2>
    <p class="faint">Your instructor can read this log. It's part of your class records.</p>
    ${r.entries.length ? r.entries.map(logEntryHtml).join('') : '<p class="faint">Nothing yet. Work through a scenario and save your reflection.</p>'}`;
  $('#logBack').addEventListener('click', () => loaders.lead());
}

function logEntryHtml(e) {
  return `<div class="card"><b>${esc(e.title)}</b> <span class="faint">${esc(e.date)} · ${esc(e.competency)}</span>
    ${block('Decision', e.decision)}${block('Reasoning', e.reasoning)}${block('What happened', e.outcome)}
    ${block('Reflection', e.reflection)}${block('What I learned', e.learned)}</div>`;
}

// ── Instructor: leadership section on the Instructor screen ──
async function instructorLeadership(body) {
  const d = await api('/api/instructor/scenarios');
  if (d.error) return;
  const sec = document.createElement('div');
  body.appendChild(sec);
  sec.innerHTML = `<div class="card"><h3>🧭 Leadership</h3>
      ${d.cadets.map(c => `<div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:6px;margin:6px 0">
        <span>${esc(c.name)} <span class="faint">${c.shared ? `${c.count} scenario${c.count === 1 ? '' : 's'}` : 'waiting to share'}</span></span>
        ${c.count ? `<button class="btn small" data-ilog="${esc(c.id)}">View log</button>` : ''}</div><div data-ilogout="${esc(c.id)}"></div>`).join('') || '<p class="faint">No Cadets yet.</p>'}</div>
    <div class="card"><h3>Scenarios</h3>
      <p class="faint">Tick the ones for today's class and present them in order — Next and Previous on the projector.</p>
      <div class="sc-bar"><button class="btn primary" id="presentSel" disabled>🖥️ Present selected (0)</button>
        <button class="btn small" id="pickAll">Select all</button><button class="btn small" id="pickNone">Clear</button></div>
      <div class="sc-list">${d.scenarios.map(s => `<div class="sc-row">
        <label class="sc-pick"><input type="checkbox" data-pick="${esc(s.id)}" aria-label="Include ${esc(s.title)}">
          <span><span class="sc-title">${esc(s.title)}</span>
          <span class="sc-meta">${esc(s.competency)} · ${s.origin === 'practice' ? 'practice' : 'yours'}${s.done ? ` · used ${s.done}×` : ''}</span></span></label>
        <span class="sc-act"><button class="btn small" data-present="${esc(s.id)}" title="Present just this one">▶ Present</button>
          <button class="btn small" data-sedit="${esc(s.id)}" title="${s.origin === 'practice' ? 'Make your own copy to edit' : 'Edit'}">${s.origin === 'practice' ? 'Copy' : 'Edit'}</button></span></div>${debriefHtml(s.debrief)}`).join('')}</div>
      <button class="btn primary" id="sNew" style="margin-top:12px">＋ New scenario</button><div id="sForm"></div></div>`;
  const byId = id => d.scenarios.find(s => s.id === id);
  const TEMPLATE = 'Title: \nCompetency: \nSituation:\n\nChoice: \nOutcome: \nStrengths: \nWeaknesses: \nChoice: \nOutcome: \nStrengths: \nWeaknesses: \nPrinciples:\n- \nOther approaches:\n\nReflection: What would you do differently next time?\nNotice: \nDiscussion:\n- \nFollow-up: ';
  const form = s => {
    $('#sForm').innerHTML = `<div class="card" style="margin-top:12px"><h3>${s && s.origin === 'instructor' ? 'Edit scenario' : 'New scenario'}</h3>
      ${s && s.origin === 'practice' ? '<p class="faint">This saves your own copy; the practice scenario stays as it is.</p>' : ''}
      <textarea id="sText" rows="18" style="width:100%;font-family:inherit">${esc(s ? s.text : TEMPLATE)}</textarea>
      <p class="faint">2 to 4 choices. Each choice needs an Outcome; Strengths and Weaknesses are optional. Keep it everyday leadership — not combat.
        Notice, Discussion and Follow-up are your debrief: they show only on your screens, never to Cadets or on the projector.</p>
      <div class="row" style="flex-wrap:wrap;gap:8px"><button class="btn primary" id="sSave">Save</button>
        ${s && s.origin === 'instructor' ? '<button class="btn small" id="sDel">Delete</button>' : ''}<button class="btn small" id="sCancel">Cancel</button></div>
      <p class="faint" id="sMsg" role="alert"></p></div>`;
    $('#sCancel').addEventListener('click', () => { $('#sForm').innerHTML = ''; });
    $('#sSave').addEventListener('click', async () => {
      const r = await api('/api/instructor/scenario', { id: s ? s.id : '', text: $('#sText').value });
      if (r.error) $('#sMsg').textContent = r.error; else loaders.instructor();
    });
    if ($('#sDel')) $('#sDel').addEventListener('click', async () => {
      if (!confirm('Delete this scenario? Cadets keep their log entries.')) return;
      await api('/api/instructor/scenario', { action: 'delete', id: s.id }); loaders.instructor();
    });
  };
  $('#sNew').addEventListener('click', () => form(null));
  sec.querySelectorAll('[data-sedit]').forEach(b => b.addEventListener('click', () => form(byId(b.dataset.sedit))));
  sec.querySelectorAll('[data-present]').forEach(b => b.addEventListener('click', () => presentScenarios([b.dataset.present])));
  const picked = () => [...sec.querySelectorAll('[data-pick]:checked')].map(x => x.dataset.pick);
  const count = () => {
    const n = picked().length;
    $('#presentSel').disabled = !n;
    $('#presentSel').textContent = n ? `🖥️ Present selected (${n})` : '🖥️ Present selected';
    sec.querySelectorAll('.sc-row').forEach(r => r.classList.toggle('on', r.querySelector('[data-pick]').checked));
  };
  const pickAll = on => { sec.querySelectorAll('[data-pick]').forEach(x => { x.checked = on; }); count(); };
  sec.querySelectorAll('[data-pick]').forEach(cb => cb.addEventListener('change', count));
  $('#pickAll').addEventListener('click', () => pickAll(true));
  $('#pickNone').addEventListener('click', () => pickAll(false));
  count();
  $('#presentSel').addEventListener('click', () => presentScenarios(picked()));
  sec.querySelectorAll('[data-ilog]').forEach(b => b.addEventListener('click', async () => {
    const out = sec.querySelector(`[data-ilogout="${b.dataset.ilog}"]`);
    if (out.innerHTML) { out.innerHTML = ''; return; }
    const r = await api('/api/instructor/leadership-log?id=' + encodeURIComponent(b.dataset.ilog));
    out.innerHTML = (r.entries || []).map(logEntryHtml).join('');
  }));
}

// A run of scenarios for one class: the projector steps through them; each one starts a fresh vote.
let presentQueue = [], presentAt = 0;
async function presentScenarios(ids, at = 0) {
  if (!ids.length) return;
  presentQueue = ids; presentAt = Math.max(0, Math.min(at, ids.length - 1));
  await api('/api/instructor/live', { action: 'start', scenario: presentQueue[presentAt] });
  classroomMode();
}

// ── Classroom mode: big type for the projector, live anonymous vote counts ──
async function classroomMode() {
  openView('classroom');
  const box = $('#classroomBody');
  const draw = async () => {
    const lv = await api('/api/instructor/live');
    if (!lv.scenario) { clearInterval(livePoll); backFromClassroom(); return; }
    const sc = lv.scenario, max = Math.max(1, ...lv.counts);
    box.innerHTML = `<div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <span class="faint">CLASSROOM MODE · ${lv.votes} vote${lv.votes === 1 ? '' : 's'} · Cadets vote in 🧭 Lead</span>
        <span class="row" style="gap:8px">${presentQueue.length > 1 ? `<button class="btn small" id="cmPrev" ${presentAt === 0 ? 'disabled' : ''}>◀ Previous</button>
          <span class="faint">${presentAt + 1} of ${presentQueue.length}</span>
          <button class="btn small primary" id="cmNext" ${presentAt >= presentQueue.length - 1 ? 'disabled' : ''}>Next ▶</button>` : ''}<button class="btn small" id="cmReveal">${lv.revealed ? 'Hide guidance' : 'Reveal discussion guidance'}</button>
        <button class="btn small" id="cmStop">End</button></span></div>
      <h1 style="font-size:clamp(26px,4vw,44px);margin:14px 0 6px">${esc(sc.title)}</h1>
      <p style="font-size:clamp(18px,2.4vw,28px);white-space:pre-wrap;line-height:1.4">${esc(sc.situation)}</p>
      ${sc.choices.map((c, i) => `<div style="margin:14px 0;font-size:clamp(17px,2.2vw,26px)">
        <b>${LETTERS[i]}.</b> ${esc(c)}
        <div style="display:flex;align-items:center;gap:10px;margin-top:6px"><div style="height:14px;border-radius:7px;background:var(--tan);width:${Math.round(lv.counts[i] / max * 70)}%;min-width:4px"></div>
        <span class="faint">${lv.counts[i]}</span></div>
        ${lv.revealed ? `<div class="card" style="font-size:clamp(15px,1.6vw,20px);margin-top:8px">${esc(lv.guidance.outcomes[i].outcome)}</div>` : ''}</div>`).join('')}
      ${lv.revealed ? `<div class="card" style="font-size:clamp(15px,1.6vw,20px)"><b>Leadership principles</b><ul>${lv.guidance.principles.map(p => `<li>${esc(p)}</li>`).join('')}</ul>
        ${lv.guidance.alternatives ? `<b>Other approaches</b><div style="white-space:pre-wrap">${esc(lv.guidance.alternatives)}</div>` : ''}</div>` : ''}`;
    $('#cmReveal').addEventListener('click', async () => { await api('/api/instructor/live', { action: 'reveal', on: !lv.revealed }); draw(); });
    $('#cmStop').addEventListener('click', async () => { presentQueue = []; await api('/api/instructor/live', { action: 'stop' }); draw(); });
    if ($('#cmNext')) $('#cmNext').addEventListener('click', () => presentScenarios(presentQueue, presentAt + 1));
    if ($('#cmPrev')) $('#cmPrev').addEventListener('click', () => presentScenarios(presentQueue, presentAt - 1));
  };
  await draw();
  clearInterval(livePoll);
  // stop polling when the view closes or the session locks (an error), never keep calling a locked server
  livePoll = setInterval(() => {
    if (!$('#classroom').classList.contains('on')) { clearInterval(livePoll); return; }
    draw().catch(() => clearInterval(livePoll));
  }, 3000);
}

// The instructor's debrief for a scenario (instructor screens only -- never on the projector or a Cadet's screen).
function debriefHtml(db) {
  if (!db || !(db.notice || (db.discussion || []).length || db.follow_up || (db.principles || []).length)) return '';
  return `<details class="debrief" style="margin:0 0 8px"><summary class="faint" style="cursor:pointer;min-height:32px">📝 Instructor debrief</summary>
    <div style="font-size:15px;margin:4px 0 8px">
      ${(db.principles || []).length ? `<div><b>Leadership principles</b><ul style="margin:4px 0 6px 18px;padding:0">${db.principles.map(p => `<li>${esc(p)}</li>`).join('')}</ul></div>` : ''}
      ${db.notice ? `<div><b>What Cadets should notice</b><p style="margin:4px 0 6px">${esc(db.notice)}</p></div>` : ''}
      ${(db.discussion || []).length ? `<div><b>Discussion questions</b><ol style="margin:4px 0 6px 18px;padding:0">${db.discussion.map(q => `<li>${esc(q)}</li>`).join('')}</ol></div>` : ''}
      ${db.follow_up ? `<div><b>Follow-up activity</b> <span class="faint">(optional)</span><p style="margin:4px 0 0">${esc(db.follow_up)}</p></div>` : ''}</div></details>`;
}
