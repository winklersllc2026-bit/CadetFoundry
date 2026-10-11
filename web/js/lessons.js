// Lessons (Phase 4). Cadets: "My assignments" at the top of Learn, and the lesson page. Instructors: write, assign
// and track lessons on the Instructor screen. Phone-first: one column, large touch targets, nothing side by side
// that can't wrap. The page's security policy blocks inline handlers -- listeners are attached in JS.
'use strict';

const STATE_NAME = { not_started: 'Not started', in_progress: 'In progress', complete: 'Complete', unknown: 'Waiting to share' };

// ── Cadet: My assignments (top of Learn) ──
const studyLoader = loaders.study;
loaders.study = async (pick) => {
  await studyLoader(pick);
  if (STATUS.kind !== 'cadet' || studyBody.dataset.section) return;     // only on the All sections view
  const r = await api('/api/lessons');
  if (!r.assignments || !r.assignments.length) return;
  const card = document.createElement('div');
  card.className = 'card'; card.id = 'myAssignments'; card.style.borderColor = 'var(--tan)';
  card.innerHTML = `<h3>📋 My assignments</h3>${r.assignments.map(a => `
    <button class="btn" data-lesson="${esc(a.id)}" style="display:block;width:100%;text-align:left;margin:6px 0">
      <b>${esc(a.title)}</b><br><span class="faint">${esc(STATE_NAME[a.state] || a.state)}${a.state === 'complete' && a.total ? ` · ${a.score}/${a.total}` : ''}${a.due ? ` · due ${esc(a.due)}` : ''}</span>
    </button>`).join('')}`;
  const h2 = studyBody.querySelector('h2');
  h2 ? h2.after(card) : studyBody.prepend(card);
  card.querySelectorAll('[data-lesson]').forEach(b => b.addEventListener('click', () => openLesson(b.dataset.lesson)));
};

async function openLesson(aid) {
  openView('lesson');
  const box = $('#lessonBody');
  box.innerHTML = '<p class="faint">Loading…</p>';
  const r = await api('/api/lesson?a=' + encodeURIComponent(aid));
  if (r.error) { box.innerHTML = `<p>${esc(r.error)}</p>`; return; }
  const L = r.lesson, done = r.work.state === 'complete', key = r.answers || [], mine = r.work.answers || [];
  const meta = [L.let_level && `${STATUS.level_label || 'Year'} ${L.let_level}`, L.competency, r.assignment.due && `Due ${r.assignment.due}`].filter(Boolean);
  box.innerHTML = `<button class="btn small" id="lessonBack">← Learn</button>
    <h2 style="margin-top:12px">${esc(L.title)}</h2>
    ${meta.length ? `<p class="faint">${meta.map(esc).join(' · ')}</p>` : ''}
    ${L.objective ? `<div class="card"><b>Objective:</b> ${esc(L.objective)}</div>` : ''}
    ${L.content ? `<div class="card lessonText">${md(L.content)}</div>` : ''}
    ${L.source ? `<p class="faint">Source: ${esc(L.source)} <span title="Written by your instructor">· Instructor lesson</span></p>` : '<p class="faint">Instructor lesson</p>'}
    ${L.vocabulary.length ? `<div class="card"><h3>Vocabulary</h3><dl style="margin:0">${L.vocabulary.map(v =>
      `<dt style="font-weight:700;margin-top:8px">${esc(v.term)}</dt><dd style="margin:2px 0 0 0">${esc(v.definition)}</dd>`).join('')}</dl></div>` : ''}
    ${L.questions.length ? `<div class="card"><h3>Questions</h3>${L.questions.map((q, i) => `
      <fieldset style="border:0;padding:0;margin:14px 0"><legend style="font-weight:700">${i + 1}. ${esc(q.q)}</legend>
      ${q.choices.map((c, j) => {
        const mark = done ? (j === key[i] ? ' ✅' : j === mine[i] ? ' ❌' : '') : '';
        return `<label style="display:flex;gap:10px;align-items:center;min-height:44px;cursor:pointer">
          <input type="radio" name="q${i}" value="${j}" ${mine[i] === j ? 'checked' : ''} ${done ? 'disabled' : ''} style="width:22px;height:22px">
          <span>${esc(c)}${mark}</span></label>`;
      }).join('')}</fieldset>`).join('')}</div>` : ''}
    ${L.reflection ? `<div class="card"><h3>Reflection</h3><label for="lessonRefl">${esc(L.reflection)}</label>
      <textarea id="lessonRefl" rows="4" ${done ? 'disabled' : ''} style="width:100%;margin-top:8px">${esc(r.work.reflection || '')}</textarea></div>` : ''}
    ${done ? `<div class="card" style="border-color:var(--tan)"><b>Submitted ${esc(r.work.completed || '')}.</b>
      ${r.work.total ? ` You got ${r.work.score} of ${r.work.total}.` : ''} Your instructor can see your answers and reflection.</div>`
      : `<button class="btn primary" id="lessonSubmit" style="width:100%;margin:8px 0 24px">Submit to my instructor</button>
         <p class="faint" id="lessonMsg" role="alert"></p>`}`;
  $('#lessonBack').addEventListener('click', () => openView('study'));
  if (done) return;
  $('#lessonSubmit').addEventListener('click', async () => {
    const answers = {};
    L.questions.forEach((_, i) => { const c = document.querySelector(`input[name=q${i}]:checked`); if (c) answers[i] = Number(c.value); });
    const res = await api('/api/lesson/submit', { a: aid, answers, reflection: $('#lessonRefl') ? $('#lessonRefl').value : '' });
    if (res.error) { $('#lessonMsg').textContent = res.error; return; }
    openLesson(aid);                                 // reload: shows the score and the right answers
  });
}

