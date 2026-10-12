// Cadet Foundry shell: the Serve, Progress and Instructor pages (Lead is web/js/scenarios.js). Progress is a frame a
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
        <button class="btn small" ${go('study')}>💼 Military jobs explorer (in Learn)</button>
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

// ── Instructor ── (instructor profile + Class PIN; Cadets only see an explanation)
// One section at a time, picked from a short menu: Today (where class starts), Class, Lessons, Present, Reports,
// Settings -- instead of one long page of everything.
const KIND_NAME = { class: 'Class', platoon: 'Platoon', squad: 'Squad' };
const STATUS_NAME = {
  shared: ['✅', 'Records shared'],
  open: ['ℹ️', 'No PIN on this profile — records aren’t protected'],
  waiting: ['⏳', 'Waiting — shares records the next time this Cadet signs in'],
};
const INST_SECTIONS = [['today', '🏠', 'Today'], ['class', '👥', 'Class'], ['lessons', '📋', 'Lessons'],
  ['present', '🖥️', 'Present'], ['reports', '📊', 'Reports'], ['settings', '⚙️', 'Settings']];
let instSection = 'today';

// Each load gets a number; an older, slower load stops drawing and its sections land in containers that are
// no longer on the page (the screen used to show some sections twice when opened twice quickly).
let instructorRun = 0;
loaders.instructor = async (section) => {
  if (typeof section === 'string') instSection = section;
  const run = ++instructorRun;
  const body = $('#instructorBody');
  if (STATUS.kind !== 'instructor') {
    body.innerHTML = `<h2>Instructor</h2><div class="card"><h3>🎓 For instructors</h3>
      <p>This area is for your instructor: classes, assignments and progress. Your private check-ins and chats
      are never shown here — only class records like lessons, quizzes, fitness and service.</p></div>`;
    return;
  }
  const ov = await api('/api/instructor/overview');
  if (ov.error) {                                  // signed in as an instructor, but the class records are locked
    body.innerHTML = `<h2>Instructor</h2><div class="card"><h3>🔐 Open your class</h3>
      <p>Enter the Class PIN to open instructor tools. It stays open until you sign out.</p>
      <div class="row" style="flex-wrap:wrap;gap:8px"><input id="insPin" type="password" inputmode="numeric" maxlength="12"
        placeholder="Class PIN" aria-label="Class PIN" style="flex:1;min-width:160px;font-size:20px;letter-spacing:.2em">
      <button class="btn primary" id="insGo">Open</button></div><p class="faint" id="insMsg" role="alert"></p></div>`;
    const go = async () => {
      const r = await api('/api/instructor/unlock', { admin: $('#insPin').value });
      if (r.ok) loaders.instructor(); else $('#insMsg').textContent = r.error;
    };
    $('#insGo').addEventListener('click', go);
    $('#insPin').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    $('#insPin').focus();
    return;
  }
  if (run !== instructorRun) return;                // a newer load of this screen is already drawing
  body.innerHTML = `<h2>Instructor</h2>
    <nav class="row" id="instNav" aria-label="Instructor sections" style="flex-wrap:wrap;gap:6px;margin-bottom:12px">
      ${INST_SECTIONS.map(([id, ic, name]) => `<button class="btn${id === instSection ? ' primary' : ''}" data-isec="${id}"
        ${id === instSection ? 'aria-current="page"' : ''}>${ic} ${name}</button>`).join('')}</nav>
    <div id="instSec"></div>`;
  body.querySelectorAll('[data-isec]').forEach(b => b.addEventListener('click', () => loaders.instructor(b.dataset.isec)));
  const sec = $('#instSec');
  const steps = { today: instToday, class: instClass, lessons: instLessons, present: instPresent, reports: instReports,
    settings: instSettings }[instSection] || instToday;
  await steps(sec, ov, run);
};

