'use strict';
// Me tab: profile, security, Instructor PIN, library check and updates, backup; first-run tour. Loaded last.

// ── ADD-ONS ── (offline AI and voice: installed from here with a progress bar; needs internet once)
let addonTimer = null;
async function showAddons() {
  const st = await api('/api/addons'), j = st.job || {}, running = j.state === 'running';
  const row = (key, title, what, info) => `<div style="padding:8px 0;border-bottom:1px solid var(--line)">
      <div class="row" style="justify-content:space-between"><div><b>${title}</b> <span class="faint">— ${what}</span></div>
      ${info.installed ? '<span style="color:var(--green)">✓ Installed</span>'
        : `<button class="btn small primary" data-addon="${key}" ${running ? 'disabled' : ''}>Install (${esc(info.size)})</button>`}</div>
      ${j.name === key && j.state ? `<div style="margin-top:6px">${j.state === 'error' ? `<span style="color:var(--red)">${esc(j.msg)}</span>`
        : `<div style="height:8px;background:var(--line);border-radius:4px;overflow:hidden"><div style="height:100%;width:${j.pct || 0}%;background:var(--tan)"></div></div>
           <div class="faint">${esc(j.state === 'done' ? j.msg : j.step)}</div>`}</div>` : ''}</div>`;
  const html = `<h3>🧩 Add-ons</h3><p class="faint">Optional. Each needs internet once, then works offline. You can keep using Vanguard while one installs.</p>
    ${row('ai', 'Offline AI', 'answers in full sentences, simpler explanations, mock board grading', st.ai)}
    ${row('voice', 'Voice', 'talk to Vanguard with the 🎤 button', st.voice)}`;
  let card = $('#addonsCard');
  if (!card) { $('#meBody').insertAdjacentHTML('beforeend', '<div class="card" id="addonsCard"></div>'); card = $('#addonsCard'); }
  card.innerHTML = html;
  card.querySelectorAll('[data-addon]').forEach(b => b.onclick = async () => {
    const admin = (await api('/api/lock')).admin_set ? prompt('Class PIN (installing changes this device):') : '';
    if (admin === null) return;
    const r = await api('/api/addons/install', { name: b.dataset.addon, admin });
    if (r.error) alert(r.error);
    showAddons();
  });
  clearTimeout(addonTimer);
  if (running && document.body.contains(card)) addonTimer = setTimeout(showAddons, 1500);
  else if (j.state === 'done') refreshStatus();
}

