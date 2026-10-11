'use strict';
// Log tab: logbook, board packet, letters, PCS, AFT, sleep, check-in, leave, LES, money.

// ── LOG ──
loaders.logbook = async () => {
  const lb = document.querySelector('[data-pane="letters"]');      // the instructor can switch letters off
  if (lb) lb.hidden = (STATUS.modules_off || []).includes('letters');
  if (!$('#logKind').options.length) {
    $('#logKind').innerHTML = (STATUS.log_kinds || ['Note']).map(k => `<option>${esc(k)}</option>`).join('');
    $('#logDate').value = new Date().toISOString().slice(0, 10);
  }
  const rows = await api('/api/log');
  $('#logList').innerHTML = rows.length ? rows.map(r => `<div class="card"><div class="row" style="justify-content:space-between">
      <div><span class="chip">${esc(r.kind)}</span><span class="faint">${esc(r.date)}</span>${r.score ? ` <b>${esc(r.score)}</b>` : ''}</div>
      <button class="btn small danger" data-del="${esc(r.id)}">Delete</button></div><div style="margin-top:6px;white-space:pre-wrap">${esc(r.text)}</div></div>`).join('')
    : '<div class="empty">Nothing logged yet. Track PT scores, ranges, training and goals here.</div>';
};
$('#logForm').addEventListener('submit', async e => {
  e.preventDefault();
  if (!$('#logText').value.trim()) return;
  await api('/api/log', { kind: $('#logKind').value, date: $('#logDate').value, score: $('#logScore').value, text: $('#logText').value });
  $('#logText').value = ''; $('#logScore').value = ''; loaders.logbook();
});
$('#logList').addEventListener('click', async e => {
  const d = e.target.closest('[data-del]'); if (!d || !confirm('Delete this entry?')) return;
  await api('/api/log/delete', { id: d.dataset.del }); loaders.logbook();
});

// Board packet: the Soldier's own record on one printout (profile, AFT history, exam scores, logbook), black on white.
async function boardPacket() {
  const d = await api('/api/packet'), p = d.profile || {};
  const ev = ['MDL', 'HRP', 'SDC', 'PLK', '2MR'];
  const pct = b => Math.round(100 * b.pct);
  const html = `<div class="packet"><h2>${esc(p.name || 'Cadet')}</h2>
    <div>${[p.grade && esc(p.grade)].filter(Boolean).join(' · ')}</div>
    ${p.goals ? `<div><b>Goals:</b> ${esc(p.goals)}</div>` : ''}
    <h3>Army Fitness Test results</h3>${d.aft.length ? `<table><tr><th>Date</th>${ev.map(e => `<th>${e}</th>`).join('')}<th>Total</th></tr>
      ${d.aft.slice().reverse().map(t => `<tr><td>${esc(t.date)}</td>${ev.map(e => `<td>${t.events[e] ? `${esc(t.events[e].raw)} (${t.events[e].points})` : '—'}</td>`).join('')}<td><b>${t.total}</b></td></tr>`).join('')}</table>`
      : '<p>No scored tests saved yet.</p>'}
    <h3>Study exams (best score by topic)</h3>${Object.keys(d.exams.best).length ? `<table><tr><th>Topic</th><th>Best</th><th>Date</th></tr>
      ${Object.entries(d.exams.best).map(([t, b]) => `<tr><td>${esc(t)}</td><td>${b.right}/${b.total} (${pct(b)}%)</td><td>${esc(b.date)}</td></tr>`).join('')}</table>`
      : '<p>No exams taken yet.</p>'}
    <h3>Logbook</h3>${d.log.length ? `<table><tr><th style="width:16%">Date</th><th style="width:14%">Kind</th><th>Entry</th></tr>
      ${d.log.map(r => `<tr><td>${esc(r.date)}</td><td>${esc(r.kind)}</td><td>${r.score ? `<b>${esc(r.score)}</b> — ` : ''}${esc(r.text)}</td></tr>`).join('')}</table>`
      : '<p>Nothing logged yet.</p>'}
    <p style="margin-top:12px;font-size:8pt">Printed ${esc(d.made)} from Cadet Foundry, a personal study aid and logbook. Entries are the Soldier's own records, not official Army records.</p></div>`;
  $('#logList').innerHTML = `<div class="card"><div class="row"><button class="btn small" id="packetBack">← Logbook</button><button class="btn primary" id="packetPrint">Print</button></div>
    <p class="faint">Your record on paper — for a board, a counseling session or your own files. Prints black on white.</p></div>
    <div id="packetPreview" style="background:#fff;color:#000;padding:12px;border-radius:8px">${html}</div>`;
  $('#packetBack').onclick = loaders.logbook;
  $('#packetPrint').onclick = () => {
    let area = $('#printArea');
    if (!area) { area = document.createElement('div'); area.id = 'printArea'; document.body.appendChild(area); }
    area.innerHTML = html;
    window.print();
  };
}
$('#packetBtn').onclick = boardPacket;

// ── LETTERS HOME ──
const PANES = [
  ['log', '📝 Logbook', 'Logbook', () => loaders.logbook()],
  ['letters', '✉️ Letters', 'Letters', () => loadLetters()],
  ['checkin', '🙂 Check-in', 'Daily check-in', () => loadCheckin()],
  ['leave', '🏖️ Leave', 'Leave tracker', () => loadLeave()],
  ['money', '💵 Money', 'Budget', () => loadMoney()],
  ['fit', '💪 AFT', 'Army Fitness Test', () => loadAft()],
  ['pcs', '📦 PCS', 'PCS / first duty station', () => loadPcs()],
];
// leave, the AFT scorer and PCS belong to Explore Military Service (Serve opens them); they're hidden from the bar
const EXPLORE_PANES = new Set(['leave', 'fit', 'pcs']);
$('#paneBar').innerHTML = PANES.map(([k, label]) => `<button class="btn small" data-pane="${k}"${EXPLORE_PANES.has(k) ? ' hidden' : ''}>${label}</button>`).join('');
function showPane(which, load = true) {
  for (const [k, , title, fn] of PANES) {
    $('#' + k + 'Pane').hidden = k !== which;
    const b = document.querySelector(`[data-pane="${k}"]`);
    b.classList.toggle('primary', k === which); b.setAttribute('aria-pressed', String(k === which));
    if (k === which) { $('#logTitle').textContent = title; load && fn && fn(); }
  }
}
$('#paneBar').addEventListener('click', e => { const b = e.target.closest('[data-pane]'); if (b) showPane(b.dataset.pane); });
showPane('log', false);               // the Log tab loads the list itself when opened

