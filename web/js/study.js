'use strict';
// Study tab: cards, quizzes, MOS explorer, land nav, report drills, exams, manual search, Basic timeline, board prep, pocket cards.

// ── STUDY ──
const studyBody = $('#studyBody');
// Learn: the five categories from the owner's spec (§7), then Explore Military Service for any curious Cadet, and
// Basic Training & Beyond only for a Cadet who said they plan to join (the server decides what each profile sees).
const CATEGORY_ICON = { leadership: '🧭', citizenship: '🏛️', military: '🎖️', health: '💚', careers: '💼', explore: '🎗️', basic: '🪖' };
const CATEGORY_BLURB = {
  leadership: 'Values, leader attributes and how good leaders act. Practice it in 🧭 Lead.',
  citizenship: 'The Constitution, your rights, how government works, and being part of your community.',
  military: 'Ranks, customs and courtesies, drill, uniforms, map reading and military traditions.',
  health: 'Fitness, nutrition, sleep, heat safety and taking care of yourself.',
  careers: 'Planning what comes next: college, careers, apprenticeships, tests — and money basics.',
  explore: 'For Cadets curious about serving: benefits, pay, training and Army jobs. Information only.',
  basic: 'Your study guide for basic training and beyond — because you said you plan to join.',
};

loaders.study = async () => {
  const [topics, dly] = await Promise.all([api('/api/topics'), api('/api/daily')]);
  const st = dly.status, cats = STATUS.categories || {};
  const byCat = {};
  topics.forEach(t => t.cards.forEach(c => (byCat[c.category] = byCat[c.category] || []).push(c)));
  const chips = list => (list || []).map(c => `<button class="chip" data-card="${esc(c.id)}" style="background:none;cursor:pointer">${esc(c.title)}</button>`).join('');
  const extra = {
    leadership: '<button class="btn small" id="toLead">🧭 Leadership scenarios</button>',
    citizenship: '<button class="btn small" data-books="1">📜 Founding documents</button>',
    military: '<button class="btn small" id="navGo">🗺️ Map reading practice</button> <button class="btn small" data-books="1">📚 Army history</button>',
    explore: '<button class="btn small" id="jobsGo">💼 Army jobs explorer</button> <button class="btn small" id="toServe">More in 🤝 Serve</button>',
    basic: `<div class="row" style="flex-wrap:wrap;gap:6px"><button class="btn small" id="nineGo">📻 9-line</button><button class="btn small" id="saluteGo">SALUTE</button>
      <button class="btn small" id="laceGo">LACE</button><button class="btn small" id="bpUniform">Uniform check</button><button class="btn small" id="bpBoard">Mock board</button>
      <button class="btn small" id="bpCreed">Soldier's Creed</button><button class="btn small" id="printGo">🖨️ Pocket cards</button></div><div id="bctCard" style="margin-top:8px"></div>`,
  };
  const section = cat => {
    const list = byCat[cat] || [];
    if (!list.length && !extra[cat]) return '';
    return `<div class="card"${cat === 'basic' || cat === 'explore' ? ' style="border-color:var(--tan)"' : ''}>
      <div class="topic"><div><h3>${CATEGORY_ICON[cat] || ''} ${esc(cats[cat])}</h3><div class="faint">${esc(CATEGORY_BLURB[cat] || '')}</div></div>
      ${list.length ? `<button class="btn small" data-quiz="${esc(cat)}">Quiz</button>` : ''}</div>
      ${list.length ? `<div style="margin-top:8px">${chips(list)}</div>` : '<p class="faint" style="margin:8px 0 0">Study cards for this section are being written.</p>'}
      ${extra[cat] ? `<div style="margin-top:10px">${extra[cat]}</div>` : ''}</div>`;
  };
  const order = ['leadership', 'citizenship', 'military', 'health', 'careers', 'explore', 'basic'].filter(c => c in cats);
  studyBody.innerHTML = `<h2>Learn</h2>
    <div class="card" style="border-color:var(--tan)"><div class="row" style="justify-content:space-between">
      <div><h3>🔥 Daily 10</h3><div class="faint">${st.done_today ? `Done today: ${st.today_score.right}/${st.today_score.total}. ` : 'Ten questions, every day. '}Streak: <b>${st.streak}</b> day${st.streak === 1 ? '' : 's'} · best ${st.best}</div></div>
      <button class="btn primary" id="dailyGo">${st.done_today ? 'Again' : 'Start'}</button></div></div>
    ${order.map(section).join('')}
    <div class="card"><div class="row" style="justify-content:space-between"><div><h3>📚 Books</h3><div class="faint">The Constitution and founding documents, American military history, and classics — free on this device.</div></div>
      <button class="btn small" id="booksGo">Open</button></div></div>
    ${(STATUS.modules_off || []).includes('faith') ? '' : `<div class="card"><div class="row" style="justify-content:space-between"><div><h3>📖 Faith texts</h3><div class="faint">Optional: read and search public-domain scripture — the Bible, Tanakh, Quran, Book of Mormon, Bhagavad Gita and more. Pick yours in 👤 Me.</div></div>
      <button class="btn small" data-open-faith>Open</button></div></div>`}
    <form class="card" id="libSearch" role="search"><h3>🔎 Search the library</h3>
      <div class="row" style="flex-wrap:nowrap"><input id="libQ" type="search" placeholder="e.g. Bill of Rights, salute, sleep" aria-label="Search the library" style="flex:1"><button class="btn primary">Search</button></div>
      <div class="faint">Searches the study cards and documents on this device — instant, no AI. Tap a result to read it.</div>
      <div id="libResults" aria-live="polite"></div></form>
    <div class="card"><div class="row" style="justify-content:space-between"><div><h3>📝 Exam mode</h3><div class="faint">A timed multiple-choice test — graded on the device, with your score history.</div></div>
      <button class="btn small" id="examGo">Take an exam</button></div></div>
    <div class="card"><div class="row" style="justify-content:space-between"><div><h3>Mixed quiz</h3><div class="faint">10 questions from everything you can see — the ones you miss come back more often.</div></div><button class="btn primary" data-quiz="">Start</button></div></div>`;
  const on = (id, fn) => { const el = $('#' + id); if (el) el.onclick = fn; };
  $('#dailyGo').onclick = () => chooseQuiz('', true);
  on('navGo', landNav); on('examGo', examSetup); on('jobsGo', () => jobsExplorer()); on('booksGo', () => booksShelf());
  document.querySelectorAll('[data-open-faith]').forEach(b => { b.onclick = () => openView('faith'); });
  on('toLead', () => openView('lead')); on('toServe', () => openView('serve'));
  on('printGo', pocketCards); on('bpUniform', uniformCheck); on('bpBoard', () => mockBoard()); on('bpCreed', creedDrill);
  on('nineGo', nineLine); on('saluteGo', saluteDrill); on('laceGo', () => sortDrill('LACE'));
  studyBody.querySelectorAll('[data-books]').forEach(b => { b.onclick = () => booksShelf(); });
  if ($('#bctCard')) showBct();
  $('#libSearch').onsubmit = e => { e.preventDefault(); librarySearch($('#libQ').value); };
};