// Set up your class: three steps, each done right where it's shown (instructor Home and Today) -- make a class, put
// Cadets in it, open class to phones -- plus a warning for profiles phones can't open (no PIN yet). Returns true
// when everything is ready.
async function classSetup(box, ov, reload, { compactWhenReady = false } = {}) {
  let cls = {};
  try { cls = await api('/api/classroom'); } catch (e) { }
  const loose = ov.cadets.filter(c => !c.unit), noPin = cls.no_pin || [];
  // Phones are optional (owner, 2026-10-12): a class taught from the projector is ready without them.
  const ready = !!(ov.units.length && !loose.length);           // a no-PIN profile is a warning, not a blocker
  const noPinNote = short => noPin.length ? `<p style="margin:10px 0 0">⚠ <b>No PIN yet:</b> ${noPin.map(esc).join(', ')}. <span class="faint">Phones can't open ${noPin.length === 1 ? 'this profile' : 'these profiles'}${short ? '' : ` until ${noPin.length === 1 ? 'it has' : 'they have'} a PIN`}. Sign in to ${noPin.length === 1 ? 'it' : 'each one'} on this computer, then 👤 Me → Security → Set a PIN.</span></p>` : '';
  const step = (done, title, body) => `<div class="row" style="align-items:flex-start;gap:12px;margin:12px 0;flex-wrap:nowrap">
      <span style="font-size:22px;line-height:1.2">${typeof done === 'string' ? done : done ? '✅' : '⬜'}</span><div style="flex:1"><b>${title}</b>${body ? `<div style="margin-top:6px">${body}</div>` : ''}</div></div>`;
  if (STATUS.sample && ov.units.length && !loose.length) {   // the sample class stays on this computer: nothing to open
    box.innerHTML = `<div class="card"><span>✅ <b>The sample class is set up.</b> <span class="faint">${ov.units.map(u => esc(u.name)).join(' · ')}.
      In your own Cadet Foundry, Cadet phones can be turned on so Cadets join and vote; the sample stays on this computer.</span></span></div>`;
    return true;
  }
  if (ready && compactWhenReady) {
    box.innerHTML = `<div class="card"><div class="row" style="justify-content:space-between;gap:10px;flex-wrap:wrap">
      <span>✅ <b>Your class is set up.</b> <span class="faint">${ov.units.map(u => `${esc(u.name)} · code <b class="mono" style="letter-spacing:.12em;color:var(--tan2)">${esc(u.code || '')}</b>`).join(' · ')}
        · Cadet phones ${STATUS.lan ? 'on' : 'off'}</span></span>
      ${STATUS.lan ? `<span class="row" style="gap:8px"><button class="btn" id="tJoin">📱 Join screen (QR code)</button>
      ${cls.local ? '<button class="btn small" id="tClose" title="Phones can no longer reach Cadet Foundry; it keeps running on this computer">Turn phones off</button>' : ''}</span>` : ''}</div>${noPinNote(true)}</div>`;
  } else {
    box.innerHTML = `<div class="card" style="border-color:var(--tan)"><h3>${ready ? '✅ Your class is ready' : '🧭 Set up your class'}</h3>
    ${step(ov.units.length, '1. Make your class', ov.units.length
      ? `<span class="faint">${ov.units.map(u => `${esc(u.name)} — join code <b class="mono" style="letter-spacing:.12em;color:var(--tan2)">${esc(u.code || '')}</b>`).join('<br>')}</span>`
      : `<div class="row" style="gap:8px;flex-wrap:wrap"><input id="sName" placeholder="Class name (e.g. LET 1, 3rd period)" maxlength="40" aria-label="Class name" style="flex:1;min-width:200px">
         <button class="btn primary" id="sMake">Create class</button></div><p class="faint" id="sMsg" role="alert" style="margin:4px 0 0"></p>`)}
    ${step(ov.units.length && !loose.length, '2. Put your Cadets in it', !ov.cadets.length
      ? '<span class="faint">No Cadets yet. With Cadet phones on, Cadets scan the QR code on the Join screen and land in your class on their own. You can teach from the projector without them.</span>'
      : loose.length && ov.units.length
        ? `<div class="faint" style="margin-bottom:6px">${loose.length} Cadet${loose.length === 1 ? ' isn’t' : 's aren’t'} in a class yet: ${loose.map(c => esc(c.name)).join(', ')}</div>
           <div class="row" style="gap:8px;flex-wrap:wrap"><select id="sUnit" aria-label="Class" style="flex:1;min-width:180px">${ov.units.map(u => `<option value="${esc(u.id)}">${esc(u.name)}</option>`).join('')}</select>
           <button class="btn primary" id="sPut">Add ${loose.length === 1 ? 'them' : `all ${loose.length}`} to this class</button></div>`
        : loose.length ? '<span class="faint">Make your class first (step 1).</span>'
          : `<span class="faint">All ${ov.cadets.length} Cadet${ov.cadets.length === 1 ? ' is' : 's are'} in a class. Move anyone in 👥 Class.</span>`)}
    ${step(STATUS.lan ? '✅' : '📱', '3. Cadet phones (optional)', STATUS.lan
      ? `<button class="btn primary" id="tJoin">📱 Show the Join screen (QR code)</button>
         ${cls.local ? '<button class="btn small" id="tClose" title="Phones can no longer reach Cadet Foundry; it keeps running on this computer">Turn phones off</button>' : ''}
         <div class="faint" style="margin-top:6px">Phones are on. Put the Join screen on the projector; Cadets scan it with their phone camera.</div>`
      : cls.local ? `<div class="faint" style="margin-bottom:6px">Off — you don't need them. Questions and scenarios run as a show of hands.</div>
         <button class="btn" id="tOpen">📱 Turn phones on</button>
         <div class="faint" style="margin-top:6px">Lets Cadets on the same Wi-Fi join from their phones, vote and answer.
         If Windows asks whether to allow Cadet Foundry (Python) on networks, choose <b>Allow</b>.</div><p class="faint" id="tOpenMsg" role="status" style="margin:4px 0 0"></p>`
        : '<span class="faint">Turn phones on from the instructor’s own computer.</span>')}
    ${noPinNote(false)}
    </div>`;
  }
  const q = s => box.querySelector(s);
  if (q('#tJoin')) q('#tJoin').addEventListener('click', () => window.open('/join', '_blank', 'noopener'));
  if (q('#tOpen')) q('#tOpen').addEventListener('click', () => switchClassroom(true, q('#tOpen'), q('#tOpenMsg')));
  if (q('#tClose')) q('#tClose').addEventListener('click', () => {
    if (confirm('Turn Cadet phones off? Cadets’ phones disconnect; Cadet Foundry keeps running on this computer. Everyone’s work is saved.'))
      switchClassroom(false, q('#tClose'));
  });
  if (q('#sMake')) {
    const make = async () => {
      const r = await api('/api/instructor/unit', { action: 'add', name: q('#sName').value, kind: 'class', parent: '' });
      if (r.error) q('#sMsg').textContent = r.error; else reload();
    };
    q('#sMake').addEventListener('click', make);
    q('#sName').addEventListener('keydown', e => { if (e.key === 'Enter') make(); });
  }
  if (q('#sPut')) q('#sPut').addEventListener('click', async () => {
    q('#sPut').disabled = true;
    for (const c of loose) await api('/api/instructor/assign', { cadet: c.id, unit: q('#sUnit').value });
    reload();
  });
  return ready;
}

