// Cadet flash drives (owner, 2026-10-12): the instructor makes a drive for a Cadet (or for "any Cadet" in a class)
// from Me; the Cadet studies at home; when the drive is plugged back into this computer, their class work comes in
// and new lessons go out -- automatically, with a notice. Listeners in JS (the page's policy blocks inline handlers).
'use strict';

const gb = n => (n / 2 ** 30).toFixed(n < 2 ** 30 ? 2 : 1) + ' GB';

async function cadetDrivesCard(box) {
  const made = await api('/api/instructor/drives').catch(() => ({ error: 'x' }));
  const open = !made.error;
  const count = open ? Object.keys(made.made || {}).length : 0;
  box.innerHTML = `<h3>💾 Cadet flash drives</h3>
    <p>Make a flash drive a Cadet takes home to study — no internet needed, on any Windows computer. When they
      bring it back and it's plugged into this computer, their class work comes in and new lessons go onto it, on its own.
      Private notes stay on the drive.</p>
    ${open ? `<button class="btn primary" id="drvNew">💾 Create a Cadet flash drive</button>
      ${count ? `<p class="faint" style="margin:8px 0 0">${count} drive${count === 1 ? '' : 's'} made on this computer. Lost one? Make a new drive for that Cadet — it has the work they last brought to class.</p>` : ''}`
      : '<p class="faint">Open your class first (🏠 Home → Class PIN) to make or bring in Cadet drives.</p>'}`;
  if (open) $('#drvNew').addEventListener('click', () => driveWizard(box));
}