// ── BOOKS: free public-domain reading, offline ──
// Books are for reading, not for answers -- Ask stays with official sources.
async function booksShelf(q = '') {
  const r = await api('/api/books');
  const have = r.books.filter(b => b.installed);
  if (!have.length) {
    studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button><div class="card" style="margin-top:12px">
      <h3>📚 Books</h3><p>No books are on this device yet.</p><p class="faint">An administrator adds them once with <code>python tools/fetch_books.py</code> (needs internet one time).</p></div>`;
    $('#backStudy').onclick = loaders.study; return;
  }
  const hits = q ? (await api(`/api/books/search?q=${encodeURIComponent(q)}`)).hits : null;
  const row = b => `<div class="card" data-book="${esc(b.id)}" style="cursor:pointer;margin:8px 0">
      <div class="row" style="justify-content:space-between;flex-wrap:nowrap"><div><b>${esc(b.title)}</b>${b.subtitle ? `<div class="faint">${esc(b.subtitle)}</div>` : ''}<div class="faint">${esc(b.author)}</div></div>
      <span class="faint" style="white-space:nowrap">${b.at != null ? `Continue · ${b.at + 1}/${b.chapters.length}` : `${b.chapters.length} ${b.chapters.length === 1 ? 'part' : 'parts'}`}</span></div></div>`;
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><h3>📚 Books</h3>
      <p class="faint">Free, public-domain books kept on this device. They're for reading — Ask answers only from official Army sources.</p>
      <div class="row"><input id="bookQ" type="search" value="${esc(q)}" placeholder="Search the books (a word or phrase)" style="flex:1"><button class="btn primary" id="bookGo">Search</button></div></div>
    ${hits ? `<div class="card"><h4>${hits.length ? `Found in ${hits.length} place${hits.length === 1 ? '' : 's'}` : 'Not found in the books on this device.'}</h4>
      ${hits.map((h, n) => `<div data-hit="${n}" style="cursor:pointer;border-top:1px solid var(--line);padding:8px 0"><b>${esc(h.title)}</b> <span class="faint">· ${esc(h.chapter)}</span><div class="faint">…${esc(h.snippet)}…</div></div>`).join('')}</div>` : ''}
    ${r.shelves.map(sh => { const bs = have.filter(b => b.shelf === sh); return bs.length ? `<h3 style="margin:16px 0 4px">${esc(sh)}</h3>${bs.map(row).join('')}` : ''; }).join('')}
    ${r.missing.length ? `<p class="faint">Not on this device yet: ${r.missing.map(esc).join(', ')}. An administrator adds them with <code>python tools/fetch_books.py</code>.</p>` : ''}`;
  $('#backStudy').onclick = loaders.study;
  $('#bookGo').onclick = () => booksShelf($('#bookQ').value.trim());
  $('#bookQ').onkeydown = e => { if (e.key === 'Enter') $('#bookGo').click(); };
  studyBody.querySelectorAll('[data-book]').forEach(c => c.onclick = () => {
    const b = have.find(x => x.id === c.dataset.book); bookReader(b.id, b.at || 0);
  });
  studyBody.querySelectorAll('[data-hit]').forEach(c => c.onclick = () => { const h = hits[+c.dataset.hit]; bookReader(h.id, h.ch, q); });
}

// Book text: paragraphs from blank lines, hard-wrapped lines joined, _italics_ and ### headings kept.
function bookHtml(text, mark) {
  return text.split(/\n\s*\n/).map(p => {
    const t = p.trim(); if (!t) return '';
    if (/^#{1,4}\s/.test(t)) return `<h4>${esc(t.replace(/^#+\s*/, ''))}</h4>`;
    let h = esc(t.replace(/\s*\n\s*/g, ' ')).replace(/_([^_]+)_/g, '<i>$1</i>');
    if (mark) h = h.replace(new RegExp(esc(mark).replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+'), 'gi'), m => `<mark>${m}</mark>`);
    return `<p>${h}</p>`;
  }).join('');
}

async function bookReader(id, ch = 0, mark = '') {
  const r = await api(`/api/books/read?id=${encodeURIComponent(id)}&ch=${ch}`);
  if (r.error) { booksShelf(); return; }
  api('/api/books/place', { id, ch: r.ch });                // remember where this Soldier is (their profile only)
  const shelf = (await api('/api/books')).books.find(b => b.id === id) || {};
  studyBody.innerHTML = `<button class="btn small" id="backBooks">← Books</button>
    <div class="card" style="margin-top:12px"><div class="faint">${esc(r.title)}</div>
      <div class="row" style="margin:6px 0"><select id="bookCh" style="flex:1">${(shelf.chapters || []).map((t, i) => `<option value="${i}" ${i === r.ch ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></div>
      <h2 style="margin:8px 0">${esc(r.chapter)}</h2>
      <div class="book-text" style="line-height:1.65">${bookHtml(r.text, mark)}</div>
      <div class="row" style="justify-content:space-between;margin-top:12px">
        <button class="btn small" id="chPrev" ${r.ch === 0 ? 'disabled' : ''}>← Previous</button>
        <span class="faint">${r.ch + 1} of ${r.of}</span>
        <button class="btn small" id="chNext" ${r.ch >= r.of - 1 ? 'disabled' : ''}>Next →</button></div>
      <p class="faint" style="margin-top:12px">${esc(shelf.license || '')} Source: ${esc(shelf.url || '')}</p></div>`;
  $('#backBooks').onclick = () => booksShelf();
  $('#bookCh').onchange = e => bookReader(id, +e.target.value);
  $('#chPrev').onclick = () => bookReader(id, r.ch - 1);
  $('#chNext').onclick = () => bookReader(id, r.ch + 1);
  if (speech.ok) {
    const b = document.createElement('button'); b.className = 'btn small'; b.textContent = '🔊'; b.title = 'Read aloud (on this device)';
    b.onclick = () => speech.toggle(r.text, b); $('#chPrev').after(b);
  }
  const m = studyBody.querySelector('mark'); (m || studyBody).scrollIntoView({ block: m ? 'center' : 'start' });
}

// ── ARMY JOBS (MOS) EXPLORER ──
async function jobsExplorer(q = '', area = '') {
  const r = await api(`/api/jobs?q=${encodeURIComponent(q)}&area=${encodeURIComponent(area)}`);
  if (!r.total) {
    studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button><div class="card" style="margin-top:12px">
      <p>The job list isn't on this device yet.</p><p class="faint">An administrator adds it once with <code>python tools/fetch_library.py</code> (needs internet one time).</p></div>`;
    $('#backStudy').onclick = loaders.study; return;
  }
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><h3>💼 Army jobs</h3>
      <div class="row"><input id="jobQ" value="${esc(q)}" placeholder="Code (11B), job (medic), or interest (helicopters, computers…)" style="flex:1"><button class="btn primary" id="jobGo">Search</button></div>
      <div style="margin-top:8px"><button class="chip" data-area="" style="cursor:pointer;${!area ? 'border-color:var(--tan);color:var(--tan2)' : ''}">All</button>${r.areas.map(a =>
        `<button class="chip" data-area="${esc(a)}" style="cursor:pointer;${a === area ? 'border-color:var(--tan);color:var(--tan2)' : ''}">${esc(a)}</button>`).join('')}</div>
      <p class="faint">${r.jobs.length} of ${r.total} jobs · official summaries from goarmy.com (saved ${esc(r.fetched)}) · requirements and openings change — ask a career counselor or recruiter.</p></div>
    <div id="jobList">${r.jobs.map(j => `<div class="card" data-job="${esc(j.code + '|' + j.title)}" style="cursor:pointer">
      <div class="row" style="justify-content:space-between"><b>${j.code ? `<span class="mono" style="color:var(--tan2)">${esc(j.code)}</span> ` : ''}${esc(j.title)}</b><span class="faint">${esc(j.area)}</span></div>
      <div class="faint" style="margin-top:4px">${esc(j.summary.slice(0, 160))}${j.summary.length > 160 ? '…' : ''}</div></div>`).join('') || '<div class="empty">No matching jobs.</div>'}</div>`;
  $('#backStudy').onclick = loaders.study;
  $('#jobGo').onclick = () => jobsExplorer($('#jobQ').value, area);
  $('#jobQ').onkeydown = e => { if (e.key === 'Enter') $('#jobGo').click(); };
  studyBody.querySelectorAll('[data-area]').forEach(b => b.onclick = () => jobsExplorer($('#jobQ').value, b.dataset.area));
  studyBody.querySelectorAll('[data-job]').forEach(c => c.onclick = () => {
    const j = r.jobs.find(x => x.code + '|' + x.title === c.dataset.job);
    studyBody.innerHTML = `<button class="btn small" id="backJobs">← Jobs</button>
      <div class="card" style="margin-top:12px"><div class="faint">${esc(j.area)} — ${esc(j.group)}</div>
        <h2>${j.code ? esc(j.code) + ' · ' : ''}${esc(j.title)}</h2><p>${esc(j.summary)}</p>
        <p class="faint">Source: goarmy.com (${esc(j.url)})</p></div>
      <div class="row"><button class="btn primary" id="askJob">Ask Vanguard about this job</button></div>`;
    $('#backJobs').onclick = () => jobsExplorer(q, area);
    $('#askJob').onclick = () => { openView('ask'); send(`Tell me about the Army job ${j.code} ${j.title}. What does the training look like and what should I know?`); };
  });
}
studyBody.addEventListener('click', async e => {
  const q = e.target.closest('[data-quiz]'), c = e.target.closest('[data-card]');
  if (q) return chooseQuiz(q.dataset.quiz);
  if (c) {
    const card = await api('/api/card?id=' + encodeURIComponent(c.dataset.card));
    studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
      <div class="card" style="margin-top:12px"><h2>${esc(card.title)}</h2><div class="faint">Source: ${esc(card.source)}</div>
      ${card.verified === false ? '<div class="faint" style="color:var(--tan);margin-top:6px">⚠️ Vanguard couldn\'t check this card against the current manual — confirm it with your cadre.</div>' : ''}
      <div class="cardbody" style="margin-top:10px">${md(card.body)}</div></div>
      <div class="row"><button class="btn primary" data-quiz="${esc(card.id)}">Quiz me on this</button>
      <button class="btn" id="askAbout">Ask Vanguard about it</button></div>`;
    $('#backStudy').onclick = loaders.study;
    $('#askAbout').onclick = () => { openView('ask'); send('Help me understand: ' + card.title); };
  }
});
// Quizzes are a chat feed: Vanguard asks, the Cadet types an answer, Vanguard grades it on the device. Nothing is
// self-reported and the answer isn't sent to the screen until after the Cadet answers (owner's rule: scores must be
// real). `daily` marks Daily 10 answers so today's score is counted from graded answers.
const QUIZ_NOTE = "Getting one wrong doesn't mean anything bad. A lot of these are just facts — knowing them doesn't make " +
  "anyone a better person, but learning more is the sign of a good mind. The more you miss now, the more you have to " +
  "look forward to: every one you learn raises your score.";
const VERDICT = { right: '✅ Right!', close: '🟡 Close.', wrong: '❌ Not quite.' };

// Two ways in (owner's design): Practice = multiple choice, to learn it; Challenge = type the answer, to prove it.
function chooseQuiz(topic, daily = false) {
  studyBody.innerHTML = `<h2>${daily ? '🔥 Daily 10' : 'Quiz'}</h2>
    <div class="card"><p>${esc(QUIZ_NOTE)}</p>
      <button class="btn primary" id="qPractice" style="display:block;width:100%;text-align:left;margin:8px 0">📝 <b>Practice</b> — multiple choice<br><span class="faint">Pick from four answers. A good way to learn it.</span></button>
      <button class="btn" id="qChallenge" style="display:block;width:100%;text-align:left;margin:8px 0">🎯 <b>Challenge</b> — type the answer<br><span class="faint">No choices. For when you've studied it.</span></button>
      <button class="btn small" id="qBack">← Back to Learn</button></div>`;
  $('#qBack').onclick = loaders.study;
  const go = async mode => {
    if (!daily) return startQuiz(topic, null, null, false, mode);
    const d = await api('/api/daily?mode=' + mode);
    startQuiz('', d.questions, async () => {
      const st = await api('/api/daily/done', {});               // scored on the device from the graded answers
      return `Streak: ${st.streak} day${st.streak === 1 ? '' : 's'} 🔥`;
    }, true, mode);
  };
  $('#qPractice').onclick = () => go('mc');
  $('#qChallenge').onclick = () => go('typed');
}

async function startQuiz(topic, preset, onDone, daily = false, mode = 'typed') {
  const qs = preset || await api('/api/quiz?n=10&mode=' + mode + '&topic=' + encodeURIComponent(topic || ''));
  let i = 0, right = 0;
  studyBody.innerHTML = `<div class="row" style="justify-content:space-between;align-items:center">
      <h2 style="margin:0">${daily ? '🔥 Daily 10' : 'Quiz'}</h2><button class="btn small" id="quit">End quiz</button></div>
    <div id="qFeed" class="thread" aria-live="polite" style="margin-top:10px"></div>
    <form id="qForm" class="composer" style="position:sticky;bottom:0;background:var(--bg);padding:8px 0">
      <input id="qIn" autocomplete="off" placeholder="Type your answer…" aria-label="Your answer" style="flex:1">
      <button class="btn primary" id="qSend">Answer</button></form>`;
  const feed = $('#qFeed'), form = $('#qForm'), input = $('#qIn');
  const say = (who, html) => {
    const m = document.createElement('div');
    m.className = 'msg ' + (who === 'me' ? 'me' : 'ai');
    m.innerHTML = (who === 'me' ? '' : '<div class="who">VANGUARD</div>') + html;
    feed.appendChild(m); m.scrollIntoView({ block: 'end' });
  };
  $('#quit').onclick = loaders.study;
  say('ai', `<p>${esc(QUIZ_NOTE)}</p>`);
  const ask = () => {
    if (i >= qs.length) return finish();
    const q = qs[i];
    say('ai', `<div class="faint">${i + 1} of ${qs.length} · ${esc(q.topic)}</div><p><b>${esc(q.q)}</b></p>
      ${q.choices ? `<div class="mcq">${q.choices.map((c, k) => `<button class="btn" data-mc="${k}" style="display:block;width:100%;text-align:left;margin:6px 0">${'ABCD'[k]}. ${esc(c)}</button>`).join('')}</div>` : ''}`);
    if (q.choices) {
      form.hidden = true;
      const box = feed.lastElementChild;
      box.querySelectorAll('[data-mc]').forEach(b => b.addEventListener('click', () => {
        box.querySelectorAll('[data-mc]').forEach(x => { x.disabled = true; x.classList.toggle('primary', x === b); });
        answer({ choice: q.choices[+b.dataset.mc] }, `${'ABCD'[+b.dataset.mc]}. ${q.choices[+b.dataset.mc]}`);
      }));
    } else {
      form.hidden = false; input.value = ''; input.disabled = false; input.focus();
    }
  };
  const finish = async () => {
    form.hidden = true;
    const extra = onDone ? await onDone(right) : '';
    say('ai', `<p><b>${right} of ${qs.length} right.</b>${extra ? ' ' + esc(extra) : ''}</p><p class="faint">${esc(QUIZ_NOTE)}</p>
      <div class="row"><button class="btn primary" id="again">Again</button><button class="btn" id="backStudy">Back to Learn</button></div>`);
    $('#again').onclick = () => chooseQuiz(daily ? '' : topic);
    $('#backStudy').onclick = loaders.study;
  };
  const answer = async (body, shown) => {
    say('me', `<p>${esc(shown)}</p>`);
    const q = qs[i];
    const g = await api('/api/quiz/answer', { id: q.id, daily, ...body });
    if (g.error) { say('ai', `<p>${esc(g.error)}</p>`); input.disabled = false; return; }
    if (g.correct) right++;
    say('ai', `<p><b>${VERDICT[g.verdict] || ''}</b> ${g.verdict === 'right' ? '' : 'The answer: '}${g.verdict === 'right' ? '' : `<b>${esc(g.answer)}</b>`}</p>
      ${g.verdict === 'right' ? `<p class="faint">${esc(g.answer)}</p>` : ''}${g.why ? `<p class="faint">${esc(g.why)}</p>` : ''}
      <div class="faint">${esc(g.source || '')}</div>`);
    i++;
    setTimeout(ask, 400);
  };
  form.onsubmit = ev => {
    ev.preventDefault();
    const text = input.value.trim();
    if (!text || input.disabled) return;
    input.disabled = true;
    answer({ answer: text }, text);
  };
  ask();
}

// ── LAND NAV PRACTICE ──
// A practice map with 1,000-meter grid squares. Grids are read RIGHT, then UP (TC 3-25.26).
function landNav() {
  const W = 360, CELL = 90, E0 = 30 + Math.floor(Math.random() * 60), N0 = 10 + Math.floor(Math.random() * 70);
  const digits = [4, 6, 8][Math.floor(Math.random() * 3)];
  const x = 8 + Math.random() * (W - 16), y = 8 + Math.random() * (W - 16);   // point position in px
  const east = E0 + x / CELL, north = N0 + (W - y) / CELL;                   // in kilometers (grid lines)
  const fmt = (v, n) => String(Math.floor(v * 10 ** (n - 2))).padStart(n, '0');
  const answer = digits === 4 ? fmt(east, 2) + fmt(north, 2)
    : digits === 6 ? fmt(east, 3) + fmt(north, 3) : fmt(east, 4) + fmt(north, 4);
  let lines = '';
  for (let k = 0; k <= 4; k++) {
    const p = k * CELL;
    lines += `<line x1="${p}" y1="0" x2="${p}" y2="${W}" stroke="currentColor" stroke-opacity=".5"/><line x1="0" y1="${p}" x2="${W}" y2="${p}" stroke="currentColor" stroke-opacity=".5"/>`;
    if (k < 4) lines += `<text x="${p + 2}" y="${W - 4}" font-size="11" fill="currentColor">${String(E0 + k).padStart(2, '0')}</text>
      <text x="2" y="${W - p - 16}" font-size="11" fill="currentColor">${String(N0 + k).padStart(2, '0')}</text>`;
  }
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><h3>What is the ${digits}-digit grid of the ★ point?</h3>
      <p class="faint">Each square is 1,000 meters. Line numbers are on the left (northing) and bottom (easting). Read right, then up.${digits > 4 ? ' Estimate tenths' + (digits === 8 ? ' and hundredths' : '') + ' of a square.' : ''}</p>
      <svg viewBox="0 0 ${W} ${W}" style="width:100%;max-width:${W}px;display:block;margin:8px auto;color:var(--muted);background:var(--bg);border:1px solid var(--line2);border-radius:8px">
        ${lines}<text x="${x}" y="${y}" font-size="18" text-anchor="middle" dominant-baseline="middle" fill="var(--tan2)">★</text></svg>
      <div class="row"><input id="navIn" inputmode="numeric" maxlength="${digits}" placeholder="${'0'.repeat(digits)}" style="flex:1;font-size:20px;letter-spacing:.2em"><button class="btn primary" id="navCheck">Check</button></div>
      <p id="navMsg"></p><div class="row"><button class="btn small" id="navNext">Next point</button></div></div>`;
  $('#backStudy').onclick = loaders.study; $('#navNext').onclick = landNav;
  $('#navCheck').onclick = () => {
    const v = $('#navIn').value.replace(/\D/g, ''), half = digits / 2;
    const tol = digits === 8 ? 2 : 0;    // 8-digit: within 20 m counts (estimating hundredths by eye)
    const ok = v.length === digits && Math.abs(+v.slice(0, half) - +answer.slice(0, half)) <= tol && Math.abs(+v.slice(half) - +answer.slice(half)) <= tol;
    $('#navMsg').innerHTML = ok ? `<b style="color:var(--green)">✓ Correct</b> — ${answer.slice(0, half)} ${answer.slice(half)}`
      : `<b style="color:var(--red)">Not quite.</b> The answer is <b>${answer.slice(0, half)} ${answer.slice(half)}</b> — easting first (right), then northing (up).`;
  };
}

// ── REPORT DRILLS ──
// 9-line MEDEVAC request (ATP 4-02.2, Appendix C) and SALUTE report (TC 3-21.76, Table 2-7).
const rnd = a => a[Math.floor(Math.random() * a.length)];
const rint = (lo, hi) => lo + Math.floor(Math.random() * (hi - lo + 1));
const norm = s => String(s).toUpperCase().replace(/[^A-Z0-9]/g, '');
// "1A BREAK 2C", "A1 C2", "L1 BREAK A2" -> {A: 1, C: 2}
const counts = s => {
  const out = {};
  for (const m of String(s).toUpperCase().replace(/BREAK/g, ' ').matchAll(/(\d+)\s*([A-Z])|([A-Z])\s*(\d+)/g)) {
    const k = m[2] || m[3]; out[k] = (out[k] || 0) + +(m[1] || m[4]);
  }
  return out;
};
const sameCounts = (a, b) => { const ka = Object.keys(a).sort(), kb = Object.keys(b).sort(); return ka.join() === kb.join() && ka.every(k => a[k] === b[k]); };
const fmtCounts = (c, order) => [...order].filter(k => c[k]).map(k => order === 'LA' ? k + c[k] : c[k] + k).join(' BREAK ');

const NINE = {
  4: [['A', 'None'], ['B', 'Hoist'], ['C', 'Extraction equipment'], ['D', 'Ventilator']],
  6: [['N', 'No enemy troops in area'], ['P', 'Possibly enemy troops (approach with caution)'], ['E', 'Enemy troops in area (approach with caution)'], ['X', 'Enemy troops in area (armed escort required)']],
  7: [['A', 'Panels'], ['B', 'Pyrotechnic signal'], ['C', 'Smoke signal'], ['D', 'None'], ['E', 'Other']],
  9: [['', '— leave out (no contamination)'], ['C', 'Chemical'], ['B', 'Biological'], ['R', 'Radiological'], ['N', 'Nuclear']],
};
const PREC = { A: 'URGENT', B: 'URGENT-SURGICAL', C: 'PRIORITY', D: 'ROUTINE', E: 'CONVENIENCE' };
const NAT = { A: 'U.S. Soldier', B: 'U.S. citizen (civilian)', C: 'partner-nation soldier', D: 'local national (civilian)', E: 'wounded enemy prisoner' };

// Drill clock: starts when the drill opens; Check records the time (all-correct runs count toward a best).
function drillClock(el) {
  const t0 = Date.now(), fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const tick = setInterval(() => { if (!document.body.contains(el)) return clearInterval(tick); el.textContent = '⏱ ' + fmt((Date.now() - t0) / 1000); }, 500);
  return async (drill, perfect) => {
    clearInterval(tick);
    const secs = (Date.now() - t0) / 1000, r = await api('/api/drill/time', { drill, seconds: secs, perfect });
    el.textContent = '⏱ ' + fmt(secs);
    return `Time ${fmt(secs)}` + (r.new_best ? ' — new personal best! 🎯' : r.best ? ` · best ${fmt(r.best)}` : perfect ? '' : ' · get every line right to set a best time');
  };
}

function nineScenario() {
  const L = 'ABCDEFGHJKLMNPQRSTUV';
  const grid = `${rnd(['11S', '14R', '17S', '18S', '38S', '42S'])} ${rnd([...L])}${rnd([...L])} ${String(rint(0, 9999)).padStart(4, '0')} ${String(rint(0, 9999)).padStart(4, '0')}`;
  const freq = `${rint(30, 87)}.${rnd(['000', '150', '250', '350', '500', '750', '900'])}`;
  const call = `${rnd(['Bulldog', 'Saber', 'Viking', 'Dragon', 'Warrior', 'Ranger'])} ${rint(1, 6)}${rint(1, 9)}`;
  const patients = Array.from({ length: rint(1, 4) }, (_, i) => {
    const p = rnd(['A', 'A', 'B', 'C', 'C', 'D']);
    const litter = p === 'A' || p === 'B' ? Math.random() < 0.85 : p === 'C' ? Math.random() < 0.5 : false;
    const nat = i === 0 ? 'A' : rnd(['A', 'A', 'A', 'A', 'C', 'D', 'E']);
    return { p, litter, nat };
  });
  const equip = rnd(['A', 'A', 'A', 'B', 'C', 'D']);
  const sec = rnd(['N', 'P', 'E', 'X']);
  const mark = rnd(['A', 'B', 'C', 'C', 'D', 'E']);
  const cbrn = Math.random() < 0.15 ? rnd(['C', 'B', 'R', 'N']) : '';
  const prec = {}, type = {}, nat = new Set();
  for (const x of patients) { prec[x.p] = (prec[x.p] || 0) + 1; type[x.litter ? 'L' : 'A'] = (type[x.litter ? 'L' : 'A'] || 0) + 1; nat.add(x.nat); }
  const story = [
    `Your squad's pickup site is at grid <b>${grid}</b>. Your radio there is on <b>${freq}</b>, call sign <b>${call}</b>.`,
    `Your medic reports:<ul>${patients.map((x, i) => `<li>Patient ${i + 1} — ${NAT[x.nat]}: <b>${PREC[x.p]}</b>, ${x.litter ? 'needs a litter' : 'can walk (ambulatory)'}.</li>`).join('')}</ul>`,
    { A: 'The aircraft can land normally — no special equipment is needed.', B: 'The site is in thick trees; the aircraft can\'t land and will have to lift patients out.',
      C: 'One patient is trapped in a damaged vehicle and has to be cut out.', D: 'The medic says one patient needs help breathing — a ventilator.' }[equip],
    { N: 'No enemy have been seen in the area.', P: 'You heard gunfire a few kilometers away — enemy may be in the area.',
      E: 'Enemy are in the area, but not firing on you right now.', X: 'Enemy are close and firing — the evacuation will need an armed escort.' }[sec],
    { A: 'You will mark the site with VS-17 panels.', B: 'You will mark the site with a star cluster (pyrotechnic).', C: 'You will mark the site with smoke.',
      D: 'You have nothing to mark the site with.', E: 'You will mark the site with an IR strobe.' }[mark],
    cbrn ? `Your detector shows <b>${{ C: 'chemical', B: 'biological', R: 'radiological', N: 'nuclear' }[cbrn]}</b> contamination at the site.` : 'There is no CBRN contamination.',
  ];
  return { grid, freq, call, prec, type, nat: [...nat].sort(), equip, sec, mark, cbrn, story };
}

function nineLine() {
  const s = nineScenario();
  const sel = (n, opts) => `<select id="l${n}"><option value="?">—</option>${opts.map(([v, t]) => `<option value="${v}">${v ? v + ' — ' : ''}${esc(t)}</option>`).join('')}</select>`;
  const lines = [
    [1, 'Location of pickup site', '<input id="l1" placeholder="grid zone + grid">'],
    [2, 'Radio frequency, call sign, suffix', '<input id="l2" placeholder="frequency, call sign">'],
    [3, 'Number of patients by precedence', '<input id="l3" placeholder="e.g. 1A BREAK 2C">'],
    [4, 'Special equipment required', sel(4, NINE[4])],
    [5, 'Number of patients by type', '<input id="l5" placeholder="e.g. L1 BREAK A2">'],
    [6, 'Security of pickup site (wartime)', sel(6, NINE[6])],
    [7, 'Method of marking pickup site', sel(7, NINE[7])],
    [8, 'Patient nationality and status', '<input id="l8" placeholder="letter(s), e.g. A or A E">'],
    [9, 'CBRN contamination (wartime)', sel(9, NINE[9])],
  ];
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><div class="row" style="justify-content:space-between"><h3 style="margin:0">9-line MEDEVAC request — practice</h3><b id="clock">⏱ 0:00</b></div>
      <div class="faint">Practice scenario (wartime). Turn it into the 9 lines.</div>
      <div style="margin-top:8px">${s.story.map(p => p.startsWith('Your medic') ? p : `<p>${p}</p>`).join('')}</div></div>
    <div class="card">${lines.map(([n, label, ctl]) => `<div style="margin:8px 0"><div class="faint"><b>Line ${n}</b> · ${label}</div>${ctl}<div id="m${n}" style="font-size:14px"></div></div>`).join('')}
      <div class="row"><button class="btn primary" id="nineCheck">Check</button><button class="btn small" id="nineNext">New scenario</button></div>
      <div id="nineSum"></div></div>`;
  $('#backStudy').onclick = loaders.study; $('#nineNext').onclick = nineLine;
  const stopClock = drillClock($('#clock')); let timed = false;
  if (STATUS.voice && navigator.mediaDevices) {
    // Say the whole request like on the radio; Vanguard listens for radio words only (on this device).
    const say = document.createElement('div');
    say.className = 'card';
    say.innerHTML = `<div class="row" style="justify-content:space-between"><div><b>🎤 Say it on the radio</b>
      <div class="faint">"I have a MEDEVAC request, OVER. Line one, one seven sierra papa… Line two… OVER." Use the phonetic alphabet; say numbers digit by digit.</div></div>
      <button class="btn" id="nineSay">Start</button></div><div id="nineHeard" style="font-size:14px"></div>`;
    $('#nineCheck').closest('.card').before(say);
    $('#nineSay').onclick = async () => {
      const b = $('#nineSay');
      if (!mic.rec) {
        try { await mic.start(); b.textContent = '⏹ Done'; b.classList.add('primary'); } catch { alert('The microphone is not available.'); }
        return;
      }
      b.textContent = '…'; b.disabled = true;
      const r = await api('/api/voice', { audio: await mic.stop(), rate: 16000, mode: 'radio' });
      b.textContent = 'Again'; b.disabled = false; b.classList.remove('primary');
      if (r.error) { $('#nineHeard').textContent = r.error; return; }
      fillNine(r.lines || {});
      const got = Object.keys(r.lines || {}).length;
      $('#nineHeard').innerHTML = `<p class="faint">Heard: ${esc(r.text) || '(nothing)'}</p>
        <p>${r.opened ? '✓' : '✗'} Opened with "I have a MEDEVAC request" · ${r.closed ? '✓' : '✗'} Ended with OVER · ${got} line${got === 1 ? '' : 's'} heard</p>`;
      $('#nineCheck').click();
    };
  }
  $('#nineCheck').onclick = async () => {
    const v = n => $('#l' + n).value;
    const letters = String(v(8)).toUpperCase().replace(/BREAK/g, ' ').match(/\b[A-E]\b|(?<=\d)[A-E]/g) || [];
    const want = {
      1: [norm(v(1)) === norm(s.grid), s.grid],
      2: [norm(v(2)).includes(norm(s.freq)) && norm(v(2)).includes(norm(s.call)), `${s.freq}, ${s.call}`],
      3: [sameCounts(counts(v(3)), s.prec), fmtCounts(s.prec, 'ABCDE')],
      4: [v(4) === s.equip, `${s.equip} — ${NINE[4].find(o => o[0] === s.equip)[1]}`],
      5: [sameCounts(counts(v(5)), s.type), fmtCounts(s.type, 'LA')],
      6: [v(6) === s.sec, `${s.sec} — ${NINE[6].find(o => o[0] === s.sec)[1]}`],
      7: [v(7) === s.mark, `${s.mark} — ${NINE[7].find(o => o[0] === s.mark)[1]}`],
      8: [[...new Set(letters)].sort().join() === s.nat.join(), s.nat.join(' ')],
      9: [v(9) === s.cbrn, s.cbrn ? `${s.cbrn} — ${NINE[9].find(o => o[0] === s.cbrn)[1]}` : 'Leave it out — no contamination'],
    };
    let right = 0;
    for (const [n, [ok, ans]] of Object.entries(want)) {
      if (ok) right++;
      $('#m' + n).innerHTML = ok ? '<b style="color:var(--green)">✓</b>' : `<b style="color:var(--red)">✗</b> ${esc(ans)}`;
    }
    const time = timed ? '' : (timed = true, await stopClock('9-line', right === 9));
    $('#nineSum').innerHTML = `<p><b>${right} / 9 lines right.</b> ${right === 9 ? 'Ready to send.' : 'Fix the red lines and check again.'}${time ? ' ' + esc(time) + '.' : ''}</p>
      <p class="faint">Remember: say "I have a MEDEVAC request", send lines 1–5 on first contact, say each line number in the clear, end with OVER. Don't send the smoke or panel color — the crew calls it on arrival.</p>`;
  };
}

