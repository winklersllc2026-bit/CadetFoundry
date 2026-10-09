// Vanguard shell: the Serve, Progress and Instructor pages (Lead is web/js/scenarios.js). Progress is a frame a
// later phase fills in; Serve already holds Explore Military Service (pay, letters, PCS, leave, Army jobs).
'use strict';

const SOON = (what, phase) => `<p class="faint">${what} <b>Coming in a later update</b> (${phase}). Until then your instructor leads this part in class.</p>`;

// Lead: web/js/scenarios.js

loaders.serve = () => {
  // data-go="view[:pane]" -- the page's security policy blocks inline onclick handlers
  const go = (v, pane) => `data-go="${v}${pane ? ':' + pane : ''}"`;
  $('#serveBody').innerHTML = `<h2>Serve</h2>
    <div class="card"><h3>🤝 Service learning</h3>
      <p>Track your service projects: date, hours, organization, your role, and what you learned. Your instructor
      verifies them.</p>${SOON('The service log is being built.', 'Phase 7')}</div>
    <div class="card" id="exploreMil"><h3>🎖️ Explore Military Service</h3>
      <p class="faint">For Cadets who want to learn what military service is like. Information only — nothing here
      signs you up or shares anything with a recruiter. Numbers come straight from official tables.</p>
      <div class="row" style="flex-wrap:wrap;gap:6px">
        <button class="btn small" ${go('logbook', 'money')}>💵 Military pay and budgeting</button>
        <button class="btn small" ${go('study')}>🪖 Army jobs explorer (in Learn)</button>
        <button class="btn small" ${go('logbook', 'fit')}>🏋️ Army Fitness Test scorer</button>
        <button class="btn small" ${go('logbook', 'leave')}>🏖️ How military leave works</button>
        <button class="btn small" ${go('logbook', 'pcs')}>📦 Moving with the military (PCS)</button>
        <button class="btn small" ${go('logbook', 'letters')}>✉️ Letters to family, service members and veterans</button>
      </div>
      <p class="faint">Ask questions like "What does an E-4 with 3 years make?" or "What is the ETS box on a pay
      statement?" with 💬 Ask.</p></div>`;
  $('#serveBody').querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => {
    const [v, pane] = b.dataset.go.split(':'); openView(v, pane);
  }));
};

loaders.progress = () => {
  $('#progressBody').innerHTML = `<h2>My Progress</h2>
    <div class="card"><h3>📈 Your growth over time</h3>
      <p>Lessons and quiz mastery, leadership scenarios and reflections, fitness improvement, service hours, and
      recognition — in one place, with a portfolio you can print.</p>
      ${SOON('Your progress page is being built.', 'Phase 8')}
      <p class="faint">Already here: your quiz progress in Learn and your fitness history in Train.</p></div>`;
};

// ── Instructor ── (instructor profile + Instructor PIN; Cadets only see an explanation)
const KIND_NAME = { class: 'Class', platoon: 'Platoon', squad: 'Squad' };
const STATUS_NAME = {
  shared: ['✅', 'Records shared'],
  open: ['ℹ️', 'No PIN on this profile — records aren’t encrypted'],
  waiting: ['⏳', 'Waiting — shares records the next time this Cadet signs in'],
};

