// Pilot tools (Phase 10): the instructor's pilot setup, snapshots, survey switch, their own feedback and the
// end-of-pilot report; the Cadet's anonymous survey (at the top of My Progress while it's open). Listeners in JS.
'use strict';

const plPct = v => v == null ? '—' : `${v}%`;
const plSigned = v => v == null ? '—' : `${v > 0 ? '+' : ''}${v}`;

async function instructorPilot(body) {
  const d = await api('/api/instructor/pilot');
  if (d.error) return;
  const c = d.config || {}, fb = d.feedback, now = d.now, base = d.baseline, ch = d.change;
  const metrics = c.metrics || Object.keys(d.metric_names);
  const sec = document.createElement('div');
  sec.className = 'card';
  sec.id = 'pilotCard';
  sec.innerHTML = `<h3>🧪 Pilot program</h3>
    <p class="faint">Make the pilot measurable: set it up, take a starting snapshot, open the Cadet survey near the end, add your own feedback, and print the report.</p>
    ${plMetricsHtml(d.metrics, c)}
    <div class="row" style="flex-wrap:wrap;gap:8px"><button class="btn small primary" id="plOnePage">🖨️ One-page summary</button>
      <button class="btn small" id="plToday">💬 Feedback about today</button></div><div id="plTodayBox"></div>
    ${plModeHtml(d.stored)}
    <details ${c.start ? '' : 'open'}><summary><b>Pilot setup</b></summary>
      <label for="plSchool">School</label><input id="plSchool" maxlength="100" value="${esc(c.school || '')}">
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <div style="flex:1;min-width:150px"><label for="plProg">Program</label><input id="plProg" maxlength="60" value="${esc(c.program || (STATUS.programs || {})[STATUS.program] || 'JROTC')}"></div>
        <div style="flex:1;min-width:150px"><label for="plInst">Instructor</label><input id="plInst" maxlength="80" value="${esc(c.instructor || '')}"></div></div>
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <div style="flex:1;min-width:140px"><label for="plStart">Start</label><input id="plStart" type="date" value="${esc(c.start || '')}"></div>
        <div style="flex:1;min-width:140px"><label for="plEnd">End</label><input id="plEnd" type="date" value="${esc(c.end || '')}"></div>
        <div style="flex:1;min-width:100px"><label for="plN">Cadets planned</label><input id="plN" inputmode="numeric" value="${esc(c.cadets_planned || '')}"></div></div>
      <div style="margin-top:8px"><b>Measure</b></div>
      ${Object.entries(d.metric_names).map(([k, v]) => `<label style="display:flex;gap:10px;align-items:center;min-height:40px"><input type="checkbox" data-plm="${k}" ${metrics.includes(k) ? 'checked' : ''} style="width:22px;height:22px"> ${esc(v)}</label>`).join('')}
      <label for="plNotes">Notes</label><textarea id="plNotes" rows="2" style="width:100%">${esc(c.notes || '')}</textarea>
      <button class="btn primary" id="plSave" style="margin-top:8px">Save pilot setup</button><p class="faint" id="plMsg" role="alert"></p></details>
    ${c.start ? `<div style="margin-top:12px"><b>${esc(c.school || 'Pilot')}</b> · ${esc(c.program || '')} · ${esc(c.start)} to ${esc(c.end || '…')}${d.weeks != null ? ` · ${d.weeks} weeks so far` : ''}</div>
    <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
      <button class="btn small" id="plSnap">📸 Take a snapshot now</button>
      <button class="btn small ${c.survey_open ? '' : 'primary'}" id="plSurvey">${c.survey_open ? 'Close the Cadet survey' : '📝 Open the Cadet survey'}</button>
      <button class="btn small primary" id="plPrint">🖨️ Print pilot report</button></div>
    <p class="faint">Snapshots: ${d.snapshots.length}${base ? ` (first ${esc(base.date)})` : ' — take one at the start so the report can show change'}.
      Cadet survey: ${c.survey_open ? 'open — Cadets see it at the top of My Progress' : 'closed'} · ${fb.cadet_responses} response${fb.cadet_responses === 1 ? '' : 's'}.</p>
    <details><summary><b>Your feedback</b></summary>
      <div style="margin-top:8px">How satisfied are you with Cadet Foundry so far?</div>
      <div class="row" style="flex-wrap:wrap;gap:6px">${[1, 2, 3, 4, 5].map(n => `<label style="display:flex;gap:6px;align-items:center;min-height:40px"><input type="radio" name="plSat" value="${n}" style="width:22px;height:22px"> ${n}</label>`).join('')}</div>
      <label for="plMin">About how many minutes a week did it save you? (negative if it cost you time)</label><input id="plMin" inputmode="numeric">
      <div style="margin-top:8px">Would you use Cadet Foundry next semester?</div>
      <div class="row" style="gap:12px">${['yes', 'maybe', 'no'].map(v => `<label style="display:flex;gap:6px;align-items:center;min-height:40px"><input type="radio" name="plAgain" value="${v}" style="width:22px;height:22px"> ${v[0].toUpperCase() + v.slice(1)}</label>`).join('')}</div>
      <label for="plCom">Comments</label><textarea id="plCom" rows="2" style="width:100%"></textarea>
      <button class="btn primary" id="plFb" style="margin-top:8px">Save my feedback</button><p class="faint" id="plFbMsg" role="alert"></p>
      ${fb.instructor.length ? `<p class="faint">Saved ${fb.instructor.length} time${fb.instructor.length === 1 ? '' : 's'}; latest ${esc(fb.latest_instructor.date)}: satisfaction ${fb.latest_instructor.satisfaction}/5, next semester: ${esc(fb.latest_instructor.use_again)}.</p>` : ''}</details>` : ''}`;
  body.appendChild(sec);
  plModeWire(sec, d);
  $('#plOnePage').addEventListener('click', () => printPilotSummary(d));
  $('#plToday').addEventListener('click', () => classFeedbackForm($('#plTodayBox'), () => loaders.instructor(), { skipLabel: 'Cancel' }));
  $('#plSave').addEventListener('click', async () => {
    const r = await api('/api/instructor/pilot', { school: $('#plSchool').value, program: $('#plProg').value, instructor: $('#plInst').value,
      start: $('#plStart').value, end: $('#plEnd').value, cadets_planned: $('#plN').value, notes: $('#plNotes').value,
      metrics: [...sec.querySelectorAll('[data-plm]:checked')].map(x => x.dataset.plm) });
    if (r.error) $('#plMsg').textContent = r.error; else loaders.instructor();
  });
  if (!c.start) return;
  $('#plSnap').addEventListener('click', async () => { await api('/api/instructor/pilot/snapshot', {}); loaders.instructor(); });
  $('#plSurvey').addEventListener('click', async () => { await api('/api/instructor/pilot/survey', { open: !c.survey_open }); loaders.instructor(); });
  $('#plFb').addEventListener('click', async () => {
    const sat = sec.querySelector('[name=plSat]:checked'), again = sec.querySelector('[name=plAgain]:checked');
    const r = await api('/api/instructor/pilot/feedback', { satisfaction: sat ? sat.value : '', minutes_saved: $('#plMin').value,
      use_again: again ? again.value : '', comment: $('#plCom').value });
    $('#plFbMsg').textContent = r.error || 'Saved — thank you.';
  });
  $('#plPrint').addEventListener('click', () => printPilotReport(d));
}

