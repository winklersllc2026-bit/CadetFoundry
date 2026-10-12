'use strict';
// The class Join screen (/join): what Start Classroom opens on the projector. A big QR code and the address Cadets
// type, plus -- for an instructor with class records open -- a unit's join code, built into the QR code so a Cadet
// who scans it lands in the right class. Listeners in JS (the page's security policy blocks inline handlers).
(() => {
  const box = document.getElementById('join');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let KEY = 'cadetfoundry-join-unit', unit = '';
  try { unit = localStorage.getItem(KEY) || ''; } catch (e) { }

  async function draw() {
    let c;
    try { c = await (await fetch('/api/classroom')).json(); } catch (e) { return; }
    if (!c.lan) {
      box.innerHTML = `<h1>Phones can't join yet</h1>
        <p class="lead">Cadet Foundry is open on this computer only.</p>
        <div class="card"><p class="big">To let Cadets join from their phones:</p>
          <ol><li>Open Cadet Foundry and sign in as the instructor.</li><li>On your Home screen, press <b>📱 Open class to phones</b>.</li></ol></div>
        <div class="row"><a class="btn" href="/">Open Cadet Foundry</a></div>`;
      return;
    }
    const units = c.units || [];
    if (unit && !units.some(u => u.id === unit)) unit = '';
    if (!unit && units.length === 1) unit = units[0].id;
    const u = units.find(x => x.id === unit);
    const base = c.urls[0] || '';
    const target = base && u ? `${base}?join=${encodeURIComponent(u.code)}` : base;
    box.innerHTML = `<h1>Join this class</h1>
      <p class="lead">Your work stays on this computer — nothing goes to the internet.</p>
      ${base ? `<div class="grid">
        <div class="qr" id="qr">${QR.svg(target, 360)}</div>
        <div>
          <div class="card"><ol>
            <li>Join the <b>same Wi-Fi</b> as this computer.</li>
            <li>Scan the code with your phone's camera — or type:<div class="addr">${esc(base.replace(/\/$/, ''))}</div></li>
            <li>Choose your name and a PIN. That's it.</li></ol></div>
          ${units.length ? `<div class="card"><label class="faint" for="unitPick">Join code for</label>
            <div class="row"><select id="unitPick">${units.length > 1 ? '<option value="">No class (Cadets pick later)</option>' : ''}${units.map(x =>
              `<option value="${esc(x.id)}" ${x.id === unit ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>
            ${u ? `<div class="code" style="margin-top:8px">${esc(u.code)}</div>
              <p class="faint">Built into the QR code. Cadets who type the address enter it when they sign up.</p>` : ''}</div>`
            : c.local ? `<div class="card"><p class="big" style="margin:0 0 6px">Put Cadets in your class automatically</p>
              <p class="faint" style="margin:0 0 12px">Make your class once. Its join code then goes into this QR code, and every Cadet who scans it lands in your class.</p>
              <a class="btn primary-link" href="/?go=class" target="_blank" rel="noopener">Set up my class →</a></div>` : ''}
          ${c.local && (c.no_pin || []).length ? `<div class="card warn"><b>⚠ No PIN yet:</b> ${c.no_pin.map(esc).join(', ')}
            <p class="faint" style="margin:6px 0 0">Phones can't open ${c.no_pin.length === 1 ? 'this profile' : 'these profiles'} until ${c.no_pin.length === 1 ? 'it has' : 'they have'} a PIN.
            They still open on this computer: sign in, then 👤 Me → Security → Set a PIN.</p></div>` : ''}
          <p class="faint">${c.cadets} Cadet profile${c.cadets === 1 ? '' : 's'} on this Cadet Foundry.
            ${c.urls.length > 1 ? `Other addresses for this computer: ${c.urls.slice(1).map(x => esc(x.replace(/\/$/, ''))).join(', ')}` : ''}</p>
        </div></div>`
      : `<div class="card"><p class="big">This computer isn't on a network.</p><p>Connect it to Wi-Fi or turn on its hotspot, then reload this page.</p></div>`}
      <div class="row" style="margin-top:18px">
        ${base ? '<button class="primary" id="copy">Copy address</button>' : ''}
        <a class="btn" href="/" target="_blank" rel="noopener">Open Cadet Foundry</a>
        ${c.local ? '<button class="end" id="end">End class</button>' : ''}</div>
      <p class="faint" id="msg" role="status"></p>`;
    const pick = document.getElementById('unitPick');
    if (pick) pick.addEventListener('change', () => { unit = pick.value; try { localStorage.setItem(KEY, unit); } catch (e) { } draw(); });
    const copy = document.getElementById('copy');
    if (copy) copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(target); document.getElementById('msg').textContent = 'Copied.'; }
      catch (e) { document.getElementById('msg').textContent = target; }
    });
    const end = document.getElementById('end');
    if (end) end.addEventListener('click', async () => {
      if (!confirm('End class? Cadet Foundry closes for everyone. Everyone\'s work is already saved.')) return;
      const r = await fetch('/api/quit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!r.ok) { document.getElementById('msg').textContent = (await r.json()).error || 'Sign in to Cadet Foundry first, then try again.'; return; }
      clearInterval(timer);
      box.innerHTML = '<h1>Class is closed</h1><p class="lead">Everyone\'s work is saved. You can close this window.</p>';
    });
  }
  draw();
  const timer = setInterval(() => { if (!document.activeElement || document.activeElement.tagName !== 'SELECT') draw(); }, 15000);
})();
