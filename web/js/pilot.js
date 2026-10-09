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
    <details ${c.start ? '' : 'open'}><summary><b>Pilot setup</b></summary>
      <label for="plSchool">School</label><input id="plSchool" maxlength="100" value="${esc(c.school || '')}">
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <div style="flex:1;min-width:150px"><label for="plProg">Program</label><input id="plProg" maxlength="60" value="${esc(c.program || 'Army JROTC')}"></div>
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
      <div style="margin-top:8px">How satisfied are you with Vanguard so far?</div>
      <div class="row" style="flex-wrap:wrap;gap:6px">${[1, 2, 3, 4, 5].map(n => `<label style="display:flex;gap:6px;align-items:center;min-height:40px"><input type="radio" name="plSat" value="${n}" style="width:22px;height:22px"> ${n}</label>`).join('')}</div>
      <label for="plMin">About how many minutes a week did it save you? (negative if it cost you time)</label><input id="plMin" inputmode="numeric">
      <div style="margin-top:8px">Would you use Vanguard next semester?</div>
      <div class="row" style="gap:12px">${['yes', 'maybe', 'no'].map(v => `<label style="display:flex;gap:6px;align-items:center;min-height:40px"><input type="radio" name="plAgain" value="${v}" style="width:22px;height:22px"> ${v[0].toUpperCase() + v.slice(1)}</label>`).join('')}</div>
      <label for="plCom">Comments</label><textarea id="plCom" rows="2" style="width:100%"></textarea>
      <button class="btn primary" id="plFb" style="margin-top:8px">Save my feedback</button><p class="faint" id="plFbMsg" role="alert"></p>
      ${fb.instructor.length ? `<p class="faint">Saved ${fb.instructor.length} time${fb.instructor.length === 1 ? '' : 's'}; latest ${esc(fb.latest_instructor.date)}: satisfaction ${fb.latest_instructor.satisfaction}/5, next semester: ${esc(fb.latest_instructor.use_again)}.</p>` : ''}</details>` : ''}`;
  body.appendChild(sec);
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
  area.innerHTML = `<div style="font-family:Georgia,serif;color:#000"><div style="letter-spacing:.2em;font-weight:700">VANGUARD</div>
    <h1 style="margin:4px 0">JROTC Pilot Report</h1>
    <div>${esc(c.school || '')} · ${esc(c.program || '')}${c.instructor ? ' · Instructor: ' + esc(c.instructor) : ''} · printed ${esc(new Date().toLocaleDateString())}</div>
    <table border="1" cellpadding="5" style="border-collapse:collapse;width:100%;margin-top:12px;font-size:13px">${rows.join('')}</table>
    ${base ? `<p style="font-size:12px">Change is measured from the first snapshot (${esc(base.date)}).</p>` : `<p style="font-size:12px">${(d.cannot_measure || []).map(esc).join(' ')}</p>`}
    ${survey}${ins}
    ${c.notes ? `<h2>Notes</h2><p>${esc(c.notes)}</p>` : ''}
    <p style="font-size:11px;margin-top:20px">Every number comes from records kept on the instructor's device. Vanguard is designed to support JROTC instruction; it is not an official JROTC, Army or school product.</p></div>`;
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
    box.innerHTML = '<p style="margin:0">📝 Thanks for answering the Vanguard survey!</p>';
  } else {
    box.innerHTML = `<h3>📝 A quick survey about Vanguard</h3>
      <p class="faint">Anonymous — your name isn't saved with your answers. It takes about a minute.</p>
      ${s.questions.map(q => `<fieldset style="border:0;padding:0;margin:12px 0"><legend><b>${esc(q.q)}</b></legend>
        <div class="row" style="flex-wrap:wrap;gap:4px">${Object.entries(s.scale).map(([v, t]) => `<label style="display:flex;gap:6px;align-items:center;min-height:40px;margin-right:8px">
          <input type="radio" name="sv-${q.id}" value="${v}" style="width:22px;height:22px"> ${esc(t)}</label>`).join('')}</div></fieldset>`).join('')}
      <label for="svCom">What would make Vanguard better? (optional)</label><textarea id="svCom" rows="2" style="width:100%"></textarea>
      <button class="btn primary" id="svSend" style="margin-top:8px">Send</button><p class="faint" id="svMsg" role="alert"></p>`;
  }
  container.prepend(box);
  if (s.done) return;
  box.querySelector('#svSend').addEventListener('click', async () => {
    const answers = {};
    s.questions.forEach(q => { const x = box.querySelector(`[name=sv-${q.id}]:checked`); if (x) answers[q.id] = +x.value; });
    const r = await api('/api/pilot/survey', { answers, comment: box.querySelector('#svCom').value });
    if (r.error) { box.querySelector('#svMsg').textContent = r.error; return; }
    box.innerHTML = '<p style="margin:0">📝 Thanks for answering the Vanguard survey!</p>';
  });
}