// ── PCS / FIRST DUTY STATION CHECKLIST ── (Military OneSource guidance + the Soldier's own items)
async function loadPcs(st) {
  st = st || await api('/api/pcs');
  const done = new Set(st.done), item = (id, text, custom) => `<label class="row" style="align-items:flex-start;flex-wrap:nowrap;gap:10px;margin:6px 0;cursor:pointer">
    <input type="checkbox" data-pcs="${esc(id)}" ${done.has(id) ? 'checked' : ''} style="width:auto;flex:none;margin-top:5px"><span style="flex:1">${esc(text)}</span>
    ${custom ? `<button class="btn small" data-pcsrm="${esc(id)}" title="Remove">✕</button>` : ''}</label>`;
  const all = st.groups.flatMap(g => g[1]).length + st.custom.length, n = st.done.length;
  $('#pcsPane').innerHTML = `<div class="card"><div class="row" style="justify-content:space-between">
      <div><label>Report date (from your orders)</label><input id="pcsDate" type="date" value="${esc(st.report_date)}"></div>
      <div style="text-align:right">${st.days !== null ? `<div style="font-size:30px;font-weight:700">${Math.abs(st.days)}</div><div class="faint">${st.days >= 0 ? 'days to report' : 'days since reporting'}</div>` : ''}</div></div>
      <div class="bar" style="margin-top:10px"><i style="width:${all ? Math.round(100 * n / all) : 0}%"></i></div><div class="faint">${n} of ${all} done</div>
      <p class="faint">OPSEC: keep report dates and unit details off social media. This list stays on this device.</p></div>
    ${st.groups.map(([title, items]) => `<div class="card"><h3>${esc(title)}</h3>${items.map(([id, text]) => item(id, text)).join('')}</div>`).join('')}
    <div class="card"><h3>My items</h3>${st.custom.map(c => item(c.id, c.text, true)).join('') || '<p class="faint">Add anything your sponsor or unit tells you.</p>'}
      <div class="row"><input id="pcsNew" placeholder="e.g. Call my sponsor" style="flex:1"><button class="btn small" id="pcsAdd">Add</button></div></div>
    <p class="faint">Source: ${esc(st.source)}. Your orders, sponsor and transportation office have the final word.</p>`;
  $('#pcsPane').querySelectorAll('[data-pcs]').forEach(c => c.onchange = async () => loadPcs(await api('/api/pcs', { toggle: c.dataset.pcs })));
  $('#pcsPane').querySelectorAll('[data-pcsrm]').forEach(b => b.onclick = async e => { e.preventDefault(); loadPcs(await api('/api/pcs', { remove: b.dataset.pcsrm })); });
  $('#pcsDate').onchange = async () => loadPcs(await api('/api/pcs', { report_date: $('#pcsDate').value }));
  $('#pcsAdd').onclick = async () => { if ($('#pcsNew').value.trim()) loadPcs(await api('/api/pcs', { add: $('#pcsNew').value })); };
}

// My fitness plan: built from the Soldier's own AFT results saved in the logbook (FM 7-22 SMART goals, table 6-2 drills).
async function showAftPlan() {
  const p = await api('/api/aft/plan'), el = $('#aftPlan');
  if (!el) return;
  if (!p.tests.length) { el.innerHTML = `<div class="card"><h3>📈 My plan</h3><p class="faint">${esc(p.message)}</p></div>`; return; }
  const arrow = c => c === null ? '' : c > 0 ? ` <span style="color:var(--green)">▲${c}</span>` : c < 0 ? ` <span style="color:var(--red)">▼${-c}</span>` : ' <span class="faint">=</span>';
  el.innerHTML = `<div class="card"><h3>📈 My plan</h3>
    <div class="faint">From your latest test (${esc(p.latest)})${p.tests.length > 1 ? ', compared with the one before' : ''} — ${p.tests.length} test${p.tests.length === 1 ? '' : 's'} logged</div>
    ${p.rows.map(r => `<div style="margin:6px 0"><div class="row" style="justify-content:space-between"><span>${esc(r.name)} · ${esc(r.raw)}</span>
      <span><b style="color:${r.below_min ? 'var(--red)' : 'inherit'}">${r.points}</b>${arrow(r.change)}</span></div>
      <div class="bar"><i style="width:${r.points}%;${r.event === p.weakest ? 'background:var(--tan)' : ''}"></i></div></div>`).join('')}
    <h3 style="margin-top:12px">Your goal</h3>
    <p><b>${esc(p.goal.short)}</b></p><p>${esc(p.goal.steps)}</p>
    <details><summary>H2F drills by what they train</summary><ul style="font-size:14px">${Object.entries(p.drills).map(([k, v]) =>
      `<li><b>${esc(k)}:</b> ${v.map(esc).join(', ')}</li>`).join('')}</ul></details>
    <div class="row" style="margin-top:8px"><button class="btn small" id="planAsk">Ask Cadet Foundry how to train my ${esc(p.goal.name)}</button></div>
    <p class="faint">${esc(p.source)} Train with your unit's program and your cadre — this is a study aid.</p></div>`;
  $('#planAsk').onclick = () => { openView('ask'); send(`How do I improve my ${p.goal.name} for the Army Fitness Test? Use FM 7-22.`); };
}

