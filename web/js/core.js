'use strict';
// Shared: API calls, profiles and the PIN lock screen, text size, night mode, tabs, status.

const $ = s => document.querySelector(s);
const api = async (path, body) => {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (r.status === 401 && !['/api/unlock', '/api/recover', '/api/pin/recovery', '/api/pin/remove', '/api/pin/set', '/api/profiles/delete', '/api/profiles/create'].includes(path)) {
    showLock();                                   // session expired or locked
    throw new Error('locked');
  }
  return r.json();
};

// ── Profiles + PIN lock screen ──
// A recovery code is shown exactly once. It's the Soldier's spare key to their encrypted files.
function showRecoveryCode(code, done) {
  const o = document.createElement('div');
  o.style.cssText = 'position:fixed;inset:0;z-index:200;background:var(--bg);overflow:auto;padding:16px;display:grid;place-items:center';
  o.innerHTML = `<div class="card" style="width:100%;max-width:420px;text-align:center">
      <div style="font-size:28px">🔑</div><h2>Your recovery code</h2>
      <p>If you ever forget your PIN, this code is the <b>only</b> way back into your files.</p>
      <div style="font:700 24px ui-monospace,Consolas,monospace;letter-spacing:.08em;padding:14px;border:2px dashed var(--line);border-radius:10px;margin:12px 0;user-select:all">${esc(code)}</div>
      <p class="faint">Write it down and keep it somewhere safe — not on this device. It won't be shown again. Nobody, including whoever runs this device, can recover your files without your PIN or this code.</p>
      <label style="display:flex;gap:8px;align-items:center;justify-content:center"><input type="checkbox" id="rcOk" style="width:auto"> I wrote it down</label>
      <button class="btn primary" id="rcDone" style="width:100%;margin-top:10px" disabled>Continue</button></div>`;
  document.body.appendChild(o);
  o.querySelector('#rcOk').onchange = ev => { o.querySelector('#rcDone').disabled = !ev.target.checked; };
  o.querySelector('#rcDone').onclick = () => { o.remove(); done && done(); };
}