function printPilotReport(d) {
  const c = d.config, now = d.now, base = d.baseline, ch = d.change, fb = d.feedback, on = c.metrics || [];
  const row = (label, value, note = '') => `<tr><td>${label}</td><td><b>${value}</b></td><td>${note}</td></tr>`;
  const rows = [];
  rows.push(row('Duration', d.weeks != null ? `${d.weeks} weeks` : '—', `${esc(c.start || '')} to ${esc(c.end || '')}`));
  rows.push(row('Cadets', `${now.cadets ?? '—'}`, c.cadets_planned ? `${c.cadets_planned} planned` : ''));
  if (on.includes('engagement')) rows.push(row('Active Cadets (last 14 days)', `${now.active ?? '—'}`, d.engagement.length ? `weekly: ${d.engagement.map(e => `${e.active}/${e.cadets}`).join(', ')}` : ''));
  if (on.includes('lessons')) rows.push(row('Lessons assigned', d.lessons_assigned, `completion ${plPct(now.lesson_completion_pct)}`));
  if (on.includes('academics')) rows.push(row('Average lesson score', plPct(now.avg_lesson_score_pct),
    `${ch.avg_lesson_score_pct != null ? `change ${plSigned(ch.avg_lesson_score_pct)} points` : ''}${ch.cards_mastered != null ? ` · study cards mastered ${plSigned(ch.cards_mastered)}` : ''}`));
  if (on.includes('leadership')) rows.push(row('Leadership scenarios completed', now.scenarios ?? '—', ch.scenarios != null ? `${plSigned(ch.scenarios)} during the pilot` : ''));
  if (on.includes('fitness')) rows.push(row('Average fitness improvement', now.avg_fitness_improvement_pct == null ? '—' : `${plSigned(now.avg_fitness_improvement_pct)}%`, 'each Cadet measured against their own first result'));
  if (on.includes('service')) rows.push(row('Service hours (verified)', now.service_hours ?? '—', ch.service_hours != null ? `${plSigned(ch.service_hours)} during the pilot` : ''));
  if (on.includes('workload')) rows.push(row('Instructor time saved', fb.avg_minutes_saved != null ? `${fb.avg_minutes_saved} min/week` : 'not reported', 'instructor\'s own estimate'));
  if (on.includes('feedback') && fb.latest_instructor) rows.push(row('Instructor: use next semester?', esc(fb.latest_instructor.use_again), `satisfaction ${fb.latest_instructor.satisfaction}/5`));
  const survey = on.includes('feedback') && fb.cadet_responses ? `<h2>Cadet feedback (${fb.cadet_responses} anonymous response${fb.cadet_responses === 1 ? '' : 's'}, 1–5)</h2>
    <table border="1" cellpadding="4" style="border-collapse:collapse;width:100%;font-size:12px">${Object.entries(fb.questions).map(([k, q]) => `<tr><td>${esc(q)}</td><td><b>${fb.averages[k] ?? '—'}</b></td></tr>`).join('')}</table>
    ${fb.cadet_comments.length ? `<h3>What Cadets said</h3><ul>${fb.cadet_comments.slice(0, 40).map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}` : '';
  const ins = on.includes('feedback') && fb.instructor.length ? `<h2>Instructor feedback</h2><ul>${fb.instructor.filter(r => r.comment).map(r => `<li>${esc(r.date)}: ${esc(r.comment)}</li>`).join('')}</ul>` : '';
  let area = $('#printArea');
  if (!area) { area = document.createElement('div'); area.id = 'printArea'; document.body.appendChild(area); }
  area.innerHTML = `<div style="font-family:Georgia,serif;color:#000"><div style="letter-spacing:.2em;font-weight:700">CADET FOUNDRY</div>
    <h1 style="margin:4px 0">JROTC Pilot Report</h1>
    <div>${esc(c.school || '')} · ${esc(c.program || '')}${c.instructor ? ' · Instructor: ' + esc(c.instructor) : ''} · printed ${esc(new Date().toLocaleDateString())}</div>
    <table border="1" cellpadding="5" style="border-collapse:collapse;width:100%;margin-top:12px;font-size:13px">${rows.join('')}</table>
    ${base ? `<p style="font-size:12px">Change is measured from the first snapshot (${esc(base.date)}).</p>` : `<p style="font-size:12px">${(d.cannot_measure || []).map(esc).join(' ')}</p>`}
    ${survey}${ins}
    ${c.notes ? `<h2>Notes</h2><p>${esc(c.notes)}</p>` : ''}
    <p style="font-size:11px;margin-top:20px">Every number comes from records kept on the instructor's device. Cadet Foundry is designed to support JROTC instruction; it is not an official JROTC, military or school product.</p></div>`;
  window.print();
}