// Open class to phones (or close it) without closing Cadet Foundry: the server listens again in the other mode, then this
// page reloads once it answers. Sign-ins stay. Only from the instructor's own computer.
async function switchClassroom(open, btn, msg) {
  if (btn) btn.disabled = true;
  if (msg) msg.textContent = open ? 'Turning Cadet phones on… (a few seconds)' : 'Turning Cadet phones off…';
  const r = await api('/api/instructor/classroom', { open });
  if (r.error) { if (msg) msg.textContent = r.error; if (btn) btn.disabled = false; return; }
  for (let i = 0; i < 60; i++) {                   // up to about 30 seconds while it switches
    await new Promise(res => setTimeout(res, 500));
    try {
      const s = await (await fetch('/api/lock', { cache: 'no-store' })).json();
      if (s.lan === open) { location.reload(); return; }
    } catch (e) { }                                  // not answering yet: still switching
  }
  if (msg) msg.textContent = 'This is taking longer than usual. Reload the page in a moment.';
}

// When a projector screen (scenario vote, live question, video) ends: back to the class-day run sheet if one is
// running, otherwise to the instructor tools.
let classDayActive = false;
function backFromClassroom() {
  if (classDayActive) { openView('home'); return; }
  loaders.instructor(); openView('instructor');
}

