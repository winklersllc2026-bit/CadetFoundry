// Instructor analytics (Phase 9): the dashboard at the top of the Instructor screen, reports (CSV and print), the
// program backup, the quiz-question editor and pop quizzes. Phone-first; listeners in JS.
'use strict';

const dTile = (n, label, sub = '') => `<div style="min-width:110px"><div style="font-size:28px;font-weight:700">${n}</div>
  <div class="faint">${label}${sub ? `<br>${sub}` : ''}</div></div>`;
const dPct = v => v == null ? '—' : `${v}%`;
const dSigned = v => v == null ? '—' : `${v > 0 ? '+' : ''}${v}%`;

async function instructorDashboard(box, ov, unit = '') {
  // box: the slot at the top of the Instructor screen (each load of the screen has its own)
  const d = await api('/api/instructor/dashboard?unit=' + encodeURIComponent(unit));
  if (d.error || !box) return;
  box.id = 'dashCard';
  const mine = ov.units.some(u => u.owner && u.owner === ov.me);      // "My Cadets": the units this instructor teaches
  const opts = (mine ? `<option value="mine" ${unit === 'mine' ? 'selected' : ''}>My Cadets</option>` : '') + `<option value="" ${unit === '' ? 'selected' : ''}>Whole program</option>` + ov.units.map(u => `<option value="${esc(u.id)}" ${u.id === unit ? 'selected' : ''}>${esc(u.name)}</option>`).join('');
  box.innerHTML = `<div class="card" style="border-color:var(--tan)">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px"><h3 style="margin:0">📊 Dashboard</h3>
        <select id="dUnit" aria-label="Show" style="max-width:220px">${opts}</select></div>
      <div class="row" style="flex-wrap:wrap;gap:18px;margin-top:12px">
        ${dTile(d.cadets, 'Cadets', `${d.active} active in the last ${d.active_days} days`)}
        ${dTile(dPct(d.lesson_completion_pct), 'lesson completion')}
        ${dTile(dPct(d.avg_lesson_score_pct), 'average lesson score')}
        ${dTile(dSigned(d.avg_fitness_improvement_pct), 'average fitness improvement')}
        ${dTile(+d.service_hours % 1 ? (+d.service_hours).toFixed(1) : d.service_hours, 'service hours verified')}
        ${dTile(d.scenarios, 'leadership scenarios done')}</div>
      ${d.service_pending || d.lessons_overdue || d.waiting_to_share ? `<p style="margin:12px 0 0">Needs you:
        ${d.service_pending ? `<b>${d.service_pending}</b> service entr${d.service_pending === 1 ? 'y' : 'ies'} to review · ` : ''}
        ${d.lessons_overdue ? `<b>${d.lessons_overdue}</b> overdue lesson${d.lessons_overdue === 1 ? '' : 's'} · ` : ''}
        ${d.waiting_to_share ? `<b>${d.waiting_to_share}</b> Cadet${d.waiting_to_share === 1 ? '' : 's'} not sharing records yet` : ''}</p>` : ''}
      <details style="margin-top:10px"><summary>Each Cadet</summary>
        ${d.rows.map(r => `<div style="border-top:1px solid var(--line);padding:8px 0">
          <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:6px"><b>${esc(r.name)}</b>
            <span class="faint">${[r.rank, r.billet, r.unit, r.let ? (STATUS.level_label || 'Year') + ' ' + r.let : ''].filter(Boolean).map(esc).join(' · ')}</span></div>
          ${r.shared ? `<div class="faint">Lessons ${r.lessons_completed}/${r.lessons_assigned}${r.lessons_overdue ? ` (${r.lessons_overdue} overdue)` : ''}
            · score ${dPct(r.lesson_score_pct)} · scenarios ${r.scenarios} · service ${r.service_hours} hrs
            · fitness ${dSigned(r.fitness_improvement_pct)} · last active ${esc(r.last_active || '—')}</div>
            <button class="btn small" data-dprog="${esc(r.id)}" style="margin-top:6px">📈 Progress</button>`
          : '<div class="faint">Waiting to share — signs in next time.</div>'}</div>`).join('') || '<p class="faint">No Cadets here yet.</p>'}
      </details></div>
    <div class="card"><h3>🧾 Reports</h3>
      <p class="faint">For your records or your school. Only names and numbers — never private notes.</p>
      <div class="row" style="flex-wrap:wrap;gap:8px"><a class="btn small" id="dCsv" href="/api/instructor/report.csv?unit=${encodeURIComponent(unit)}" download>⬇ Class report (spreadsheet)</a>
        <button class="btn small" id="dPrint">🖨️ Print class report</button></div></div>`;
  box.querySelector('#dUnit').addEventListener('change', e => instructorDashboard(box, ov, e.target.value));
  box.querySelectorAll('[data-dprog]').forEach(b => b.addEventListener('click', () => instructorProgress(b.dataset.dprog)));
  $('#dPrint').addEventListener('click', () => {
    const unitName = unit === 'mine' ? 'My Cadets' : unit ? (ov.units.find(u => u.id === unit) || {}).name : 'Whole program';
    const rows = d.rows.map(r => `<tr><td>${esc(r.name)}</td><td>${esc(r.unit || '')}</td><td>${r.shared ? `${r.lessons_completed}/${r.lessons_assigned}` : '—'}</td>
      <td>${r.shared ? dPct(r.lesson_score_pct) : '—'}</td><td>${r.shared ? r.scenarios : '—'}</td><td>${r.shared ? r.service_hours : '—'}</td>
      <td>${r.shared ? dSigned(r.fitness_improvement_pct) : '—'}</td><td>${esc(r.last_active || '')}</td></tr>`).join('');
    let area = $('#printArea');
    if (!area) { area = document.createElement('div'); area.id = 'printArea'; document.body.appendChild(area); }
    area.innerHTML = `<div style="font-family:Georgia,serif;color:#000"><div style="letter-spacing:.2em;font-weight:700">VANGUARD</div>
      <h1 style="margin:4px 0">Class report — ${esc(unitName)}</h1><div>${esc(new Date().toLocaleDateString())}</div>
      <p>${d.cadets} Cadets · ${d.active} active in the last ${d.active_days} days · lesson completion ${dPct(d.lesson_completion_pct)}
        · average lesson score ${dPct(d.avg_lesson_score_pct)} · average fitness improvement ${dSigned(d.avg_fitness_improvement_pct)}
        · ${d.service_hours} service hours · ${d.scenarios} leadership scenarios</p>
      <table style="width:100%;border-collapse:collapse;font-size:12px" border="1" cellpadding="4">
        <tr><th>Cadet</th><th>Unit</th><th>Lessons</th><th>Score</th><th>Scenarios</th><th>Service hrs</th><th>Fitness</th><th>Last active</th></tr>${rows}</table>
      <p style="font-size:11px">Vanguard is designed to support JROTC instruction; it is not an official JROTC, military or school record.</p></div>`;
    window.print();
  });
}