// ── Cadet: the anonymous survey, at the top of My Progress while it's open ──
async function cadetSurvey(container) {
  const s = await api('/api/pilot/survey');
  if (!s.open) return;
  const box = document.createElement('div');
  box.className = 'card';
  box.style.borderColor = 'var(--tan)';
  if (s.done) {
    box.innerHTML = '<p style="margin:0">📝 Thanks for answering the Cadet Foundry survey!</p>';
  } else {
    box.innerHTML = `<h3>📝 A quick survey about Cadet Foundry</h3>
      <p class="faint">Anonymous — your name isn't saved with your answers. It takes about a minute.</p>
      ${s.questions.map(q => `<fieldset style="border:0;padding:0;margin:12px 0"><legend><b>${esc(q.q)}</b></legend>
        <div class="row" style="flex-wrap:wrap;gap:4px">${Object.entries(s.scale).map(([v, t]) => `<label style="display:flex;gap:6px;align-items:center;min-height:40px;margin-right:8px">
          <input type="radio" name="sv-${q.id}" value="${v}" style="width:22px;height:22px"> ${esc(t)}</label>`).join('')}</div></fieldset>`).join('')}
      <label for="svCom">What would make Cadet Foundry better? (optional)</label><textarea id="svCom" rows="2" style="width:100%"></textarea>
      <button class="btn primary" id="svSend" style="margin-top:8px">Send</button><p class="faint" id="svMsg" role="alert"></p>`;
  }
  container.prepend(box);
  if (s.done) return;
  box.querySelector('#svSend').addEventListener('click', async () => {
    const answers = {};
    s.questions.forEach(q => { const x = box.querySelector(`[name=sv-${q.id}]:checked`); if (x) answers[q.id] = +x.value; });
    const r = await api('/api/pilot/survey', { answers, comment: box.querySelector('#svCom').value });
    if (r.error) { box.querySelector('#svMsg').textContent = r.error; return; }
    box.innerHTML = '<p style="margin:0">📝 Thanks for answering the Cadet Foundry survey!</p>';
  });
}