// ── Instructor: lessons and assignments (added below the roster on the Instructor screen) ──
async function instructorLessons(body, ov) {
  const data = await api('/api/instructor/lessons');
  if (data.error) return;
  const sec = document.createElement('div');
  body.appendChild(sec);
  const lessonById = id => data.lessons.find(l => l.id === id);
  sec.innerHTML = `<div class="card"><h3>📋 Assignments</h3>
      ${data.assignments.length ? data.assignments.map(a => `<div class="card" style="margin:8px 0;padding:12px">
        <b>${esc(a.title)}</b> <span class="faint">→ ${esc(a.to)}${a.due ? ` · due ${esc(a.due)}` : ''}</span>
        <div style="margin-top:6px">${a.complete} of ${a.assigned} complete · ${a.in_progress} in progress · ${a.not_started} not started${a.unknown ? ` · ${a.unknown} waiting to share` : ''}</div>
        <div class="row" style="flex-wrap:wrap;gap:6px;margin-top:8px"><button class="btn small" data-adet="${esc(a.id)}">Details</button>
          <button class="btn small" data-adel="${esc(a.id)}">Remove</button></div><div data-aout="${esc(a.id)}"></div></div>`).join('')
        : '<p class="faint">No assignments yet. Write a lesson, then assign it.</p>'}</div>
    ${starterLessonsHtml(data.starters, data.lessons.length)}
    <div class="card"><h3>📚 Lessons</h3>
      ${data.lessons.map(l => `<div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:6px;margin:8px 0">
        <span><b>${esc(l.title)}</b> <span class="faint">${[l.let_level && (STATUS.level_label || 'Year') + ' ' + l.let_level, l.competency, `${l.questions.length} questions`].filter(Boolean).map(esc).join(' · ')}</span></span>
        <span class="row" style="gap:6px"><button class="btn small" data-ledit="${esc(l.id)}">Edit</button>
        <button class="btn small primary" data-lassign="${esc(l.id)}">Assign</button></span></div>`).join('') || '<p class="faint">No lessons yet.</p>'}
      <button class="btn primary" id="lNew" style="margin-top:8px">＋ New lesson</button>
      <div id="lForm"></div></div>`;
  starterLessonsWire(sec, () => loaders.instructor());

  const form = (l = {}) => {
    $('#lForm').innerHTML = `<div class="card" style="margin-top:12px">
      <h3>${l.id ? 'Edit lesson' : 'New lesson'}</h3>
      <label>Title</label><input id="lTitle" maxlength="100" value="${esc(l.title || '')}">
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <div style="flex:1;min-width:120px"><label>Year</label><select id="lLet"><option value="">Any</option>${[1, 2, 3, 4].map(n => `<option value="${n}" ${l.let_level === n ? 'selected' : ''}>${esc(STATUS.level_label || 'Year')} ${n}</option>`).join('')}</select></div>
        <div style="flex:2;min-width:160px"><label>Competency</label><input id="lComp" maxlength="80" value="${esc(l.competency || '')}" placeholder="e.g. Leadership"></div></div>
      <label>Learning objective</label><input id="lObj" maxlength="500" value="${esc(l.objective || '')}">
      <label>Source</label><input id="lSrc" maxlength="200" value="${esc(l.source || '')}" placeholder="Where this comes from (your curriculum, a manual…)">
      <label>Lesson content</label><textarea id="lContent" rows="8" style="width:100%">${esc(l.content || '')}</textarea>
      <label>Questions</label><textarea id="lQs" rows="8" style="width:100%" placeholder="Q: Who salutes first?&#10;* The junior person&#10;- The senior person">${esc(l.questions_text || '')}</textarea>
      <p class="faint">One question per block: <b>Q:</b> the question, <b>*</b> before the right choice, <b>-</b> before the others.</p>
      <label>Vocabulary</label><textarea id="lVocab" rows="4" style="width:100%" placeholder="Chain of command: who reports to whom">${esc(l.vocabulary_text || '')}</textarea>
      <label>Reflection prompt</label><input id="lRefl" maxlength="500" value="${esc(l.reflection || '')}" placeholder="What did you learn about…?">
      <label>Instructor notes (only you see these)</label><textarea id="lNotes" rows="3" style="width:100%">${esc(l.notes || '')}</textarea>
      <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:10px"><button class="btn primary" id="lSave">Save lesson</button>
        ${l.id ? '<button class="btn small" id="lDel">Delete</button>' : ''}<button class="btn small" id="lCancel">Cancel</button></div>
      <p class="faint" id="lMsg" role="alert"></p></div>`;
    $('#lTitle').focus();
    $('#lCancel').addEventListener('click', () => { $('#lForm').innerHTML = ''; });
    $('#lSave').addEventListener('click', async () => {
      const r = await api('/api/instructor/lesson', { id: l.id || '', title: $('#lTitle').value, let_level: $('#lLet').value,
        competency: $('#lComp').value, objective: $('#lObj').value, source: $('#lSrc').value, content: $('#lContent').value,
        questions: $('#lQs').value, vocabulary: $('#lVocab').value, reflection: $('#lRefl').value, notes: $('#lNotes').value });
      if (r.error) $('#lMsg').textContent = r.error; else loaders.instructor();
    });
    if ($('#lDel')) $('#lDel').addEventListener('click', async () => {
      if (!confirm('Delete this lesson?')) return;
      const r = await api('/api/instructor/lesson', { action: 'delete', id: l.id });
      if (r.error) $('#lMsg').textContent = r.error; else loaders.instructor();
    });
  };

  const assignForm = l => {
    $('#lForm').innerHTML = `<div class="card" style="margin-top:12px"><h3>Assign: ${esc(l.title)}</h3>
      <label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" id="aAll" style="width:22px;height:22px"> Everyone (all Cadets)</label>
      ${ov.units.length ? `<div class="faint" style="margin-top:6px">Or units (includes their squads):</div>${ov.units.map(u =>
        `<label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" data-au="${esc(u.id)}" style="width:22px;height:22px"> ${esc(u.name)}</label>`).join('')}` : ''}
      ${ov.cadets.length ? `<details style="margin-top:6px"><summary>Or individual Cadets</summary>${ov.cadets.map(c =>
        `<label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" data-ac="${esc(c.id)}" style="width:22px;height:22px"> ${esc(c.name)}</label>`).join('')}</details>` : ''}
      <label>Due date (optional)</label><input id="aDue" type="date">
      <div class="row" style="gap:8px;margin-top:10px"><button class="btn primary" id="aGo">Assign</button><button class="btn small" id="aCancel">Cancel</button></div>
      <p class="faint" id="aMsg" role="alert"></p><p class="faint">Cadets who join a unit later get its lessons automatically — only them; nobody else sees a new assignment.</p></div>`;
    $('#aCancel').addEventListener('click', () => { $('#lForm').innerHTML = ''; });
    $('#aGo').addEventListener('click', async () => {
      const units = [...sec.querySelectorAll('[data-au]:checked')].map(x => x.dataset.au);
      const cadets = [...sec.querySelectorAll('[data-ac]:checked')].map(x => x.dataset.ac);
      const r = await api('/api/instructor/assign-lesson', { lesson: l.id, everyone: $('#aAll').checked, units, cadets, due: $('#aDue').value });
      if (r.error) $('#aMsg').textContent = r.error; else loaders.instructor();
    });
  };

  $('#lNew').addEventListener('click', () => form());
  sec.querySelectorAll('[data-ledit]').forEach(b => b.addEventListener('click', () => form(lessonById(b.dataset.ledit))));
  sec.querySelectorAll('[data-lassign]').forEach(b => b.addEventListener('click', () => assignForm(lessonById(b.dataset.lassign))));
  sec.querySelectorAll('[data-adel]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Remove this assignment? Cadets keep the work they already did.')) return;
    await api('/api/instructor/assignment', { action: 'delete', id: b.dataset.adel }); loaders.instructor();
  }));
  sec.querySelectorAll('[data-adet]').forEach(b => b.addEventListener('click', async () => {
    const out = sec.querySelector(`[data-aout="${b.dataset.adet}"]`);
    if (out.innerHTML) { out.innerHTML = ''; return; }
    const d = await api('/api/instructor/assignment?id=' + encodeURIComponent(b.dataset.adet));
    out.innerHTML = (d.cadets || []).map(c => `<div style="border-top:1px solid var(--line);padding:8px 0;margin-top:8px">
      <b>${esc(c.name)}</b> <span class="faint">${esc(STATE_NAME[c.state] || c.state)}${c.state === 'complete' && c.total ? ` · ${c.score}/${c.total}` : ''}${c.completed ? ` · ${esc(c.completed)}` : ''}</span>
      ${c.reflection ? `<div style="margin-top:4px;white-space:pre-wrap">${esc(c.reflection)}</div>` : ''}</div>`).join('');
  }));
}