async function driveWizard(box) {
  box.innerHTML = '<p class="faint">Looking for flash drives…</p>';
  const d = await api('/api/instructor/drives');
  if (d.error) { box.innerHTML = `<p>${esc(d.error)}</p>`; return; }
  if (d.job && d.job.running) return driveProgress(box);
  if (!d.units.length) {
    box.innerHTML = `<h3>💾 Create a Cadet flash drive</h3><p>Make your class first (🏠 Home → Set up your class). A drive is made for a
      Cadet in your class, or for any Cadet who'll join it.</p><button class="btn" id="drvCancel">OK</button>`;
    $('#drvCancel').addEventListener('click', () => cadetDrivesCard(box));
    return;
  }
  const usable = x => x.state === 'blank' || x.state === 'cadet';
  const stateNote = x => x.state === 'blank' ? 'ready' : x.state === 'cadet' ? `Cadet drive${x.cadet ? ' — ' + esc(x.cadet) : ''}` : esc(x.note);
  const cadets = d.cadets.slice().sort((a, b) => a.name.localeCompare(b.name));
  box.innerHTML = `<h3>💾 Create a Cadet flash drive</h3>
    <p style="margin:6px 0"><b>1. The flash drive</b> <button class="btn small" id="drvRefresh">↻ Look again</button></p>
    ${d.drives.length ? d.drives.map((x, i) => `<label style="display:flex;gap:10px;align-items:center;min-height:44px;${usable(x) ? '' : 'opacity:.55'}">
        <input type="radio" name="drv" value="${i}" ${usable(x) ? '' : 'disabled'} style="width:22px;height:22px">
        <span><b>${esc(x.path)}</b> ${esc(x.label || '')} <span class="faint">· ${gb(x.free)} free of ${gb(x.total)} · ${stateNote(x)}</span></span></label>`).join('')
      : '<p class="faint">No flash drive found. Plug one in (8 GB or bigger), then press ↻ Look again.</p>'}
    <p style="margin:14px 0 6px"><b>2. Who's it for?</b></p>
    <select id="drvWho" style="width:100%">
      ${d.units.map(u => `<option value="unit:${esc(u.id)}">Any Cadet in ${esc(u.name)} — they make their own profile and PIN</option>`).join('')}
      ${cadets.map(c => `<option value="cadet:${esc(c.id)}" ${c.has_pin ? '' : 'disabled'}>${esc(c.name)}${c.has_pin ? '' : ' (needs a PIN first)'}</option>`).join('')}
    </select>
    <p class="faint" id="drvWhoNote" style="margin:4px 0 0"></p>
    <p style="margin:14px 0 6px"><b>3. What goes on it</b></p>
    <label style="display:flex;gap:10px;align-items:center;min-height:44px"><input type="checkbox" id="drvVideos" checked style="width:22px;height:22px">
      <span>The official videos <span class="faint">— they play with no internet (${gb(d.sizes.videos - d.sizes.basic)} more)</span></span></label>
    <p class="faint" id="drvSize" style="margin:0"></p>
    <label id="drvEraseBox" style="display:none;gap:10px;align-items:flex-start;margin:10px 0"><input type="checkbox" id="drvErase" style="width:22px;height:22px;flex:none">
      <span>This drive belongs to another Cadet. Erase it for the new Cadet. <span class="faint">(Their class work is already saved on this computer; their private notes on the drive will be gone.)</span></span></label>
    <div class="row" style="gap:8px;margin-top:14px;flex-wrap:wrap"><button class="btn primary" id="drvGo">Create the drive</button><button class="btn" id="drvCancel">Cancel</button></div>
    <p class="faint" id="drvMsg" role="alert"></p>`;
  const pickDrive = () => { const r = box.querySelector('input[name="drv"]:checked'); return r ? d.drives[+r.value] : null; };
  const update = () => {
    const x = pickDrive(), who = $('#drvWho').value;
    const need = $('#drvVideos').checked ? d.sizes.videos : d.sizes.basic;
    $('#drvSize').textContent = `Needs about ${gb(need)}.` + (x ? ` This drive has ${gb(x.free)} free.` : '');
    const other = x && x.state === 'cadet' && x.cadet_id && who !== 'cadet:' + x.cadet_id;
    $('#drvEraseBox').style.display = other ? 'flex' : 'none';
    $('#drvWhoNote').textContent = who.startsWith('cadet:') && x && x.state === 'cadet' && x.cadet_id === who.slice(6)
      ? 'This is already their drive: Cadet Foundry on it is updated and their work is brought in. Nothing of theirs is lost.'
      : who.startsWith('cadet:') ? 'Their profile goes on the drive, locked with their own PIN, with the lessons you\'ve given them.' : '';
  };
  box.querySelectorAll('input[name="drv"]').forEach(r => r.addEventListener('change', update));
  const first = box.querySelector('input[name="drv"]:not([disabled])');
  if (first) first.checked = true;
  $('#drvWho').addEventListener('change', update);
  $('#drvVideos').addEventListener('change', update);
  update();
  $('#drvRefresh').addEventListener('click', () => driveWizard(box));
  $('#drvCancel').addEventListener('click', () => cadetDrivesCard(box));
  $('#drvGo').addEventListener('click', async () => {
    const x = pickDrive(), who = $('#drvWho').value;
    if (!x) { $('#drvMsg').textContent = 'Pick the flash drive first.'; return; }
    $('#drvGo').disabled = true;
    const r = await api('/api/instructor/drives/make', { path: x.path, cadet: who.startsWith('cadet:') ? who.slice(6) : '',
      unit: who.startsWith('unit:') ? who.slice(5) : '', videos: $('#drvVideos').checked, erase: $('#drvErase').checked });
    if (r.error) { $('#drvMsg').textContent = r.error; $('#drvGo').disabled = false; return; }
    driveProgress(box);
  });
}

async function driveProgress(box) {
  box.innerHTML = `<h3>💾 Making the drive…</h3>
    <div style="height:14px;border-radius:7px;background:var(--line);overflow:hidden"><div id="drvBar" style="height:14px;width:0;background:var(--tan)"></div></div>
    <p class="faint" id="drvJob" role="status">Starting…</p><p class="faint">Leave the flash drive plugged in. This can take several minutes.</p>`;
  for (;;) {
    await new Promise(r => setTimeout(r, 1000));
    if (!box.isConnected) return;
    const j = await api('/api/instructor/drives/job');
    $('#drvBar').style.width = (j.pct || 0) + '%';
    $('#drvJob').textContent = j.error || j.msg || '';
    if (j.done) {
      box.innerHTML = j.error ? `<h3>💾 The drive wasn't finished</h3><p>${esc(j.error)}</p><button class="btn" id="drvAgain">Try again</button>`
        : `<h3>✅ The drive is ready</h3><p>${j.name ? `Label it <b>${esc(j.name)}</b> and hand it out.` : 'Label it and hand it to a Cadet. They make their profile and PIN the first time they open it.'}
            Unplug it safely first (Eject in File Explorer).</p>
           <p class="faint">At home: plug it into a Windows computer and double-click <b>Start Cadet Foundry.bat</b>. When it comes back, plug it in here — the work comes in on its own.</p>
           <button class="btn primary" id="drvAgain">💾 Make another</button>`;
      $('#drvAgain').addEventListener('click', () => driveWizard(box));
      return;
    }
  }
}

