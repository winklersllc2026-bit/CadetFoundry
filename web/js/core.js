'use strict';
// Shared: API calls, profiles and the PIN lock screen, text size, night mode, tabs, status.

const $ = s => document.querySelector(s);
const api = async (path, body) => {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (r.status === 401 && !['/api/unlock', '/api/recover', '/api/pin/recovery', '/api/pin/remove', '/api/pin/set', '/api/profiles/delete', '/api/profiles/create', '/api/join'].includes(path)) {
    showLock();                                   // session expired or locked
    throw new Error('locked');
  }
  const copy = r.clone();
  try {
    return await r.json();
  } catch (e) {                                   // not JSON (a refusal or an error page): say so, never fail silently
    const text = (await copy.text().catch(() => '')).trim().slice(0, 160);
    return { ok: false, error: `Cadet Foundry couldn't do that (${r.status}${text ? ': ' + text : ''}).` };
  }
};

// ── Profiles + PIN lock screen ──
// A backup code is shown exactly once. It's the spare key to a profile's protected files.
function showRecoveryCode(code, done) {
  const o = document.createElement('div');
  o.style.cssText = 'position:fixed;inset:0;z-index:200;background:var(--bg);overflow:auto;padding:16px;display:grid;place-items:center';
  o.innerHTML = `<div class="card" style="width:100%;max-width:420px;text-align:center">
      <div style="font-size:28px">🔑</div><h2>Your backup code</h2>
      <p>If you ever forget your PIN, this code is the <b>only</b> way back in.</p>
      <div style="font:700 24px ui-monospace,Consolas,monospace;letter-spacing:.08em;padding:14px;border:2px dashed var(--line);border-radius:10px;margin:12px 0;user-select:all">${esc(code)}</div>
      <p class="faint">Write it down and keep it somewhere safe — not on this device. It won't be shown again. Nobody, not even your instructor, can open your files without your PIN or this code.</p>
      <label style="display:flex;gap:8px;align-items:center;justify-content:center"><input type="checkbox" id="rcOk" style="width:auto"> I wrote it down</label>
      <button class="btn primary" id="rcDone" style="width:100%;margin-top:10px" disabled>Continue</button></div>`;
  document.body.appendChild(o);
  o.querySelector('#rcOk').onchange = ev => { o.querySelector('#rcDone').disabled = !ev.target.checked; };
  o.querySelector('#rcDone').onclick = () => { o.remove(); done && done(); };
}

const PIN_INPUT = (id, ph) => `<input id="${id}" type="password" inputmode="numeric" maxlength="12" autocomplete="new-password" placeholder="${ph}"
  style="font-size:20px;letter-spacing:.2em">`;