// ── Starter lessons: ready to assign on day one, built from cited study cards ──
function starterLessonsHtml(starters, have) {
  const left = (starters || []).filter(s => !s.added);
  if (!left.length) return '';
  return `<div class="card" id="starterCard" style="border-color:var(--tan)"><h3>📦 Starter lessons</h3>
    <p class="faint">${left.length} ready-to-assign lessons built from Cadet Foundry's cited study cards, each with four questions and a reflection.
      ${have ? '' : 'A quick way to assign something today. '}Once added they're yours to edit or delete. The ${esc(STATUS.level_label || 'Year')} levels are suggestions.</p>
    <div style="max-height:300px;overflow:auto;border:1px solid var(--line);border-radius:10px;padding:4px 10px">${left.map(s => `<label style="display:flex;gap:10px;align-items:center;min-height:44px">
      <input type="checkbox" data-starter="${esc(s.key)}" checked style="width:22px;height:22px;flex:none">
      <span>${esc(s.title)} <span class="faint">${esc(STATUS.level_label || 'Year')} ${s.let_level} · ${esc(s.competency)}</span></span></label>`).join('')}</div>
    <button class="btn primary" id="starterAdd" style="margin-top:8px">Add selected lessons</button><p class="faint" id="starterMsg" role="status"></p></div>`;
}

function starterLessonsWire(root, done) {
  const btn = root.querySelector('#starterAdd');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const keys = [...root.querySelectorAll('[data-starter]:checked')].map(x => x.dataset.starter);
    if (!keys.length) { root.querySelector('#starterMsg').textContent = 'Tick at least one lesson.'; return; }
    btn.disabled = true;
    root.querySelector('#starterMsg').textContent = 'Adding…';
    const r = await api('/api/instructor/lessons/starter', { keys });
    if (r.error) { root.querySelector('#starterMsg').textContent = r.error; btn.disabled = false; return; }
    done(r);
  });
}