// Each Soldier on this device picks their profile and enters their PIN (if they set one).
async function showLock(msg) {
  if (document.getElementById('lockScreen')) return;
  const s = await (await fetch('/api/lock')).json();
  const d = document.createElement('div');
  d.id = 'lockScreen';
  d.style.cssText = 'position:fixed;inset:0;z-index:100;background:var(--bg);overflow:auto;padding:16px;display:grid;place-items:center';
  document.body.appendChild(d);
  const go = () => location.replace('/');
  const pick = () => {
    d.innerHTML = `<div class="card" style="width:100%;max-width:380px;text-align:center">
        <div style="font-size:28px">✦</div><h2>Who's using Vanguard?</h2>
        <div style="display:grid;gap:8px;margin:12px 0">${s.profiles.map(p =>
          `<button class="btn" data-p="${esc(p.id)}" style="text-align:left">${p.kind === 'guardian' ? '👪' : '👤'} ${esc(p.name)} ${p.has_pin ? '<span class="faint">🔒</span>' : ''}</button>`).join('')}</div>
        <button class="btn small" id="newProf">+ New profile</button>
        <p class="faint">${esc(msg || '')}</p></div>`;
    d.querySelectorAll('[data-p]').forEach(b => b.onclick = () => {
      const p = s.profiles.find(x => x.id === b.dataset.p);
      p.has_pin ? pinFor(p) : api('/api/unlock', { profile: p.id, pin: '' }).then(r => r.ok && go());
    });
    $('#newProf').onclick = newProfile;
  };
  const pinFor = p => {
    d.innerHTML = `<form class="card" id="unlockForm" style="width:100%;max-width:340px;text-align:center">
        <div style="font-size:28px">🔒</div><h2>${esc(p.name)}</h2>
        <input id="pinIn" type="password" inputmode="numeric" autocomplete="off" maxlength="12" placeholder="PIN" style="text-align:center;font-size:22px;letter-spacing:.3em">
        <button class="btn primary" style="width:100%;margin-top:10px">Unlock</button>
        <p class="faint" id="unlockMsg">${p.lockout ? `Too many wrong PINs. Try again in ${p.lockout} seconds.` : ''}</p>
        <button type="button" class="btn small" id="forgotPin">Forgot PIN?</button>
        ${s.profiles.length > 1 ? '<button type="button" class="btn small" id="backPick">← Someone else</button>' : ''}</form>`;
    $('#pinIn').focus();
    if ($('#backPick')) $('#backPick').onclick = pick;
    $('#forgotPin').onclick = () => recoverFor(p);
    $('#unlockForm').onsubmit = async ev => {
      ev.preventDefault();
      const r = await api('/api/unlock', { profile: p.id, pin: $('#pinIn').value });
      if (r.ok) go(); else { $('#unlockMsg').textContent = r.error; $('#pinIn').value = ''; }
    };
  };
  const recoverFor = p => {
    d.innerHTML = `<form class="card" id="recForm" style="width:100%;max-width:380px">
        <h2>🔑 Forgot your PIN?</h2>
        <p class="faint">Enter the recovery code you wrote down when you set your PIN, then choose a new PIN. Your files stay encrypted the whole time.</p>
        <label>Recovery code</label><input id="recCode" autocomplete="off" maxlength="40" placeholder="XXXXX-XXXXX-XXXXX-XXXXX" style="font-family:ui-monospace,Consolas,monospace;text-transform:uppercase">
        <label>New PIN (6–12 digits)</label><input id="recPin" type="password" inputmode="numeric" maxlength="12" autocomplete="off">
        <button class="btn primary" style="width:100%;margin-top:12px">Set new PIN</button>
        <p class="faint" id="recMsg">No recovery code? Restore your encrypted backup into a new profile, or ask for help — nobody can open these files without the PIN or the code.</p>
        <button type="button" class="btn small" id="recBack">← Back</button></form>`;
    $('#recCode').focus();
    $('#recBack').onclick = () => pinFor(p);
    $('#recForm').onsubmit = async ev => {
      ev.preventDefault();
      const r = await api('/api/recover', { profile: p.id, code: $('#recCode').value, pin: $('#recPin').value });
      if (r.ok) showRecoveryCode(r.recovery, go); else $('#recMsg').textContent = r.error;
    };
  };
  const newProfile = () => {
    d.innerHTML = `<form class="card" id="newForm" style="width:100%;max-width:380px">
        <h2>${s.profiles.length ? 'New profile' : 'Welcome to Vanguard'}</h2>
        <p class="faint">Your logbook, letters and progress stay in your own profile on this device.</p>
        <label>Your name</label><input id="npName" maxlength="40" autocomplete="off">
        <label>This profile is for</label><select id="npKind"><option value="cadet">A Cadet</option><option value="guardian">A parent or guardian</option><option value="instructor">An instructor</option></select>
        <div id="npAdmBox" hidden><label>Instructor PIN</label><input id="npAdm" type="password" inputmode="numeric" maxlength="12" autocomplete="off" placeholder="Set in 👤 Me by the instructor">
          <p class="faint">Instructor profiles need the Instructor PIN and their own PIN.</p></div>
        <label>PIN (6–12 digits)${s.profiles.length ? '' : ' — recommended'}</label>
        <input id="npPin" type="password" inputmode="numeric" maxlength="12" autocomplete="off" placeholder="${s.profiles.length ? 'Strongly recommended on a shared device' : 'Optional'}">
        <p class="faint">With a PIN, your files are encrypted on this device. You'll get a <b>recovery code</b> in case you ever forget it.</p>
        <button class="btn primary" style="width:100%;margin-top:12px">Create profile</button>
        <p class="faint" id="npMsg"></p>
        ${s.profiles.length ? '<button type="button" class="btn small" id="backPick">← Back</button>' : ''}</form>`;
    $('#npName').focus();
    if ($('#backPick')) $('#backPick').onclick = pick;
    $('#npKind').addEventListener('change', () => { $('#npAdmBox').hidden = $('#npKind').value !== 'instructor'; });
    $('#newForm').onsubmit = async ev => {
      ev.preventDefault();
      const r = await api('/api/profiles/create', { name: $('#npName').value, pin: $('#npPin').value, kind: $('#npKind').value, admin: $('#npAdm').value });
      if (r.ok) (r.recovery ? showRecoveryCode(r.recovery, go) : go()); else $('#npMsg').textContent = r.error;
    };
  };
  const want = new URLSearchParams(location.search);
  history.replaceState(null, '', '/');
  if (!s.profiles.length || want.has('new')) newProfile();
  else if (want.has('pick')) pick();
  else if (s.profiles.length === 1 && !s.profiles[0].has_pin) {
    const r = await api('/api/unlock', { profile: s.profiles[0].id, pin: '' });
    if (r.ok) { go(); return; }
    pick();
  } else if (s.profiles.length === 1) pinFor(s.profiles[0]);
  else pick();
}
// The app starts only once a profile is unlocked.
const unlocked = (async () => {
  // Wait until every script in web/js/ has run, so nothing here races ahead of a later file.
  if (document.readyState === 'loading') await new Promise(r => document.addEventListener('DOMContentLoaded', r));
  const s = await (await fetch('/api/lock')).json();
  if (!s.unlocked) { showLock(); return null; }
  return s;
})();
const heightText = n => (+n > 0 ? `${Math.floor(+n / 12)}'${+n % 12}"` : '');   // inches -> 5'10"
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Small, safe Markdown: escape first, then bold / italic / code / lists / paragraphs.
function md(text) {
  const lines = esc(text).split('\n');
  let html = '', inList = false, para = [];
  const inline = s => s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(^|\W)\*(?!\s)(.+?)\*(?=\W|$)/g, '$1<i>$2</i>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const flush = () => { if (para.length) { html += '<p>' + inline(para.join('<br>')) + '</p>'; para = []; } };
  for (const l of lines) {
    const li = l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
    if (li) { flush(); if (!inList) { html += '<ul>'; inList = true; } html += '<li>' + inline(li[1]) + '</li>'; continue; }
    if (inList) { html += '</ul>'; inList = false; }
    if (!l.trim()) { flush(); continue; }
    const h = l.match(/^#{1,4}\s+(.*)/);
    if (h) { flush(); html += '<p><b>' + inline(h[1]) + '</b></p>'; continue; }
    para.push(l);
  }
  flush(); if (inList) html += '</ul>';
  return html;
}

// ── large text (remembered on this device) ──
(() => {
  const btn = $('#textBtn');
  const apply = big => { document.documentElement.dataset.text = big ? 'large' : ''; btn.setAttribute('aria-pressed', String(big)); btn.textContent = big ? 'A−' : 'A+'; };
  let big = false;
  try { big = localStorage.getItem('vanguard-text') === 'large'; } catch (e) {}
  apply(big);
  btn.onclick = () => { big = !big; apply(big); try { localStorage.setItem('vanguard-text', big ? 'large' : ''); } catch (e) {} };
})();

// Icon-only buttons (✕, 🔊, 🎤 …) get a spoken name for screen readers from their title.
new MutationObserver(() => {
  document.querySelectorAll('button[title]:not([aria-label])').forEach(b => {
    if (!/[A-Za-z]{2}/.test(b.textContent)) b.setAttribute('aria-label', b.title);
  });
}).observe(document.body, { childList: true, subtree: true });

// ── red-light night mode (remembered on this device) ──
(() => {
  const btn = $('#modeBtn'), meta = document.querySelector('meta[name=theme-color]');
  const apply = red => {
    document.documentElement.dataset.mode = red ? 'red' : '';
    btn.innerHTML = red ? '☀️<span class="lbl"> Day</span>' : '🔴<span class="lbl"> Night</span>';
    btn.setAttribute('aria-pressed', String(red));
    meta.content = red ? '#000000' : '#0f120e';
  };
  let red = false;
  try { red = localStorage.getItem('vanguard-mode') === 'red'; } catch (e) {}
  apply(red);
  btn.onclick = () => {
    red = !red; apply(red);
    try { localStorage.setItem('vanguard-mode', red ? 'red' : ''); } catch (e) {}
  };
})();

// ── tabs ──
const loaders = {};
// Shows one view. Header buttons (Ask, Me, Instructor) open views that aren't tabs; then no tab is lit.
function openView(v, pane) {
  document.querySelectorAll('#tabs button').forEach(x => x.classList.toggle('on', x.dataset.v === v && (x.dataset.pane || '') === (pane || '')));
  document.querySelectorAll('.view').forEach(x => x.classList.toggle('on', x.id === v));
  if (pane && typeof showPane === 'function') showPane(pane); else loaders[v] && loaders[v]();
}
$('#tabs').addEventListener('click', e => {
  const b = e.target.closest('button'); if (b) openView(b.dataset.v, b.dataset.pane);
});
document.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', () => openView(b.dataset.open)));

// ── status ──
let STATUS = {};
const FAMILY_SUGGEST = ['What is JROTC?', 'What does LET level mean?', 'What are the Army Values?',
  'What do military ranks mean?', 'How can I support my Cadet?']
let landed = false;
async function refreshStatus() {
  STATUS = await api('/api/status');
  if (!landed && STATUS.kind === 'instructor') openView('instructor');   // instructors start in their tools
  landed = true;
  if ((document.body.dataset.kind = STATUS.kind || 'cadet') === 'guardian') {          // family member's profile
    $('#suggest').innerHTML = FAMILY_SUGGEST.map(q => `<button>${esc(q)}</button>`).join('');
    const hi = document.querySelector('#thread .msg.ai p');
    if (hi) hi.textContent = "I'm Vanguard — here to help you understand JROTC and support your Cadet. Ask me anything. Everything stays on this device.";
  }
  const e = STATUS.engine, el = $('#engine');
  const online = e.online_enabled && e.online_keys.length;
  el.innerHTML = e.model
    ? `<span class="dot ok"></span><span>Offline AI: ${esc(e.model)}${online ? ' + online' : ''}</span>`
    : online ? '<span class="dot ok"></span><span>Online AI</span>'
             : '<span class="dot warn"></span><span>Library only (no AI model)</span>';
  const p = STATUS.profile || {};
  $('#hello').textContent = p.name ? `· ${p.rank ? p.rank + ' ' : ''}${p.name}` : '';
}
