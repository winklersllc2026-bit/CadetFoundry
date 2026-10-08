'use strict';
// Ask tab: chat, sources, Simpler.

// ── ASK ──
const thread = $('#thread'), logEl = $('#log');
function addMsg(role, html) {
  const d = document.createElement('div');
  d.className = 'msg ' + (role === 'user' ? 'me' : 'ai');
  if (role === 'user') d.textContent = html; else d.innerHTML = '<div class="who">VANGUARD</div><div class="body">' + html + '</div>';
  thread.appendChild(d); logEl.scrollTop = logEl.scrollHeight;
  return d;
}
let busy = false;
// A publication 5+ years old gets a warning wherever it's cited (search, answer sources).
const oldEd = ed => !!ed && +ed.slice(0, 4) <= new Date().getFullYear() - 5;
const aiReady = () => { const e = (STATUS || {}).engine || {}; return !!(e.model || (e.online_enabled && (e.online_keys || []).length)); };
// Read a server-sent event stream (chat, simplify) and hand each event to onEvent.
async function streamEvents(url, payload, onEvent) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const reader = res.body.getReader(), dec = new TextDecoder(); let buf = '';
  for (;;) {
    const { value, done } = await reader.read(); if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const line = buf.slice(0, i); buf = buf.slice(i + 2);
      if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)));
    }
  }
}
async function send(text) {
  text = (text || '').trim(); if (!text || busy) return;
  if (intake.active) { $('#msgIn').value = ''; return intake.answer(text); }   // first-run interview
  busy = true; $('#sendBtn').disabled = true; $('#msgIn').value = '';
  if (speech.ok) speech.stop();                            // a new question stops reading the last answer
  addMsg('user', text); $('#suggest').hidden = true;
  const box = addMsg('ai', '<p class="faint">Thinking…</p>'), body = box.querySelector('.body');
  let full = '', care = false;
  try {
    await streamEvents('/api/chat', { message: text }, ev => {
      if (ev.banner) care = true;
      if (ev.t) { full += ev.t; body.innerHTML = md(full); logEl.scrollTop = logEl.scrollHeight; }
      if (ev.done && ev.cites && ev.cites.length) {
        // one chip per passage used; tap it to read the exact text the answer came from
        const s = document.createElement('div'); s.className = 'sources';
        s.innerHTML = ev.cites.map((c, n) => `<button class="chip" data-cite="${n}" style="cursor:pointer;background:none">📄 ${esc(c.source)} · ${esc(c.where)}${oldEd(c.edition) ? ` · ⚠️ ${esc(c.edition.slice(0, 4))}` : ''}</button>`).join('') +
          '<div class="cite" hidden style="margin-top:8px"></div>';
        const panel = s.querySelector('.cite');
        s.querySelectorAll('[data-cite]').forEach(b => b.onclick = () => {
          const c = ev.cites[+b.dataset.cite], open = !panel.hidden && panel.dataset.n === b.dataset.cite;
          panel.hidden = open; panel.dataset.n = b.dataset.cite;
          panel.innerHTML = open ? '' : `<div class="card" style="margin:0"><div class="faint">${esc(c.source)} — ${esc(c.where)}${/^page \d+$/.test(c.where) ? ' (counted from the start of the PDF)' : ''}${c.edition ? ` · edition ${esc(c.edition)}` : ''}</div>
            ${oldEd(c.edition) ? `<div class="faint" style="color:var(--tan)">⚠️ This edition is from ${esc(c.edition.slice(0, 4))} — guidance may have changed. Check with your cadre or the current publication.</div>` : ''}
            <div style="white-space:pre-wrap;font-size:14px;margin-top:6px">${esc(c.text)}</div></div>`;
        });
        box.appendChild(s);
      }
    });
  } catch (err) { body.innerHTML = '<p>Something went wrong talking to Vanguard. Is it still running?</p>'; }
  if (full && !care && aiReady() && !(STATUS && STATUS.library_only)) {   // re-say it in plain words (needs the AI)
    const b = document.createElement('button');
    b.className = 'btn small'; b.textContent = '🔁 Simpler'; b.title = 'Explain it in plainer words'; b.style.margin = '6px 6px 0 0';
    b.onclick = async () => {
      b.disabled = true;
      const out = document.createElement('div'); out.className = 'card'; out.style.margin = '8px 0 0';
      out.innerHTML = '<div class="faint">🤖 In plain words — AI rewording; the ✅ checked answer and 📄 sources are the official text</div><div class="body"><p class="faint">…</p></div>';
      b.after(out);
      let txt = '';
      await streamEvents('/api/simplify', { text: full }, ev => { if (ev.t) { txt += ev.t; out.querySelector('.body').innerHTML = md(txt); } });
      if (speech.ok) { const r = document.createElement('button'); r.className = 'btn small'; r.textContent = '🔊'; r.title = 'Read aloud (on this device)'; r.style.marginTop = '6px'; r.onclick = () => speech.toggle(txt, r); out.appendChild(r); }
    };
    box.appendChild(b);
  }
  if (full && speech.ok) {
    const b = document.createElement('button');
    b.className = 'btn small'; b.textContent = '🔊'; b.title = 'Read aloud (on this device)'; b.style.marginTop = '6px';
    b.onclick = () => speech.toggle(full, b); box.appendChild(b);
    if (speech.auto) speech.say(full, b);                  // auto-read uses the same button, so ⏹ stops it
  }
  busy = false; $('#sendBtn').disabled = false; logEl.scrollTop = logEl.scrollHeight;
  loadChats();                                 // a new chat takes its name from the first question
}
$('#composer').addEventListener('submit', e => { e.preventDefault(); send($('#msgIn').value); });
$('#msgIn').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send($('#msgIn').value); } });
thread.addEventListener('click', e => {           // the suggestions (re-drawn with every conversation)
  if (e.target.tagName === 'BUTTON' && e.target.closest('#suggest') && !intake.active) send(e.target.textContent);
});