// ── ARMY FITNESS TEST SCORER ── (official score tables; scoring happens on the device, in vanguard/fitness.py)
async function loadAft() {
  const info = await api('/api/aft'), pane = $('#fitPane');
  pane.innerHTML = `<form class="card" id="aftForm">
      <div class="row"><div style="flex:1"><label>Age</label><input id="aftAge" type="number" min="17" max="99" inputmode="numeric" required></div>
        <div style="flex:1"><label>Sex</label><select id="aftSex"><option value="M">Male</option><option value="F">Female</option></select></div></div>
      <label>Standard</label><select id="aftStd"><option value="general">General — combat-enabling jobs (300 total)</option><option value="combat">Combat — combat specialties (350 total, sex-neutral)</option></select>
      ${info.events.map(e => `<label>${esc(e.help)}</label><input data-ev="${e.id}" placeholder="${e.id === 'MDL' || e.id === 'HRP' ? '0' : '0:00'}" inputmode="${e.id === 'MDL' || e.id === 'HRP' ? 'numeric' : 'text'}">`).join('')}
      <div class="row" style="margin-top:10px"><button class="btn primary">Score it</button><span class="faint">Leave an event blank to score the others.</span></div>
      <p class="faint">${esc(info.note)}<br>Source: ${esc(info.source)}.</p></form><div id="aftOut"></div><div id="aftPlan"></div>`;
  const me = STATUS.profile || {};                  // from the first-run interview
  if (me.age) $('#aftAge').value = me.age;
  if (me.sex) $('#aftSex').value = me.sex;
  showAftPlan();
  $('#aftForm').onsubmit = async ev => {
    ev.preventDefault();
    const raw = {}; pane.querySelectorAll('[data-ev]').forEach(i => raw[i.dataset.ev] = i.value.trim());
    const r = await api('/api/aft/score', { raw, age: $('#aftAge').value, sex: $('#aftSex').value, standard: $('#aftStd').value });
    if (r.error) { $('#aftOut').innerHTML = `<div class="card"><b style="color:var(--red)">${esc(r.error)}</b></div>`; return; }
    const verdict = !r.complete ? `<b>${r.total}</b> points from ${r.events.length} of 5 events`
      : r.passed ? `<b style="color:var(--green)">${r.total} — meets the ${r.standard} standard</b>`
      : `<b style="color:var(--red)">${r.total} — doesn't meet the ${r.standard} standard yet</b>`;
    const names = Object.fromEntries(info.events.map(e => [e.id, e.help]));
    $('#aftOut').innerHTML = `<div class="card"><h3>${verdict}</h3>
      <div class="faint">Age group ${esc(r.age_group)} · need ${r.min_event}+ in every event and ${r.min_total}+ total</div>
      ${r.errors.length ? `<p style="color:var(--red)">${r.errors.map(esc).join('<br>')}</p>` : ''}
      ${r.events.map(e => `<div style="margin:8px 0"><div class="row" style="justify-content:space-between"><span>${esc(e.event)} · ${esc(e.raw)}</span>
        <b style="color:${e.points < r.min_event ? 'var(--red)' : 'inherit'}">${e.points}</b></div>
        <div class="bar"><i style="width:${e.points}%"></i></div></div>`).join('')}
      ${r.weakest ? `<p>Biggest gain available: <b>${esc(names[r.weakest])}</b>.</p>` : ''}
      <div class="row">${r.weakest ? '<button class="btn" id="aftAsk">Ask Cadet Foundry how to improve it</button>' : ''}<button class="btn primary" id="aftSave">Save to logbook</button></div>
      <p class="faint">${esc(r.source)}. Your unit's graders and the official tables decide your record score.</p></div>`;
    if ($('#aftAsk')) $('#aftAsk').onclick = () => { openView('ask'); send(`How do I improve my ${names[r.weakest]}? Use FM 7-22.`); };
    $('#aftSave').onclick = async () => {
      await api('/api/log', { kind: 'PT', date: new Date().toISOString().slice(0, 10), score: String(r.total),
        text: `AFT (${r.standard} standard, ${r.age_group}): ` + r.events.map(e => `${e.event} ${e.raw} = ${e.points}`).join(', ') + (r.complete ? (r.passed ? ' — met standard' : ' — below standard') : ' — partial') });
      $('#aftSave').textContent = 'Saved ✓'; $('#aftSave').disabled = true; showAftPlan();
    };
  };
}

