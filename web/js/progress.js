// My Progress (Phase 8). Cadets: their growth in one place, from their own class records, and a printable portfolio
// (sections chosen by the instructor). Instructors: the same view for any Cadet, with recognition to add, the
// portfolio sections to choose, and printing. No invented percentages, no rankings. Listeners in JS.
'use strict';

const PG_KIND_ICON = { award: '🏅', promotion: '⬆️', certification: '📜', recognition: '👏', comment: '💬' };
const pgH = h => `${+h % 1 ? (+h).toFixed(2).replace(/0$/, '') : +h}`;
const pgStat = (n, label) => `<div><div style="font-size:26px;font-weight:700">${n}</div><div class="faint">${label}</div></div>`;

function progressHtml(d, forPrint = false) {
  const ac = d.academics, ld = d.leadership, ft = d.fitness, sv = d.service, on = forPrint ? d.sections : Object.keys(d.section_names);
  const box = (title, inner) => forPrint ? `<h2 style="margin:18px 0 6px;border-bottom:1px solid #000">${title}</h2>${inner}` : `<div class="card"><h3>${title}</h3>${inner}</div>`;
  const parts = [];
  if (on.includes('academics')) parts.push(box('📘 Academics', `
    <p>Lessons completed: <b>${ac.lessons_completed}</b> of ${ac.lessons_assigned}${ac.lesson_score_pct != null ? ` · lesson questions right: <b>${ac.lesson_score_pct}%</b>` : ''}
      · study cards mastered: <b>${ac.cards_mastered}</b> of ${ac.cards_total}${ac.exams ? ` · exams taken: ${ac.exams}${ac.best_exam != null ? ` (best ${ac.best_exam}%)` : ''}` : ''}</p>
    ${ac.categories.filter(c => c.total).map(c => `<div style="margin:6px 0">${esc(c.name)} <span class="faint">${c.known} of ${c.total} questions known</span>
      ${forPrint ? '' : `<div class="bar"><i style="width:${Math.round(100 * c.known / c.total)}%"></i></div>`}</div>`).join('')}`));
  if (on.includes('leadership')) parts.push(box('🧭 Leadership', `
    <p>Leadership scenarios completed: <b>${ld.scenarios_completed}</b> (${ld.different_scenarios} different)${ld.competencies.length ? ` · ${ld.competencies.map(esc).join(', ')}` : ''}</p>
    ${ld.recent.map(e => `<div style="margin:8px 0"><b>${esc(e.title)}</b> <span class="faint">${esc(e.date)}</span>
      ${e.reflection ? `<div><i>Reflection:</i> ${esc(e.reflection)}</div>` : ''}${e.learned ? `<div><i>What I learned:</i> ${esc(e.learned)}</div>` : ''}</div>`).join('')}`));
  if (on.includes('fitness')) parts.push(box('💪 Fitness', `
    ${ft.events.length ? ft.events.map(e => `<div style="margin:6px 0"><b>${esc(e.name)}</b>: ${esc(e.first)} → <b>${esc(e.latest)}</b>
      <span class="faint">${e.count > 1 ? `(${esc(e.improvement_shown)}${e.improvement_pct != null ? `, ${e.improvement_pct > 0 ? '+' : ''}${e.improvement_pct}%` : ''}) · best ${esc(e.best)}` : '(starting point)'}${e.goal ? ` · goal ${esc(e.goal)}${e.goal_reached ? ' ✓' : ''}` : ''}</span></div>`).join('')
      : '<p class="faint">No fitness results yet.</p>'}
    ${ft.avg_improvement_pct != null ? `<p>Average improvement: <b>${ft.avg_improvement_pct > 0 ? '+' : ''}${ft.avg_improvement_pct}%</b></p>` : ''}`));
  if (on.includes('service')) parts.push(box('🤝 Service', `
    <p>Verified service: <b>${pgH(sv.verified_hours)} hours</b> · ${sv.projects} project${sv.projects === 1 ? '' : 's'}${sv.pending_hours ? ` · ${pgH(sv.pending_hours)} hours waiting for review` : ''}</p>
    ${sv.recent.map(r => `<div style="margin:6px 0"><b>${esc(r.project)}</b> <span class="faint">${esc(r.date)} · ${pgH(r.hours)} hrs${r.role ? ' · ' + esc(r.role) : ''}</span>
      ${r.reflection ? `<div><i>Reflection:</i> ${esc(r.reflection)}</div>` : ''}</div>`).join('')}`));
  if (on.includes('recognition')) parts.push(box('🏅 Recognition and achievements', `
    ${d.recognition.map(r => `<div style="margin:6px 0">${PG_KIND_ICON[r.kind] || ''} <b>${esc(d.kinds[r.kind] || r.kind)}${r.title ? ': ' + esc(r.title) : ''}</b>
      <span class="faint">${esc(r.date)}</span>${r.note ? `<div>${esc(r.note)}</div>` : ''}${r._rm ? r._rm : ''}</div>`).join('') || (forPrint ? '' : '<p class="faint">Awards and comments from your instructor will show here.</p>')}
    ${d.achievements.length ? `<p style="margin-top:10px">${d.achievements.map(a => `${forPrint ? '• ' : '<span class="chip">'}${esc(a.title)}${forPrint ? '<br>' : '</span>'}`).join(' ')}</p>` : ''}`));
  return parts.join('');
}

