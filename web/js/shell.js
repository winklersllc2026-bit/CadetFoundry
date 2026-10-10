// Vanguard shell: the Serve, Progress and Instructor pages (Lead is web/js/scenarios.js). Progress is a frame a
// later phase fills in; Serve already holds Explore Military Service (pay, letters, PCS, leave, Army jobs).
'use strict';

const SOON = (what, phase) => `<p class="faint">${what} <b>Coming in a later update</b> (${phase}). Until then your instructor leads this part in class.</p>`;

// Lead: web/js/scenarios.js

loaders.serve = async () => {
  // data-go="view[:pane]" -- the page's security policy blocks inline onclick handlers
  const go = (v, pane) => `data-go="${v}${pane ? ':' + pane : ''}"`;
  await refreshStatus();
  const cats = STATUS.categories || {}, track = (STATUS.profile || {}).military_track === 'yes';
  const cadet = STATUS.kind === 'cadet', basicAllowed = (STATUS.categories_enabled || []).includes('basic');
  $('#serveBody').innerHTML = `<h2>Serve</h2>
    <div class="card"><h3>🤝 Service learning</h3>
      <p class="faint">Your service projects: date, hours, organization, your role, and what you learned. Your instructor verifies them.</p>
      <div id="serviceBox"></div>
      ${(STATUS.modules_off || []).includes('letters') ? '' : `<button class="btn small" ${go('logbook', 'letters')} style="margin-top:8px">✉️ Write to family, service members or veterans</button>`}</div>
    ${'explore' in cats ? `<div class="card" id="exploreMil"><h3>🎗️ Explore Military Service</h3>
      <p class="faint">For Cadets who want to learn what military service is like. Information only — nothing here
      signs you up or shares anything with a recruiter. Numbers come straight from official tables.</p>
      <div class="row" style="flex-wrap:wrap;gap:6px">
        <button class="btn small" ${go('study')}>💼 Army jobs explorer (in Learn)</button>
        <button class="btn small" ${go('logbook', 'money')}>💵 Military pay and budgeting</button>
        <button class="btn small" ${go('logbook', 'fit')}>🏋️ Army Fitness Test scorer</button>
        <button class="btn small" ${go('logbook', 'leave')}>🏖️ How military leave works</button>
        <button class="btn small" ${go('logbook', 'pcs')}>📦 Moving with the military (PCS)</button>
      </div>
      <p class="faint">Ask questions like "What does an E-4 with 3 years make?" with 💬 Ask.</p>
      ${cadet && basicAllowed ? `<div class="card" style="margin-top:10px">
        <label style="display:flex;gap:12px;align-items:flex-start;cursor:pointer">
          <input type="checkbox" id="milTrack" ${track ? 'checked' : ''} style="width:24px;height:24px;flex:none;margin-top:2px">
          <span><b>I plan to join the military.</b><br><span class="faint">Adds the <b>🪖 Basic Training &amp; Beyond</b> study guide to Learn:
          what basic training is like, the General Orders, the Soldier's Creed, military law, safety and more. You can turn it off any time.</span></span></label>
        <p class="faint" id="milMsg" role="status"></p></div>` : ''}</div>` : ''}`;
  $('#serveBody').querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => {
    const [v, pane] = b.dataset.go.split(':');
    window.moneyMilitary = !!b.closest('#exploreMil');       // the Money pane opens its military pay tools
    openView(v, pane);
  }));
  if (typeof serviceCadet === 'function') serviceCadet($('#serviceBox'));       // web/js/service.js
  if ($('#milTrack')) $('#milTrack').addEventListener('change', async e => {
    const on = e.target.checked;
    const r = await api('/api/profile', { military_track: on ? 'yes' : '' });
    if (r.error) { $('#milMsg').textContent = r.error; e.target.checked = !on; return; }
    await refreshStatus();
    $('#milMsg').textContent = on ? 'Added: 🪖 Basic Training & Beyond is now in Learn.' : 'Removed from Learn.';
  });
};

// My Progress: web/js/progress.js

// ── Instructor ── (instructor profile + Instructor PIN; Cadets only see an explanation)
const KIND_NAME = { class: 'Class', platoon: 'Platoon', squad: 'Squad' };
const STATUS_NAME = {
  shared: ['✅', 'Records shared'],
  open: ['ℹ️', 'No PIN on this profile — records aren’t encrypted'],
  waiting: ['⏳', 'Waiting — shares records the next time this Cadet signs in'],
};