// ── Pilot mode: online AI stays off, what's stored on this device, and End pilot ──
function plModeHtml(st) {
  const n = (v, one, many) => `${v} ${v === 1 ? one : many}`;
  return `<div style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:10px 0">
    <label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" id="plMode" ${st.pilot_mode ? 'checked' : ''} style="width:24px;height:24px">
      <span><b>Pilot mode</b> <span class="faint">— recommended while you run a pilot</span></span></label>
    <p class="faint" style="margin:4px 0">Every question stays on this device (online AI is off, whatever the settings say), you can see what's stored, and you can delete the pilot's data in one step when it ends.</p>
    ${st.pilot_mode ? `<div style="margin-top:8px"><b>What's stored on this device now</b>
      <ul style="margin:6px 0 6px 18px;padding:0">
        <li>${n(st.cadets, 'Cadet profile', 'Cadet profiles')}${st.guardians ? `, ${n(st.guardians, 'guardian profile', 'guardian profiles')}` : ''}, ${n(st.instructors, 'instructor profile', 'instructor profiles')}</li>
        <li>${n(st.units, 'class or squad', 'classes and squads')}, ${n(st.lessons, 'lesson', 'lessons')}, ${n(st.assignments, 'assignment', 'assignments')}</li>
        <li>Pilot: ${n(st.snapshots, 'snapshot', 'snapshots')}, ${n(st.survey_answers, 'survey answer', 'survey answers')} (no names), ${n(st.instructor_feedback, 'feedback entry', 'feedback entries')} from you</li>
        <li>Online AI: <b>${st.online_ai ? 'on' : 'off'}</b> · Folder: <code>${esc(st.folder)}</code> (${st.size_mb} MB)</li></ul>
      <p class="faint" style="margin:4px 0">Cadets' chats, notes and check-ins: only that Cadet can open them. Class records: you, with the Class PIN. Nothing is sent anywhere.</p>
      <button class="btn small danger" id="plEnd">End pilot…</button><div id="plEndBox"></div></div>` : ''}</div>`;
}