// ── CONVERSATIONS ── (sidebar on the left; on a phone it slides in from ☰ Chats)
const WELCOME = thread.innerHTML;                 // Vanguard's greeting + the suggestions
function showChat(messages) {
  thread.innerHTML = WELCOME;
  $('#suggest').hidden = messages.length > 0;
  for (const m of messages) m.role === 'user' ? addMsg('user', m.content) : addMsg('ai', md(m.content));
  logEl.scrollTop = logEl.scrollHeight;
}
async function loadChats() {
  const { current, chats } = await api('/api/chats');
  const day = t => { const d = new Date(t * 1000), now = new Date(), diff = (now - d) / 864e5;
    return d.toDateString() === now.toDateString() ? 'Today' : diff < 2 ? 'Yesterday' : diff < 7 ? 'This week' : 'Older'; };
  let last = '';
  $('#chatList').innerHTML = chats.filter(c => c.n || c.id === current).map(c => {
    const head = day(c.updated) !== last ? `<div class="when">${(last = day(c.updated))}</div>` : '';
    return `${head}<div class="ci${c.id === current ? ' on' : ''}" data-id="${esc(c.id)}" title="${esc(c.title)}"><span class="t">${esc(c.title)}</span>
      <button type="button" data-act="rename" aria-label="Rename">✎</button><button type="button" data-act="delete" aria-label="Delete">🗑</button></div>`;
  }).join('') || '<p class="faint" style="padding:4px">Your conversations will show up here.</p>';
  $('#chatTitle').textContent = (chats.find(c => c.id === current) || {}).title || 'New chat';
}
async function newChat() {
  if (busy || intake.active) return;
  await api('/api/chats/new', {});
  showChat([]); $('#chatSide').classList.remove('open'); loadChats(); $('#msgIn').focus();
}
$('#newChat').onclick = newChat; $('#newChat2').onclick = newChat;
$('#chatToggle').onclick = () => $('#chatSide').classList.toggle('open');
document.querySelector('.chatMain').addEventListener('click', e => { if (!e.target.closest('#chatToggle')) $('#chatSide').classList.remove('open'); });
$('#chatList').addEventListener('click', async e => {
  const row = e.target.closest('.ci'); if (!row || busy || intake.active) return;
  const id = row.dataset.id, act = e.target.dataset.act;
  if (act === 'rename') {
    const t = prompt('Name this conversation:', row.title); if (t && t.trim()) await api('/api/chats/rename', { id, title: t });
  } else if (act === 'delete') {
    if (!confirm(`Delete "${row.title}"?`)) return;
    await api('/api/chats/delete', { id });
    showChat(await api('/api/history'));
  } else {
    showChat((await api('/api/chats/open', { id })).messages || []);
    $('#chatSide').classList.remove('open');
  }
  loadChats();
});
const chatReady = (async () => {   // the conversation you were in (the first-run interview waits for it)
  if (!await unlocked) return;
  showChat(await api('/api/history'));
  loadChats();
})();