// Today: is class open, the join codes, what needs you, and one-tap starts for class.
async function instToday(sec, ov) {
  const mine = ov.units.filter(u => u.owner === ov.me), units = mine.length ? mine : ov.units;
  const d = await api('/api/instructor/dashboard?unit=' + (mine.length ? 'mine' : ''));
  const needs = [d.service_pending && `<b>${d.service_pending}</b> service entr${d.service_pending === 1 ? 'y' : 'ies'} to review`,
    d.lessons_overdue && `<b>${d.lessons_overdue}</b> overdue lesson${d.lessons_overdue === 1 ? '' : 's'}`,
    d.waiting_to_share && `<b>${d.waiting_to_share}</b> Cadet${d.waiting_to_share === 1 ? '' : 's'} not sharing records yet`].filter(Boolean);
  sec.innerHTML = `<div id="setupBox"></div>
    <div class="card"><h3>👥 ${mine.length ? 'My Cadets' : 'Cadets'}</h3>
      ${d.cadets ? `<p><b>${d.cadets}</b> Cadet${d.cadets === 1 ? '' : 's'} · ${d.active} active in the last ${d.active_days} days</p>`
        : `<p><b>No Cadets yet.</b> ${STATUS.lan ? 'Open the Join screen and have Cadets scan the code.' : 'Cadets make their own profile with a PIN the first time they open Cadet Foundry.'}</p>`}
      ${units.length ? `<div class="faint">Join codes — a Cadet who types one (or scans it on the Join screen) lands in that class:</div>
        ${units.map(u => `<div class="row" style="justify-content:space-between;margin:6px 0"><span>${esc(u.name)}</span>
          <b class="mono" style="letter-spacing:.15em;color:var(--tan2)">${esc(u.code || '')}</b></div>`).join('')}`
        : '<p class="faint">Add a class or platoon in 👥 Class to get a join code for it.</p>'}
      ${needs.length ? `<p style="margin:10px 0 0">Needs you: ${needs.join(' · ')}</p>` : ''}</div>
    <div class="card"><h3>Start something</h3><div class="tiles" style="margin:0">
      <button class="tile" data-tgo="present"><span>📡</span>Ask a live question<small>Cadets answer on their phones</small></button>
      <button class="tile" data-tgo="present"><span>🗳️</span>Present a scenario<small>The class votes, then discusses</small></button>
      <button class="tile" data-tgo="lessons"><span>📋</span>Assign a lesson<small>Write it once, assign it to a class</small></button>
      <button class="tile" data-tgo="reports"><span>📊</span>See how they're doing<small>Dashboard and reports</small></button></div></div>`;
  sec.querySelectorAll('[data-tgo]').forEach(b => b.addEventListener('click', () => loaders.instructor(b.dataset.tgo)));
  await classSetup($('#setupBox'), ov, () => loaders.instructor('today'));
}