// ── LIBRARY CHECK + SIGNED UPDATES (Me tab) ──
async function showIntegrity() {
  const st = await api('/api/integrity'), adm = (await api('/api/lock')).admin_set;
  const aiMode = (await api('/api/status')).ai_mode || 'library';
  const icon = { ok: '✅', changed: '⚠️', bad_signature: '⛔', unrecorded: 'ℹ️' }[st.status] || 'ℹ️';
  const list = (t, xs) => xs && xs.length ? `<div class="faint">${t}: ${xs.slice(0, 8).map(esc).join(', ')}${xs.length > 8 ? ` and ${xs.length - 8} more` : ''}</div>` : '';
  const old = $('#integrityCard'); if (old) old.remove();
  $('#meBody').insertAdjacentHTML('beforeend', `<div class="card" id="integrityCard"><h3>🔒 Library check and updates</h3>
    <p>${icon} ${esc(st.message)}</p>${list('Changed', st.changed)}${list('Missing', st.missing)}${list('New, not fingerprinted', st.added)}
    <div class="row"><button class="btn small" id="intCheck">Check again</button></div>
    <h4>Class PIN</h4>
    <p class="faint">${adm ? 'Set. It opens your class in 🎓 Instructor and controls the AI setting, Learn sections, updates and the library. It is separate from everyone\'s own PIN.' : 'Not set. Installing updates needs a Class PIN, so one profile can\'t change Vanguard for everyone on a shared device. Whoever looks after this device should set it.'}</p>
    <div class="row">${adm ? '<input id="admCur" type="password" inputmode="numeric" maxlength="12" placeholder="Current Class PIN" style="flex:1">' : ''}
      <input id="admNew" type="password" inputmode="numeric" maxlength="12" placeholder="New Class PIN (6–12 digits)" style="flex:1">
      <button class="btn small" id="admSave">${adm ? 'Change' : 'Set Class PIN'}</button></div><p class="faint" id="admMsg"></p>
    <h4>AI setting</h4>
    <p class="faint">Applies to every profile on this device. <b>Off:</b> no AI writing — ✅ checked answers and the exact library text only. <b>Library only</b> (recommended for class): the AI may only explain what the library holds, and says so when it holds nothing. <b>Library + AI:</b> broader explanations, always labeled as AI.</p>
    <div class="row" role="radiogroup" aria-label="AI setting">${[['off', 'Off'], ['library', 'Library only'], ['ai', 'Library + AI']].map(([v, t]) =>
      `<label style="margin-right:12px"><input type="radio" name="aiMode" value="${v}" ${aiMode === v ? 'checked' : ''} ${adm ? '' : 'disabled'}> ${t}</label>`).join('')}</div>
    <div class="row"><input id="libAdm" type="password" inputmode="numeric" maxlength="12" placeholder="Class PIN" style="flex:1" ${adm ? '' : 'disabled'}>
      <button class="btn small" id="aiSave" ${adm ? '' : 'disabled'}>Save AI setting</button></div>
    <p class="faint" id="libMsg">${adm ? '' : 'Set a Class PIN above first.'}</p>
    <p class="faint">Vanguard ${esc(st.version)}. ${st.update_key ? 'Updates must be signed by the publisher.' : 'No release key on this copy — signed updates aren\'t set up yet.'}</p>
    ${st.update_key ? `<details><summary>Install an update from a USB stick</summary>
      <label>Update file (.zip)</label><input type="file" id="updZip" accept=".zip">
      <label>Signature (.sig)</label><input type="file" id="updSig" accept=".sig">
      <label>Class PIN</label><input type="password" id="updAdmin" inputmode="numeric" maxlength="12">
      <div class="row" style="margin-top:8px"><button class="btn primary" id="updGo">Check and install</button></div><p id="updMsg"></p></details>` : ''}</div>`);
  $('#intCheck').onclick = async () => { await api('/api/integrity/check', {}); showIntegrity(); };
  $('#aiSave').onclick = async () => {
    const pick = document.querySelector('input[name=aiMode]:checked');
    const r = await api('/api/admin/ai-mode', { admin: $('#libAdm').value, mode: pick ? pick.value : 'library' });
    if (r.ok) { STATUS.ai_mode = r.ai_mode; STATUS.library_only = r.ai_mode === 'off'; showIntegrity(); } else $('#libMsg').textContent = r.error;
  };
  $('#admSave').onclick = async () => {
    const r = await api('/api/admin/pin', { new: $('#admNew').value, current: $('#admCur') ? $('#admCur').value : '' });
    if (r.ok) showIntegrity(); else $('#admMsg').textContent = r.error;
  };
  if ($('#updGo')) $('#updGo').onclick = async () => {
    const z = $('#updZip').files[0], g = $('#updSig').files[0];
    if (!z || !g) { $('#updMsg').textContent = 'Choose both the .zip and its .sig file.'; return; }
    $('#updMsg').textContent = 'Checking the signature…';
    const b64 = await new Promise(res => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.readAsDataURL(z); });
    const r = await api('/api/update', { zip: b64, sig: await g.text(), admin: $('#updAdmin').value });
    $('#updMsg').innerHTML = r.ok ? `<b style="color:var(--green)">✓ Installed version ${esc(r.version)}</b> (was ${esc(r.current)}). Close Vanguard and start it again to finish.`
      : `<b style="color:var(--red)">Not installed.</b> ${esc(r.error || '')}`;
  };
}

