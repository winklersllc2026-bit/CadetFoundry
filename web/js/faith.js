'use strict';
// Faith tab.

// ── FAITH ──
const faithBody = $('#faithBody');
loaders.faith = async () => {
  const cat = await api('/api/faith/catalog');
  if (!cat.installed.length) {
    faithBody.innerHTML = `<h2>Faith</h2><div class="card"><p>No scripture texts are installed on this device yet.</p>
      <p class="faint">An administrator can add them with <code>python tools/fetch_faith.py</code> (needs internet once). Everything stays optional — you choose what to use.</p></div>`;
    return;
  }
  const mine = new Set((STATUS.profile && STATUS.profile.faith_texts || '').split(',').filter(Boolean));
  const opts = cat.installed.map(t => `<option value="${esc(t.id)}" ${mine.has(t.id) ? 'selected' : ''}>${esc(t.name)} — ${esc(t.tradition)}</option>`).join('');
  faithBody.innerHTML = `<h2>Faith</h2>
    <div class="card"><label for="ftr">Text</label><select id="ftr">${opts}</select>
      <label for="fref">Look up a passage</label>
      <div class="row"><input id="fref" placeholder="e.g. John 3:16, Psalm 23, Gita 2:47, Quran 2:255" style="flex:1"><button class="btn primary" id="fgo">Read</button></div>
      <div class="row" style="margin-top:8px"><button class="btn small" id="fcmp">Compare all translations</button><button class="btn small" id="fsearch">Search for words</button><button class="btn small" id="fask">Ask Vanguard about it</button></div>
      <div class="faint" style="margin-top:8px">Optional and personal. Installed: ${cat.installed.length} texts from ${new Set(cat.installed.map(t => t.tradition)).size} traditions. Public-domain translations.</div>
    </div><div id="fout"></div><div id="fplans"></div>`;
  const plans = await api('/api/faith/plans');
  const showPlans = () => {
    $('#fplans').innerHTML = plans.length ? `<div class="card"><h3>Reading plans</h3>${plans.map(p => `
      <div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding:8px 0">
        <span>${esc(p.name)}<br><span class="faint">${p.done} of ${p.days} days</span></span>
        <button class="btn small" data-plan="${esc(p.id)}">${p.done ? 'Continue' : 'Start'}</button></div>`).join('')}</div>` : '';
    $('#fplans').querySelectorAll('[data-plan]').forEach(b => b.onclick = () => openPlan(b.dataset.plan));
  };
  const openPlan = async (pid, day) => {
    const r = await api(`/api/faith/plan?id=${encodeURIComponent(pid)}` + (day !== undefined ? `&day=${day}` : ''));
    if (r.error) { $('#fout').innerHTML = `<div class="card">${esc(r.error)}</div>`; return; }
    $('#fout').innerHTML = `<div class="card"><div class="tr-name">${esc(r.plan)} — day ${r.day + 1} of ${r.days}</div><div class="faint">${esc(r.text)}</div>
      ${r.verses.map(v => `<p class="verse"><b>${esc(v.ref)}</b>${esc(v.text)}</p>`).join('')}
      <div class="row">${r.day > 0 ? '<button class="btn small" id="pPrev">← Previous</button>' : ''}
        <button class="btn primary small" id="pDone">${r.done ? '✓ Read' : 'Mark as read'}</button>
        ${r.day + 1 < r.days ? '<button class="btn small" id="pNext">Next →</button>' : ''}</div></div>`;
    $('#fout').scrollIntoView({ behavior: 'smooth' });
    if ($('#pPrev')) $('#pPrev').onclick = () => openPlan(pid, r.day - 1);
    if ($('#pNext')) $('#pNext').onclick = () => openPlan(pid, r.day + 1);
    $('#pDone').onclick = async () => { await api('/api/faith/plan/done', { id: pid, day: r.day });
      const p = plans.find(x => x.id === pid); if (p && !r.done) p.done++; showPlans(); openPlan(pid, Math.min(r.day + 1, r.days - 1)); };
  };
  showPlans();
  const out = $('#fout'), tr = () => $('#ftr').value, ref = () => $('#fref').value.trim();
  const render = (res, title) => {
    if (res.error) { out.innerHTML = `<div class="card">${esc(res.error)}</div>`; return; }
    out.innerHTML = res.results.map(r => `<div class="card"><div class="tr-name">${esc(r.name)} <span class="chip">${esc(r.tradition)}</span></div>
      ${r.verses.length ? r.verses.map(v => `<p class="verse"><b>${esc(v.ref)}</b>${esc(v.text)}</p>`).join('') : '<p class="faint">Not found in this text.</p>'}</div>`).join('') || `<div class="empty">${esc(title)}: nothing found.</div>`;
  };
  $('#fgo').onclick = async () => render(await api(`/api/faith/lookup?ref=${encodeURIComponent(ref())}&ids=${encodeURIComponent(tr())}`), ref());
  $('#fref').onkeydown = e => { if (e.key === 'Enter') $('#fgo').click(); };
  $('#fcmp').onclick = async () => render(await api(`/api/faith/lookup?ref=${encodeURIComponent(ref())}&compare=1&ids=${encodeURIComponent(tr())}`), ref());
  $('#fsearch').onclick = async () => render(await api(`/api/faith/search?q=${encodeURIComponent(ref())}&ids=${encodeURIComponent(tr())}`), ref());
  $('#fask').onclick = () => { if (!ref()) return; document.querySelector('[data-v=ask]').click(); send(`Help me understand ${ref()}`); };
};