// Who's using Cadet Foundry: pick your name and type your PIN; a new Cadet joins in about 30 seconds (name, PIN, done);
// the very first time on the instructor's computer, a short setup walks the instructor through it.
async function showLock(msg) {
  if (document.getElementById('lockScreen')) return;
  const s = await (await fetch('/api/lock')).json();
  const d = document.createElement('div');
  d.id = 'lockScreen';
  d.style.cssText = 'position:fixed;inset:0;z-index:100;background:var(--bg);overflow:auto;padding:16px;display:grid;place-items:center';
  document.body.appendChild(d);
  const go = () => location.replace('/');
  const want = new URLSearchParams(location.search);
  const joinCode = (want.get('join') || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 12);
  history.replaceState(null, '', '/');
  // a demo box says so, and any Cadet Foundry with installers on it offers them (both on every sign-in screen)
  const extras = (s.demo ? '<p class="faint" style="border-top:1px solid var(--line);padding-top:10px;text-align:center">🧪 <b>Demo unit.</b> This small, portable Cadet Foundry runs on a Raspberry Pi — about 10 Cadets at a time. Please sign in a few at a time.</p>' : '')
    + (s.downloads ? '<p style="margin:6px 0 0;text-align:center"><a href="/download" style="color:var(--tan)">⬇ Get Cadet Foundry for your own computer</a></p>' : '');
  const pinRule = s.lan || s.profiles.length ? 'required' : 'recommended';
  const pick = () => {
    d.innerHTML = `<div class="card" style="width:100%;max-width:400px;text-align:center">
        <div style="font-size:28px">✦</div><h2>Who's using Cadet Foundry?</h2>
        <button class="btn primary" id="newProf" style="width:100%;min-height:52px;font-size:18px">I'm new — join</button>
        <p class="faint" style="margin:14px 0 6px">Or tap your name:</p>
        <div style="display:grid;gap:8px;margin:0 0 12px">${s.profiles.map(p =>
          `<button class="btn" data-p="${esc(p.id)}" style="text-align:left;min-height:48px">${p.kind === 'guardian' ? '👪' : p.kind === 'instructor' ? '🎓' : '👤'} ${esc(p.name)} ${p.has_pin ? '<span class="faint">🔒</span>' : ''}</button>`).join('')}</div>
        <p class="faint">${esc(msg || '')}</p>${extras}
        ${s.on_this_computer && !s.sample ? '<button class="btn small" id="pickSample" style="margin-top:6px">🧪 See a sample class</button><p class="faint" id="pickSampleMsg" role="status"></p>' : ''}</div>`;
    if ($('#pickSample')) $('#pickSample').onclick = () => startSample($('#pickSample'), $('#pickSampleMsg'));
    d.querySelectorAll('[data-p]').forEach(b => b.onclick = () => {
      const p = s.profiles.find(x => x.id === b.dataset.p);
      p.has_pin ? pinFor(p) : api('/api/unlock', { profile: p.id, pin: '' }).then(r => r.ok && go());
    });
    $('#newProf').onclick = () => newProfile();
  };
  const pinFor = p => {
    d.innerHTML = `<form class="card" id="unlockForm" style="width:100%;max-width:340px;text-align:center">
        <div style="font-size:28px">🔒</div><h2>${esc(p.name)}</h2>
        <label for="pinIn">Your PIN</label>
        <input id="pinIn" type="password" inputmode="numeric" autocomplete="off" maxlength="12" style="text-align:center;font-size:22px;letter-spacing:.3em">
        <button class="btn primary" style="width:100%;margin-top:10px">Sign in</button>
        <p class="faint" id="unlockMsg" role="alert">${p.lockout ? `Too many wrong PINs. Wait ${p.lockout} seconds and try again.` : ''}</p>
        <button type="button" class="btn small" id="forgotPin">Forgot your PIN?</button>
        ${s.profiles.length > 1 ? '<button type="button" class="btn small" id="backPick">← Someone else</button>' : ''}</form>`;
    $('#pinIn').focus();
    if ($('#backPick')) $('#backPick').onclick = pick;
    $('#forgotPin').onclick = () => recoverFor(p);
    $('#unlockForm').onsubmit = async ev => {
      ev.preventDefault();
      const btn = $('#unlockForm button.primary');
      btn.disabled = true;
      $('#unlockMsg').textContent = 'Signing in…';
      let r;
      try {
        r = await api('/api/unlock', { profile: p.id, pin: $('#pinIn').value });
      } catch (e) {                               // no answer at all: Cadet Foundry stopped, or the network dropped
        r = { ok: false, error: "Couldn't reach Cadet Foundry. Is its window still open on the instructor's computer?" };
      }
      btn.disabled = false;
      if (r.ok) { $('#unlockMsg').textContent = 'Opening…'; go(); } else { $('#unlockMsg').textContent = r.error || 'That PIN didn’t work.'; $('#pinIn').value = ''; }
    };
  };
  const recoverFor = p => {
    d.innerHTML = `<form class="card" id="recForm" style="width:100%;max-width:380px">
        <h2>🔑 Forgot your PIN?</h2>
        <p class="faint">Type the backup code you wrote down when you made your PIN, then choose a new PIN. Your files stay protected the whole time.</p>
        <label for="recCode">Backup code</label><input id="recCode" autocomplete="off" maxlength="40" placeholder="XXXXX-XXXXX-XXXXX-XXXXX" style="font-family:ui-monospace,Consolas,monospace;text-transform:uppercase">
        <label for="recPin">New PIN (6–12 digits)</label>${PIN_INPUT('recPin', '')}
        <button class="btn primary" style="width:100%;margin-top:12px">Set new PIN</button>
        <p class="faint" id="recMsg" role="alert">No backup code? Ask your instructor for help — nobody can open these files without the PIN or the code.</p>
        <button type="button" class="btn small" id="recBack">← Back</button></form>`;
    $('#recCode').focus();
    $('#recBack').onclick = () => pinFor(p);
    $('#recForm').onsubmit = async ev => {
      ev.preventDefault();
      const r = await api('/api/recover', { profile: p.id, code: $('#recCode').value, pin: $('#recPin').value });
      if (r.ok) showRecoveryCode(r.recovery, go); else $('#recMsg').textContent = r.error;
    };
  };
  // A new profile: name, PIN, (join code) -- everything else is optional, under "More options" or later in 👤 Me.
  const newProfile = (kind = 'cadet') => {
    d.innerHTML = `<form class="card" id="newForm" style="width:100%;max-width:400px">
        <h2>${s.profiles.length ? 'Join Cadet Foundry' : 'Welcome to Cadet Foundry'}</h2>
        <p class="faint">Your work stays in your own profile on this device. It takes about 30 seconds.</p>
        <label for="npName">What's your name?</label><input id="npName" maxlength="40" autocomplete="off" placeholder="First and last name">
        <label for="npPin">Choose a PIN (6–12 digits)${pinRule === 'recommended' ? ' — recommended' : ''}</label>${PIN_INPUT('npPin', '')}
        <label for="npPin2">Type it again</label>${PIN_INPUT('npPin2', '')}
        <p class="faint">Only you will know it. You'll use it to sign in.</p>
        <div id="npJoinBox"><label for="npJoin">Join code from your instructor <span class="faint">(if you have one)</span></label>
          <input id="npJoin" maxlength="12" autocomplete="off" value="${esc(joinCode)}" placeholder="e.g. K7M2QD" style="font-family:ui-monospace,Consolas,monospace;text-transform:uppercase;letter-spacing:.15em">
          <p class="faint" id="npJoinName" role="status"></p></div>
        <details id="npMore" ${kind !== 'cadet' ? 'open' : ''}><summary class="faint" style="cursor:pointer;min-height:36px">More options</summary>
          <label for="npKind">This profile is for</label><select id="npKind"><option value="cadet">A Cadet</option><option value="guardian">A parent or guardian</option><option value="instructor">An instructor</option></select>
          <div id="npAdmBox" hidden><label for="npAdm">Class PIN</label>${PIN_INPUT('npAdm', '')}
            <p class="faint">${s.admin_set ? 'An instructor profile needs the Class PIN (set up on this computer) plus its own PIN.'
              : 'Set up the instructor on the instructor\'s computer first — it chooses the Class PIN.'}</p></div></details>
        <button class="btn primary" style="width:100%;margin-top:12px;min-height:50px;font-size:18px">Start</button>
        <p class="faint" id="npMsg" role="alert"></p>
        ${s.profiles.length ? '<button type="button" class="btn small" id="backPick">← Back</button>' : ''}${extras}</form>`;
    $('#npKind').value = kind;
    $('#npName').focus();
    if ($('#backPick')) $('#backPick').onclick = pick;
    const kindChanged = () => {
      const k = $('#npKind').value;
      $('#npAdmBox').hidden = k !== 'instructor';
      $('#npJoinBox').hidden = k !== 'cadet';
    };
    $('#npKind').addEventListener('change', kindChanged); kindChanged();
    let lookT = null;
    const lookUp = async () => {
      const c = $('#npJoin').value.trim();
      if (!c) { $('#npJoinName').textContent = ''; return; }
      const r = await api('/api/join-code?c=' + encodeURIComponent(c));
      $('#npJoinName').textContent = r.name ? `✓ You'll join: ${r.name}` : (c.replace(/[^A-Za-z0-9]/g, '').length >= 6 ? 'That code isn\'t right — check it with your instructor.' : '');
    };
    $('#npJoin').addEventListener('input', () => { clearTimeout(lookT); lookT = setTimeout(lookUp, 350); });
    if (joinCode) lookUp();
    $('#newForm').onsubmit = async ev => {
      ev.preventDefault();
      const k = $('#npKind').value;
      if ($('#npPin').value !== $('#npPin2').value) { $('#npMsg').textContent = "The two PINs don't match. Type them again."; $('#npPin2').value = ''; return; }
      const r = await api('/api/profiles/create', { name: $('#npName').value, pin: $('#npPin').value, kind: k,
        admin: $('#npAdm').value, join: k === 'cadet' ? $('#npJoin').value : '' });
      if (!r.ok) { $('#npMsg').textContent = r.error; return; }
      const done = () => r.joined ? joinedNote(r.joined) : go();
      r.recovery ? showRecoveryCode(r.recovery, done) : done();
    };
  };
  const joinedNote = name => {
    d.innerHTML = `<div class="card" style="width:100%;max-width:380px;text-align:center"><div style="font-size:34px">✅</div>
      <h2>You're in</h2><p>You joined <b>${esc(name)}</b>. Your instructor will see your class work — never your private notes.</p>
      <button class="btn primary" id="jnGo" style="width:100%;min-height:50px">Let's go</button></div>`;
    $('#jnGo').onclick = go;
  };
  // First time on the instructor's computer: Welcome → Class PIN → your name and PIN → backup code → ready.
  const setup = () => {
    let classPin = '', program = '';
    const step = html => { d.innerHTML = `<div class="card" style="width:100%;max-width:440px">${html}</div>`; };
    const welcome = () => {
      step(`<div style="font-size:30px;text-align:center">✦</div><h2 style="text-align:center">Welcome to Cadet Foundry</h2>
        <p>Cadet Foundry stays on this computer. Cadets can join from phones on the same Wi-Fi. Nothing is sent to the internet.</p>
        <label style="display:flex;gap:10px;align-items:flex-start;margin:4px 0 12px">
          <input type="checkbox" id="suAgree" ${s.terms_ok ? 'checked' : ''} style="width:24px;height:24px;flex:none;margin-top:2px">
          <span>I've read and agree to the <a href="#" data-legal="terms">Terms of use</a> and the <a href="#" data-legal="privacy">Privacy notice</a>.</span></label>
        <button class="btn primary" id="suInst" style="width:100%;min-height:52px;font-size:18px">I'm the instructor — set up this class</button>
        <button class="btn small" id="suJustMe" style="width:100%;margin-top:10px">Just me — I'm a Cadet using this on my own</button>
        <button class="btn small" id="suSample" style="width:100%;margin-top:10px">🧪 Just looking? See a sample class first</button>
        <p class="faint" id="suSampleMsg" role="status" style="text-align:center"></p>${extras}`);
      // Setting up needs the "I agree" box ticked (the sample class doesn't: nothing real is set up there)
      const agreed = async () => {
        if (!$('#suAgree').checked) { $('#suSampleMsg').textContent = 'Tick the box to agree to the Terms of use and Privacy notice first.'; return false; }
        if (!s.terms_ok) {
          const r = await api('/api/terms/accept', {});
          if (r.error) { $('#suSampleMsg').textContent = r.error; return false; }
          s.terms_ok = true;
        }
        return true;
      };
      $('#suInst').onclick = async () => { if (await agreed()) programStep(); };
      $('#suSample').onclick = () => startSample($('#suSample'), $('#suSampleMsg'));
      $('#suJustMe').onclick = async () => { if (await agreed()) newProfile('cadet'); };
    };
    // Which program: sets the words Cadet Foundry uses (LET / NS / LE / Year) and puts that branch first in Learn.
    const PROGS = [['army', '⭐', 'Army JROTC'], ['navy', '⚓', 'Navy JROTC'], ['air_force', '✈️', 'Air Force JROTC'],
      ['marine_corps', '🦅', 'Marine Corps JROTC'], ['space_force', '🚀', 'Space Force JROTC'], ['coast_guard', '🛟', 'Coast Guard JROTC<small>No Coast Guard study cards yet — Cadets see every other branch</small>'],
      ['', '🎖️', 'More than one / not sure']];
    const programStep = () => {
      step(`<div class="faint">Step 1 of 4</div><h2>Your program</h2>
        <p>Which JROTC program is this? Cadets can still explore every branch — this just sets the words Cadet Foundry uses.</p>
        <div class="tiles" style="margin:0">${PROGS.map(([k, ic, name]) => `<button class="tile" data-prog="${k}"><span>${ic}</span>${name}</button>`).join('')}</div>
        <button type="button" class="btn small" id="suBack" style="margin-top:10px">← Back</button>`);
      $('#suBack').onclick = welcome;
      d.querySelectorAll('[data-prog]').forEach(b => { b.onclick = () => { program = b.dataset.prog; pinStep(); }; });
    };
    const pinStep = () => {
      step(`<div class="faint">Step 2 of 4</div><h2>Class PIN</h2>
        <p>Only you (and any other instructors) should know this. It protects the whole class and the settings. Use 6–12 digits.</p>
        <form id="suPinForm"><label for="suPin">Class PIN</label>${PIN_INPUT('suPin', '')}
        <label for="suPin2">Type it again</label>${PIN_INPUT('suPin2', '')}
        <button class="btn primary" style="width:100%;margin-top:12px">Next</button></form>
        <p class="faint" id="suMsg" role="alert"></p><button type="button" class="btn small" id="suBack">← Back</button>`);
      $('#suPin').value = classPin; $('#suPin').focus();
      $('#suBack').onclick = programStep;
      $('#suPinForm').onsubmit = ev => {
        ev.preventDefault();
        const a = $('#suPin').value, b = $('#suPin2').value;
        if (!/^\d{6,12}$/.test(a)) { $('#suMsg').textContent = 'Use 6 to 12 digits.'; return; }
        if (a !== b) { $('#suMsg').textContent = "The two PINs don't match."; $('#suPin2').value = ''; return; }
        classPin = a; meStep();
      };
    };
    const meStep = () => {
      step(`<div class="faint">Step 3 of 4</div><h2>Your screen</h2>
        <form id="suMeForm"><label for="suName">Your name</label><input id="suName" maxlength="40" autocomplete="off" placeholder="e.g. SFC Rivera">
        <label for="suMyPin">Your PIN (6–12 digits)</label>${PIN_INPUT('suMyPin', '')}
        <label for="suMyPin2">Type it again</label>${PIN_INPUT('suMyPin2', '')}
        <p class="faint">Your PIN opens your own screen. Make it different from the Class PIN.</p>
        <button class="btn primary" style="width:100%;margin-top:12px">Next</button></form>
        <p class="faint" id="suMsg" role="alert"></p><button type="button" class="btn small" id="suBack">← Back</button>`);
      $('#suName').focus();
      $('#suBack').onclick = pinStep;
      $('#suMeForm').onsubmit = async ev => {
        ev.preventDefault();
        if ($('#suMyPin').value !== $('#suMyPin2').value) { $('#suMsg').textContent = "The two PINs don't match."; $('#suMyPin2').value = ''; return; }
        if ($('#suMyPin').value === classPin) { $('#suMsg').textContent = 'Make your PIN different from the Class PIN.'; return; }
        const r = await api('/api/profiles/create', { name: $('#suName').value, pin: $('#suMyPin').value, kind: 'instructor', admin: classPin });
        if (!r.ok) { $('#suMsg').textContent = r.error; return; }
        if (program) await api('/api/instructor/program', { program });   // the class is already open for them
        showRecoveryCode(r.recovery, ready);         // Step 4: the backup code
      };
    };
    const ready = () => {
      step(`<div style="font-size:34px;text-align:center">✅</div><h2 style="text-align:center">You're ready</h2>
        <p>How do you want to use Cadet Foundry right now?</p>
        <button class="btn primary" id="suClass" style="width:100%;min-height:52px;font-size:18px">Open it for the class</button>
        <button class="btn" id="suLocal" style="width:100%;margin-top:10px;min-height:48px">Use it on this computer only</button>
        <p class="faint" id="suMsg" role="status"></p>`);
      $('#suLocal').onclick = go;
      $('#suClass').onclick = () => {
        if (s.lan) { location.replace('/join'); return; }
        // open class to phones right here (the desktop icon starts Cadet Foundry for this computer only)
        $('#suClass').disabled = true;
        $('#suMsg').innerHTML = 'Opening class to phones… If Windows asks whether to allow Cadet Foundry (Python) on networks, choose <b>Allow</b>.';
        api('/api/instructor/classroom', { open: true }).then(async r => {
          if (r.error) { $('#suMsg').textContent = r.error; $('#suClass').disabled = false; return; }
          for (let i = 0; i < 60; i++) {
            await new Promise(res => setTimeout(res, 500));
            try { if ((await (await fetch('/api/lock', { cache: 'no-store' })).json()).lan) { location.replace('/join'); return; } } catch (e) { }
          }
          $('#suMsg').textContent = 'This is taking longer than usual. Reload the page in a moment.';
        });
      };
    };
    welcome();
  };
  const notYet = () => {                         // a phone arrived before the instructor set up the class
    d.innerHTML = `<div class="card" style="width:100%;max-width:380px;text-align:center"><div style="font-size:30px">⏳</div>
      <h2>Not set up yet</h2><p>Your instructor sets up Cadet Foundry on their computer first. Then come back and join.</p>
      <button class="btn primary" id="nyAgain" style="width:100%;min-height:48px">Try again</button>${extras}</div>`;
    $('#nyAgain').onclick = () => location.reload();
  };
  if (s.sample) { sampleArrive(d, s); return; }
  if (!s.on_this_computer && !s.admin_set && !s.demo) notYet();
  else if (!s.profiles.length) (s.on_this_computer ? setup() : newProfile());
  else if (joinCode || want.has('new')) newProfile();
  else if (want.has('pick')) pick();
  else if (s.profiles.length === 1 && !s.profiles[0].has_pin && s.on_this_computer) {
    const r = await api('/api/unlock', { profile: s.profiles[0].id, pin: '' });
    if (r.ok) { go(); return; }
    pick();
  } else if (s.profiles.length === 1 && s.on_this_computer) pinFor(s.profiles[0]);
  else pick();
}