// Class: units with their join codes and teachers, the Cadets, and their fitness and service records.
async function instClass(sec, ov, run) {
  const units = ov.units, unitName = id => (units.find(u => u.id === id) || {}).name || '';
  const unitOpts = (sel, blank) => `<option value="">${blank}</option>` +
    units.map(u => `<option value="${esc(u.id)}" ${u.id === sel ? 'selected' : ''}>${esc(KIND_NAME[u.kind] || '')}: ${esc(u.name)}</option>`).join('');
  const instOpts = sel => `<option value="">Shared — any instructor</option>` + (ov.instructors || []).map(i =>
    `<option value="${esc(i.id)}" ${i.id === sel ? 'selected' : ''}>${esc(i.name)}${i.id === ov.me ? ' (me)' : ''}</option>`).join('');
  sec.innerHTML = `${STATUS.lan ? `<div class="card"><h3>📡 Class is open</h3>
      <p class="faint">Anyone on this Wi-Fi can reach Cadet Foundry's sign-in screen (they see shortened names, and every profile needs a PIN).
      For a pilot, use a <b>dedicated hotspot</b> only your class joins — not the school's open or guest Wi-Fi. End class
      (Join screen → End class, or Me → Quit) when you're done. Details: SECURITY.md → "The classroom network".</p></div>` : ''}
    <div class="card"><h3>Classes, platoons and squads</h3>
      <p class="faint">Each one has a <b>join code</b>. Cadets who type it when they sign up — or scan the QR code on the Join screen — are placed in it automatically.</p>
      ${units.length ? units.map(u => `<div class="card" style="margin:8px 0;padding:12px">
        <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:6px">
          <span>${esc(KIND_NAME[u.kind])}: <b>${esc(u.name)}</b>${u.parent ? ` <span class="faint">(in ${esc(unitName(u.parent))})</span>` : ''}</span>
          <span>Join code <b class="mono" style="letter-spacing:.15em;color:var(--tan2)">${esc(u.code || '')}</b></span></div>
        <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
          <label class="faint" style="margin:0">Taught by</label><select data-owner="${esc(u.id)}" aria-label="Instructor for ${esc(u.name)}" style="flex:1;min-width:160px">${instOpts(u.owner)}</select>
          <button class="btn small" data-newcode="${esc(u.id)}">New code</button>
          <button class="btn small" data-del="${esc(u.id)}" aria-label="Remove ${esc(u.name)}">Remove</button></div></div>`).join('')
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
          <select data-let="${esc(c.id)}" aria-label="Year for ${esc(c.name)}" style="flex:1;min-width:110px">
            <option value="">${esc(STATUS.level_label || 'Year')}…</option>${ov.let_levels.map(l => `<option value="${l}" ${c.let === l ? 'selected' : ''}>${esc(STATUS.level_label || 'Year')} ${l}</option>`).join('')}</select>
        </div>
        <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
          <input data-rank="${esc(c.id)}" value="${esc(c.rank || '')}" maxlength="40" placeholder="Cadet rank" aria-label="Cadet rank for ${esc(c.name)}" style="flex:1;min-width:130px">
          <input data-billet="${esc(c.id)}" value="${esc(c.billet || '')}" maxlength="40" placeholder="Billet (job in the cadet corps)" aria-label="Billet for ${esc(c.name)}" style="flex:2;min-width:170px">
        </div>
        <div class="faint" style="margin-top:6px">${c.status === 'waiting' ? '' : c.status === 'damaged' ? 'This Cadet’s class records couldn’t be read (a damaged file). The rest of the class is unaffected.' : `Quiz questions known: ${c.questions_known} · Exams: ${c.exams}${c.last_study ? ` · Last studied ${esc(c.last_study)}` : ''}`}</div>
        ${c.status === 'waiting' ? '' : `<button class="btn small" data-prog="${esc(c.id)}" style="margin-top:8px">📈 Progress and portfolio</button>`}
      </div>`).join('') : `<p><b>No Cadets yet.</b> ${STATUS.lan ? 'Open the Join screen and have Cadets scan the code.' : 'Cadets make their own profile with a PIN the first time they open Cadet Foundry.'}</p>`}
      <p class="faint">You see class records only. Cadets' private check-ins, chats and notes are never shown.</p></div>`;
  $('#uAdd').addEventListener('click', async () => {
    const r = await api('/api/instructor/unit', { action: 'add', name: $('#uName').value, kind: $('#uKind').value, parent: $('#uParent').value });
    if (r.error) $('#uMsg').textContent = r.error; else loaders.instructor();
  });
  sec.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Remove this unit? Its Cadets become unassigned and its join code stops working; nothing else is deleted.')) return;
    await api('/api/instructor/unit', { action: 'delete', id: b.dataset.del }); loaders.instructor();
  }));
  sec.querySelectorAll('[data-newcode]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Make a new join code? The old one stops working. Cadets already in this unit stay in it.')) return;
    await api('/api/instructor/unit', { action: 'code', id: b.dataset.newcode }); loaders.instructor();
  }));
  sec.querySelectorAll('[data-owner]').forEach(s => s.addEventListener('change', () => api('/api/instructor/unit', { action: 'owner', id: s.dataset.owner, owner: s.value })));
  sec.querySelectorAll('[data-unit]').forEach(s => s.addEventListener('change', () => api('/api/instructor/assign', { cadet: s.dataset.unit, unit: s.value })));
  sec.querySelectorAll('[data-prog]').forEach(b => b.addEventListener('click', () => instructorProgress(b.dataset.prog)));
  sec.querySelectorAll('[data-let]').forEach(s => s.addEventListener('change', () => s.value && api('/api/instructor/assign', { cadet: s.dataset.let, let: Number(s.value) })));
  // cadet rank and billet: saved when the instructor leaves the box; the Cadet sees them on Home
  sec.querySelectorAll('[data-rank]').forEach(i => i.addEventListener('change', () => api('/api/instructor/assign', { cadet: i.dataset.rank, rank: i.value })));
  sec.querySelectorAll('[data-billet]').forEach(i => i.addEventListener('change', () => api('/api/instructor/assign', { cadet: i.dataset.billet, billet: i.value })));
  const extra = document.createElement('div');
  sec.appendChild(extra);
  for (const step of [() => typeof instructorTrain === 'function' && instructorTrain(extra),        // train.js
    () => typeof instructorService === 'function' && instructorService(extra)]) {                   // service.js
    if (run !== instructorRun) return;
    await step();
  }
}