// Plug in = sync: while an instructor is signed in with the class open, plugged-in Cadet drives are brought in.
function driveNotice(text, bad) {
  let host = $('#drvToasts');
  if (!host) {
    host = document.createElement('div');
    host.id = 'drvToasts';
    host.setAttribute('role', 'status');
    host.setAttribute('aria-live', 'polite');
    host.style.cssText = 'position:fixed;right:16px;bottom:84px;z-index:50;display:grid;gap:8px;max-width:min(420px,calc(100vw - 32px))';
    document.body.appendChild(host);
  }
  const t = document.createElement('div');
  t.className = 'card';
  t.style.cssText = `margin:0;border-color:${bad ? 'var(--red)' : 'var(--tan)'};box-shadow:0 10px 30px rgba(0,0,0,.4)`;
  t.innerHTML = `<div class="row" style="justify-content:space-between;gap:10px;flex-wrap:nowrap"><span>💾 ${esc(text)}</span><button class="btn small" aria-label="Close">✕</button></div>`;
  t.querySelector('button').addEventListener('click', () => t.remove());
  host.appendChild(t);
  setTimeout(() => t.remove(), 15000);
}

let driveWatchOn = false, driveWatchWait = 0;
function driveWatch() {
  if (driveWatchOn) return;
  driveWatchOn = true;
  setInterval(async () => {
    if (STATUS.kind !== 'instructor') return;           // (also in a background tab: plug in = sync)
    if (driveWatchWait > 0) { driveWatchWait--; return; }
    let r;
    try { r = await api('/api/instructor/drives/sync'); } catch (e) { driveWatchWait = 6; return; }
    if (r.error) { driveWatchWait = 6; return; }               // class not open yet: check again in half a minute
    for (const n of r.notices || []) {
      if (n.error) driveNotice(n.error, true);
      else (n.notices || []).forEach(x => driveNotice(x));
      if (!n.error && n.lessons_sent) driveNotice(`${n.lessons_sent} lesson${n.lessons_sent === 1 ? '' : 's'} on the drive. Safe to unplug.`);
    }
  }, 5000);
}

// Running from a USB drive (usb_home.py): this computer's backups of the class, if it's the instructor's own computer.
async function usbBackupCard(box) {
  const u = await api('/api/instructor/usb').catch(() => ({ error: 'x' }));
  if (u.error || u.where !== 'usb') return;
  box.hidden = false;
  const list = u.backups || [];
  box.innerHTML = `<h3>💾 Backups of your class</h3>
    <p>Your class lives on the USB drive ${esc(u.drive)}. ${u.trusted === true
      ? `This computer keeps a backup copy — the newest five. ${list.length ? `Newest: <b>${esc(list[0].when)}</b>.` : 'None yet.'}`
      : u.trusted === false ? "You said this isn't your own computer, so no backup is kept here."
        : "Say on 🏠 Home whether this is your own computer to keep a backup here."}</p>
    ${u.trusted === true ? `<div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn" id="ubNow">Back up now</button>
      <button class="btn small" id="ubOpen">Show the backups folder</button></div>
      <p class="faint" style="margin:8px 0 0">Lost or broken drive? Make a new drive, then restore the newest backup onto it:
      <code>python tools/make_usb.py E:\ --restore "backup file"</code> — or email support@cadetfoundry.org for help.</p>` : ''}
    ${u.trusted === false ? '<button class="btn small" id="ubYes">This is my own computer — keep a backup</button>' : ''}
    <p class="faint" id="ubMsg" role="status"></p>`;
  const msg = t => { $('#ubMsg').textContent = t; };
  if ($('#ubNow')) $('#ubNow').addEventListener('click', async () => {
    const r = await api('/api/instructor/usb/backup', {});
    if (r.error) return msg(r.error);
    usbBackupCard(box);
  });
  if ($('#ubOpen')) $('#ubOpen').addEventListener('click', async () => { const r = await api('/api/instructor/open-folder', { path: u.folder }); if (r.error) msg(r.error); });
  if ($('#ubYes')) $('#ubYes').addEventListener('click', async () => { await api('/api/instructor/usb/trust', { yes: true }); usbBackupCard(box); });
}