// ── SLEEP (FM 7-22, ch. 11) + MY PEOPLE ──
const spRow = (r, roles) => `<div class="sp" style="border-top:1px solid var(--line);padding:8px 0">
  <div class="row"><select data-f="role" style="flex:1">${roles.map(x => `<option ${x === r.role ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select>
    <button type="button" class="btn small" data-sprm title="Remove">✕</button></div>
  <div class="row" style="margin-top:6px"><input data-f="name" placeholder="Name" value="${esc(r.name || '')}" style="flex:1"><input data-f="phone" placeholder="Phone" inputmode="tel" value="${esc(r.phone || '')}" style="flex:1"></div>
  <input data-f="note" placeholder="Note (e.g. office hours, building)" value="${esc(r.note || '')}" style="margin-top:6px"></div>`;
const peopleList = people => people && people.length ? `<div style="margin-top:8px"><b>Your people:</b><ul>${people.map(p =>
  `<li>${esc(p.role)}: <b>${esc(p.name)}</b>${p.phone ? ' — ' + esc(p.phone) : ''}${p.note ? ` <span class="faint">(${esc(p.note)})</span>` : ''}</li>`).join('')}</ul></div>` : '';
function sleepCard(sl) {
  const max = 10, H = 80, bars = sl.series.map(d => `<div title="${esc(d.date)}: ${d.sleep} h" style="flex:1;display:flex;flex-direction:column;justify-content:flex-end">
    <div style="height:${Math.round(Math.min(d.sleep, max) / max * H)}px;background:${d.sleep < sl.target ? 'var(--tan)' : 'var(--olive)'};border-radius:4px"></div></div>`).join('');
  return `<div class="card"><h3>😴 Sleep</h3>
    ${sl.nights ? `<p><b>${sl.avg7} h</b> a night on average this week · ${sl.short7} of ${sl.nights} night${sl.nights === 1 ? '' : 's'} under ${sl.target} h${sl.debt7 ? ` · about <b>${sl.debt7} h</b> of sleep debt` : ''}</p>
      <div style="position:relative;height:${H}px;display:flex;gap:4px;align-items:stretch">${bars}
        <div style="position:absolute;left:0;right:0;bottom:${Math.round(sl.target / max * H)}px;border-top:1px dashed var(--muted)" title="${sl.target} hours"></div></div>
      <p class="faint">Last ${sl.series.length} check-ins; dashed line = ${sl.target} hours. Log sleep in the check-in above.</p>`
      : '<p class="faint">Add hours of sleep in your check-in to see your week here.</p>'}
    <ul style="font-size:14px">
      <li>Most Soldiers need <b>7 to 9 hours of sleep every 24 hours</b> to maximize health and sustain performance. <span class="faint">(FM 7-22, 11-3)</span></li>
      <li>Regularly getting less than 7–8 hours builds a <b>sleep debt</b>: you may feel fine, but alertness and judgment are impaired. <span class="faint">(11-11)</span></li>
      <li>Rule of thumb: if you sleep <b>2 or more hours longer on days off</b>, you're carrying sleep debt. <span class="faint">(11-11)</span></li>
      <li>An afternoon nap can help pay down sleep debt — as long as naps don't keep you from falling asleep at night. <span class="faint">(11-7)</span></li>
      <li>Sleep as much as you can, whenever you can, as the situation allows. <span class="faint">(FM 7-22, ch. 11)</span></li>
    </ul></div>`;
}

// ── DAILY CHECK-IN + BREATHING ──
async function loadCheckin() {
  const { rows, concern, sleep, support, roles } = await api('/api/checkin');
  const today = new Date().toISOString().slice(0, 10), t = rows.find(r => r.date === today) || {};
  const scale = (name, val, lo, hi) => `<div class="row" style="gap:6px">${[1, 2, 3, 4, 5].map(n =>
    `<label class="chip" style="cursor:pointer;margin:0"><input type="radio" name="${name}" value="${n}" ${val == n ? 'checked' : ''} style="width:auto"> ${n}</label>`).join('')}
    <span class="faint">${lo} → ${hi}</span></div>`;
  $('#checkinPane').innerHTML = `
    <form class="card" id="ciForm"><h3>How are you today?</h3><p class="faint">Private — only on this device. It takes ten seconds.</p>
      <label>Mood</label>${scale('mood', t.mood, '1 rough', '5 great')}
      <label>Stress</label>${scale('stress', t.stress, '1 calm', '5 maxed out')}
      <label for="ciSleep">Hours of sleep last night</label><input id="ciSleep" type="number" min="0" max="24" step="0.5" value="${t.sleep ?? ''}" style="max-width:140px">
      <label for="ciNote">Anything on your mind? (optional)</label><textarea id="ciNote" rows="2">${esc(t.note || '')}</textarea>
      <div class="row" style="margin-top:8px"><button class="btn primary">Save check-in</button></div></form>
    ${concern ? `<div class="card" style="border-color:var(--tan)"><p>${esc(concern)}</p>${peopleList(support)}</div>` : ''}
    ${sleepCard(sleep)}
    <div class="card"><h3>🤝 My people</h3>
      <p class="faint">The people you'd call on a hard day. Cadet Foundry shows them next to the crisis lines — on this device only.</p>
      <div id="spRows">${(support.length ? support : [{ role: 'Battle buddy' }]).map(r => spRow(r, roles)).join('')}</div>
      <div class="row"><button class="btn small" id="spAdd">+ Add someone</button><button class="btn primary small" id="spSave">Save</button><span class="faint" id="spMsg"></span></div></div>
    <div class="card"><h3>Tactical breathing</h3>
      <p class="faint">Box breathing: in 4 · hold 4 · out 4 · hold 4. Used to stay calm under stress — before a test, the range, or sleep.</p>
      <div style="display:grid;place-items:center;padding:12px"><div id="breathBox" style="width:150px;height:150px;border:3px solid var(--tan);border-radius:16px;display:grid;place-items:center;font-size:20px;transition:transform 4s linear">Ready</div></div>
      <div class="row" style="justify-content:center"><button class="btn primary" id="breathGo">Start (2 minutes)</button></div></div>
    <div class="card"><h3>Last 14 days</h3>${rows.length ? `<div class="row" style="gap:4px;align-items:flex-end;height:90px">${rows.slice(0, 14).reverse().map(r =>
      `<div title="${esc(r.date)}: mood ${r.mood}, stress ${r.stress}, sleep ${r.sleep}h" style="flex:1;display:grid;gap:2px;align-content:end">
        <div style="height:${r.mood * 14}px;background:var(--olive);border-radius:4px"></div></div>`).join('')}</div>
      <p class="faint">Bars show mood (taller = better).</p>` : '<p class="faint">No check-ins yet.</p>'}</div>`;
  $('#ciForm').onsubmit = async ev => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    const r = await api('/api/checkin', { mood: +(f.get('mood') || 3), stress: +(f.get('stress') || 3), sleep: +($('#ciSleep').value || 0), note: $('#ciNote').value });
    if (r.error) alert(r.error); else loadCheckin();
  };
  $('#spAdd').onclick = () => $('#spRows').insertAdjacentHTML('beforeend', spRow({ role: 'Other' }, roles));
  $('#spRows').addEventListener('click', e => { const x = e.target.closest('[data-sprm]'); if (x) x.closest('.sp').remove(); });
  $('#spSave').onclick = async () => {
    const contacts = [...document.querySelectorAll('#spRows .sp')].map(d => ({ role: d.querySelector('[data-f=role]').value,
      name: d.querySelector('[data-f=name]').value, phone: d.querySelector('[data-f=phone]').value, note: d.querySelector('[data-f=note]').value }));
    const saved = await api('/api/support', { contacts });
    $('#spMsg').textContent = `Saved ${saved.length} ✓`;
  };
  let timer = null;
  $('#breathGo').onclick = () => {
    if (timer) { clearInterval(timer); timer = null; $('#breathBox').textContent = 'Ready'; $('#breathBox').style.transform = ''; $('#breathGo').textContent = 'Start (2 minutes)'; return; }
    const steps = [['Breathe in', 'scale(1.25)'], ['Hold', 'scale(1.25)'], ['Breathe out', 'scale(1)'], ['Hold', 'scale(1)']];
    let i = 0, end = Date.now() + 120000;
    const tick = () => {
      if (Date.now() > end) { clearInterval(timer); timer = null; $('#breathBox').textContent = 'Done'; $('#breathGo').textContent = 'Again'; return; }
      const [label, tf] = steps[i++ % 4]; $('#breathBox').textContent = label; $('#breathBox').style.transform = tf;
    };
    tick(); timer = setInterval(tick, 4000); $('#breathGo').textContent = 'Stop';
  };
}

// ── LEAVE ──
async function loadLeave() {
  const lv = await api('/api/leave');
  $('#leavePane').innerHTML = `
    <div class="card"><div class="row" style="justify-content:space-between"><div><div class="faint">Estimated balance</div>
      <div style="font-size:34px;font-weight:700;color:var(--tan2)">${lv.balance} days</div></div>
      <div class="faint" style="text-align:right">Earned ${lv.earned} (${lv.months} months × 2.5)<br>Used ${lv.used_total}</div></div>
      <p class="faint">Active-duty members earn 2.5 days of leave per month of service (10 U.S.C. § 701). This is an estimate — your LES shows your official balance.</p></div>
    <form class="card" id="lvSetup"><h3>Setup</h3><div class="row">
      <div style="flex:1"><label>Date you entered active duty</label><input type="date" id="lvStart" value="${esc(lv.start)}"></div>
      <div style="flex:1"><label>Starting balance (optional)</label><input type="number" step="0.5" id="lvBal" value="${lv.starting_balance || 0}"></div></div>
      <button class="btn small" style="margin-top:8px">Save</button></form>
    <form class="card" id="lvAdd"><h3>Add leave taken</h3><div class="row">
      <input type="date" id="lvFrom" style="flex:1"><input type="date" id="lvTo" style="flex:1"><input type="number" step="0.5" id="lvDays" placeholder="Days" style="flex:1"></div>
      <select id="lvKind" style="margin-top:8px"><option>Ordinary leave</option><option>Emergency leave</option><option>Convalescent leave</option><option>Pass (not charged)</option></select>
      <button class="btn small" style="margin-top:8px">Add</button></form>
    <div class="card"><h3>History</h3>${lv.used.length ? lv.used.map(u => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding:6px 0">
      <span>${esc(u.from)} → ${esc(u.to)} · <b>${u.days}</b> days <span class="faint">${esc(u.kind)}</span></span><button class="btn small danger" data-dlv="${esc(u.id)}">Delete</button></div>`).join('') : '<p class="faint">Nothing yet.</p>'}</div>`;
  $('#lvSetup').onsubmit = async ev => { ev.preventDefault(); await api('/api/leave', { start: $('#lvStart').value, starting_balance: +$('#lvBal').value || 0 }); loadLeave(); };
  $('#lvAdd').onsubmit = async ev => {
    ev.preventDefault();
    let days = +$('#lvDays').value;
    if (!days && $('#lvFrom').value && $('#lvTo').value) days = Math.round((new Date($('#lvTo').value) - new Date($('#lvFrom').value)) / 864e5) + 1;
    if ($('#lvKind').value.startsWith('Pass')) days = 0;
    await api('/api/leave', { add: { from: $('#lvFrom').value, to: $('#lvTo').value, days, kind: $('#lvKind').value } }); loadLeave();
  };
  $('#leavePane').querySelectorAll('[data-dlv]').forEach(b => b.onclick = async () => { await api('/api/leave', { delete: b.dataset.dlv }); loadLeave(); });
}

// ── LES decoder: DFAS's explanation of each numbered block ──
async function lesDecoder() {
  const d = await api('/api/les');
  if (!d.fields || !d.fields.length) { $('#lesCard').style.display = 'none'; return; }
  const kind = () => $('#lesKind').value;
  const text = f => (kind() === 'reserve' && f.reserve) || f.active;
  let open = null;                                   // the block being shown
  const show = f => {
    open = f;
    $('#lesInfo').innerHTML = `<div class="card" style="margin:0"><div class="faint">Block ${f.n} · ${esc(f.section)}</div><h3 style="margin:4px 0">${esc(f.label)}</h3>
      <p>${esc(text(f))}</p>${f.note ? `<p class="faint">Cadet Foundry's note: ${esc(f.note)}</p>` : ''}</div>`;
    $('#lesGrid').querySelectorAll('[data-les]').forEach(b => b.classList.toggle('primary', +b.dataset.les === f.n));
  };
  const grid = list => {
    $('#lesGrid').innerHTML = d.sections.map(sec => {
      const fs = list.filter(f => f.n >= sec.from && f.n <= sec.to);
      return fs.length ? `<div style="margin:8px 0"><div class="faint">${esc(sec.name)}</div><div class="row" style="gap:4px">${fs.map(f =>
        `<button class="btn small" data-les="${f.n}" title="${esc(f.label)}">${f.n} <span class="faint">${esc(f.label)}</span></button>`).join('')}</div></div>` : '';
    }).join('') || '<p class="faint">No block matches that.</p>';
    $('#lesGrid').querySelectorAll('[data-les]').forEach(b => {
      b.onclick = () => show(d.fields[+b.dataset.les - 1]);
      if (open && +b.dataset.les === open.n) b.classList.add('primary');
    });
  };
  const filter = () => {
    const q = $('#lesFind').value.trim().toLowerCase();
    if (!q) return grid(d.fields);
    if (/^\d{1,2}$/.test(q) && +q >= 1 && +q <= 78) { grid(d.fields); return show(d.fields[+q - 1]); }
    const word = new RegExp('(^|[^a-z0-9])' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));   // "fica" must not match "identification"
    const named = d.fields.filter(f => word.test((f.label + ' ' + f.section).toLowerCase()));   // what's printed on the LES comes first
    const hits = named.length ? named : d.fields.filter(f => text(f).toLowerCase().includes(q));
    grid(hits);
    if (hits.length === 1) show(hits[0]);
  };
  $('#lesFind').oninput = filter;
  $('#lesKind').onchange = () => { filter(); if (open) show(open); };
  grid(d.fields);
}

// ── MONEY (budget) ──
async function loadMoney(local) {
  const bd = local || await api('/api/budget');
  const rowsHtml = (rows, kind) => rows.map((r, i) => `<div class="row" style="flex-wrap:nowrap;margin:4px 0">
      <input value="${esc(r.name)}" data-k="${kind}" data-i="${i}" data-f="name" style="flex:2"><input type="number" step="0.01" value="${r.amount}" data-k="${kind}" data-i="${i}" data-f="amount" style="flex:1">
      <button class="btn small danger" data-rm="${kind}" data-i="${i}" title="Remove this line">✕</button></div>`).join('');
  const total = rows => rows.reduce((s, r) => s + (+r.amount || 0), 0);
  const inc = total(bd.income), exp = total(bd.expenses), left = inc - exp;
  const pt = await api('/api/pay');
  $('#moneyPane').innerHTML = `
    <div class="card"><div class="row" style="justify-content:space-between">
      <div><div class="faint">Left over each month</div><div style="font-size:30px;font-weight:700;color:${left >= 0 ? 'var(--green)' : 'var(--red)'}">$${left.toFixed(2)}</div></div>
      <div class="faint" style="text-align:right">In $${inc.toFixed(2)}<br>Out $${exp.toFixed(2)}</div></div>
      <p class="faint">Use your real numbers — paychecks, allowance and bills. Plain math on your own numbers — not financial advice. See the Money Basics study cards for how to budget.</p></div>
    <div class="card"><h3>Money in (monthly)</h3>${rowsHtml(bd.income, 'income') || '<p class="faint">e.g. Part-time job, allowance, babysitting</p>'}<button class="btn small" data-add="income">+ Add</button></div>
    <div class="card"><h3>Money out (monthly)</h3>${rowsHtml(bd.expenses, 'expenses') || '<p class="faint">e.g. Phone, gas, car insurance, savings</p>'}<button class="btn small" data-add="expenses">+ Add</button></div>
    <div class="card"><label>Savings goal</label><input id="bdGoal" value="${esc(bd.goal)}" placeholder="e.g. $500 emergency fund by graduation"></div>
    <button class="btn primary" id="bdSave">Save budget</button>
    <details class="card" style="margin-top:14px"><summary><b>🎖️ Military pay tools</b> <span class="faint">— pay estimate, reading a pay statement (LES), retirement savings (TSP). For Cadets exploring military service.</span></summary>
    <div class="card"><h3>💵 Pay estimate</h3>
      ${pt.grades.length ? `<div class="row">
        <div style="flex:1"><label>Grade</label><select id="payGrade">${pt.grades.map(g => `<option>${esc(g)}</option>`).join('')}</select></div>
        <div style="flex:1"><label>Years served</label><input id="payYears" type="number" min="0" max="45" step="1" value="0"></div>
        <div style="flex:1"><label>+ months</label><input id="payMonths" type="number" min="0" max="11" step="1" value="0"></div></div>
        <label>BAH ($/month, from your LES or the DoD BAH calculator — leave 0 if you live in the barracks)</label><input id="payBah" type="number" min="0" step="1" value="0">
        <div class="row" style="margin-top:8px"><button class="btn primary" id="payGo">Estimate</button></div><div id="payOut"></div>
        <p class="faint">Basic pay table effective ${pt.effective.map(esc).join(' / ')}; BAS effective ${esc(pt.bas_effective)} (DFAS). Pay tables change every January — if these dates are old, your pay is likely higher; your LES is the real number. Before taxes and deductions.</p>`
        : '<p class="faint">No pay tables installed (see tools/pay_tables.py).</p>'}</div>
    <div class="card" id="lesCard"><h3>📄 Read your LES</h3>
      <p class="faint">Your Leave and Earnings Statement has 78 numbered blocks. Tap a number or search for what's printed on yours (for example <i>ETS BAL</i> or <i>EOM PAY</i>).</p>
      <div class="row"><select id="lesKind" style="flex:1"><option value="active">Active duty</option><option value="reserve">Reserve / National Guard</option></select>
        <input id="lesFind" placeholder="Block name or number" style="flex:2"></div>
      <div id="lesInfo" style="margin:10px 0"></div><div id="lesGrid"></div>
      <p class="faint">Explanations are DFAS's own wording (<i>How to read an active duty Army LES</i> and <i>How to read a Reserve and National Guard LES</i>, dfas.mil). Cadet Foundry's notes are marked. Questions about your pay go to your finance office.</p></div>
    <div class="card" style="margin-top:14px"><h3>TSP calculator (Blended Retirement System)</h3>
      <div class="row">
        <div style="flex:1"><label>Monthly basic pay ($)</label><input id="tspPay" type="number" min="0" step="1" placeholder="from your LES"></div>
        <div style="flex:1"><label>You contribute (%)</label><input id="tspPct" type="number" min="0" max="100" step="1" value="5"></div>
      </div>
      <div class="row">
        <div style="flex:1"><label>Months served so far</label><input id="tspServed" type="number" min="0" step="1" value="0"></div>
        <div style="flex:1"><label>Years to look ahead</label><input id="tspYears" type="number" min="1" max="40" step="1" value="4"></div>
        <div style="flex:1"><label>Example growth per year (%)</label><input id="tspRate" type="number" min="0" max="15" step="0.5" value="0"></div>
      </div>
      <div id="tspOut" style="margin-top:10px"></div>
      <p class="faint">Rules as written in the official <i>Summary of the Thrift Savings Plan</i> (TSPBK08, pp. 5–6, tsp.gov, downloaded 2026-10-07): automatic 1% of basic pay after 60 days of service; matching on the first 5% you contribute — first 3% dollar-for-dollar, next 2% at 50¢ — for BRS members who began service on or after Jan 1, 2018, starting after two years of service; the automatic 1% vests after two years. Assumes your pay stays the same. Growth is only an example you choose, not a prediction or advice. Confirm with your finance office.</p>
    </div>
    </details>`;
  if (window.moneyMilitary) { $('#moneyPane details').open = true; window.moneyMilitary = false; }   // opened from Serve
  lesDecoder();
  if ($('#payGo')) $('#payGo').onclick = async () => {
    const r = await api('/api/pay', { grade: $('#payGrade').value, years: $('#payYears').value, months: $('#payMonths').value, bah: $('#payBah').value });
    if (r.error) { $('#payOut').innerHTML = `<p style="color:var(--red)">${esc(r.error)}</p>`; return; }
    const $$ = n => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    $('#payOut').innerHTML = `<table style="width:100%;margin-top:8px">
        <tr><td>Basic pay</td><td style="text-align:right">${$$(r.basic)}</td></tr><tr><td>BAS (food)</td><td style="text-align:right">${$$(r.bas)}</td></tr>
        ${r.bah ? `<tr><td>BAH (housing)</td><td style="text-align:right">${$$(r.bah)}</td></tr>` : ''}
        <tr><td><b>Total per month</b></td><td style="text-align:right"><b>${$$(r.total)}</b></td></tr></table>
      <div class="row" style="margin-top:8px"><button class="btn small" id="payToBudget">Add to my budget</button><button class="btn small" id="payToTsp">Use in TSP calculator</button></div>`;
    $('#payToBudget').onclick = () => {
      const d = collect(), names = ['Basic pay', 'BAS', 'BAH'];
      d.income = d.income.filter(x => !names.includes(x.name));
      d.income.unshift(...[['Basic pay', r.basic], ['BAS', r.bas], ['BAH', r.bah]].filter(x => x[1]).map(([name, amount]) => ({ name, amount })));
      Object.assign(bd, d); renderKeep();
    };
    $('#payToTsp').onclick = () => { $('#tspPay').value = Math.round(r.basic); $('#tspPay').dispatchEvent(new Event('input')); $('#tspPay').scrollIntoView({ behavior: 'smooth' }); };
  };
  const tsp = () => {
    const pay = +$('#tspPay').value || 0, pct = Math.max(0, +$('#tspPct').value || 0) / 100;
    const served = Math.max(0, Math.floor(+$('#tspServed').value || 0)), years = Math.max(1, Math.min(40, +$('#tspYears').value || 1));
    const r = Math.max(0, +$('#tspRate').value || 0) / 100 / 12;
    if (!pay) { $('#tspOut').innerHTML = '<p class="faint">Enter your monthly basic pay to see the numbers.</p>'; return; }
    const matchRate = c => Math.min(c, 0.03) + 0.5 * Math.min(Math.max(c - 0.03, 0), 0.02);
    let own = 0, auto = 0, match = 0, bal = 0;
    for (let m = 0; m < years * 12; m++) {
      const month = served + m;                       // months of service at this point
      const o = pay * pct, a = month >= 2 ? pay * 0.01 : 0, mt = month >= 24 ? pay * matchRate(pct) : 0;
      own += o; auto += a; match += mt; bal = (bal + o + a + mt) * (1 + r);
    }
    const fullMatch = pay * matchRate(0.05), mineNow = pay * matchRate(pct), missed = Math.max(0, fullMatch - mineNow);
    const $f = v => '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    $('#tspOut').innerHTML = `<div class="row" style="justify-content:space-between">
        <div><div class="faint">You put in</div><b>${$f(own)}</b></div><div><div class="faint">Automatic 1%</div><b>${$f(auto)}</b></div>
        <div><div class="faint">Matching</div><b>${$f(match)}</b></div><div><div class="faint">Total after ${years} yr${years > 1 ? 's' : ''}</div><b style="color:var(--tan2)">${$f(bal)}</b></div></div>
      ${pct < 0.05 ? `<p style="color:var(--tan2)">Once matching starts, contributing 5% instead of ${Math.round(pct * 100)}% would add <b>${$f(missed)}/month</b> of free matching money.</p>`
                   : '<p class="faint">You contribute at least 5% — you get the full match once it starts.</p>'}
      ${served + years * 12 < 24 ? '<p class="faint">Matching hasn\'t started in this period (it begins after two years of service).</p>' : ''}`;
  };
  ['tspPay', 'tspPct', 'tspServed', 'tspYears', 'tspRate'].forEach(id => $('#' + id).addEventListener('input', tsp));
  tsp();
  const collect = () => {
    const out = { income: bd.income.map(r => ({ ...r })), expenses: bd.expenses.map(r => ({ ...r })), goal: $('#bdGoal').value };
    $('#moneyPane').querySelectorAll('input[data-k]').forEach(inp => { out[inp.dataset.k][+inp.dataset.i][inp.dataset.f] = inp.value; });
    return out;
  };
  $('#moneyPane').querySelectorAll('[data-add]').forEach(b => b.onclick = () => { const d = collect(); d[b.dataset.add].push({ name: '', amount: 0 }); Object.assign(bd, d); renderKeep(); });
  $('#moneyPane').querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { const d = collect(); d[b.dataset.rm].splice(+b.dataset.i, 1); Object.assign(bd, d); renderKeep(); });
  $('#bdSave').onclick = async () => {
    const d = collect();
    d.income = d.income.filter(r => r.name.trim()); d.expenses = d.expenses.filter(r => r.name.trim());
    const r = await api('/api/budget', d); if (r.error) alert(r.error); else loadMoney();
  };
  function renderKeep() { loadMoney(bd); }   // re-render with unsaved edits; Save writes them
}

async function loadLetters(keepDraft) {
  const { contacts, letters } = await api('/api/letters');
  const pane = $('#lettersPane');
  const prev = keepDraft ? { to: $('#ltTo')?.value, notes: $('#ltNotes')?.value, text: $('#ltText')?.value } : {};
  const opts = contacts.map(c => `<option value="${esc(c.id)}">${esc(c.name)}${c.relation ? ' (' + esc(c.relation) + ')' : ''}</option>`).join('');
  pane.innerHTML = `
    <div class="card"><h3>Write a letter</h3>
      <label for="ltTo">To</label>
      <select id="ltTo">${opts || ''}<option value="">Someone else…</option></select>
      <label for="ltNotes">Your notes — what you want to tell them (a few words is fine)</label>
      <textarea id="ltNotes" rows="3" placeholder="e.g. tell mom I passed the PT test, food is better than I thought, miss her cooking, made a good friend named Ruiz"></textarea>
      <div class="row" style="margin-top:8px"><button class="btn primary" id="ltDraft">✍️ Help me write it</button><span class="faint" id="ltMsg"></span></div>
      <label for="ltText">Your letter</label>
      <textarea id="ltText" rows="10" placeholder="Write here, or let Cadet Foundry draft it from your notes and then make it yours."></textarea>
      <div id="ltFlags"></div>
      <div class="row" style="margin-top:8px"><button class="btn" id="ltCheck">🛡️ OPSEC check</button><button class="btn" id="ltSave">💾 Save</button><button class="btn" id="ltBig">🔍 Large print</button></div>
    </div>
    <div class="card"><h3>Address book</h3>
      ${contacts.length ? contacts.map(c => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding:8px 0;flex-wrap:nowrap">
          <div><b>${esc(c.name)}</b> <span class="faint">${esc(c.relation)}</span><div style="white-space:pre-wrap" class="muted">${esc(c.address)}</div></div>
          <button class="btn small danger" data-delc="${esc(c.id)}">Delete</button></div>`).join('') : '<p class="faint">No one saved yet.</p>'}
      <div class="row" style="margin-top:8px"><input id="cName" placeholder="Name" style="flex:2"><input id="cRel" placeholder="Relation (Mom, wife…)" style="flex:1"></div>
      <textarea id="cAddr" rows="3" placeholder="Mailing address" style="margin-top:8px"></textarea>
      <button class="btn small" id="cAdd" style="margin-top:8px">Add person</button>
    </div>
    <div class="card"><h3>Saved letters</h3>
      ${letters.length ? letters.map(l => `<div style="border-bottom:1px solid var(--line);padding:8px 0">
          <div class="row" style="justify-content:space-between"><span><b>${esc(l.to || 'Letter')}</b> <span class="faint">${esc(l.date)}</span></span>
          <span class="row" style="gap:6px"><button class="btn small" data-openl="${esc(l.id)}">Open</button><button class="btn small danger" data-dell="${esc(l.id)}">Delete</button></span></div>
          <div class="faint" style="margin-top:4px">${esc(l.text.slice(0, 120))}…</div></div>`).join('') : '<p class="faint">Nothing saved yet.</p>'}
    </div>`;
  if (prev.to !== undefined) { $('#ltTo').value = prev.to; $('#ltNotes').value = prev.notes || ''; $('#ltText').value = prev.text || ''; }
  const toName = () => { const o = $('#ltTo').selectedOptions[0]; return o && o.value ? o.textContent.replace(/\s*\(.*\)$/, '') : ''; };
  const showFlags = flags => {
    $('#ltFlags').innerHTML = !flags.length
      ? '<p style="color:var(--green);margin:8px 0 0">✓ No OPSEC concerns found. Still read it once more before you send it.</p>'
      : `<div class="card" style="border-color:var(--red);margin:8px 0 0"><b style="color:var(--red)">Take a second look before sending:</b>
         ${flags.map(f => `<p style="margin:6px 0">“${esc(f.sentence)}”<br><span class="faint">${esc(f.why.join(', '))}</span></p>`).join('')}
         <p class="faint">Leave out movements, specific dates, locations, numbers and security details — even in letters to family.</p></div>`;
  };
  $('#ltDraft').onclick = async () => {
    if (!$('#ltNotes').value.trim()) { $('#ltMsg').textContent = 'Add a few notes first.'; return; }
    $('#ltMsg').textContent = 'Writing…'; $('#ltDraft').disabled = true;
    const c = contacts.find(x => x.id === $('#ltTo').value) || {};
    const r = await api('/api/letters/draft', { to: c.name || toName(), relation: c.relation || '', notes: $('#ltNotes').value });
    $('#ltDraft').disabled = false;
    if (r.error) { $('#ltMsg').textContent = r.error; return; }
    $('#ltMsg').textContent = 'Draft ready — make it yours.'; $('#ltText').value = r.text; showFlags(r.flags);
  };
  $('#ltCheck').onclick = async () => showFlags(await api('/api/letters/check', { text: $('#ltText').value }));
  $('#ltSave').onclick = async () => {
    if (!$('#ltText').value.trim()) return;
    await api('/api/letters', { to: toName(), text: $('#ltText').value }); loadLetters();
  };
  $('#ltBig').onclick = () => {
    const w = document.createElement('div');
    w.style.cssText = 'position:fixed;inset:0;background:var(--bg);color:var(--text);z-index:50;overflow:auto;padding:24px;font-size:22px;line-height:1.7;white-space:pre-wrap';
    w.textContent = $('#ltText').value || '(empty)';
    const close = document.createElement('button'); close.className = 'btn primary'; close.textContent = 'Close';
    close.style.cssText = 'position:fixed;top:12px;right:12px'; close.onclick = () => w.remove();
    w.appendChild(close); document.body.appendChild(w);
  };
  $('#cAdd').onclick = async () => {
    if (!$('#cName').value.trim()) return;
    await api('/api/contacts', { name: $('#cName').value, relation: $('#cRel').value, address: $('#cAddr').value });
    loadLetters(true);
  };
  pane.querySelectorAll('[data-delc]').forEach(b => b.onclick = async () => { if (confirm('Delete this person?')) { await api('/api/contacts/delete', { id: b.dataset.delc }); loadLetters(true); } });
  pane.querySelectorAll('[data-dell]').forEach(b => b.onclick = async () => { if (confirm('Delete this letter?')) { await api('/api/letters/delete', { id: b.dataset.dell }); loadLetters(true); } });
  pane.querySelectorAll('[data-openl]').forEach(b => b.onclick = () => {
    const l = letters.find(x => x.id === b.dataset.openl); $('#ltText').value = l.text; $('#ltText').scrollIntoView({ behavior: 'smooth' });
  });
}