// ── The Terms of use and Privacy notice (cadetfoundry/legal/), readable anywhere -- even before setup, and offline ──
async function showLegal(doc) {
  let d = {};
  try { d = await (await fetch('/api/legal?doc=' + encodeURIComponent(doc), { cache: 'no-store' })).json(); } catch (e) { }
  const box = document.createElement('div');
  box.style.cssText = 'position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.6);display:grid;place-items:center;padding:16px';
  box.innerHTML = `<div class="card" role="dialog" aria-modal="true" style="max-width:720px;width:100%;max-height:86vh;overflow:auto">
    <div class="legal">${d.text ? md(d.text) : esc(d.error || "This document couldn't be opened.")}</div>
    <button class="btn primary" style="margin-top:12px;min-height:46px">Close</button></div>`;
  document.body.appendChild(box);
  const close = () => box.remove();
  box.querySelector('button').addEventListener('click', close);
  box.addEventListener('click', e => { if (e.target === box) close(); });
  box.querySelector('button').focus();
}
document.addEventListener('click', e => {
  const a = e.target.closest('[data-legal]');
  if (a) { e.preventDefault(); showLegal(a.dataset.legal); }
});

// ── The sample class (cadetfoundry/sample.py): a separate copy of Cadet Foundry with made-up Cadets ──
async function startSample(btn, msgEl) {
  if (btn) btn.disabled = true;
  if (msgEl) msgEl.textContent = 'Opening the sample class…';
  const r = await api('/api/sample/start', {});
  if (r.error || !r.url) {
    if (msgEl) msgEl.textContent = r.error || "The sample class couldn't open.";
    if (btn) btn.disabled = false;
    return;
  }
  location.href = r.url;
}

