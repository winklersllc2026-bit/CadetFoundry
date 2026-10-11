// Train (Phase 6): personal improvement, not pass/fail. Cadets: one card per event -- latest, best, first, how far
// you've come, a trend line, your goal, and a quick way to log a result. Instructors: the program's events,
// recording results on test day, and each Cadet's progress. Listeners in JS (no inline handlers).
'use strict';

const UNIT_HINT = { reps: 'e.g. 25', time: 'm:ss, e.g. 1:45 or :20', lbs: 'pounds', inches: 'inches', laps: 'laps' };
// the local date (toISOString alone is UTC, which is already tomorrow on a US evening)
const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };

// a small trend line; "up" always means better, whichever way the event is scored
function sparkline(ev) {
  const pts = ev.history.map(h => h.value);
  if (pts.length < 2) return '';
  const w = 140, h = 36, lo = Math.min(...pts), hi = Math.max(...pts), span = hi - lo || 1;
  const xy = pts.map((v, i) => {
    const y = ev.better === 'higher' ? (hi - v) / span : (v - lo) / span;
    return `${(i / (pts.length - 1) * (w - 6) + 3).toFixed(1)},${(y * (h - 6) + 3).toFixed(1)}`;
  }).join(' ');
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Trend over ${pts.length} results, higher on the line is better">
    <polyline points="${xy}" fill="none" stroke="var(--tan)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function growthLine(ev) {
  if (!ev.count) return 'No results yet — log your first one to set your starting point.';
  if (ev.count === 1) return `Starting point set on ${esc(ev.first_date)}. Log again to see your progress.`;
  if (ev.improvement > 0) return `<b>${esc(ev.improvement_shown)}</b> since ${esc(ev.first_date)}${ev.improvement_pct ? ` (${ev.improvement_pct > 0 ? '+' : ''}${ev.improvement_pct}%)` : ''}`;
  if (ev.improvement === 0) return `Holding steady since ${esc(ev.first_date)}.`;
  return `${esc(ev.improvement_shown)} from your first result — your best is ${esc(ev.best)}. Keep at it.`;
}

loaders.train = async () => {
  const body = $('#trainBody');
  const d = await api('/api/train');
  if (d.not_cadet) {
    body.innerHTML = `<h2>Train</h2><div class="card"><p>Train tracks a Cadet's own fitness progress. ${STATUS.kind === 'instructor'
      ? 'Your class view is on the 🎓 Instructor screen.' : ''}</p></div>`;
    return;
  }
  body.innerHTML = `<h2>Train</h2><p class="faint">Measured against yourself: where you started, where you are, and where you're going.</p>
    ${d.events.map(ev => `<div class="card" data-ev="${esc(ev.event)}">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div><h3 style="margin:0">${esc(ev.name)}</h3>${ev.suggested ? '' : ''}<div class="faint">${esc(ev.description || '')}</div></div>
        ${sparkline(ev)}</div>
      ${ev.count ? `<div class="row" style="flex-wrap:wrap;gap:18px;margin:10px 0">
        <div><div style="font-size:26px;font-weight:700">${esc(ev.latest)}</div><div class="faint">Latest${ev.latest_is_best && ev.count > 1 ? ' · personal best 🏅' : ''}</div></div>
        <div><div style="font-size:20px;font-weight:700">${esc(ev.best)}</div><div class="faint">Best</div></div>
        <div><div style="font-size:20px;font-weight:700">${esc(ev.first)}</div><div class="faint">First</div></div></div>` : ''}
      <p style="margin:6px 0">${growthLine(ev)}</p>
      ${ev.goal ? `<p class="faint" style="margin:4px 0">🎯 Goal: <b>${esc(ev.goal)}</b>${ev.goal_by ? ` by ${esc(ev.goal_by)}` : ''}${ev.goal_reached ? ' — reached! Set a new one.' : ''}</p>` : ''}
      <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
        <input data-val placeholder="${esc(UNIT_HINT[ev.unit] || '')}" aria-label="New result for ${esc(ev.name)}" inputmode="${ev.unit === 'time' ? 'text' : 'decimal'}" style="flex:1;min-width:110px">
        <input data-date type="date" value="${today()}" max="${today()}" aria-label="Date" style="flex:1;min-width:140px">
        <button class="btn primary" data-add>Log it</button></div>
      <p class="faint" data-msg role="alert"></p>
      <details><summary>Goal and history</summary>
        <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
          <input data-goal placeholder="Goal (${esc(UNIT_HINT[ev.unit] || '')})" aria-label="Goal for ${esc(ev.name)}" value="${esc(ev.goal || '')}" style="flex:1;min-width:110px">
          <input data-goalby type="date" aria-label="Goal date" value="${esc(ev.goal_by || '')}" style="flex:1;min-width:140px">
          <button class="btn small" data-setgoal>Save goal</button></div>
        ${ev.history.slice().reverse().map(h => `<div class="row" style="justify-content:space-between;border-top:1px solid var(--line);padding:6px 0;margin-top:6px">
          <span>${esc(h.date)} · <b>${esc(h.shown)}</b>${h.by === 'instructor' ? ' <span class="faint">(recorded by your instructor)</span>' : ''}</span>
          ${h.by === 'self' ? `<button class="btn small" data-del="${esc(h.id)}" aria-label="Remove ${esc(h.date)} result">Remove</button>` : ''}</div>`).join('')}
      </details></div>`).join('')}
    <div class="card"><h3>📝 My private logbook</h3><p class="faint">Notes, training and goals just for you. Your instructor can't read it.</p>
      <button class="btn small" id="toLogbook">Open my logbook</button></div>`;
  $('#toLogbook').addEventListener('click', () => openView('logbook', 'log'));
  body.querySelectorAll('[data-ev]').forEach(card => {
    const ev = card.dataset.ev, msg = card.querySelector('[data-msg]');
    const after = r => { if (r.error) msg.textContent = r.error; else loaders.train(); };
    card.querySelector('[data-add]').addEventListener('click', async () =>
      after(await api('/api/train/add', { event: ev, value: card.querySelector('[data-val]').value, date: card.querySelector('[data-date]').value })));
    card.querySelector('[data-val]').addEventListener('keydown', e => { if (e.key === 'Enter') card.querySelector('[data-add]').click(); });
    card.querySelector('[data-setgoal]').addEventListener('click', async () =>
      after(await api('/api/train/goal', { event: ev, target: card.querySelector('[data-goal]').value, by: card.querySelector('[data-goalby]').value })));
    card.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => {
      if (confirm('Remove this result?')) after(await api('/api/train/delete', { id: b.dataset.del }));
    }));
  });
};