function plModeWire(sec, d) {
  $('#plMode').addEventListener('change', async ev => {
    await api('/api/instructor/pilot/mode', { on: ev.target.checked });
    loaders.instructor();
  });
  const end = $('#plEnd');
  if (!end) return;
  end.addEventListener('click', () => {
    const st = d.stored, box = $('#plEndBox');
    end.hidden = true;
    box.innerHTML = `<div class="card" style="border-color:var(--red,#c0392b);margin-top:10px">
      <h3>End the pilot?</h3>
      <p>This <b>permanently removes</b> from this device: ${st.cadets} Cadet profile${st.cadets === 1 ? '' : 's'} (their class records and private files)${st.guardians ? `, ${st.guardians} guardian profile${st.guardians === 1 ? '' : 's'}` : ''}, ${st.assignments} assignment${st.assignments === 1 ? '' : 's'}, and the pilot's setup, snapshots and survey answers. It can't be undone.</p>
      <p class="faint">Kept: instructor profiles, the Class PIN, your lessons, and your classes and squads (with new join codes).</p>
      <p><b>1. Save what the school keeps first.</b></p>
      <div class="row" style="flex-wrap:wrap;gap:8px"><a class="btn small" href="/api/instructor/report.csv" download>⬇ Class report (spreadsheet)</a>
        <button class="btn small" id="plEndPrint">🖨️ Print pilot report</button></div>
      <label style="display:flex;gap:10px;align-items:center;min-height:44px;margin-top:8px"><input type="checkbox" id="plEndSaved" style="width:22px;height:22px"> I've saved what the school keeps.</label>
      <p><b>2. Confirm.</b></p>
      <label for="plEndPin">Class PIN</label>${PIN_INPUT('plEndPin', '')}
      <label for="plEndWord">Type DELETE</label><input id="plEndWord" autocomplete="off" maxlength="10">
      <div class="row" style="gap:8px;margin-top:10px"><button class="btn danger" id="plEndGo">Delete pilot data</button><button class="btn" id="plEndNo">Cancel</button></div>
      <p class="faint" id="plEndMsg" role="alert"></p></div>`;
    $('#plEndPrint').addEventListener('click', () => printPilotReport(d));
    $('#plEndNo').addEventListener('click', () => { box.innerHTML = ''; end.hidden = false; });
    $('#plEndGo').addEventListener('click', async () => {
      if (!$('#plEndSaved').checked) { $('#plEndMsg').textContent = "Save what the school keeps first, then tick the box."; return; }
      if ($('#plEndWord').value.trim() !== 'DELETE') { $('#plEndMsg').textContent = 'Type DELETE to confirm.'; return; }
      $('#plEndGo').disabled = true;
      const r = await api('/api/instructor/pilot/end', { admin: $('#plEndPin').value, confirm: 'DELETE' });
      if (r.error) { $('#plEndMsg').textContent = r.error; $('#plEndGo').disabled = false; return; }
      box.innerHTML = `<div class="card" style="margin-top:10px"><div style="font-size:30px">✅</div><h3>Pilot data deleted</h3>
        <p>Removed from this device: ${r.cadets} Cadet profile${r.cadets === 1 ? '' : 's'}${r.guardians ? `, ${r.guardians} guardian profile${r.guardians === 1 ? '' : 's'}` : ''}, ${r.assignments} assignment${r.assignments === 1 ? '' : 's'}, and the pilot's setup, snapshots and survey answers.</p>
        <p>Still on this device: ${r.remaining_profiles.map(p => esc(p.name)).join(', ') || 'no profiles'}, your lessons, and your classes (with new join codes).</p>
        <p class="faint">Deleted files can still be recovered from a disk that isn't encrypted — keep BitLocker on.</p>
        <button class="btn primary" id="plEndDone">Done</button></div>`;
      $('#plEndDone').addEventListener('click', () => loaders.instructor());
    });
  });
}