async function sampleArrive(d, s) {
  d.innerHTML = `<div class="card" style="width:100%;max-width:420px;text-align:center"><div style="font-size:34px">🧪</div>
    <h2>Building a sample class</h2><p>Eight made-up Cadets, two squads, lessons, scenarios and a pilot in progress. Your own Cadet Foundry isn't touched.</p>
    <p class="faint" id="smStep" role="status">Starting…</p></div>`;
  for (;;) {
    let st = {};
    try { st = await (await fetch('/api/sample/status', { cache: 'no-store' })).json(); } catch (e) { }
    if (st.error) {
      $('#smStep').innerHTML = `${esc(st.error)}<br><a href="${esc(s.sample_back || '/')}">Back to my Cadet Foundry</a>`;
      return;
    }
    if (st.ready) break;
    if (st.step) $('#smStep').textContent = st.step + '…';
    await new Promise(r => setTimeout(r, 700));
  }
  const r = await api('/api/sample/enter', {});
  if (r.ok) location.replace('/'); else $('#smStep').textContent = r.error || 'Try reloading the page.';
}

function sampleBanner(back) {
  const bar = document.createElement('div');
  bar.id = 'sampleBar';
  bar.setAttribute('role', 'note');
  bar.style.cssText = 'position:sticky;top:0;z-index:60;background:var(--tan);color:#111;padding:8px 12px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;font-size:15px';
  bar.innerHTML = '<span>🧪 <b>Sample class</b> — made-up Cadets. Try anything; changes here are thrown away.</span><button class="btn small" id="sampleLeave" style="background:#fff;color:#111">Leave sample</button>';
  document.body.prepend(bar);
  $('#sampleLeave').addEventListener('click', async () => {
    const r = await api('/api/sample/leave', {});
    location.href = (r && r.back) || back || '/';
  });
}