loaders.instructor = async () => {
  const body = $('#instructorBody');
  if (STATUS.kind !== 'instructor') {
    body.innerHTML = `<h2>Instructor</h2><div class="card"><h3>🎓 For instructors</h3>
      <p>This area is for your JROTC instructor: classes, assignments and progress. Your private check-ins and chats
      are never shown here — only class records like lessons, quizzes, fitness and service.</p></div>`;
    return;
  }
  const ov = await api('/api/instructor/overview');
  if (ov.error) {                                  // signed in as an instructor, but the class records are locked
    body.innerHTML = `<h2>Instructor</h2><div class="card"><h3>🔐 Open class records</h3>
      <p>Enter the Instructor PIN to see your classes and Cadets' class records on this device. It stays open until
      you sign out.</p>
      <div class="row" style="flex-wrap:wrap;gap:8px"><input id="insPin" type="password" inputmode="numeric" maxlength="12"
        placeholder="Instructor PIN" aria-label="Instructor PIN" style="flex:1;min-width:160px">
      <button class="btn primary" id="insGo">Open</button></div><p class="faint" id="insMsg" role="alert"></p></div>`;
    const go = async () => {
      const r = await api('/api/instructor/unlock', { admin: $('#insPin').value });
      if (r.ok) loaders.instructor(); else $('#insMsg').textContent = r.error;
    };
    $('#insGo').addEventListener('click', go);
    $('#insPin').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    return;
  }
  const units = ov.units, unitName = id => (units.find(u => u.id === id) || {}).name || '';
  const unitOpts = (sel, blank) => `<option value="">${blank}</option>` +
    units.map(u => `<option value="${esc(u.id)}" ${u.id === sel ? 'selected' : ''}>${esc(KIND_NAME[u.kind] || '')}: ${esc(u.name)}</option>`).join('');
  const shared = ov.cadets.filter(c => c.status !== 'waiting').length;
  body.innerHTML = `<h2>Instructor</h2>
    <div class="card"><div class="row" style="flex-wrap:wrap;gap:16px">
      <div><div style="font-size:28px;font-weight:700">${ov.cadets.length}</div><div class="faint">Cadets on this device</div></div>
      <div><div style="font-size:28px;font-weight:700">${shared}</div><div class="faint">sharing class records</div></div>
      <div><div style="font-size:28px;font-weight:700">${units.length}</div><div class="faint">classes, platoons, squads</div></div>
    </div></div>
    <div class="card"><h3>Classes, platoons and squads</h3>
      ${units.length ? `<ul style="padding-left:18px;margin:0 0 10px">${units.map(u => `<li style="margin:6px 0">
        ${esc(KIND_NAME[u.kind])}: <b>${esc(u.name)}</b>${u.parent ? ` <span class="faint">(in ${esc(unitName(u.parent))})</span>` : ''}
        <button class="btn small" data-del="${esc(u.id)}" aria-label="Remove ${esc(u.name)}">Remove</button></li>`).join('')}</ul>`
        : '<p class="faint">None yet. Add your first class or platoon.</p>'}
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <input id="uName" placeholder="Name (e.g. Alpha Platoon)" aria-label="Unit name" maxlength="40" style="flex:2;min-width:160px">
        <select id="uKind" aria-label="Kind" style="flex:1;min-width:110px">${Object.entries(KIND_NAME).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
        <select id="uParent" aria-label="Part of" style="flex:1;min-width:140px">${unitOpts('', 'Part of… (none)')}</select>
        <button class="btn primary" id="uAdd">Add</button></div><p class="faint" id="uMsg" role="alert"></p></div>
    <div class="card"><h3>Cadets</h3>
      ${ov.cadets.length ? ov.cadets.map(c => `<div class="card" style="margin:8px 0;padding:12px">
        <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:6px"><b>${esc(c.name)}</b>
          <span class="faint" title="${esc(STATUS_NAME[c.status][1])}">${STATUS_NAME[c.status][0]} ${esc(STATUS_NAME[c.status][1])}</span></div>
        <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
          <select data-unit="${esc(c.id)}" aria-label="Unit for ${esc(c.name)}" style="flex:2;min-width:150px">${unitOpts(c.unit, 'No unit')}</select>
          <select data-let="${esc(c.id)}" aria-label="LET level for ${esc(c.name)}" style="flex:1;min-width:110px">
            <option value="">LET level…</option>${ov.let_levels.map(l => `<option value="${l}" ${c.let === l ? 'selected' : ''}>LET ${l}</option>`).join('')}</select>
        </div>
        <div class="faint" style="margin-top:6px">${c.status === 'waiting' ? '' : `Quiz questions known: ${c.questions_known} · Exams: ${c.exams}${c.last_study ? ` · Last studied ${esc(c.last_study)}` : ''}`}</div>
      </div>`).join('') : '<p class="faint">No Cadet profiles on this device yet. Cadets create their own profile with a PIN when they first open Vanguard.</p>'}
      <p class="faint">You see class records only. Cadets' private check-ins, chats and notes are never shown.</p></div>`;
  $('#uAdd').addEventListener('click', async () => {
    const r = await api('/api/instructor/unit', { action: 'add', name: $('#uName').value, kind: $('#uKind').value, parent: $('#uParent').value });
    if (r.error) $('#uMsg').textContent = r.error; else loaders.instructor();
  });
  body.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Remove this unit? Its Cadets become unassigned; nothing else is deleted.')) return;
    await api('/api/instructor/unit', { action: 'delete', id: b.dataset.del }); loaders.instructor();
  }));
  body.querySelectorAll('[data-unit]').forEach(s => s.addEventListener('change', () => api('/api/instructor/assign', { cadet: s.dataset.unit, unit: s.value })));
  body.querySelectorAll('[data-let]').forEach(s => s.addEventListener('change', () => s.value && api('/api/instructor/assign', { cadet: s.dataset.let, let: Number(s.value) })));
  if (typeof instructorLessons === 'function') await instructorLessons(body, ov);   // web/js/lessons.js
  if (typeof instructorLeadership === 'function') await instructorLeadership(body);   // web/js/scenarios.js
  if (typeof instructorTrain === 'function') await instructorTrain(body);             // web/js/train.js
};