// ── Instructor: Train section on the Instructor screen ──
async function instructorTrain(body) {
  const d = await api('/api/instructor/train');
  if (d.error) return;
  const sec = document.createElement('div');
  body.appendChild(sec);
  const unitOpts = Object.entries(d.units).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
  sec.innerHTML = `<div class="card"><h3>💪 Train</h3>
      <p class="faint">Cadets are measured against themselves. Choose the events your program uses — Cadet Foundry has no built-in standard.</p>
      ${d.cadets.length ? d.cadets.map(c => `<details style="margin:6px 0"><summary><b>${esc(c.name)}</b> <span class="faint">${c.shared ? '' : '· waiting to share'}</span></summary>
        ${c.events.filter(e => e.count).map(e => `<div style="margin:6px 0 6px 14px">${esc(e.name)}: <b>${esc(e.latest)}</b>
          <span class="faint">${e.count > 1 ? `· ${esc(e.improvement_shown)} since ${esc(e.first_date)} · best ${esc(e.best)}` : '· starting point'}${e.goal ? ` · goal ${esc(e.goal)}` : ''}</span></div>`).join('')
          || '<div class="faint" style="margin-left:14px">No results yet.</div>'}</details>`).join('') : '<p class="faint">No Cadets yet.</p>'}</div>
    <div class="card"><h3>Record results (test day)</h3>
      <div class="row" style="flex-wrap:wrap;gap:8px"><select id="rEv" aria-label="Event" style="flex:2;min-width:150px">${d.events.map(e => `<option value="${esc(e.id)}">${esc(e.name)}</option>`).join('')}</select>
        <input id="rDate" type="date" value="${today()}" max="${today()}" aria-label="Date" style="flex:1;min-width:140px"></div>
      ${d.cadets.map(c => `<div class="row" style="justify-content:space-between;gap:8px;margin:6px 0"><label for="r-${esc(c.id)}" style="flex:1">${esc(c.name)}</label>
        <input id="r-${esc(c.id)}" data-res="${esc(c.id)}" ${c.shared ? '' : 'disabled placeholder="waiting" title="Waiting to share — signs in next time"'} style="width:130px"></div>`).join('')}
      <button class="btn primary" id="rSave" style="margin-top:8px">Save results</button><p class="faint" id="rMsg" role="alert"></p></div>
    <div class="card"><h3>Events</h3>
      ${d.events.map(e => `<div class="row" style="justify-content:space-between;gap:8px;margin:6px 0">
        <span>${esc(e.name)} <span class="faint">${esc(d.units[e.unit] || e.unit)} · ${e.better} is better${e.suggested ? ' · suggested' : ''}</span></span>
        <button class="btn small" data-rmev="${esc(e.id)}">Remove</button></div>`).join('')}
      <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
        <input id="eName" placeholder="Event name" maxlength="40" aria-label="Event name" style="flex:2;min-width:150px">
        <select id="eUnit" aria-label="Unit" style="flex:1;min-width:120px">${unitOpts}</select>
        <select id="eBetter" aria-label="Better is" style="flex:1;min-width:120px"><option value="higher">Higher is better</option><option value="lower">Lower is better</option></select>
        <button class="btn primary" id="eAdd">Add event</button></div><p class="faint" id="eMsg" role="alert"></p>
      <p class="faint">Removing an event hides it from Train; Cadets' past results are kept.</p></div>`;
  $('#rSave').addEventListener('click', async () => {
    const results = {};
    sec.querySelectorAll('[data-res]').forEach(i => { if (i.value.trim()) results[i.dataset.res] = i.value.trim(); });
    const r = await api('/api/instructor/train/record', { event: $('#rEv').value, date: $('#rDate').value, results });
    if (r.error) { $('#rMsg').textContent = r.error; return; }
    const bad = Object.entries(r.errors || {});
    $('#rMsg').textContent = `Saved ${r.saved.length}.` + (r.skipped.length ? ` ${r.skipped.length} waiting to share.` : '') +
      (bad.length ? ' Not saved: ' + bad.map(([, m]) => m).join('; ') : '');
    if (!bad.length) setTimeout(() => loaders.instructor(), 1200);
  });
  $('#eAdd').addEventListener('click', async () => {
    const r = await api('/api/instructor/train/event', { name: $('#eName').value, unit: $('#eUnit').value, better: $('#eBetter').value });
    if (r.error) $('#eMsg').textContent = r.error; else loaders.instructor();
  });
  sec.querySelectorAll('[data-rmev]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Remove this event from Train? Past results are kept.')) return;
    await api('/api/instructor/train/event', { action: 'remove', id: b.dataset.rmev }); loaders.instructor();
  }));
}