async function instLessons(sec, ov) {
  if (typeof instructorLessons === 'function') await instructorLessons(sec, ov);     // lessons.js
}

async function instPresent(sec, ov, run) {
  if (typeof instructorQuizzes === 'function') await instructorQuizzes(sec, ov);     // dashboard.js: live questions, pop quiz
  if (run !== instructorRun) return;
  if (typeof instructorLeadership === 'function') await instructorLeadership(sec);   // scenarios.js: present, class vote
}

async function instReports(sec, ov, run) {
  const top = document.createElement('div');
  sec.appendChild(top);
  if (typeof instructorDashboard === 'function') await instructorDashboard(top, ov);  // dashboard.js
  if (run !== instructorRun) return;
  if (typeof instructorPilot === 'function') await instructorPilot(sec);             // pilot.js
}

// What Cadet Foundry is and isn't -- plainly, for instructors (Settings) and everyone (Me). Cadet Foundry supports what a program
// already does; it never claims to be official or to replace a program's own systems.
function aboutHtml(open = false) {
  const li = xs => xs.map(x => `<li>${x}</li>`).join('');
  return `<div class="card"><details ${open ? 'open' : ''}><summary style="cursor:pointer;min-height:40px"><b>ℹ️ What Cadet Foundry is — and isn't</b></summary>
    <div class="row" style="flex-wrap:wrap;gap:16px;align-items:flex-start;margin-top:8px">
      <div style="flex:1;min-width:230px"><b>Cadet Foundry is</b><ul style="margin:6px 0 0 18px;padding:0">${li([
        'A supplemental learning and leadership tool for your classroom',
        'Instructor-controlled — you decide what Cadets get and when',
        'Offline-first: it runs on this computer, with no student accounts in the cloud',
        'A leadership and learning resource built from cited public sources',
        `A pilot product under active development (version ${esc(STATUS.version || '')})`])}</ul></div>
      <div style="flex:1;min-width:230px"><b>Cadet Foundry isn't</b><ul style="margin:6px 0 0 18px;padding:0">${li([
        'An official JROTC, military, school or government system — and no one has endorsed it',
        "A replacement for your program's official systems, curriculum or records",
        'A grading authority — its scores are for practice and feedback',
        'A student information system',
        "A substitute for the instructor's judgment",
        'A crisis service — the safety check shows help numbers but notifies no one'])}</ul></div></div>
    <p class="faint" style="margin:10px 0 0">Cadet Foundry complements what your program already does. A free community project — the Cadet Foundry project ·
      <a href="#" data-legal="terms">Terms of use</a> · <a href="#" data-legal="privacy">Privacy notice</a> · support@cadetfoundry.org</p></details></div>`;
}

