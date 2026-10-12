// Presentation mode (owner, 2026-10-12): today's plan as one slideshow for the projector. The instructor clicks
// through the opening question, the lesson and study cards (taught as slides), videos, scenarios, live questions and
// the exit question -- with a presentation clicker or the arrow keys. A question shows first; the next click reveals
// the answer. Cadet phones are optional: with phones off, questions and scenarios run as a show of hands; with
// phones on, the vote counts show too. Listeners in JS (the page's policy blocks inline handlers).
'use strict';

let deck = null;                                   // { plan, slides, at, step, poll, keys }
const DECK_LETTERS = 'ABCDEF';

// Text split into slide-sized pieces, only between paragraphs -- so a heading always stays with its list. A single
// paragraph too long for one slide is cut between its list items, its first line repeated as the heading.
function deckChunks(text, max = 60) {
  const count = s => s.split(/\s+/).filter(Boolean).length;
  const blocks = [];
  for (const b of String(text || '').split(/\n\s*\n/).map(x => x.trim()).filter(Boolean)) {
    const lines = b.split('\n');
    if (count(b) <= max * 1.6 || lines.length < 3) { blocks.push(b); continue; }
    const head = /^\s*(?:[-*•]|\d+\.)\s/.test(lines[0]) ? '' : lines.shift();
    let part = [], first = true;
    const flush = () => {
      blocks.push([first ? head : head && head.replace(/:?\s*(\*\*)?:?\s*$/, ' (continued)$1'), ...part].filter(Boolean).join('\n'));
      part = []; first = false;
    };
    for (const l of lines) {
      if (part.length && count(head + ' ' + part.join(' ') + ' ' + l) > max) flush();
      part.push(l);
    }
    if (part.length) flush();
  }
  const out = [];
  let cur = [];
  for (const b of blocks) {
    if (cur.length && count(cur.join(' ') + ' ' + b) > max) { out.push(cur.join('\n\n')); cur = []; }
    cur.push(b);
  }
  if (cur.length) out.push(cur.join('\n\n'));
  return out;
}