// ── ME ──
loaders.me = async () => {
  await refreshStatus();
  const p = STATUS.profile || {}, e = STATUS.engine, lib = STATUS.library;
  const mems = await api('/api/memory');
  const lock = await api('/api/lock');
  const cat = (STATUS.modules_off || []).includes('faith') ? [] : ((await api('/api/faith/catalog').catch(() => ({}))).installed || []);
  const myFaith = new Set((p.faith_texts || '').split(',').filter(Boolean));
  const faithBoxes = cat.length ? cat.map(t => `<label style="display:flex;gap:8px;align-items:center;margin:4px 0;color:var(--text)">
      <input type="checkbox" class="faithPick" value="${esc(t.id)}" ${myFaith.has(t.id) ? 'checked' : ''} style="width:auto">
      ${esc(t.name)} <span class="faint">— ${esc(t.tradition)}</span></label>`).join('')
    : '<p class="faint">No scripture texts installed on this device.</p>';
  const isInst = STATUS.kind === 'instructor', isCadet = STATUS.kind === 'cadet';
  const gradeOpts = ['', ...(STATUS.grades || [])].map(s => `<option ${p.grade === s ? 'selected' : ''}>${esc(s)}</option>`).join('');
  const cadetTiles = !isInst && STATUS.kind !== 'guardian';
  $('#meBody').innerHTML = `<h2>Me</h2>
    ${cadetTiles ? `<div class="tiles">
      <button class="tile" data-go-view="progress"><span>📈</span>My progress<small>Growth and portfolio</small></button>
      <button class="tile" data-go-view="train"><span>💪</span>Train<small>Fitness against yourself</small></button>
      <button class="tile" data-go-view="serve"><span>🤝</span>Serve<small>Service hours · explore the military</small></button>
      <button class="tile" data-go-view="logbook"><span>📝</span>Logbook<small>Notes, letters, budget</small></button>
    </div>` : ''}
    <div class="card"><div class="row" style="justify-content:space-between">
      <div><div class="faint">Profile on this device</div><div id="profName" style="font-size:20px;font-weight:700">${STATUS.kind === 'guardian' ? '👪' : STATUS.kind === 'instructor' ? '🎓' : '👤'} ${esc(lock.current.name)}
        <button class="btn small" id="renameProf" aria-label="Rename this profile" style="margin-left:6px">✎ Rename</button></div></div>
      <div class="row" style="gap:6px"><button class="btn small" id="switchProf">⇄ Switch profile</button><button class="btn small" id="addProf">+ Add profile</button><button class="btn small danger" id="delProf">Delete profile</button></div></div>
      <p class="faint">Everyone on this device has their own profile, locked by their own PIN. Other Cadets can never see yours.</p></div>
    ${isCadet ? `<div class="card"><h3>🎓 My class</h3>
      <p class="faint">${lock.current.joined ? `You joined <b>${esc(lock.current.joined)}</b> with a join code.` : 'Your instructor can put you in a class, or you can join one with the code they give you.'}</p>
      <div class="row" style="flex-wrap:wrap;gap:8px"><input id="joinIn" maxlength="12" placeholder="Join code" aria-label="Join code" autocomplete="off"
        style="flex:1;min-width:140px;font-family:ui-monospace,Consolas,monospace;text-transform:uppercase;letter-spacing:.15em">
        <button class="btn small primary" id="joinGo">Join</button></div><p class="faint" id="joinMsg" role="status"></p></div>` : ''}
    <form class="card" id="profForm">
      <div class="row" style="flex-wrap:wrap;gap:8px"><div style="flex:2;min-width:180px"><label>Name</label><input name="name" value="${esc(p.name)}"></div>
      ${isCadet ? `<div style="flex:1;min-width:140px"><label>Grade</label><select name="grade">${gradeOpts}</select></div>` : ''}</div>
      ${isCadet ? `<label>What I want to get better at</label><input name="interests" value="${esc(p.interests)}" placeholder="e.g. public speaking, fitness, leadership">` : ''}
      ${isInst ? '' : `<label>${isCadet ? 'My goals' : 'What would help you most'}</label><textarea name="goals" rows="2" placeholder="${isCadet
        ? 'e.g. lead my squad at the next drill meet, raise my grades, run a faster mile' : 'e.g. understanding JROTC and the terms my Cadet uses'}">${esc(p.goals)}</textarea>`}
      ${isCadet && (STATUS.categories_enabled || []).includes('basic') ? `<label style="display:flex;gap:10px;align-items:flex-start;margin-top:10px;color:var(--text)">
        <input type="checkbox" id="mtBox" ${p.military_track === 'yes' ? 'checked' : ''} style="width:22px;height:22px;flex:none">
        <span>I plan to join the military <span class="faint">— adds the 🪖 Basic Training &amp; Beyond study guide to Learn</span></span></label>` : ''}
      ${isInst ? '<p class="faint">Program settings — the Class PIN and the AI setting — are further down this page; classes, lessons and Cadets are in 🎓 Instructor.</p>' : ''}
      ${cat.length ? `<label>My faith texts (optional — used first in the Faith tab and when you ask about a passage)</label><div>${faithBoxes}</div>` : ''}
      <div class="row" style="margin-top:10px"><button class="btn primary">Save</button><span class="faint" id="profSaved"></span></div>
    </form>
    ${isInst ? '' : `<div class="card"><h3>What Vanguard remembers about you</h3>
      ${mems.length ? mems.map(m => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding:6px 0"><span>${esc(m.text)}</span><button class="btn small danger" data-forget="${esc(m.id)}">Forget</button></div>`).join('') : '<p class="faint">Nothing yet. Vanguard learns as you talk, or add something:</p>'}
      <div class="row" style="margin-top:8px"><input id="memIn" placeholder="e.g. I'm working on my plank time" style="flex:1"><button class="btn small" id="memAdd">Add</button></div></div>`}
    <div class="card"><h3>Security</h3>
      <p class="muted">${lock.pin_set ? `A PIN protects Vanguard. It locks after <b>${lock.idle_minutes}</b> minutes without use.${lock.encrypted ? ' Your files are <b>protected with your PIN</b> on this device.' : ''}` : 'No PIN set — anyone who picks up this device can open Vanguard, and your files are not protected. Set a PIN of 6–12 digits.'}</p>
      <p class="faint">Your PIN and your <b>backup code</b> are the only keys to your protected files. If you forget your PIN, use "Forgot your PIN?" on the sign-in screen. Lost your code? Make a new one here (it replaces the old one).</p>
      <div class="row">
        ${lock.pin_set ? '<input id="pinCur" type="password" inputmode="numeric" maxlength="12" placeholder="Current PIN" style="flex:1">' : ''}
        <input id="pinNew" type="password" inputmode="numeric" maxlength="12" placeholder="${lock.pin_set ? 'New PIN' : 'New PIN (6–12 digits)'}" style="flex:1">
        <button class="btn small" id="pinSave">${lock.pin_set ? 'Change PIN' : 'Set PIN'}</button>
      </div>
      ${lock.pin_set ? `<div class="row" style="margin-top:8px">
        <label style="margin:0">Lock after</label><select id="idleSel" style="width:auto">${[5, 10, 15, 30, 60].map(m => `<option ${m === lock.idle_minutes ? 'selected' : ''}>${m}</option>`).join('')}</select><span class="faint">minutes</span>
        <button class="btn small" id="lockNow">🔒 Lock now</button><button class="btn small" id="newCode">🔑 New backup code</button>${isInst ? '' : '<button class="btn small danger" id="pinRemove">Remove PIN</button>'}</div>` : ''}
      ${isInst ? '<p class="faint">An instructor profile always keeps its PIN.</p>' : ''}
      <p class="faint" id="pinMsg"></p>
      <p class="faint">For full protection if the device is lost, also turn on disk encryption (BitLocker on Windows) — see SECURITY.md.</p>
    </div>
    <div class="card"><h3>About this device</h3>
      <p class="muted">${e.model ? `Offline AI model: <b>${esc(e.model)}</b>.` : 'No offline AI model installed — the library, study tools and logbook still work.'}</p>
      <p class="muted">Library: ${lib.cards} study cards, ${lib.quiz_questions} quiz questions, ${lib.documents.length} official documents. Vanguard works completely offline.</p>
      <p class="muted">Voice: ${speech.ok ? `read-aloud ready (${esc(speech.voice.name)}, on this device)` : 'no offline voice found for read-aloud'}${STATUS.voice ? ' · 🎤 talk-to-Vanguard installed' : ' · 🎤 talk-to-Vanguard not installed (tools/install_voice.py)'}.</p>
      ${speech.ok ? `<label style="color:var(--text)"><input type="checkbox" id="autoRead" ${speech.auto ? 'checked' : ''} style="width:auto"> Read every answer aloud automatically</label>` : ''}
      <div class="row" style="margin-top:8px"><button class="btn small" id="quitApp">⏻ Quit Vanguard</button>${isInst ? '' : '<button class="btn small" id="tourAgain">Take the tour</button>'}<button class="btn small" id="reloadLib">Reload library</button><button class="btn small danger" id="clearChat">Clear chat history</button></div>
    </div>
    <div class="card"><h3>Backup and move to a new device</h3>
      <p class="muted">Saves your profile, logbook, letters, address book, study progress and what Vanguard remembers into one <b>encrypted</b> file. Device settings are never included.</p>
      ${isInst ? '<p class="faint">This backs up your own profile only. Your program — classes, lessons, scenarios, fitness events — isn\'t in it yet; a program export is coming in a later update.</p>' : ''}
      <label>Backup password (at least 10 characters — three or four words works well)</label>
      <input id="bkPass" type="password" autocomplete="new-password" maxlength="200" placeholder="Needed to open the backup later — write it down">
      <div class="row" style="margin-top:8px"><button class="btn small" id="bkSave">⬇ Download encrypted backup</button>
        <label class="btn small" style="margin:0;color:var(--text)">⬆ Restore from backup<input type="file" id="restoreFile" accept=".json,application/json" hidden></label></div>
      <p class="faint" id="restoreMsg">Restoring replaces what's on this device with the backup. Without the backup password, nobody can open the file.</p></div>
    <p class="faint">Vanguard is designed to support JROTC instruction. It isn't an official JROTC, military or school source — your instructor and official sources come first. What you enter is saved on this device and there is no tracking. If this device uses an online AI service, ordinary Ask questions go to it — without your name, notes or earlier chats.</p>`;
  $('#profForm').onsubmit = async ev => {
    ev.preventDefault();
    const data = Object.fromEntries(new FormData(ev.target));
    if ($('#mtBox')) data.military_track = $('#mtBox').checked ? 'yes' : '';
    data.faith_texts = [...document.querySelectorAll('.faithPick:checked')].map(x => x.value).join(',');
    const r = await api('/api/profile', data);
    $('#profSaved').textContent = r.error ? r.error : 'Saved.'; refreshStatus();
  };
  $('#meBody').querySelectorAll('[data-forget]').forEach(b => b.onclick = async () => { await api('/api/memory/forget', { id: b.dataset.forget }); loaders.me(); });
  if ($('#memAdd')) $('#memAdd').onclick = async () => { if ($('#memIn').value.trim()) { await api('/api/memory', { text: $('#memIn').value }); loaders.me(); } };
  showIntegrity().then(showAddons);
  $('#renameProf').onclick = () => {
    $('#profName').innerHTML = `<form id="renameForm" class="row" style="flex-wrap:nowrap"><input id="renameIn" maxlength="40" value="${esc(lock.current.name)}" aria-label="New profile name" style="flex:1">
      <button class="btn small primary">Save</button><button type="button" class="btn small" id="renameCancel">Cancel</button></form><div class="faint" id="renameMsg"></div>`;
    $('#renameIn').focus();
    $('#renameCancel').onclick = loaders.me;
    $('#renameForm').onsubmit = async ev => {
      ev.preventDefault();
      const r = await api('/api/profiles/rename', { name: $('#renameIn').value });
      if (r.ok) loaders.me(); else $('#renameMsg').textContent = r.error || 'Could not rename.';
    };
  };
  $('#switchProf').onclick = async () => { await api('/api/lock', {}); location.replace('/?pick=1'); };
  $('#addProf').onclick = async () => { await api('/api/lock', {}); location.replace('/?new=1'); };
  $('#delProf').onclick = async () => {
    if (!confirm(`Permanently delete the profile "${lock.current.name}" and everything in it (logbook, letters, progress)? Download a backup first if you want to keep it.`)) return;
    const pin = lock.pin_set ? prompt('Enter this profile\'s PIN to confirm:') : '';
    if (pin === null) return;
    const r = await api('/api/profiles/delete', { pin });
    if (r.ok) location.reload(); else alert(r.error);
  };
  $('#pinSave').onclick = async () => {
    const r = await api('/api/pin/set', { new: $('#pinNew').value, current: $('#pinCur') ? $('#pinCur').value : '' });
    if (r.ok) (r.recovery ? showRecoveryCode(r.recovery, () => loaders.me()) : loaders.me()); else $('#pinMsg').textContent = r.error;
  };
  if (lock.pin_set) {
    $('#newCode').onclick = async () => {
      const cur = $('#pinCur').value;
      if (!cur) { $('#pinMsg').textContent = 'Type your current PIN first.'; $('#pinCur').focus(); return; }
      const r = await api('/api/pin/recovery', { pin: cur });
      if (r.recovery) { $('#pinCur').value = ''; showRecoveryCode(r.recovery); } else $('#pinMsg').textContent = r.error;
    };
    $('#idleSel').onchange = async ev => { await api('/api/pin/idle', { minutes: +ev.target.value }); loaders.me(); };
    $('#lockNow').onclick = async () => { await api('/api/lock', {}); location.reload(); };
    if ($('#pinRemove')) $('#pinRemove').onclick = async () => {
      const cur = $('#pinCur').value;
      if (!cur) { $('#pinMsg').textContent = 'Type your current PIN first.'; return; }
      if (!confirm('Remove the PIN? Your files will be decrypted, and anyone with this device could open them.')) return;
      const r = await api('/api/pin/remove', { current: cur });
      if (r.ok) loaders.me(); else $('#pinMsg').textContent = r.error;
    };
  }
  $('#restoreFile').onchange = async ev => {
    const f = ev.target.files[0]; if (!f) return;
    if (!confirm('Replace everything on this device with this backup?')) { ev.target.value = ''; return; }
    let data; try { data = JSON.parse(await f.text()); } catch (e) { $('#restoreMsg').textContent = "That file couldn't be read."; return; }
    ev.target.value = '';
    if (data.vanguard_backup_sealed && !$('#bkPass').value) { $('#restoreMsg').textContent = 'Type the backup password first, then choose the file again.'; $('#bkPass').focus(); return; }
    $('#restoreMsg').textContent = 'Opening the backup…';
    const r = await api('/api/restore', { file: data, password: $('#bkPass').value });
    $('#restoreMsg').textContent = r.error ? r.error : `Restored (${r.restored.length} parts, backup from ${r.from}).`;
    if (!r.error) setTimeout(() => location.reload(), 1200);
  };
  $('#bkSave').onclick = async () => {
    $('#restoreMsg').textContent = 'Encrypting…';
    const r = await api('/api/backup', { password: $('#bkPass').value });
    if (r.error) { $('#restoreMsg').textContent = r.error; return; }
    const url = URL.createObjectURL(new Blob([JSON.stringify(r.file)], { type: 'application/json' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: r.name });
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
    $('#bkPass').value = '';
    $('#restoreMsg').textContent = 'Encrypted backup saved. Keep the password somewhere safe — the file is useless without it.';
  };
  if ($('#autoRead')) $('#autoRead').onchange = ev => speech.setAuto(ev.target.checked);
  if ($('#tourAgain')) $('#tourAgain').onclick = () => tour(lock.current.id);
  $('#quitApp').onclick = async () => {
    if (!confirm('Close Vanguard? Open it again any time from the desktop icon.')) return;
    await api('/api/quit', {});
    document.body.innerHTML = '<div style="display:grid;place-items:center;height:100vh;padding:16px;text-align:center"><div><h2>Vanguard is closed.</h2><p>Open it again from the <b>Vanguard</b> icon. You can close this tab.</p></div></div>';
  };
  $('#reloadLib').onclick = async () => {
    const admin = (await api('/api/lock')).admin_set ? prompt('Class PIN:') : '';
    if (admin === null) return;
    const r = await api('/api/library/reload', { admin });
    if (r.error) alert(r.error); else loaders.me();
  };
  $('#clearChat').onclick = async () => { if (confirm('Clear the chat history?')) { await api('/api/history/clear', {}); location.reload(); } };
};

