// Service learning (Phase 7). Cadets: hours, a log form (pick an instructor project or type one), each entry's
// review status. Instructors: entries waiting for review (verify / return with a note), Cadets' totals, and the
// program's service projects. Phone-first; listeners in JS.
'use strict';

const SV_STATUS = { pending: '⏳ Waiting for review', verified: '✅ Verified', returned: '↩ Returned' };
const svDate = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
const svHours = h => `${+h % 1 ? (+h).toFixed(2).replace(/0$/, '') : +h} hr${+h === 1 ? '' : 's'}`;

async function serviceCadet(box) {
  const d = await api('/api/service');
  if (d.not_cadet) { box.innerHTML = '<p class="faint">Service hours are logged by Cadets. Instructors review them in 🎓 Instructor.</p>'; return; }
  const t = d.totals, editing = box.dataset.edit || '';
  const ed = editing ? d.entries.find(e => e.id === editing) : null;
  box.innerHTML = `<div class="row" style="flex-wrap:wrap;gap:18px;margin:8px 0">
      <div><div style="font-size:28px;font-weight:700">${svHours(t.verified_hours)}</div><div class="faint">verified</div></div>
      <div><div style="font-size:20px;font-weight:700">${svHours(t.pending_hours)}</div><div class="faint">waiting for review</div></div>
      <div><div style="font-size:20px;font-weight:700">${t.projects}</div><div class="faint">project${t.projects === 1 ? '' : 's'} verified</div></div></div>
    <details ${ed || !d.entries.length ? 'open' : ''}><summary><b>${ed ? 'Fix this entry' : '＋ Log service'}</b></summary>
      ${ed && ed.note ? `<p style="margin:8px 0"><b>Your instructor's note:</b> ${esc(ed.note)}</p>` : ''}
      <label for="svProj">Project</label><select id="svProj">${d.projects.map(p => `<option value="${esc(p.id)}" ${ed && ed.project_id === p.id ? 'selected' : ''}>${esc(p.title)}${p.date ? ' · ' + esc(p.date) : ''}</option>`).join('')}
        <option value="" ${ed && !ed.project_id ? 'selected' : ''}>Something else…</option></select>
      <div id="svOther"><label for="svName">What was the project?</label><input id="svName" maxlength="80" value="${esc(ed && !ed.project_id ? ed.project : '')}" placeholder="e.g. Food drive">
        <label for="svOrg">Organization</label><input id="svOrg" maxlength="80" value="${esc(ed ? ed.organization : '')}" placeholder="e.g. Church food pantry"></div>
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <div style="flex:1;min-width:140px"><label for="svDate">Date</label><input id="svDate" type="date" max="${svDate()}" value="${esc(ed ? ed.date : svDate())}"></div>
        <div style="flex:1;min-width:100px"><label for="svHrs">Hours</label><input id="svHrs" inputmode="decimal" value="${esc(ed ? ed.hours : '')}" placeholder="e.g. 4"></div></div>
      <label for="svRole">Your role</label><input id="svRole" maxlength="60" value="${esc(ed ? ed.role : '')}" placeholder="e.g. Team lead, volunteer, organizer">
      <label for="svRefl">${esc(d.prompt)}</label><textarea id="svRefl" rows="3" style="width:100%">${esc(ed ? ed.reflection : '')}</textarea>
      <div class="row" style="gap:8px;margin-top:8px"><button class="btn primary" id="svSave">${ed ? 'Send for review again' : 'Send to my instructor'}</button>
        ${ed ? '<button class="btn small" id="svCancel">Cancel</button>' : ''}</div>
      <p class="faint" id="svMsg" role="alert"></p></details>
    ${d.entries.map(e => `<div class="card" style="margin:8px 0;padding:12px">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:6px"><b>${esc(e.project)}</b><span>${SV_STATUS[e.status] || ''}</span></div>
      <div class="faint">${esc(e.date)} · ${svHours(e.hours)}${e.role ? ' · ' + esc(e.role) : ''}${e.organization ? ' · ' + esc(e.organization) : ''}</div>
      <div style="margin-top:6px;white-space:pre-wrap">${esc(e.reflection)}</div>
      ${e.note ? `<div style="margin-top:6px"><b>Instructor:</b> ${esc(e.note)}</div>` : ''}
      ${e.status !== 'verified' ? `<div class="row" style="gap:6px;margin-top:8px"><button class="btn small" data-svedit="${esc(e.id)}">Edit</button>
        <button class="btn small" data-svdel="${esc(e.id)}">Delete</button></div>` : ''}</div>`).join('')}`;
  const other = () => { $('#svOther').hidden = !!$('#svProj').value; };
  $('#svProj').addEventListener('change', other); other();
  $('#svSave').addEventListener('click', async () => {
    const body = { id: editing, project_id: $('#svProj').value, project: $('#svName').value, organization: $('#svOrg').value,
      date: $('#svDate').value, hours: $('#svHrs').value, role: $('#svRole').value, reflection: $('#svRefl').value };
    const r = await api(editing ? '/api/service/edit' : '/api/service/add', body);
    if (r.error) { $('#svMsg').textContent = r.error; return; }
    box.dataset.edit = ''; serviceCadet(box);
  });
  if ($('#svCancel')) $('#svCancel').addEventListener('click', () => { box.dataset.edit = ''; serviceCadet(box); });
  box.querySelectorAll('[data-svedit]').forEach(b => b.addEventListener('click', () => { box.dataset.edit = b.dataset.svedit; serviceCadet(box); }));
  box.querySelectorAll('[data-svdel]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Delete this entry?')) return;
    const r = await api('/api/service/delete', { id: b.dataset.svdel });
    if (r.error) alert(r.error); else serviceCadet(box);
  }));
}

// ── Instructor: Service section on the Instructor screen ──
async function instructorService(body) {
  const d = await api('/api/instructor/service');
  if (d.error) return;
  const sec = document.createElement('div');
  body.appendChild(sec);
  const waiting = d.cadets.flatMap(c => c.entries.filter(e => e.status === 'pending').map(e => ({ ...e, cadet: c.id, name: c.name })));
  sec.innerHTML = `<div class="card"><h3>🤝 Service — ${waiting.length} waiting for review</h3>
      ${waiting.map(e => `<div class="card" style="margin:8px 0;padding:12px" data-entry="${esc(e.id)}" data-cadet="${esc(e.cadet)}">
        <b>${esc(e.name)}</b> — ${esc(e.project)} <span class="faint">${esc(e.date)} · ${svHours(e.hours)}${e.role ? ' · ' + esc(e.role) : ''}${e.organization ? ' · ' + esc(e.organization) : ''}</span>
        <div style="margin-top:6px;white-space:pre-wrap">${esc(e.reflection)}</div>
        <input data-note placeholder="Note (needed to return it)" maxlength="500" aria-label="Note to ${esc(e.name)}" style="margin-top:8px">
        <div class="row" style="gap:6px;margin-top:6px"><button class="btn small primary" data-rv="verify">✅ Verify</button><button class="btn small" data-rv="return">↩ Return</button></div>
        <p class="faint" data-rvmsg role="alert"></p></div>`).join('') || '<p class="faint">Nothing waiting. 👍</p>'}
      <h4>Hours by Cadet</h4>
      ${d.cadets.map(c => `<div class="row" style="justify-content:space-between;gap:8px;margin:4px 0"><span>${esc(c.name)}</span>
        <span class="faint">${c.shared ? `${svHours(c.totals.verified_hours)} verified · ${svHours(c.totals.pending_hours)} waiting` : 'waiting to share'}</span></div>`).join('') || '<p class="faint">No Cadets yet.</p>'}</div>
    <div class="card"><h3>Service projects</h3>
      <p class="faint">Post a project so Cadets can pick it when they log hours.</p>
      ${d.projects.map(p => `<div class="row" style="justify-content:space-between;gap:8px;margin:6px 0">
        <span><b>${esc(p.title)}</b> <span class="faint">${[p.date, p.organization, p.hours ? svHours(p.hours) : ''].filter(Boolean).map(esc).join(' · ')}</span></span>
        <button class="btn small" data-rmproj="${esc(p.id)}">Remove</button></div>`).join('')}
      <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
        <input id="pTitle" placeholder="Project (e.g. Community Cleanup)" maxlength="80" aria-label="Project" style="flex:2;min-width:180px">
        <input id="pOrg" placeholder="Organization" maxlength="80" aria-label="Organization" style="flex:1;min-width:140px">
        <input id="pDate" type="date" aria-label="Date" style="flex:1;min-width:140px">
        <button class="btn primary" id="pAdd">Post project</button></div><p class="faint" id="pMsg" role="alert"></p></div>`;
  sec.querySelectorAll('[data-entry]').forEach(card => card.querySelectorAll('[data-rv]').forEach(b => b.addEventListener('click', async () => {
    const r = await api('/api/instructor/service/review', { cadet: card.dataset.cadet, id: card.dataset.entry, action: b.dataset.rv,
      note: card.querySelector('[data-note]').value });
    if (r.error) { card.querySelector('[data-rvmsg]').textContent = r.error; return; }
    card.innerHTML = `<p style="margin:0">${b.dataset.rv === 'verify' ? '✅ Verified' : '↩ Returned'}: ${esc(r.project)}</p>`;
  })));
  $('#pAdd').addEventListener('click', async () => {
    const r = await api('/api/instructor/service/project', { title: $('#pTitle').value, organization: $('#pOrg').value, date: $('#pDate').value });
    if (r.error) $('#pMsg').textContent = r.error; else loaders.instructor();
  });
  sec.querySelectorAll('[data-rmproj]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Remove this project from the list? Cadets keep the hours they logged.')) return;
    await api('/api/instructor/service/project', { action: 'remove', id: b.dataset.rmproj }); loaders.instructor();
  }));
}