// The app starts only once a profile is unlocked.
const unlocked = (async () => {
  // Wait until every script in web/js/ has run, so nothing here races ahead of a later file.
  if (document.readyState === 'loading') await new Promise(r => document.addEventListener('DOMContentLoaded', r));
  const s = await (await fetch('/api/lock')).json();
  if (!s.unlocked) { showLock(); return null; }
  if (s.sample) sampleBanner(s.sample_back);
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
    const q = l.match(/^&gt;\s?(.*)/);                     // "> quoted text" (escaped above)
    if (q) { flush(); html += '<blockquote>' + inline(q[1]) + '</blockquote>'; continue; }
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
  try { big = localStorage.getItem('cadetfoundry-text') === 'large'; } catch (e) {}
  apply(big);
  btn.onclick = () => { big = !big; apply(big); try { localStorage.setItem('cadetfoundry-text', big ? 'large' : ''); } catch (e) {} };
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
  try { red = localStorage.getItem('cadetfoundry-mode') === 'red'; } catch (e) {}
  apply(red);
  btn.onclick = () => {
    red = !red; apply(red);
    try { localStorage.setItem('cadetfoundry-mode', red ? 'red' : ''); } catch (e) {}
  };
})();

// ── tabs ──
const loaders = {};
// Shows one view. Header buttons (Ask, Me, Instructor) open views that aren't tabs; then no tab is lit.
// Screens reached from a tab keep that tab lit: Train, Serve, Progress and the logbook live under Me; Faith under Learn.
const TAB_OF = { train: 'me', serve: 'me', progress: 'me', logbook: 'me', faith: 'study', lesson: 'home' };
function openView(v, pane) {
  const tab = TAB_OF[v] || v;
  document.querySelectorAll('#tabs button').forEach(x => x.classList.toggle('on', x.dataset.v === tab));
  document.querySelectorAll('.view').forEach(x => x.classList.toggle('on', x.id === v));
  if (pane && typeof showPane === 'function') showPane(pane); else loaders[v] && loaders[v]();
}
$('#tabs').addEventListener('click', e => {
  const b = e.target.closest('button'); if (b) openView(b.dataset.v, b.dataset.pane);
});
document.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', () => openView(b.dataset.open)));