// One slide = { phase, label, html(step), steps (how many reveals), enter(), leave() }.
async function buildDeck(plan) {
  const need = t => plan.items.some(i => i.type === t);
  const [ls, vd] = await Promise.all([need('lesson') ? api('/api/instructor/lessons') : {}, need('video') ? api('/api/videos') : {}]);
  const cards = {};
  await Promise.all(plan.items.filter(i => i.type === 'card').map(async i => { cards[i.id] = await api('/api/card?id=' + encodeURIComponent(i.id)); }));
  const order = CD_PHASES.map(p => p[0]);
  const deckPhase = it => it.type === 'lesson' ? 'learn' : cdPhase(it);                // the lesson is taught first
  const items = plan.items.map((it, i) => ({ it, i })).sort((a, b) => order.indexOf(deckPhase(a.it)) - order.indexOf(deckPhase(b.it)) || a.i - b.i);
  const slides = [];
  const add = (item, s) => slides.push({ item, steps: 0, ...s });
  const big = (title, sub) => `<h1 class="dk-h1">${esc(title)}</h1>${sub ? `<p class="dk-sub">${sub}</p>` : ''}`;
  for (const { it } of items) {
    const ph = deckPhase(it);
    if (it.type === 'prompt') {
      add(it, { phase: ph, label: it.id === 'close' ? 'Exit question' : 'Opening question',
        html: () => big(it.title, it.id === 'close' ? 'Think about it, then share one answer before you go.' : "Take a minute to think. Then we'll hear a few answers.") });
    } else if (it.type === 'card') {
      const c = cards[it.id];
      if (!c || c.error) continue;
      const svc = c.service && c.service !== 'joint' ? (STATUS.services || {})[c.service] || '' : '';
      add(it, { phase: ph, label: 'Study card', html: () => `${big(c.title, esc([svc, c.topic].filter(Boolean).join(' · ')))}<p class="dk-src">Source: ${esc(c.source)}</p>` });
      const parts = deckChunks(c.body);
      parts.forEach((p, k) => add(it, { phase: ph, label: `${c.title} · ${k + 1} of ${parts.length}`, html: () => `<div class="dk-body">${md(p)}</div>` }));
      (c.quiz || []).slice(0, 4).forEach((q, k) => add(it, {
        phase: ph, label: `Check on learning · ${k + 1}`, steps: 1,
        html: step => `<h2 class="dk-q">${esc(q.q)}</h2>${step ? `<div class="dk-answer">${esc(q.a)}</div>` : '<p class="dk-sub">Think of your answer…</p>'}`,
      }));
    } else if (it.type === 'lesson') {
      const l = (ls.lessons || []).find(x => x.id === it.id);
      if (!l) continue;
      add(it, { phase: ph, label: 'Lesson', html: () => `${big(l.title, l.objective ? `<b>Objective:</b> ${esc(l.objective)}` : '')}${l.source ? `<p class="dk-src">Source: ${esc(l.source)}</p>` : ''}` });
      const parts = deckChunks(l.content);
      parts.forEach((p, k) => add(it, { phase: ph, label: `${l.title} · ${k + 1} of ${parts.length}`, html: () => `<div class="dk-body">${md(p)}</div>` }));
      for (let k = 0; k < (l.vocabulary || []).length; k += 4) {
        const v = l.vocabulary.slice(k, k + 4);
        add(it, { phase: ph, label: 'Vocabulary', steps: 1, html: step => `<h2 class="dk-q">Vocabulary</h2>${v.map(x =>
          `<div class="dk-vocab"><b>${esc(x.term)}</b>${step ? ` — ${esc(x.definition)}` : ''}</div>`).join('')}` });
      }
      (l.questions || []).forEach((q, k) => add(it, {
        phase: ph, label: `Check on learning · ${k + 1} of ${l.questions.length}`, steps: 1,
        html: step => `<h2 class="dk-q">${esc(q.q)}</h2>${q.choices.map((c, j) =>
          `<div class="dk-choice ${step && j === q.answer ? 'right' : ''}"><b>${DECK_LETTERS[j]}.</b> ${esc(c)}${step && j === q.answer ? ' ✅' : ''}</div>`).join('')}`,
      }));
    } else if (it.type === 'video') {
      const v = (vd.videos || []).find(x => x.id === it.id);
      if (!v) continue;
      const credit = v.kind === 'youtube' ? `${esc(v.channel)} — the service's official YouTube channel`
        : `Official video${v.credit ? ` by ${esc(v.credit)}` : ''}, ${esc(v.date || '')} · public domain · via DVIDS (dvidshub.net)`;
      add(it, { phase: ph, label: 'Video', html: () => `<h2 class="dk-q">${esc(v.title)}</h2>
        ${v.local ? `<video controls playsinline src="${esc(v.src)}" style="width:100%;max-height:62vh;background:#000;border-radius:10px"></video>`
          : `<p class="dk-sub">${v.kind === 'youtube' ? 'This video is on YouTube and needs internet.' : "This video isn't saved on this computer, so it needs internet."}</p>
             <a class="btn primary" href="${esc(v.url)}" target="_blank" rel="noopener noreferrer">▶ Open the video</a>`}
        <p class="dk-src">${credit}</p>`,
        leave: box => { const el = box.querySelector('video'); if (el) el.pause(); } });
    } else if (it.type === 'scenario') {
      add(it, { phase: ph, label: 'Leadership scenario', steps: 1, live: 'scenario',
        enter: () => api('/api/instructor/live', { action: 'start', scenario: it.id }),
        html: (step, lv) => {
          const sc = (lv || {}).scenario;
          if (!sc) return big(it.title, 'Loading…');
          const max = Math.max(1, ...(lv.counts || [0])), phones = STATUS.lan;
          return `<h2 class="dk-q" style="margin-bottom:6px">${esc(sc.title)}</h2>
            <p class="dk-text" style="white-space:pre-wrap">${esc(sc.situation)}</p>
            ${sc.choices.map((c, i) => `<div class="dk-choice"><b>${DECK_LETTERS[i]}.</b> ${esc(c)}
              ${phones ? `<div class="dk-bar"><i style="width:${Math.round(lv.counts[i] / max * 70)}%"></i><span>${lv.counts[i]}</span></div>` : ''}
              ${step ? `<div class="dk-note">${esc(lv.guidance.outcomes[i].outcome)}</div>` : ''}</div>`).join('')}
            ${step ? `<div class="dk-note"><b>Leadership principles</b><ul>${lv.guidance.principles.map(p => `<li>${esc(p)}</li>`).join('')}</ul></div>`
              : `<p class="dk-sub">${phones ? `Vote in 🧭 Lead on your phone · ${lv.votes} vote${lv.votes === 1 ? '' : 's'}` : 'Hands up: who picks A? B? C? D?'}</p>`}`;
        },
        reveal: () => api('/api/instructor/live', { action: 'reveal', on: true }),
        read: () => api('/api/instructor/live'),
        stop: () => api('/api/instructor/live', { action: 'stop' }) });
    } else if (it.type === 'question') {
      add(it, { phase: ph, label: 'Live question', steps: 1, live: 'quiz',
        enter: async () => {
          const r = await api('/api/instructor/live-quiz', { action: 'start', id: it.id, mode: 'mc' });
          if (r.error) await api('/api/instructor/live-quiz', { action: 'start', id: it.id, mode: 'typed' });   // no fair choices
        },
        html: (step, lq) => {
          if (!lq || !lq.id) return big(it.title, 'Loading…');
          const max = Math.max(1, ...(lq.counts || [0])), phones = STATUS.lan;
          return `<h2 class="dk-q">${esc(lq.q)}</h2>
            ${lq.mode === 'mc' ? lq.choices.map((c, i) => {
              const right = step && c === (lq.right || lq.a);
              return `<div class="dk-choice ${right ? 'right' : ''}"><b>${DECK_LETTERS[i]}.</b> ${esc(c)}${right ? ' ✅' : ''}
                ${phones && step ? `<div class="dk-bar"><i style="width:${Math.round(lq.counts[i] / max * 70)}%"></i><span>${lq.counts[i]}</span></div>` : ''}</div>`;
            }).join('') : ''}
            ${step ? `<div class="dk-answer">${esc(lq.a)}${phones && lq.answered ? `<div class="dk-src">${lq.right} of ${lq.answered} right</div>` : ''}</div>`
              : `<p class="dk-sub">${phones ? `Answer in 🧭 Lead on your phone · ${lq.answered} answered` : lq.mode === 'mc' ? 'Hands up: A? B? C? D?' : 'Think of your answer…'}</p>`}`;
        },
        reveal: () => api('/api/instructor/live-quiz', { action: 'reveal', on: true }),
        read: () => api('/api/instructor/live-quiz'),
        stop: () => api('/api/instructor/live-quiz', { action: 'stop' }) });
    }
  }
  const lesson = plan.items.find(i => i.type === 'lesson');
  if (lesson) {                                      // the assignment, just before the exit question
    const at = slides.findIndex(s => s.phase === 'close');
    const s = { item: lesson, phase: 'assign', label: "Today's assignment", steps: 0,
      html: () => big(lesson.title, lesson.done ? 'Find it on your Cadet Foundry Home screen.' : 'Your instructor will give you this lesson.') };
    if (at < 0) slides.push(s); else slides.splice(at, 0, s);
  }
  return slides;
}