function timelineHtml(tl) {
  if (!tl.length) return '';
  return `<div class="card"><h3>📅 Month by month</h3><div style="overflow-x:auto"><table style="border-collapse:collapse;width:100%;font-size:14px">
    <tr class="faint"><th style="text-align:left">Month</th><th>Lessons</th><th>Scenarios</th><th>Service hrs</th><th>Fitness results</th><th>Exams</th></tr>
    ${tl.map(m => `<tr style="border-top:1px solid var(--line)"><td>${esc(m.month)}</td><td style="text-align:center">${m.lessons}</td>
      <td style="text-align:center">${m.scenarios}</td><td style="text-align:center">${pgH(m.service_hours)}</td>
      <td style="text-align:center">${m.fitness_results}</td><td style="text-align:center">${m.exams}</td></tr>`).join('')}</table></div></div>`;
}

function printPortfolio(d, term) {
  const html = `<div style="font-family:Georgia,serif;color:#000">
    <div style="text-align:center"><div style="letter-spacing:.2em;font-weight:700">VANGUARD</div><h1 style="margin:4px 0">Cadet Development Portfolio</h1>
      <div style="font-size:18px">${esc(d.name)}${term ? ' · ' + esc(term) : ''}</div>
      <div style="font-size:12px">Printed ${esc(new Date().toLocaleDateString())}</div></div>
    ${progressHtml(d, true)}
    <p style="font-size:11px;margin-top:24px">Vanguard is designed to support JROTC instruction; it is not an official JROTC, military or school record.</p></div>`;
  let area = $('#printArea');
  if (!area) { area = document.createElement('div'); area.id = 'printArea'; document.body.appendChild(area); }
  area.innerHTML = html;
  window.print();
}

const pgTerm = () => { const d = new Date(); return `${d.getMonth() < 6 ? 'Spring' : 'Fall'} ${d.getFullYear()}`; };

loaders.progress = async () => {
  const body = $('#progressBody');
  const d = await api('/api/progress');
  if (d.not_cadet) {
    body.innerHTML = `<h2>My Progress</h2><div class="card"><p>Progress is kept for Cadets. ${STATUS.kind === 'instructor' ? 'Open a Cadet\'s progress from 🎓 Instructor → Cadets.' : ''}</p></div>`;
    return;
  }
  const ac = d.academics, sv = d.service;
  body.innerHTML = `<h2>My Progress</h2><p class="faint">Your growth over time — measured against yourself, never against anyone else.</p>
    <div class="card"><div class="row" style="flex-wrap:wrap;gap:20px">
      ${pgStat(ac.lessons_completed, 'lessons completed')}${pgStat(d.leadership.scenarios_completed, 'leadership scenarios')}
      ${pgStat(pgH(sv.verified_hours), 'service hours')}${pgStat(ac.cards_mastered, 'study cards mastered')}</div></div>
    ${progressHtml(d)}${timelineHtml(d.timeline)}
    <div class="card"><h3>🖨️ My portfolio</h3><p class="faint">A printable record of your growth. Your instructor chooses what it includes.</p>
      <button class="btn primary" id="pgPrint">Print my portfolio</button></div>`;
  $('#pgPrint').addEventListener('click', () => printPortfolio(d, pgTerm()));
  if (typeof cadetSurvey === 'function') cadetSurvey(body);                          // web/js/pilot.js
};