// ── Program backup and restore ──
function instructorBackup(body) {
  const sec = document.createElement('div');
  sec.className = 'card';
  sec.innerHTML = `<h3>💾 Program backup</h3>
    <p class="faint">Your classes, lessons and notes, assignments, scenarios, service projects, fitness events, quiz edits and settings —
      in one file sealed with a password. Cadets' own files aren't in it; each Cadet backs up their own profile.</p>
    <label for="pbPass">Backup password (at least 10 characters)</label><input id="pbPass" type="password" autocomplete="new-password" maxlength="200">
    <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px"><button class="btn small" id="pbSave">⬇ Download program backup</button>
      <label class="btn small" style="margin:0;color:var(--text)">⬆ Restore a program backup<input type="file" id="pbFile" accept=".json,application/json" hidden></label></div>
    <p class="faint" id="pbMsg" role="alert">Restoring replaces this device's program with the backup, including its Class PIN.</p>`;
  body.appendChild(sec);
  $('#pbSave').addEventListener('click', async () => {
    const r = await api('/api/instructor/program-backup', { password: $('#pbPass').value });
    if (r.error) { $('#pbMsg').textContent = r.error; return; }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(r.file)], { type: 'application/json' }));
    a.download = r.name; document.body.appendChild(a); a.click(); a.remove();
    $('#pbMsg').textContent = 'Saved. Keep the file and the password somewhere safe — both are needed to restore.';
  });
  $('#pbFile').addEventListener('change', async e => {
    const f = e.target.files[0]; if (!f) return;
    if (!confirm('Replace this device\'s program (classes, lessons, settings and Class PIN) with this backup?')) return;
    let file;
    try { file = JSON.parse(await f.text()); } catch (err) { $('#pbMsg').textContent = 'That file isn\'t a Vanguard program backup.'; return; }
    const r = await api('/api/instructor/program-restore', { file, password: $('#pbPass').value });
    if (r.error) { $('#pbMsg').textContent = r.error; return; }
    alert('Restored. Enter the Class PIN from the backup to open your class again.');
    loaders.instructor();
  });
}