async function presentDeck(plan, startAt = 0, mainForReturn = null, ovForReturn = null) {
  openView('classroom');
  const box = $('#classroomBody');
  box.innerHTML = '<p class="faint">Getting today\'s slides ready…</p>';
  const slides = await buildDeck(plan);
  if (!slides.length) {
    box.innerHTML = `<div class="card"><p>Nothing in today's plan can be shown as slides yet.</p><button class="btn" id="dkBack">← Back to today's class</button></div>`;
    $('#dkBack').addEventListener('click', backFromClassroom);
    return;
  }
  if (deck) endDeck(false);
  deck = { plan, slides, at: Math.max(0, Math.min(startAt, slides.length - 1)), step: 0, poll: null, live: null };
  const phaseName = Object.fromEntries(CD_PHASES.map(p => [p[0], p[1]]));

  const draw = () => {
    const s = deck.slides[deck.at];
    box.innerHTML = `<div class="dk">
        <div class="dk-top"><span class="faint">${esc((phaseName[s.phase] || '').toUpperCase())} · ${esc(s.label)}</span>
          <span class="row" style="gap:6px;flex-wrap:nowrap">
            <span class="faint">${deck.at + 1} / ${deck.slides.length}</span>
            <button class="btn small" id="dkPrev" aria-label="Previous slide" ${deck.at === 0 && !deck.step ? 'disabled' : ''}>◀</button>
            <button class="btn small primary" id="dkNext" aria-label="Next">${deck.step < s.steps ? 'Reveal' : '▶'}</button>
            <button class="btn small" id="dkFull" title="Full screen (F)">⛶</button>
            <button class="btn small" id="dkEnd">End</button></span></div>
        <div class="dk-slide" id="dkSlide">${s.html(deck.step, deck.live)}</div>
        <div class="dk-progress"><i style="width:${Math.round((deck.at + 1) / deck.slides.length * 100)}%"></i></div></div>`;
    $('#dkPrev').addEventListener('click', prev);
    $('#dkNext').addEventListener('click', next);
    $('#dkFull').addEventListener('click', fullScreen);
    $('#dkEnd').addEventListener('click', () => endDeck(true));
  };
  const enter = async () => {
    const s = deck.slides[deck.at];
    clearInterval(deck.poll);
    deck.live = null;
    if (!s.item.done && s.item.type !== 'lesson') { s.item.done = true; }
    plan.slide = deck.at;
    cdSave(plan);
    draw();
    if (s.enter) {
      await s.enter();
      deck.live = await s.read();
      if (deck && deck.slides[deck.at] === s) draw();
      deck.poll = setInterval(async () => {          // counts arrive while phones answer
        if (!deck || deck.slides[deck.at] !== s || !$('#classroom').classList.contains('on')) { clearInterval(deck && deck.poll); return; }
        if (!STATUS.lan) return;
        try { deck.live = await s.read(); draw(); } catch (e) { clearInterval(deck.poll); }
      }, 3000);
    }
  };
  const go = async to => {
    const was = deck.slides[deck.at];
    if (was.leave) was.leave(box);
    if (was.stop && deck.slides[to] !== was) await was.stop();
    deck.at = to; deck.step = 0;
    await enter();
  };
  const next = async () => {
    const s = deck.slides[deck.at];
    if (deck.step < s.steps) {
      deck.step++;
      if (s.reveal) { await s.reveal(); deck.live = await s.read(); }
      draw();
      return;
    }
    if (deck.at < deck.slides.length - 1) return go(deck.at + 1);
    endDeck(true);
  };
  const prev = () => {
    if (deck.step) { deck.step = 0; draw(); return; }
    if (deck.at > 0) go(deck.at - 1);
  };
  const fullScreen = () => {
    const el = $('#classroom');
    if (document.fullscreenElement) document.exitFullscreen(); else if (el.requestFullscreen) el.requestFullscreen().catch(() => { });
  };
  // A presentation clicker sends Page Down / Page Up (or the arrow keys); "B" or "." blanks the screen.
  deck.keys = e => {
    if (!$('#classroom').classList.contains('on') || !deck) return;
    if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    const blank = $('#dkBlank');
    if (blank) { blank.remove(); e.preventDefault(); return; }
    if (['ArrowRight', 'PageDown', ' ', 'n', 'N'].includes(e.key) || (e.key === 'Enter' && e.target === document.body)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'PageUp', 'p', 'P', 'Backspace'].includes(e.key)) { e.preventDefault(); prev(); }
    else if (['b', 'B', '.'].includes(e.key)) {
      const d = document.createElement('div'); d.id = 'dkBlank'; d.className = 'dk-blank'; d.title = 'Press any key to come back';
      d.addEventListener('click', () => d.remove());
      $('#classroom').appendChild(d);
    } else if (e.key === 'f' || e.key === 'F') fullScreen();
    else if (e.key === 'Escape' && !document.fullscreenElement) endDeck(true);
  };
  document.addEventListener('keydown', deck.keys);
  deck.back = () => (mainForReturn && ovForReturn ? runSheet(mainForReturn, plan, ovForReturn) : null);
  await enter();
}

async function endDeck(goBack) {
  if (!deck) return;
  const d = deck;
  deck = null;
  clearInterval(d.poll);
  document.removeEventListener('keydown', d.keys);
  const s = d.slides[d.at];
  if (s && s.leave) s.leave($('#classroomBody'));
  if (s && s.stop) await s.stop();
  if (document.fullscreenElement) document.exitFullscreen().catch(() => { });
  if (goBack) backFromClassroom();
}