function instSettings(sec) {
  // Learn sections for every Cadet on this device. Basic Training & Beyond still needs each Cadet's own opt-in.
  const CAT_NAMES = { leadership: 'Leadership', citizenship: 'Citizenship', military: 'Military Knowledge', health: 'Health & Fitness',
    careers: 'Careers', explore: 'Explore Military Service', basic: 'Basic Training & Beyond (only for Cadets who opt in)' };
  const on = STATUS.categories_enabled || Object.keys(CAT_NAMES);
  const MODS = { faith: 'Faith texts (scripture lookup and reading plans)', letters: 'Letters and address book', voice: 'Talk to Cadet Foundry (offline voice)' };
  const modsOff = STATUS.modules_off || [];
  const progs = STATUS.programs || {};
  sec.innerHTML = `${aboutHtml(true)}<div class="card"><h3>🎖️ Your JROTC program</h3>
      <p class="faint">Sets the words Cadet Foundry uses (for example, the year a Cadet is in: LET 1 in Army JROTC, NS 1 in Navy JROTC, LE 1 in Marine Corps JROTC, Year 1 in Air Force JROTC) and puts your branch first in Learn. Cadets can still explore every branch.</p>
      <select id="progPick" aria-label="JROTC program" style="width:100%;min-height:46px"><option value="">Not set / more than one program</option>
        ${Object.entries(progs).map(([k, v]) => `<option value="${k}" ${STATUS.program === k ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>
      ${STATUS.program === 'coast_guard' ? '<p class="faint">Cadet Foundry has no Coast Guard study cards yet. Cadets still see every other branch, and the shared lessons, scenarios and subjects.</p>' : ''}
      <p class="faint" id="progMsg" role="status"></p></div>
    <div class="card"><h3>📘 What Cadets can study</h3><p class="faint">Turn sections of Learn on or off for every Cadet on this device.</p>
      ${Object.entries(CAT_NAMES).map(([k, v]) => `<label style="display:flex;gap:10px;align-items:center;min-height:44px">
        <input type="checkbox" data-cat="${k}" ${on.includes(k) ? 'checked' : ''} style="width:22px;height:22px"> ${esc(v)}</label>`).join('')}
      <p class="faint" id="catMsg" role="status"></p></div>
    <div class="card"><h3>🧰 Optional tools</h3><p class="faint">Turn optional tools on or off for every profile on this device.</p>
      ${Object.entries(MODS).map(([k, v]) => `<label style="display:flex;gap:10px;align-items:center;min-height:44px">
        <input type="checkbox" data-mod="${k}" ${modsOff.includes(k) ? '' : 'checked'} style="width:22px;height:22px"> ${esc(v)}</label>`).join('')}
      <p class="faint" id="modMsg" role="status"></p></div>
    <p class="faint">The Class PIN and the AI setting are in 👤 Me.</p>`;
  sec.querySelectorAll('[data-cat]').forEach(cb => cb.addEventListener('change', async () => {
    const cats = [...sec.querySelectorAll('[data-cat]:checked')].map(x => x.dataset.cat);
    const r = await api('/api/instructor/categories', { categories: cats });
    $('#catMsg').textContent = r.error || 'Saved.';
    if (!r.error) STATUS.categories_enabled = r.categories_enabled;
  }));
  sec.querySelectorAll('[data-mod]').forEach(cb => cb.addEventListener('change', async () => {
    const off = [...sec.querySelectorAll('[data-mod]')].filter(x => !x.checked).map(x => x.dataset.mod);
    const r = await api('/api/instructor/modules', { off });
    $('#modMsg').textContent = r.error || 'Saved. Profiles see the change the next time they open Cadet Foundry.';
    if (!r.error) STATUS.modules_off = r.modules_off;
  }));
  $('#progPick').addEventListener('change', async e => {
    const r = await api('/api/instructor/program', { program: e.target.value });
    $('#progMsg').textContent = r.error || 'Saved.';
    if (!r.error) { STATUS.program = r.program; STATUS.level_label = r.level_label; }
  });
  if (typeof instructorBackup === 'function') instructorBackup(sec);                 // dashboard.js
}