// ── status ──
let STATUS = {};
const FAMILY_SUGGEST = ['What is JROTC?', 'Does joining JROTC mean my Cadet has to join the military?', 'What are the core values of each service?',
  'What do military ranks mean?', 'How can I support my Cadet?']
let landed = false;
// "/?go=class" (the Join screen's "Set up my class"): remembered through sign-in, which reloads the page
try {
  const go = new URLSearchParams(location.search).get('go');
  if (go && /^[a-z]{2,12}$/.test(go)) sessionStorage.setItem('cadetfoundry-go', go);
} catch (e) { }
async function refreshStatus() {
  STATUS = await api('/api/status');
  if (!landed) {
    let go = '';
    try { go = sessionStorage.getItem('cadetfoundry-go') || ''; sessionStorage.removeItem('cadetfoundry-go'); } catch (e) { }
    const toTools = STATUS.kind === 'instructor' && go && typeof INST_SECTIONS !== 'undefined' && INST_SECTIONS.some(s => s[0] === go);
    if (toTools) instSection = go;
    openView(toTools ? 'instructor' : 'home');     // everyone starts on Home; for an instructor that's Class day
  }
  landed = true;
  if ((document.body.dataset.kind = STATUS.kind || 'cadet') === 'guardian') {          // family member's profile
    $('#suggest').innerHTML = FAMILY_SUGGEST.map(q => `<button>${esc(q)}</button>`).join('');
    const hi = document.querySelector('#thread .msg.ai p');
    if (hi) hi.textContent = "Welcome to Cadet Foundry — I'm here to help you understand JROTC and support your Cadet. Ask me anything. Your chats are saved on this device.";
  }
  const e = STATUS.engine, el = $('#engine');
  const online = e.online_enabled && e.online_keys.length;
  const hi = document.querySelector('#thread .msg.ai p');
  if (online && hi && !hi.dataset.online) {        // say plainly what leaves the device (SECURITY.md, Online AI)
    hi.dataset.online = '1';
    hi.insertAdjacentHTML('afterend', '<p class="faint">This device uses an online AI service for ordinary questions: '
      + 'your question goes to it, but not your name, notes or earlier chats. Anything about feeling unsafe stays on this device.</p>');
  }
  el.innerHTML = e.model
    ? `<span class="dot ok"></span><span>Offline AI: ${esc(e.model)}${online ? ' + online' : ''}</span>`
    : online ? '<span class="dot ok"></span><span>Online AI</span>'
             : '<span class="dot warn"></span><span>Library only (no AI model)</span>';
  const p = STATUS.profile || {};
  $('#hello').textContent = p.name ? `· ${p.name}` : '';
}