// ── After class: how useful was Cadet Foundry today? (product feedback -- never about a Cadet) ──
const PL_DAILY_Q = { goal: 'What were you trying to accomplish today?', worked: 'What worked?',
  confusing: 'What was confusing?', change: 'What would you change?' };

function classFeedbackForm(box, onDone, { skipLabel = 'Skip' } = {}) {
  box.innerHTML = `<div class="card" style="border-color:var(--tan)"><h3>💬 How useful was Cadet Foundry today?</h3>
    <div class="row" style="gap:8px;flex-wrap:wrap" role="radiogroup" aria-label="How useful, 1 to 5">${[1, 2, 3, 4, 5].map(n => `<label style="display:flex;gap:6px;align-items:center;min-height:44px;margin-right:6px">
      <input type="radio" name="cfUse" value="${n}" style="width:22px;height:22px"> ${n}${n === 1 ? ' — not useful' : n === 5 ? ' — very useful' : ''}</label>`).join('')}</div>
    <div style="margin-top:8px">Would you use Cadet Foundry again?</div>
    <div class="row" style="gap:12px">${['yes', 'maybe', 'no'].map(v => `<label style="display:flex;gap:6px;align-items:center;min-height:44px"><input type="radio" name="cfAgain" value="${v}" style="width:22px;height:22px"> ${v[0].toUpperCase() + v.slice(1)}</label>`).join('')}</div>
    <details style="margin-top:6px"><summary style="cursor:pointer;min-height:40px">A few more questions <span class="faint">(optional)</span></summary>
      ${Object.entries(PL_DAILY_Q).map(([k, q]) => `<label for="cf-${k}">${esc(q)}</label><textarea id="cf-${k}" rows="2" maxlength="1000" style="width:100%"></textarea>`).join('')}</details>
    <p class="faint">This is about Cadet Foundry, not your Cadets — please don't name anyone. It stays on this computer.</p>
    <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn primary" id="cfSave">Save</button><button class="btn" id="cfSkip">${esc(skipLabel)}</button></div>
    <p class="faint" id="cfMsg" role="alert"></p></div>`;
  box.querySelector('#cfSkip').addEventListener('click', () => onDone(false));
  box.querySelector('#cfSave').addEventListener('click', async () => {
    const use = box.querySelector('[name=cfUse]:checked'), again = box.querySelector('[name=cfAgain]:checked');
    if (!use) { box.querySelector('#cfMsg').textContent = 'Pick 1 to 5 — or ' + skipLabel + '.'; return; }
    const body = { useful: use.value, again: again ? again.value : '' };
    Object.keys(PL_DAILY_Q).forEach(k => { body[k] = box.querySelector('#cf-' + k).value; });
    const r = await api('/api/instructor/pilot/daily', body);
    if (r.error) { box.querySelector('#cfMsg').textContent = r.error; return; }
    onDone(true);
  });
}