// Each load gets a number; an older, slower load stops drawing and its sections land in containers that are
// no longer on the page (the screen used to show some sections twice when opened twice quickly).
let instructorRun = 0;
loaders.instructor = async () => {
  const run = ++instructorRun;
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
  if (run !== instructorRun) return;                // a newer load of this screen is already drawing
  body.innerHTML = `<h2>Instructor</h2>${STATUS.lan ? `<div class="card" style="border-color:var(--tan)"><h3>📡 Classroom network is on</h3>
      <p class="faint">Anyone on this Wi-Fi can open Vanguard's sign-in screen (they see shortened names, and every profile needs a PIN).
      For a pilot, use a <b>dedicated hotspot</b> only your class joins — not the school's open or guest Wi-Fi. Close Vanguard
      (Me → Quit) when class ends. Details: SECURITY.md → "The classroom network".</p></div>` : ''}<div data-top></div>
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
        ${c.status === 'waiting' ? '' : `<button class="btn small" data-prog="${esc(c.id)}" style="margin-top:8px">📈 Progress and portfolio</button>`}
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
  body.querySelectorAll('[data-prog]').forEach(b => b.addEventListener('click', () => instructorProgress(b.dataset.prog)));
  body.querySelectorAll('[data-let]').forEach(s => s.addEventListener('change', () => s.value && api('/api/instructor/assign', { cadet: s.dataset.let, let: Number(s.value) })));
  // Learn categories for every Cadet on this device (spec §7). Basic Training & Beyond still needs each Cadet's own opt-in.
  const CAT_NAMES = { leadership: 'Leadership', citizenship: 'Citizenship', military: 'Military Knowledge', health: 'Health & Fitness',
    careers: 'Careers', explore: 'Explore Military Service', basic: 'Basic Training & Beyond (only for Cadets who opt in)' };
  const on = STATUS.categories_enabled || Object.keys(CAT_NAMES);
  const catCard = document.createElement('div');
  catCard.className = 'card';
  catCard.innerHTML = `<h3>📘 What Cadets can study</h3><p class="faint">Turn sections of Learn on or off for every Cadet on this device.</p>
    ${Object.entries(CAT_NAMES).map(([k, v]) => `<label style="display:flex;gap:10px;align-items:center;min-height:44px">
      <input type="checkbox" data-cat="${k}" ${on.includes(k) ? 'checked' : ''} style="width:22px;height:22px"> ${esc(v)}</label>`).join('')}
    <p class="faint" id="catMsg" role="status"></p>`;
  body.appendChild(catCard);
  catCard.querySelectorAll('[data-cat]').forEach(cb => cb.addEventListener('change', async () => {
    const cats = [...catCard.querySelectorAll('[data-cat]:checked')].map(x => x.dataset.cat);
    const r = await api('/api/instructor/categories', { categories: cats });
    $('#catMsg').textContent = r.error || 'Saved.';
    if (!r.error) STATUS.categories_enabled = r.categories_enabled;
  }));
  // Optional tools on or off for every profile on this device (the server refuses a switched-off tool's routes)
  const MODS = { faith: 'Faith texts (scripture lookup and reading plans)', letters: 'Letters and address book', voice: 'Talk to Vanguard (offline voice)' };
  const modsOff = STATUS.modules_off || [];
  const modCard = document.createElement('div');
  modCard.className = 'card';
  modCard.innerHTML = `<h3>🧰 Optional tools</h3><p class="faint">Turn optional tools on or off for every profile on this device.</p>
    ${Object.entries(MODS).map(([k, v]) => `<label style="display:flex;gap:10px;align-items:center;min-height:44px">
      <input type="checkbox" data-mod="${k}" ${modsOff.includes(k) ? '' : 'checked'} style="width:22px;height:22px"> ${esc(v)}</label>`).join('')}
    <p class="faint" id="modMsg" role="status"></p>`;
  body.appendChild(modCard);
  modCard.querySelectorAll('[data-mod]').forEach(cb => cb.addEventListener('change', async () => {
    const off = [...modCard.querySelectorAll('[data-mod]')].filter(x => !x.checked).map(x => x.dataset.mod);
    const r = await api('/api/instructor/modules', { off });
    $('#modMsg').textContent = r.error || 'Saved. Profiles see the change the next time they open Vanguard.';
    if (!r.error) STATUS.modules_off = r.modules_off;
  }));
  const extra = document.createElement('div');       // this load's own container for the sections below
  body.appendChild(extra);
  const steps = [
    () => typeof instructorDashboard === 'function' && instructorDashboard(body.querySelector('[data-top]'), ov),   // dashboard.js
    () => typeof instructorLessons === 'function' && instructorLessons(extra, ov),          // lessons.js
    () => typeof instructorLeadership === 'function' && instructorLeadership(extra),        // scenarios.js
    () => typeof instructorTrain === 'function' && instructorTrain(extra),                  // train.js
    () => typeof instructorService === 'function' && instructorService(extra),              // service.js
    () => typeof instructorQuizzes === 'function' && instructorQuizzes(extra, ov),          // dashboard.js
    () => typeof instructorPilot === 'function' && instructorPilot(extra),                  // pilot.js
    () => typeof instructorBackup === 'function' && instructorBackup(extra),                // dashboard.js
  ];
  for (const step of steps) {
    if (run !== instructorRun) return;
    await step();
  }
};