// ── FIRST-RUN TOUR ── (once per profile on this device; "Take the tour" on the Me tab shows it again)
const TOUR = [
  ['home', '🏠 Home', "What's due, your Daily 10, and anything your instructor starts in class — all in one place."],
  ['study', '📘 Learn', 'Pick a section at the top — any branch of service, leadership, citizenship, health, careers, faith or the library. Every card shows its source.'],
  ['lead', '🧭 Lead', 'Leadership scenarios: real situations, your decision, what happened and why, and what you would do next time.'],
  ['me', '👤 Me', 'Your progress and portfolio, fitness (Train), service hours (Serve), Explore Military Service, and your settings.'],
];
async function tour(pid) {
  if ((await api('/api/status')).kind === 'instructor') return;   // the tour shows the Cadet areas
  const done = () => { try { localStorage.setItem('tour:' + pid, '1'); } catch (e) { } };
  const o = document.createElement('div');
  o.id = 'tour';
  o.style.cssText = 'position:fixed;inset:0;z-index:150;background:rgba(0,0,0,.55);display:grid;place-items:center;padding:16px';
  document.body.appendChild(o);
  let i = 0;
  const show = () => {
    document.querySelectorAll('nav [data-v]').forEach(b => b.style.outline = '');
    if (i >= TOUR.length) { o.remove(); done(); return; }
    const [v, name, text] = TOUR[i], b = document.querySelector(`nav [data-v="${v}"]`);
    if (b) b.style.outline = '3px solid var(--tan)';
    o.innerHTML = `<div class="card" role="dialog" aria-modal="true" aria-labelledby="tourH" style="max-width:420px;width:100%">
      <div class="faint">${i + 1} of ${TOUR.length}</div><h3 id="tourH">${name}</h3><p>${text}</p>
      ${i === TOUR.length - 1 ? '<p class="faint">Your work is saved on this device. Vanguard supports your instructor — it doesn’t replace your instructor, your curriculum or official sources.</p>' : ''}
      <div class="row"><button class="btn primary" id="tourNext">${i === TOUR.length - 1 ? 'Done' : 'Next'}</button>
      ${i < TOUR.length - 1 ? '<button class="btn small" id="tourSkip">Skip the tour</button>' : ''}</div></div>`;
    $('#tourNext').onclick = () => { i++; show(); };
    if ($('#tourSkip')) $('#tourSkip').onclick = () => { i = TOUR.length; show(); };
    $('#tourNext').focus();
  };
  show();
}
unlocked.then(async s => {
  if (!s || !s.current) return;
  if ((await api('/api/status')).profile.intake_done !== 'yes') {
    if (!s.pin_set) return intake.start();                       // no PIN yet: the short interview ends with one
    await api('/api/profile', { intake_done: 'yes' });            // 30-second join: grade and goals are optional, in Me
  }
  let seen = '1';
  try { seen = localStorage.getItem('tour:' + s.current.id); } catch (e) { }
  if (!seen) tour(s.current.id);
});

unlocked.then(s => s && refreshStatus());

// Me -> My class: join (or change to) a class with the instructor's join code.
$('#meBody').addEventListener('click', async e => {
  if (!e.target.closest('#joinGo')) return;
  const r = await api('/api/join', { code: $('#joinIn').value });
  $('#joinMsg').textContent = r.error || `✓ You joined ${r.joined}. Your instructor sees it the next time they open class records.`;
});
// Me tiles: Progress, Train, Serve and the logbook live under Me (the bottom bar keeps four tabs).
$('#meBody').addEventListener('click', e => { const b = e.target.closest('[data-go-view]'); if (b) openView(b.dataset.goView); });