// ── The pilot's headline numbers ──
function plMetricsHtml(m, c) {
  const tile = (big, label, note = '') => `<div style="flex:1;min-width:140px;border:1px solid var(--line);border-radius:10px;padding:10px">
    <div style="font-size:26px;font-weight:700">${big}</div><div>${label}</div>${note ? `<div class="faint" style="font-size:13px">${note}</div>` : ''}</div>`;
  return `<div style="margin:10px 0"><b>Pilot results so far</b>
    <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:6px">
      ${tile(m.cadets, 'Cadets enrolled', c.cadets_planned ? `${c.cadets_planned} planned` : '')}
      ${tile(`${m.active} of ${m.cadets}`, `active in the last ${m.active_days || 14} days`)}
      ${tile(m.assignments_pct == null ? '—' : `${m.assignments_pct}%`, 'lesson assignments completed', `${m.assignments_completed} of ${m.assignments}`)}
      ${tile(`${m.cadets_with_scenario} of ${m.cadets}`, 'Cadets did a leadership scenario', `${m.scenarios} scenarios in all`)}
      ${tile(m.rating == null ? '—' : `${m.rating}/5`, 'how useful you rated it', m.rating_days ? `from ${m.rating_days} class day${m.rating_days === 1 ? '' : 's'}` : 'rate it when you finish class')}
      ${tile(m.would_continue ? m.would_continue.toUpperCase() : '—', 'would you continue?', 'your latest answer')}
      ${m.cadet_responses ? tile(`${m.cadet_keep_using}/5`, 'Cadets: “I’d like to keep using it”', `${m.cadet_responses} anonymous answer${m.cadet_responses === 1 ? '' : 's'}`) : ''}</div>
    <p class="faint" style="margin:6px 0 0">These numbers show how Cadet Foundry was used. They don't show that it improved learning — that takes a comparison over time, and more than one pilot.</p></div>`;
}

// ── One page to hand to a principal or program manager ──
function printPilotSummary(d) {
  const c = d.config || {}, m = d.metrics, fb = d.feedback;
  const quote = [...(d.class_feedback || [])].reverse().map(r => r.worked).find(Boolean)
    || ((fb.instructor || []).slice().reverse().find(r => r.comment) || {}).comment || '';
  const row = (k, v) => `<tr><td style="width:45%">${k}</td><td><b>${v}</b></td></tr>`;
  let area = $('#printArea');
  if (!area) { area = document.createElement('div'); area.id = 'printArea'; document.body.appendChild(area); }
  area.innerHTML = `<div style="font-family:Georgia,serif;color:#000;max-width:7in">
    <div style="letter-spacing:.2em;font-weight:700">CADET FOUNDRY</div><h1 style="margin:4px 0 12px">Pilot Summary</h1>
    <table border="1" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:14px">
      ${row('Program', esc([c.school, c.program].filter(Boolean).join(' · ') || '—'))}
      ${row('Pilot dates', esc(c.start ? `${c.start} to ${c.end || 'ongoing'}` : '—') + (d.weeks != null ? ` (${d.weeks} weeks)` : ''))}
      ${row('Cadets', `${m.cadets}${c.cadets_planned ? ` (${c.cadets_planned} planned)` : ''}`)}
      ${row(`Active in the last ${m.active_days || 14} days`, `${m.active} of ${m.cadets}`)}
      ${row('Lesson assignments completed', m.assignments ? `${m.assignments_completed} of ${m.assignments} (${m.assignments_pct}%)` : '—')}
      ${row('Average lesson score', m.avg_lesson_score_pct == null ? '—' : m.avg_lesson_score_pct + '%')}
      ${row('Leadership scenarios', `${m.scenarios} completed · ${m.cadets_with_scenario} of ${m.cadets} Cadets took part`)}
      ${row('Instructor: how useful (1–5)', m.rating == null ? '—' : `${m.rating} (${m.rating_days} class day${m.rating_days === 1 ? '' : 's'})`)}
      ${row('Instructor: would continue using Cadet Foundry', m.would_continue ? m.would_continue.toUpperCase() : '—')}
      ${m.cadet_responses ? row('Cadets: “I’d like to keep using Cadet Foundry” (1–5)', `${m.cadet_keep_using} (${m.cadet_responses} anonymous answers)`) : ''}</table>
    ${quote ? `<h3 style="margin:16px 0 4px">Instructor feedback</h3><p style="font-style:italic;margin:0">“${esc(quote)}”</p>` : ''}
    <p style="font-size:11px;margin-top:18px">Generated by Cadet Foundry ${esc(STATUS.version || '')} on ${esc(new Date().toLocaleDateString())} from records kept on the instructor's computer. These numbers describe use during the pilot, not proof of learning gains. Cadet Foundry is designed to support JROTC instruction; it is not an official JROTC, military or school product.</p></div>`;
  window.print();
}
