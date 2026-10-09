'use strict';
// First-run interview: a few short questions so Vanguard fits the Cadet. Scripted (no AI), so it is the same every
// time and works offline. Only what helps: name, grade, what they want to get better at, goals -- no body size, sex
// or military status (minors' data stays minimal). Ends with a required PIN and the recovery code, then the tour.
const SKIPPY = /^\s*(skip|pass|no|nope|why\??|prefer not.*|rather not.*|none of your business|n\/a|idk|i don'?t want to.*)\s*[.!]?\s*$/i;
// A new Soldier may type a real question instead of an answer ("can the Army pay for college"). It must never be
// saved as their name or job; Vanguard holds it and answers it right after setup. A question word alone isn't
// enough ("Will Carter", "May Lee" are names), so it also needs a "?" or a sentence's worth of words.
const QUESTION_START = /^\s*(can|could|what|what's|how|why|when|where|who|which|do|does|did|is|are|am|should|will|would|may|tell me|explain)\b/i;
const isQuestion = t => /\?\s*$/.test(t) || (QUESTION_START.test(t) && t.trim().split(/\s+/).length >= 4);
const NUM = (lo, hi, help) => v => { const n = parseFloat(String(v).replace(/[^\d.]/g, '')); return n >= lo && n <= hi ? null : help; };
const NAME_CHECK = v => v.trim().split(/\s+/).length > 4 || /\d/.test(v) ? 'Just your name, please.' : null;

function intakeQuestions(p, kind, faith) {
  const name = p.name ? `, ${p.name.split(' ')[0]}` : '';
  if (kind === 'guardian') return [
    { f: 'name', q: `Welcome to Vanguard${name}. I'll ask a few quick questions to set things up. First — what should I call you?`, chips: p.name ? [p.name] : [], check: NAME_CHECK },
    { f: 'goals', q: 'What would help you most? (for example: understanding JROTC, the terms your Cadet uses, how to support them)', optional: true },
  ];
  const qs = [
    { f: 'name', q: `Welcome to Vanguard${name}. Before we start, I'll ask you about yourself so Vanguard fits you — it takes about thirty seconds. What's your first and last name?`, chips: p.name ? [p.name] : [], check: NAME_CHECK },
    { f: 'grade', q: 'What grade are you in?', chips: STATUS.grades || [], optional: true },
    { f: 'interests', q: 'What do you want to get better at this year? Pick one or type your own.', chips: STATUS.interests || [], optional: true },
    { f: 'goals', q: 'What is one goal you have this year? (for example: lead my squad at drill, raise my grades, run a faster mile)', optional: true },
  ];
  // (no faith question: Vanguard is used in public schools; the faith library is off unless an instructor adds it)
  return qs;
}

const intake = {
  active: false, qs: [], i: 0, lock: null, held: [],
  async start() {
    await chatReady;
    const [lock, st, cat] = await Promise.all([api('/api/lock'), api('/api/status'), api('/api/faith/catalog')]);
    STATUS = st;
    if (st.kind === 'instructor') {                // the interview is for Cadets; instructors go to their tools
      STATUS.profile = await api('/api/profile', { intake_done: 'yes' });
      openView('instructor');
      return;
    }
    this.lock = lock; this.active = true; this.i = 0;
    this.qs = intakeQuestions({ ...(st.profile || {}), name: (st.profile || {}).name || lock.current.name }, st.kind, (cat && cat.installed) || []);
    openView('ask');
    $('#suggest').hidden = true;
    $('#msgIn').placeholder = 'Type your answer…';
    this.ask();
  },
  ask() {
    if (this.i >= this.qs.length) return this.pin();
    const { q, chips } = this.qs[this.i];
    const box = addMsg('ai', md(q));
    if (chips && chips.length) {
      const row = document.createElement('div'); row.className = 'suggest';
      row.innerHTML = chips.map(c => `<button type="button">${esc(c)}</button>`).join('');
      row.onclick = e => { if (e.target.tagName === 'BUTTON' && this.active) { row.remove(); this.answer(e.target.textContent); } };
      box.appendChild(row);
    }
    $('#msgIn').focus();
  },
  async answer(text) {
    text = (text || '').trim(); if (!text) return;
    const cur = this.qs[this.i];
    if (!cur) { addMsg('ai', md('Use the PIN boxes above to finish — this protects your profile.')); return; }
    addMsg('user', text);
    if (SKIPPY.test(text) && !cur.optional) {
      addMsg('ai', md(cur.hw ? `${HW_PUSHBACK}\n\n${cur.q}` : `I need this one to set you up right. ${cur.q}`));
      return;
    }
    const isChip = (cur.chips || []).includes(text);
    if (!isChip && cur.f !== 'goals' && isQuestion(text)) {            // a question, not an answer
      this.held.push(text);
      addMsg('ai', md(`Good question — I'll answer it as soon as we finish setting up.\n\n${cur.q}`));
      return;
    }
    const problem = !isChip && cur.check && cur.check(text);
    if (problem) { addMsg('ai', md(`${problem}\n\n${cur.q}`)); return; }
    const value = cur.map ? cur.map(text) : (/^(don'?t know yet|not there yet)$/i.test(text) ? '' : text);
    const r = await api('/api/profile', { [cur.f]: cur.f === 'rank' && /^future soldier/i.test(value) ? 'Future Soldier' : value });
    if (r.error) { addMsg('ai', md(`${r.error}\n\n${cur.q}`)); return; }
    STATUS.profile = r;
    this.i++; this.ask();
  },
  pin() {
    if (this.lock.pin_set) return this.adminPin();
    const box = addMsg('ai', md('Last step: **protect your profile with a PIN** (6–12 digits). It locks Vanguard when you walk away and **encrypts your files** on this device. Nobody — not even the person who set up this device — can read them without it.'));
    box.insertAdjacentHTML('beforeend', `<div class="row" style="margin-top:8px">
      <input id="inPin1" type="password" inputmode="numeric" maxlength="12" placeholder="New PIN" style="flex:1" autocomplete="new-password">
      <input id="inPin2" type="password" inputmode="numeric" maxlength="12" placeholder="Same PIN again" style="flex:1" autocomplete="new-password">
      <button class="btn primary" type="button" id="inPinGo">Set PIN</button></div><p class="faint" id="inPinMsg"></p>`);
    $('#inPin1').focus();
    $('#inPinGo').onclick = async () => {
      if ($('#inPin1').value !== $('#inPin2').value) { $('#inPinMsg').textContent = "The two PINs don't match."; return; }
      $('#inPinGo').disabled = true; $('#inPinMsg').textContent = 'Setting your PIN and encrypting your files…';
      const r = await api('/api/pin/set', { new: $('#inPin1').value, current: '' });
      if (!r.ok) { $('#inPinGo').disabled = false; $('#inPinMsg').textContent = r.error; return; }
      box.querySelector('.row').remove(); $('#inPinMsg').textContent = '✓ PIN set. Your files are encrypted.';
      const next = () => this.adminPin();
      if (r.recovery) showRecoveryCode(r.recovery, next); else next();
    };
  },
  adminPin() {
    if (this.lock.admin_set || STATUS.kind === 'guardian') return this.finish();
    const box = addMsg('ai', md("One more for whoever looks after this computer: a **Instructor PIN**. It's needed to install Vanguard updates, and it's separate from your own PIN. If this is your own device, set one now."));
    box.insertAdjacentHTML('beforeend', `<div class="row" style="margin-top:8px">
      <input id="inAdm" type="password" inputmode="numeric" maxlength="12" placeholder="Admin PIN (6–12 digits)" style="flex:1" autocomplete="new-password">
      <button class="btn primary" type="button" id="inAdmGo">Set Instructor PIN</button><button class="btn small" type="button" id="inAdmSkip">Not my device — skip</button></div><p class="faint" id="inAdmMsg"></p>`);
    $('#inAdmGo').onclick = async () => {
      const r = await api('/api/admin/pin', { new: $('#inAdm').value });
      if (!r.ok) { $('#inAdmMsg').textContent = r.error; return; }
      box.querySelector('.row').remove(); $('#inAdmMsg').textContent = '✓ Admin PIN set.'; this.finish();
    };
    $('#inAdmSkip').onclick = () => { box.querySelector('.row').remove(); this.finish(); };
  },
  async finish() {
    const p = await api('/api/profile', { intake_done: 'yes' });
    this.active = false; STATUS.profile = p;
    // md() escapes, so plain values here
    const facts = [p.name && `**${p.name}**`, p.grade, p.interests && `working on ${p.interests}`].filter(Boolean);
    addMsg('ai', md(`You're set up${facts.length ? ': ' + facts.join(' · ') : ''}.\n\nYou can change any of this in **👤 Me**.${aiReady() ? '' : ' For full-sentence answers, add the **Offline AI** in **Me → Add-ons** (needs internet once).'} Now it's your turn — ask me anything in the library, or tap a suggestion below.`));
    $('#suggest').hidden = false; $('#msgIn').placeholder = 'Ask Vanguard…';
    thread.appendChild($('#suggest'));
    refreshStatus();
    let seen = '1';
    try { seen = localStorage.getItem('tour:' + this.lock.current.id); } catch (e) { }
    if (!seen) tour(this.lock.current.id);
    const held = this.held.splice(0);
    if (held.length) setTimeout(() => send(held[0]), 600);   // the question they asked during setup
  },
};