// ── Quiz questions: view and edit the built-in ones; give a pop quiz ──
async function instructorQuizzes(body, ov) {
  const list = await api('/api/instructor/quiz');
  if (list.error) return;
  const sec = document.createElement('div');
  sec.className = 'card';
  sec.innerHTML = `<h3>📝 Quiz questions</h3>
    <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn primary" id="popGo">🎯 Give a pop quiz</button>
      <button class="btn" id="lqOwn">📡 Ask a live question</button><span id="lqResume"></span></div><div id="popForm"></div>
    <label for="lqMode" style="margin-top:12px">Live questions are</label>
    <select id="lqMode"><option value="mc">Practice — multiple choice</option><option value="typed">Challenge — typed answers</option></select>
    <p class="faint">A live question goes on the projector; Cadets answer in 🧭 Lead on their own devices. Use 📡 on any question below.</p>
    <p class="faint" style="margin-top:12px">Change the wording or answer of a built-in question for your program, or hide it. The study card itself isn't changed.</p>
    <select id="qeCard" aria-label="Study card"><option value="">Choose a study card…</option>
      ${list.cards.map(c => `<option value="${esc(c.id)}">${esc(c.title)} (${c.questions})</option>`).join('')}</select>
    <div id="qeList"></div>`;
  body.appendChild(sec);
  $('#qeCard').addEventListener('change', async e => {
    const box = $('#qeList');
    if (!e.target.value) { box.innerHTML = ''; return; }
    const d = await api('/api/instructor/quiz?card=' + encodeURIComponent(e.target.value));
    box.innerHTML = `<p class="faint">Source: ${esc(d.card.source)}</p>` + d.questions.map(q => `<div class="card" style="margin:8px 0;padding:12px" data-qe="${esc(q.id)}">
      <label>Question</label><input data-qq value="${esc(q.edit.q || q.q)}" maxlength="300">
      <label>Answer</label><input data-qa value="${esc(q.edit.a || q.a)}" maxlength="500">
      <label style="display:flex;gap:10px;align-items:center;min-height:40px"><input type="checkbox" data-qh ${q.edit.hidden ? 'checked' : ''} style="width:22px;height:22px"> Hide this question from Cadets</label>
      <div class="row" style="gap:6px;flex-wrap:wrap"><button class="btn small primary" data-qsave>Save</button>${Object.keys(q.edit).length ? '<button class="btn small" data-qreset>Back to original</button>' : ''}
        ${q.edit.hidden ? '' : '<button class="btn small" data-qlive>📡 Ask live</button>'}</div>
      <p class="faint" data-qmsg role="status">${Object.keys(q.edit).length ? 'Edited for your program.' : ''}</p></div>`).join('');
    box.querySelectorAll('[data-qe]').forEach(card => {
      const id = card.dataset.qe, orig = d.questions.find(q => q.id === id);
      card.querySelector('[data-qsave]').addEventListener('click', async () => {
        const qq = card.querySelector('[data-qq]').value, qa = card.querySelector('[data-qa]').value;
        const r = await api('/api/instructor/quiz', { id, q: qq === orig.q ? '' : qq, a: qa === orig.a ? '' : qa, hidden: card.querySelector('[data-qh]').checked });
        card.querySelector('[data-qmsg]').textContent = r.error || 'Saved.';
      });
      const rs = card.querySelector('[data-qreset]');
      if (rs) rs.addEventListener('click', async () => { await api('/api/instructor/quiz', { id, action: 'reset' }); $('#qeCard').dispatchEvent(new Event('change')); });
      const lv = card.querySelector('[data-qlive]');
      if (lv) lv.addEventListener('click', async () => {
        const r = await api('/api/instructor/live-quiz', { action: 'start', id, mode: $('#lqMode').value });
        if (r.error) { card.querySelector('[data-qmsg]').textContent = r.error; return; }
        liveQuizMode();
      });
    });
  });
  api('/api/instructor/live-quiz').then(lq => {
    if (!lq.id || !$('#lqResume')) return;
    $('#lqResume').innerHTML = '<button class="btn" id="lqBack">📡 Back to the live question</button>';
    $('#lqBack').addEventListener('click', liveQuizMode);
  }).catch(() => {});
  $('#lqOwn').addEventListener('click', () => {
    $('#popForm').innerHTML = `<div class="card" style="margin-top:10px"><label for="lqQ">Question</label><input id="lqQ" maxlength="300">
      <label for="lqA">Answer</label><input id="lqA" maxlength="300">
      <label for="lqW">Wrong choices (optional, one per line — leave empty for a typed answer)</label><textarea id="lqW" rows="3" style="width:100%"></textarea>
      <div class="row" style="gap:8px"><button class="btn primary" id="lqStart">Put it on the projector</button><button class="btn small" id="lqCancel">Cancel</button></div>
      <p class="faint" id="lqMsg2" role="alert"></p></div>`;
    $('#lqCancel').addEventListener('click', () => { $('#popForm').innerHTML = ''; });
    $('#lqStart').addEventListener('click', async () => {
      const wrong = $('#lqW').value.split('\n').map(s => s.trim()).filter(Boolean);
      const r = await api('/api/instructor/live-quiz', { action: 'start', q: $('#lqQ').value, a: $('#lqA').value, choices: wrong, mode: wrong.length ? 'mc' : 'typed' });
      if (r.error) { $('#lqMsg2').textContent = r.error; return; }
      liveQuizMode();
    });
  });
  $('#popGo').addEventListener('click', () => {
    $('#popForm').innerHTML = `<div class="card" style="margin-top:10px"><label for="popTitle">Title</label><input id="popTitle" maxlength="80" placeholder="e.g. Chain of command">
      <label for="popQs">Questions</label><textarea id="popQs" rows="7" style="width:100%" placeholder="Q: Who salutes first?&#10;* The junior person&#10;- The senior person"></textarea>
      <p class="faint"><b>Q:</b> the question, <b>*</b> the right choice, <b>-</b> the others. Due today; Cadets find it in Learn → My assignments.</p>
      <label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" id="popAll" style="width:22px;height:22px"> Everyone</label>
      ${ov.units.map(u => `<label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" data-pu="${esc(u.id)}" style="width:22px;height:22px"> ${esc(u.name)}</label>`).join('')}
      <div class="row" style="gap:8px"><button class="btn primary" id="popSend">Give it now</button><button class="btn small" id="popCancel">Cancel</button></div>
      <p class="faint" id="popMsg" role="alert"></p></div>`;
    $('#popCancel').addEventListener('click', () => { $('#popForm').innerHTML = ''; });
    $('#popSend').addEventListener('click', async () => {
      const r = await api('/api/instructor/pop-quiz', { title: $('#popTitle').value, questions: $('#popQs').value, everyone: $('#popAll').checked,
        units: [...sec.querySelectorAll('[data-pu]:checked')].map(x => x.dataset.pu) });
      if (r.error) { $('#popMsg').textContent = r.error; return; }
      $('#popForm').innerHTML = `<p>✅ Given to ${r.assignment.cadets.length || 'everyone'}${r.assignment.cadets.length ? ' Cadet' + (r.assignment.cadets.length === 1 ? '' : 's') : ''}. Results show under 📋 Assignments.</p>`;
    });
  });
}

// ── The live pop quiz on the projector: big type, counts only (never who answered what) ──
async function liveQuizMode() {
  openView('classroom');
  const box = $('#classroomBody');
  const L = 'ABCDEF';
  const draw = async () => {
    const lq = await api('/api/instructor/live-quiz');
    if (!lq.id) { clearInterval(livePoll); loaders.instructor(); openView('instructor'); return; }
    const pct = n => lq.answered ? Math.round(100 * n / lq.answered) : 0;
    const max = Math.max(1, ...(lq.counts || [0]));
    box.innerHTML = `<div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <span class="faint">LIVE QUESTION · ${lq.answered} answer${lq.answered === 1 ? '' : 's'} · Cadets answer in 🧭 Lead</span>
        <span class="row" style="gap:8px"><button class="btn small" id="lqReveal">${lq.revealed ? 'Hide answer' : 'Reveal answer'}</button>
        <button class="btn small" id="lqEnd">End</button></span></div>
      <h1 style="font-size:clamp(26px,4vw,48px);margin:18px 0">${esc(lq.q)}</h1>
      ${lq.mode === 'mc' ? lq.choices.map((c, i) => `<div style="margin:14px 0;font-size:clamp(18px,2.4vw,30px)">
        <b>${L[i]}.</b> ${esc(c)}${lq.revealed && c === lq.a ? ' ✅' : ''}
        ${lq.revealed ? `<div style="display:flex;align-items:center;gap:10px;margin-top:6px"><div style="height:14px;border-radius:7px;background:var(--tan);width:${Math.round(lq.counts[i] / max * 70)}%;min-width:4px"></div>
        <span class="faint">${lq.counts[i]}</span></div>` : ''}</div>`).join('') : '<p class="faint" style="font-size:20px">Typed answers — graded by Vanguard.</p>'}
      ${lq.revealed ? `<div class="card" style="font-size:clamp(18px,2.2vw,28px)"><b>Answer:</b> ${esc(lq.a)}
        <div class="faint" style="font-size:18px;margin-top:8px">${lq.right} of ${lq.answered} right (${pct(lq.right)}%)${lq.close ? ` · ${lq.close} close` : ''}</div></div>`
        : '<p class="faint">Results stay hidden until you reveal the answer, so nobody copies the room.</p>'}`;
    $('#lqReveal').addEventListener('click', async () => { await api('/api/instructor/live-quiz', { action: 'reveal', on: !lq.revealed }); draw(); });
    $('#lqEnd').addEventListener('click', async () => { await api('/api/instructor/live-quiz', { action: 'stop' }); draw(); });
  };
  await draw();
  clearInterval(livePoll);
  livePoll = setInterval(() => {
    if (!$('#classroom').classList.contains('on')) { clearInterval(livePoll); return; }
    draw().catch(() => clearInterval(livePoll));
  }, 3000);
}