// ── Instructor: one Cadet's progress, recognition and the portfolio ──
async function instructorProgress(pid) {
  openView('progress');
  const body = $('#progressBody');
  body.innerHTML = '<p class="faint">Loading…</p>';
  const d = await api('/api/instructor/progress?id=' + encodeURIComponent(pid));
  if (d.error || d.status === 'waiting') {
    body.innerHTML = `<button class="btn small" id="pgBack">← Instructor</button><p>${esc(d.error || `${d.name} hasn't shared class records yet — they will the next time they sign in.`)}</p>`;
    $('#pgBack').onclick = () => openView('instructor');
    return;
  }
  d.recognition.forEach(r => { r._rm = `<button class="btn small" data-rmrec="${esc(r.id)}" style="margin-top:4px">Remove</button>`; });
  body.innerHTML = `<button class="btn small" id="pgBack">← Instructor</button>
    <h2 style="margin-top:12px">${esc(d.name)} — progress</h2>
    ${progressHtml(d)}${timelineHtml(d.timeline)}
    <div class="card"><h3>Add recognition or a comment</h3>
      <div class="row" style="flex-wrap:wrap;gap:8px"><select id="rcKind" aria-label="Kind" style="flex:1;min-width:150px">${Object.entries(d.kinds).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('')}</select>
        <input id="rcTitle" maxlength="120" placeholder="Title (e.g. Cadet of the Month)" aria-label="Title" style="flex:2;min-width:180px"></div>
      <textarea id="rcNote" rows="2" style="width:100%;margin-top:8px" placeholder="Note (optional)" aria-label="Note"></textarea>
      <button class="btn primary" id="rcAdd" style="margin-top:8px">Add</button><p class="faint" id="rcMsg" role="alert"></p>
      <p class="faint">${esc(d.name)} can see recognition and comments in My Progress.</p></div>
    <div class="card"><h3>🖨️ Portfolio</h3><p class="faint">Choose what printed portfolios include (for every Cadet), then print this one.</p>
      ${Object.entries(d.section_names).map(([k, v]) => `<label style="display:flex;gap:10px;align-items:center;min-height:40px"><input type="checkbox" data-sec="${k}" ${d.sections.includes(k) ? 'checked' : ''} style="width:22px;height:22px"> ${esc(v)}</label>`).join('')}
      <label for="pgTermIn">Term</label><input id="pgTermIn" value="${esc(pgTerm())}" maxlength="40">
      <button class="btn primary" id="pgPrintI" style="margin-top:8px">Print portfolio</button></div>`;
  $('#pgBack').onclick = () => { openView('instructor'); };
  $('#rcAdd').addEventListener('click', async () => {
    const r = await api('/api/instructor/recognition', { cadet: pid, kind: $('#rcKind').value, title: $('#rcTitle').value, note: $('#rcNote').value });
    if (r.error) $('#rcMsg').textContent = r.error; else instructorProgress(pid);
  });
  body.querySelectorAll('[data-rmrec]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Remove this?')) return;
    await api('/api/instructor/recognition', { cadet: pid, action: 'remove', id: b.dataset.rmrec }); instructorProgress(pid);
  }));
  body.querySelectorAll('[data-sec]').forEach(cb => cb.addEventListener('change', async () => {
    const r = await api('/api/instructor/portfolio-sections', { sections: [...body.querySelectorAll('[data-sec]:checked')].map(x => x.dataset.sec) });
    if (!r.error) d.sections = r.sections;
  }));
  $('#pgPrintI').addEventListener('click', () => printPortfolio(d, $('#pgTermIn').value));
}