// Put spoken lines into the 9-line form: text boxes as heard, drop-downs by their brevity letter.
function fillNine(lines) {
  for (let n = 1; n <= 9; n++) {
    const el = $('#l' + n), v = lines[n];
    if (el.tagName === 'SELECT') {
      const letter = (v || '').replace(/[^A-Z]/g, '').slice(0, 1);
      if (n === 9 && !v) el.value = '';                       // line 9 left out = no contamination
      else if ([...el.options].some(o => o.value === letter)) el.value = letter;
    } else if (v !== undefined) el.value = v;
  }
}

// Sort-the-notes drills: SALUTE (TC 3-21.76, Table 2-7) and LACE (TC 3-21.76, ch. 1 and 7).
const SORT_DRILLS = {
  SALUTE: {
    title: 'SALUTE report', id: 'salute#drill', tip: 'Report what you saw — quickly, completely and accurately.',
    names: { S: 'Size', A: 'Activity', L: 'Location', U: 'Unit / Uniform', T: 'Time', E: 'Equipment' },
    facts: () => {
      const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
      return {
        S: `${rint(2, 14)} enemy personnel`,
        A: rnd(['moving north along the road', 'digging fighting positions', 'setting up a checkpoint', 'traveling southwest', 'resting near a stream bed']),
        L: `${rnd(['GA', 'NV', 'PU', 'LK'])}${String(rint(0, 999999)).padStart(6, '0')}`,
        U: rnd(['olive-drab uniforms, red star on the left shoulder', 'tan uniforms, no markings seen', 'dark green uniforms, black berets']),
        T: `${String(rint(1, 28)).padStart(2, '0')}${String(rint(0, 23)).padStart(2, '0')}${rnd(['00', '15', '30', '45'])} ${rnd(months)} ${rint(24, 27)}`,
        E: rnd(['one machine gun and one rocket launcher', 'rifles and two radios', 'one mortar tube and a pickup truck', 'rifles and a pair of binoculars']),
      };
    },
  },
  LACE: {
    title: 'LACE report', id: 'lace#drill', tip: 'Send it to your leader as soon as the unit starts to reorganize after contact. Your unit\'s SOP sets the exact format.',
    names: { L: 'Liquids', A: 'Ammunition', C: 'Casualties', E: 'Equipment' },
    facts: () => ({
      L: rnd(['about half our water left', 'one canteen left per Soldier', 'water nearly gone', 'water full']),
      A: rnd([`${rint(2, 6)} magazines per Soldier`, 'one belt left for the machine gun', 'low on 5.56', 'two grenades left']),
      C: rnd(['none', 'one wounded, can walk', 'two wounded, one needs a litter', 'one with a twisted ankle']),
      E: rnd(['one radio damaged', 'night-vision device lost', 'all equipment accounted for', 'one weapon jammed, cleared']),
    }),
  },
};
function sortDrill(kind) {
  const d = SORT_DRILLS[kind], facts = d.facts();
  const notes = Object.values(facts).sort(() => Math.random() - 0.5);
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><div class="row" style="justify-content:space-between"><h3 style="margin:0">${d.title} — practice</h3><b id="clock">⏱ 0:00</b></div>
      <p class="faint">Your notes are out of order. Put each one on the right line.</p>
      <ul>${notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul></div>
    <div class="card">${Object.keys(d.names).map(k => `<div style="margin:8px 0"><div class="faint"><b>${k}</b> · ${d.names[k]}</div>
      <select id="s${k}"><option value="">—</option>${notes.map(n => `<option>${esc(n)}</option>`).join('')}</select><div id="sm${k}" style="font-size:14px"></div></div>`).join('')}
      <div class="row"><button class="btn primary" id="salCheck">Check</button><button class="btn small" id="salNext">New report</button></div><div id="salSum"></div></div>`;
  $('#backStudy').onclick = loaders.study; $('#salNext').onclick = () => sortDrill(kind);
  const stopClock = drillClock($('#clock')); let timed = false;
  $('#salCheck').onclick = async () => {
    const keys = Object.keys(d.names); let right = 0;
    for (const k of keys) {
      const ok = $('#s' + k).value === facts[k]; if (ok) right++;
      $('#sm' + k).innerHTML = ok ? '<b style="color:var(--green)">✓</b>' : `<b style="color:var(--red)">✗</b> ${esc(facts[k])}`;
    }
    const time = timed ? '' : (timed = true, await stopClock(kind, right === keys.length));
    $('#salSum').innerHTML = `<p><b>${right} / ${keys.length} right.</b>${time ? ' ' + esc(time) + '.' : ''} ${esc(d.tip)}</p>`;
  };
}
const saluteDrill = () => sortDrill('SALUTE');

// ── EXAM MODE ── (questions from the verified cards; the answer key stays on the device's server until you submit)
async function examSetup() {
  const topics = await api('/api/topics'), h = await api('/api/exam/history');
  const fmt = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><h3>📝 Exam mode</h3>
      <label>Topic</label><select id="exTopic"><option value="">All topics</option>${topics.map(t => `<option>${esc(t.topic)}</option>`).join('')}</select>
      <label>Length</label><select id="exN"><option value="10">10 questions (7½ minutes)</option><option value="20">20 questions (15 minutes)</option><option value="5">5 questions (quick)</option></select>
      <div class="row" style="margin-top:10px"><button class="btn primary" id="exStart">Start the clock</button></div>
      <p class="faint">45 seconds per question. One answer each — no going back after you submit. When time's up, your answers are submitted.</p></div>
    <div class="card"><h3>My scores</h3>${Object.keys(h.best).length ? `<ul>${Object.entries(h.best).map(([t, b]) =>
      `<li><b>${esc(t)}</b>: best ${b.right}/${b.total} (${Math.round(100 * b.pct)}%) in ${fmt(b.seconds)} <span class="faint">${esc(b.date)}</span></li>`).join('')}</ul>
      <div class="faint">Recent: ${h.recent.map(r => `${esc(r.topic)} ${r.right}/${r.total}`).join(' · ')}</div>` : '<p class="faint">No exams yet.</p>'}</div>`;
  $('#backStudy').onclick = loaders.study;
  $('#exStart').onclick = async () => {
    const ex = await api('/api/exam/start', { topic: $('#exTopic').value, n: +$('#exN').value });
    if (ex.error) return alert(ex.error);
    examRun(ex);
  };
}
function examRun(ex) {
  const answers = {}, end = Date.now() + ex.limit * 1000;
  let i = 0, done = false, tick;
  const submit = async () => {
    if (done) return; done = true; clearInterval(tick);
    const r = await api('/api/exam/submit', { id: ex.id, answers });
    if (r.error) { studyBody.innerHTML = `<div class="card"><p>${esc(r.error)}</p></div>`; return; }
    const fmt = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
    studyBody.innerHTML = `<div class="card flash"><div class="faint">${esc(r.topic)}</div><div class="q">${r.right} / ${r.total}</div>
        <p>${Math.round(100 * r.right / r.total)}% · ${fmt(r.seconds)}${r.late ? ' · submitted after the time limit' : ''}</p>
        <div class="row" style="justify-content:center"><button class="btn primary" id="exAgain">New exam</button><button class="btn" id="backStudy">Back to Study</button></div></div>
      ${r.results.map((x, n) => `<div class="card"><div class="faint">${n + 1}. ${x.ok ? '<b style="color:var(--green)">✓</b>' : '<b style="color:var(--red)">✗</b>'}</div>
        <div>${esc(x.q)}</div>${x.ok ? '' : `<div class="faint">Your answer: ${x.chose === null ? 'none' : esc(x.choices[x.chose])}</div>`}
        <div><b>Answer:</b> ${esc(x.choices[x.answer])}</div><div class="faint">Source: ${esc(x.source)}</div></div>`).join('')}`;
    $('#exAgain').onclick = examSetup; $('#backStudy').onclick = loaders.study;
  };
  const show = () => {
    const q = ex.questions[i];
    studyBody.innerHTML = `<div class="row" style="justify-content:space-between"><span class="faint">Question ${i + 1} of ${ex.questions.length} · ${esc(ex.topic)}</span><b id="exClock" aria-live="off">⏱</b></div>
      <div class="card" style="margin-top:8px"><div class="q" style="font-size:20px">${esc(q.q)}</div>
        <div role="radiogroup" aria-label="Choices" style="display:grid;gap:8px;margin-top:12px">${q.choices.map((c, n) =>
          `<button class="btn" data-choice="${n}" role="radio" aria-checked="${answers[i] === n}" style="text-align:left;${answers[i] === n ? 'border-color:var(--tan);background:var(--card2)' : ''}">${'ABCD'[n]}. ${esc(c)}</button>`).join('')}</div>
        <div class="row" style="margin-top:12px;justify-content:space-between">
          <button class="btn small" id="exPrev" ${i === 0 ? 'disabled' : ''}>← Back</button>
          ${i < ex.questions.length - 1 ? '<button class="btn small primary" id="exNext">Next →</button>' : '<button class="btn primary" id="exSubmit">Submit exam</button>'}</div></div>
      <div class="faint">${Object.keys(answers).length} of ${ex.questions.length} answered</div>`;
    studyBody.querySelectorAll('[data-choice]').forEach(b => b.onclick = () => { answers[i] = +b.dataset.choice; if (i < ex.questions.length - 1) { i++; } show(); });
    if ($('#exPrev')) $('#exPrev').onclick = () => { i--; show(); };
    if ($('#exNext')) $('#exNext').onclick = () => { i++; show(); };
    if ($('#exSubmit')) $('#exSubmit').onclick = () => {
      const left = ex.questions.length - Object.keys(answers).length;
      if (!left || confirm(`${left} question${left === 1 ? '' : 's'} unanswered. Submit anyway?`)) submit();
    };
    paint();
  };
  const paint = () => { const s = Math.max(0, Math.round((end - Date.now()) / 1000)); const c = $('#exClock');
    if (!c && !done) { clearInterval(tick); return; }          // the Soldier left the exam: abandon it quietly
    if (c) { c.textContent = `⏱ ${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; c.style.color = s <= 30 ? 'var(--red)' : ''; }
    if (s <= 0) submit(); };
  tick = setInterval(paint, 500);
  show();
}

// ── SEARCH THE MANUALS ── (the library's own index; works with no AI model)
async function librarySearch(query) {
  const out = $('#libResults'); query = query.trim();
  if (!query) { out.innerHTML = ''; return; }
  const t0 = performance.now(), hits = await api('/api/search?k=15&q=' + encodeURIComponent(query));
  const words = [...new Set(query.toLowerCase().match(/[a-z0-9][a-z0-9'.-]{1,}/g) || [])].filter(w => w.length > 2);
  const mark = text => { let h = esc(text); for (const w of words) h = h.replace(new RegExp(`\\b(${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'), '<mark>$1</mark>'); return h; };
  const snippet = text => { const low = text.toLowerCase(), i = Math.max(0, Math.min(...words.map(w => { const j = low.indexOf(w); return j < 0 ? Infinity : j; }).concat(Infinity)) - 80);
    const s = isFinite(i) ? text.slice(i, i + 260) : text.slice(0, 260); return (i > 0 ? '…' : '') + s + (s.length < text.length ? '…' : ''); };
  out.innerHTML = hits.length ? `<div class="faint" style="margin:8px 0">${hits.length} result${hits.length === 1 ? '' : 's'} · ${Math.max(1, Math.round(performance.now() - t0))} ms</div>` +
    hits.map((h, n) => `<div class="card" style="margin:6px 0;cursor:pointer" data-hit="${n}" role="button" tabindex="0" aria-expanded="false">
      <div class="faint">📄 ${esc(h.source.split(' (')[0])} · ${esc(h.where)}${h.edition ? ` · edition ${esc(h.edition)}` : ''}</div>
      ${h.changed ? '<div class="faint" style="color:var(--red)">⚠️ This file was changed after it was installed — don\'t rely on it. See Me → Library check.</div>' : ''}
      ${oldEd(h.edition) ? `<div class="faint" style="color:var(--tan)">⚠️ This edition is from ${esc(h.edition.slice(0, 4))} — guidance may have changed. Check with your cadre or the current publication.</div>` : ''}<div class="hitText" style="font-size:15px">${mark(snippet(h.text))}</div></div>`).join('')
    : '<p class="faint">Nothing found. Try fewer or different words.</p>';
  out.querySelectorAll('[data-hit]').forEach(el => {
    const open = () => { const h = hits[+el.dataset.hit], full = el.getAttribute('aria-expanded') === 'true';
      el.setAttribute('aria-expanded', String(!full));
      el.querySelector('.hitText').innerHTML = full ? mark(snippet(h.text)) : `<div style="white-space:pre-wrap">${mark(h.text)}</div>
        ${/^page \d+$/.test(h.where) ? '<div class="faint" style="margin-top:6px">Page counted from the start of the PDF.</div>' : ''}`; };
    el.onclick = open; el.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } };
  });
}

// ── WHERE AM I IN BASIC? ── (goarmy.com's four phases; the Soldier enters their week-1 date)
async function showBct(st) {
  st = st || await api('/api/bct');
  const el = $('#bctCard'); if (!el) return;
  const ph = (i, now) => { const [name, a, b, what, items] = st.phases[i];
    return `<div style="margin:8px 0"><b>${esc(name)} Phase</b> <span class="faint">· weeks ${a}–${b}${now ? ' · you are here' : ''}</span>
      <div>${esc(what)}</div><ul style="margin:4px 0">${items.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>`; };
  const fam = document.body.dataset.kind === 'guardian';
  let head;
  if (st.week === null) head = `<p class="faint">Enter the date your Basic Combat Training week 1 starts (from your orders or your recruiter) to see where you are.</p>`;
  else if (st.week === 0) head = `<p><b>${st.days_to_start} day${st.days_to_start === 1 ? '' : 's'}</b> until week 1.</p>`;
  else if (st.phase === null) head = `<p><b>Week ${st.week}</b> — past the 10 weeks of Basic. Congratulations — on to AIT or your unit.</p>`;
  else head = `<p style="font-size:20px"><b>Week ${st.week} of 10 — ${esc(st.phases[st.phase][0])} Phase</b></p><div class="bar"><i style="width:${Math.min(100, st.week * 10)}%"></i></div>`;
  el.innerHTML = `<h3>🗓️ ${fam ? 'Where is my Soldier in Basic?' : 'Where am I in Basic?'}</h3>
    <div class="row"><input id="bctStart" type="date" value="${esc(st.start)}" style="max-width:200px" aria-label="Basic Training week 1 start date"><span class="faint">week 1 starts</span></div>
    ${head}
    ${st.phase !== null ? ph(st.phase, true) : ''}${st.next !== null && st.next !== undefined ? `<div class="faint" style="margin-top:6px">Coming next:</div>${ph(st.next, false)}` : ''}
    <details><summary>All four phases</summary>${st.phases.map((_, i) => ph(i, i === st.phase)).join('')}</details>
    <details><summary>A typical day</summary><ul>${st.day.map(x => `<li>${esc(x)}</li>`).join('')}</ul></details>
    <p class="faint">Source: ${esc(st.source)}. Your Drill Sergeants' schedule is the real one.</p>`;
  $('#bctStart').onchange = async () => showBct(await api('/api/bct', { start: $('#bctStart').value }));
}

// ── BOARD PREP ──
// A 🎤 button that fills a text box using Vanguard's own offline recognizer (only when voice is installed).
function micInto(btn, box) {
  if (!(STATUS.voice && navigator.mediaDevices)) { btn.hidden = true; return; }
  btn.onclick = async () => {
    if (!mic.rec) { try { await mic.start(); btn.textContent = '⏹'; btn.classList.add('primary'); } catch { alert('The microphone is not available.'); } return; }
    btn.textContent = '…'; btn.disabled = true;
    const r = await api('/api/voice', { audio: await mic.stop(), rate: 16000 });
    btn.textContent = '🎤'; btn.disabled = false; btn.classList.remove('primary');
    if (r.text) box.value = (box.value ? box.value + ' ' : '') + r.text; else if (r.error) alert(r.error);
  };
}

// Uniform check: one tap per item, straight from the AGSU card (DA PAM 670-1).
async function uniformCheck() {
  const card = await api('/api/card?id=uniform_agsu');
  let html = '', group = '';
  for (const line of card.body.split('\n')) {
    const g = line.match(/^\*\*(.+)\*\*$/), item = line.match(/^- \*\*(.+?)\*\*:?\s*(.*)$/);
    if (g) { group = g[1]; html += `<h3 style="margin:14px 0 4px">${esc(group)}</h3>`; }
    else if (item) html += `<label class="row" style="align-items:flex-start;flex-wrap:nowrap;gap:10px;margin:6px 0;cursor:pointer"><input type="checkbox" style="width:auto;flex:none;margin-top:5px">
      <span style="flex:1"><b>${esc(item[1])}</b> — ${md(item[2]).replace(/^<p>|<\/p>$/g, '')}</span></label>`;
  }
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><h3>Uniform check — AGSU coat (enlisted)</h3>
      <p class="faint">Tick each item as you check it on your coat. Source: ${esc(card.source)}. Guidance changes — confirm with your leadership.</p>
      <div id="ucList">${html}</div><p id="ucDone" class="faint"></p>
      <div class="row"><button class="btn" id="ucQuiz">Quiz me on placement</button></div></div>`;
  $('#backStudy').onclick = loaders.study;
  $('#ucQuiz').onclick = () => chooseQuiz('uniform_agsu');
  $('#ucList').addEventListener('change', () => {
    const boxes = $('#ucList').querySelectorAll('input[type=checkbox]'), n = [...boxes].filter(b => b.checked).length;
    $('#ucDone').textContent = n === boxes.length ? '✓ Every item checked. Ready for inspection.' : `${n} of ${boxes.length} checked`;
  });
}

// Mock board: questions from the verified study cards; answer out loud or by typing; graded against the card.
async function mockBoard(topic = '') {
  const topics = await api('/api/topics');
  const qs = await api('/api/quiz?n=5&topic=' + encodeURIComponent(topic));
  const VERDICT = { go: ['GO', 'var(--green)'], partial: ['PARTIAL', 'var(--tan)'], nogo: ['NO-GO', 'var(--red)'] };
  let i = 0, right = 0;
  const show = () => {
    if (i >= qs.length) {
      studyBody.innerHTML = `<div class="card flash"><div class="faint">Board complete</div><div class="q">${right} / ${qs.length}</div>
        <p>${right === qs.length ? 'Squared away.' : 'The ones you missed will come back more often in your quizzes.'}</p>
        <div class="row" style="justify-content:center"><button class="btn primary" id="again">Another board</button><button class="btn" id="backStudy">Back to Study</button></div></div>`;
      $('#again').onclick = () => mockBoard(topic); $('#backStudy').onclick = loaders.study; return;
    }
    const q = qs[i];
    studyBody.innerHTML = `<div class="row" style="justify-content:space-between"><button class="btn small" id="backStudy">← Study</button>
        <select id="mbTopic" style="max-width:60%"><option value="">All topics</option>${topics.map(t => `<option ${t.topic === topic ? 'selected' : ''}>${esc(t.topic)}</option>`).join('')}</select></div>
      <div class="faint" style="margin-top:10px">Question ${i + 1} of ${qs.length} · ${esc(q.topic)}</div>
      <div class="card"><div class="q" style="font-size:20px">${esc(q.q)}</div>
        <p class="faint">Answer like you would in front of the board — out loud with 🎤, or type it.</p>
        <div class="row"><textarea id="mbAns" rows="3" style="flex:1"></textarea><button class="btn" id="mbMic" title="Answer out loud">🎤</button></div>
        <div class="row" style="margin-top:8px"><button class="btn primary" id="mbGo">Submit answer</button><button class="btn small" id="mbSkip">I don't know</button></div>
        <div id="mbOut"></div></div>`;
    $('#backStudy').onclick = loaders.study;
    $('#mbTopic').onchange = e => mockBoard(e.target.value);
    micInto($('#mbMic'), $('#mbAns'));
    const submit = async skipped => {
      $('#mbGo').disabled = $('#mbSkip').disabled = true;
      // graded and recorded by Vanguard on the device -- no "count it right" button (scores are never self-reported)
      const g = await api('/api/board/grade', { id: q.id, answer: skipped ? '' : $('#mbAns').value });
      const [label, color] = VERDICT[g.verdict] || VERDICT.nogo;
      if (g.verdict === 'go') right++;
      $('#mbOut').innerHTML = `<div style="margin-top:12px"><b style="color:${color};font-size:20px">${label}</b>
          ${g.why ? `<span class="faint"> — ${esc(g.why)}</span>` : ''}${g.how === 'words' && g.missing && g.missing.length && !skipped ? `<div class="faint">Key words not heard: ${g.missing.map(esc).join(', ')}</div>` : ''}
          <p><b>Answer:</b> ${esc(g.answer || '')}</p><p class="faint">Source: ${esc(g.source || q.source)}</p>
          <div class="row"><button class="btn primary" id="mbNext">Next question</button></div></div>`;
      $('#mbNext').onclick = () => { i++; show(); };
      $('#mbNext').focus();
    };
    $('#mbGo').onclick = () => submit(false); $('#mbSkip').onclick = () => submit(true);
  };
  show();
}

// Recite the Soldier's Creed: out loud or typed, checked word by word.
function creedDrill() {
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><h3>Recite the Soldier's Creed</h3>
      <p class="faint">Say it with 🎤 or type it from memory, then check. Every word is compared with the creed (army.mil). Voice can mishear — if a word you said right is marked, try typing it.</p>
      <div class="row"><textarea id="crIn" rows="6" style="flex:1" placeholder="I am an American Soldier…"></textarea><button class="btn" id="crMic" title="Recite out loud">🎤</button></div>
      <div class="row" style="margin-top:8px"><button class="btn primary" id="crGo">Check</button><button class="btn small" id="crClear">Clear</button></div>
      <div id="crOut"></div></div>`;
  $('#backStudy').onclick = loaders.study;
  micInto($('#crMic'), $('#crIn'));
  $('#crClear').onclick = () => { $('#crIn').value = ''; $('#crOut').innerHTML = ''; };
  $('#crGo').onclick = async () => {
    const r = await api('/api/board/recite', { text: $('#crIn').value });
    $('#crOut').innerHTML = `<p style="margin-top:12px"><b>${r.right} of ${r.total} words</b>${r.perfect ? ' — word perfect. 🎖️' : ''}</p>
      <div style="line-height:1.9">${r.lines.map(l => l.map(w => w.ok ? esc(w.w) : `<b style="color:var(--red);text-decoration:underline">${esc(w.w)}</b>`).join(' ')).join('<br>')}</div>
      ${r.extra.length ? `<p class="faint">Words that aren't in the creed: ${r.extra.map(esc).join(', ')}</p>` : ''}
      <p class="faint">Red underlined = missed or said differently.</p>`;
  };
}

// ── POCKET CARDS ── (only text checked against its source; black on white for printing)
const POCKET = [
  ['9-line MEDEVAC request', `<p>Say "I have a MEDEVAC request." Send <b>lines 1–5 on first contact</b>. Say line numbers in the clear; end with OVER.</p><ul>
    <li><b>1</b> Pickup site grid (with grid zone letters)</li><li><b>2</b> Frequency, call sign, suffix (at the site)</li>
    <li><b>3</b> Patients by precedence: A Urgent · B Urgent-Surg · C Priority · D Routine · E Convenience</li>
    <li><b>4</b> Special equipment: A None · B Hoist · C Extraction · D Ventilator</li>
    <li><b>5</b> Patients by type: L# litter · A# ambulatory</li>
    <li><b>6</b> Security (war): N No enemy · P Possible · E Enemy, caution · X Armed escort</li>
    <li><b>7</b> Marking: A Panels · B Pyro · C Smoke · D None · E Other</li>
    <li><b>8</b> Nationality: A US mil · B US citizen · C Non-US mil · D Non-US citizen · E EPW</li>
    <li><b>9</b> CBRN (war, only if present): C · B · R · N</li></ul>
    <p>Urgent/Urgent-Surg ≤ 1 hr · Priority ≤ 4 hr · Routine ≤ 24 hr. Don't send smoke/panel color — the crew calls it on arrival.</p>`,
    'ATP 4-02.2 (Table 2-1, App. C); TC 3-21.76 ch. 15'],
  ['SALUTE · LACE · Which report?', `<p><b>SALUTE</b> — you see the enemy:</p><ul><li><b>S</b>ize · <b>A</b>ctivity · <b>L</b>ocation (grid)</li><li><b>U</b>nit / Uniform · <b>T</b>ime · <b>E</b>quipment</li></ul>
    <p>Report what you saw — quickly, completely, accurately.</p>
    <p><b>LACE</b> — your status after contact, to your leader:</p><ul><li><b>L</b>iquids · <b>A</b>mmunition · <b>C</b>asualties · <b>E</b>quipment</li></ul>
    <p><b>Which report?</b> See the enemy → SALUTE. Someone needs evacuation → 9-line. After contact → LACE.</p>`,
    'TC 3-21.76 (para. 2-16, Table 2-7; ch. 1, 7)'],
  ['Phonetic alphabet & radio numbers', `<p>Alpha · Bravo · Charlie · Delta · Echo · Foxtrot · Golf · Hotel · India · Juliet · Kilo · Lima · Mike · November · Oscar · Papa · Quebec · Romeo · Sierra · Tango · Uniform · Victor · Whiskey · X-ray · Yankee · Zulu</p>
    <p>Numbers digit by digit: 0 zero · 3 tree · 4 fower · 5 fife · 9 niner.</p>`, 'NATO / ICAO phonetic alphabet'],
  ["The Soldier's Creed", `<p>I am an American Soldier.<br>I am a warrior and a member of a team.<br>I serve the people of the United States, and live the Army Values.<br>
    I will always place the mission first.<br>I will never accept defeat.<br>I will never quit.<br>I will never leave a fallen comrade.<br>
    I am disciplined, physically and mentally tough, trained and proficient in my warrior tasks and drills.<br>I always maintain my arms, my equipment and myself.<br>
    I am an expert and I am a professional.<br>I stand ready to deploy, engage, and destroy, the enemies of the United States of America in close combat.<br>
    I am a guardian of freedom and the American way of life.<br>I am an American Soldier.</p>`, 'U.S. Army, army.mil/values/soldiers.html'],
  ['The Army Values — LDRSHIP', `<ul><li><b>Loyalty</b> — Bear true faith and allegiance to the U.S. Constitution, the Army, your unit and other Soldiers.</li>
    <li><b>Duty</b> — Fulfill your obligations.</li><li><b>Respect</b> — Treat people as they should be treated.</li>
    <li><b>Selfless Service</b> — Put the welfare of the nation, the Army and your subordinates before your own.</li>
    <li><b>Honor</b> — Live up to Army values.</li><li><b>Integrity</b> — Do what's right, legally and morally.</li>
    <li><b>Personal Courage</b> — Face fear, danger or adversity (physical or moral).</li></ul>`, 'U.S. Army, army.mil/values'],
];
function pocketCards() {
  const cards = POCKET.map(([t, body, src]) => `<div class="pc"><h4>${t}</h4>${body}<div class="src">Source: ${src} · Vanguard study aid</div></div>`).join('');
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Study</button>
    <div class="card" style="margin-top:12px"><h3>🖨️ Pocket cards</h3>
      <p class="faint">Prints on one letter page, black on white (even in night mode). Cut along the dashed lines. Only text checked against its official source is included.</p>
      <div class="row"><button class="btn primary" id="printNow">Print</button></div></div>
    <div id="printPreview" style="background:#fff;color:#000;padding:10px;border-radius:8px"></div>`;
  $('#printPreview').innerHTML = `<div class="pc-grid">${cards}</div>`;
  $('#backStudy').onclick = loaders.study;
  $('#printNow').onclick = () => {
    let area = $('#printArea');
    if (!area) { area = document.createElement('div'); area.id = 'printArea'; document.body.appendChild(area); }
    area.innerHTML = `<div class="pc-grid">${cards}</div>`;
    window.print();
  };
}
