'use strict';
// ASVAB practice (0.2): the four AFQT subtests with the official CAT-ASVAB question counts and time limits.
// Scoring is exact -- right answers per section, time used, a worked answer for every question -- and honest: a
// practice test can't produce a real Standard Score or AFQT percentile, so none is shown. Listeners in JS.

const ASVAB_TIPS = {
  AR: 'Practice word problems without a calculator: rates, percents, averages, ratios, money and time.',
  WK: 'Read every day and look up words you don\'t know. Learn common prefixes, roots and suffixes.',
  PC: 'Read the question first, then find the sentence in the passage that answers it.',
  MK: 'Review algebra (solving for x, factoring), exponents and roots, fractions, and basic geometry.',
};
const asvabTime = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

async function asvabHome() {
  const info = await api('/api/asvab');
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Learn</button>
    <div class="card" style="margin-top:12px"><h3>📝 ASVAB practice</h3>
      <p>Practice the four subtests that make up the <b>AFQT</b> — the score used to decide who can enlist — with the same number of questions and time limits as the real computer test.</p>
      <div style="display:grid;gap:8px">${info.order.map(s => { const x = info.sections[s]; return `<button class="btn" data-asv="${s}" style="text-align:left;min-height:52px">
        <b>${esc(x.name)} (${s})</b> <span class="faint">· ${x.questions} questions · ${x.minutes} min</span><br><span class="faint">${esc(x.about)}</span></button>`; }).join('')}
        <button class="btn primary" data-asv="ALL" style="min-height:52px">Full AFQT practice — all four (${info.order.reduce((n, s) => n + info.sections[s].questions, 0)} questions · ${info.order.reduce((n, s) => n + info.sections[s].minutes, 0)} min)</button></div></div>
    <div class="card"><h3>How your practice is scored</h3>
      <p>You get <b>exactly</b> how many you got right in each section, your time, and the worked answer to every question. Math questions are generated fresh each time, so you never see the same test twice.</p>
      <p class="faint">What a practice test <b>can't</b> give you is a real AFQT. The real ASVAB is adaptive and its scores compare you with a national group of 18–23 year olds, using questions that are kept secret. Cadet Foundry won't make up a percentile. For real scores, take the free <b>ASVAB Career Exploration Program</b> test if your school offers it — ask your instructor or counselor.</p>
      <p class="faint">Official free practice: officialasvab.com sample questions, asvabprogram.com and march2success.com. Source: officialasvab.com (checked 2026-10-10).</p></div>
    <div class="card"><h3>My practice scores</h3>${info.history.length ? info.history.map(r => `<div style="margin:6px 0"><b>${esc(r.topic)}</b> — ${r.right}/${r.total}
      <span class="faint">· ${asvabTime(r.seconds)} · ${esc(r.date)}${r.sections ? ' · ' + Object.entries(r.sections).map(([s, x]) => `${s} ${x.right}/${x.total}`).join(', ') : ''}</span></div>`).join('')
      : '<p class="faint">No practice tests yet.</p>'}</div>`;
  $('#backStudy').onclick = loaders.study;
  studyBody.querySelectorAll('[data-asv]').forEach(b => b.onclick = async () => {
    const t = await api('/api/asvab/start', { sections: b.dataset.asv === 'ALL' ? info.order : [b.dataset.asv] });
    if (t.error) return alert(t.error);
    asvabRun(t);
  });
}

function asvabRun(t) {
  const answers = {}, end = Date.now() + t.limit * 1000;
  let i = 0, done = false, tick;
  const submit = async () => {
    if (done) return; done = true; clearInterval(tick);
    const r = await api('/api/asvab/submit', { id: t.id, answers });
    if (r.error) { studyBody.innerHTML = `<div class="card"><p>${esc(r.error)}</p><button class="btn" id="asvBack">Back</button></div>`; $('#asvBack').onclick = asvabHome; return; }
    asvabResults(r);
  };
  const show = () => {
    const it = t.items[i], sec = t.section_info[it.section];
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    studyBody.innerHTML = `<div class="row" style="justify-content:space-between"><span class="faint">${esc(sec.name)} · question ${i + 1} of ${t.items.length}</span>
        <b id="asvClock">${asvabTime(left)}</b></div>
      <div class="card" style="margin-top:8px">${it.passage ? `<blockquote style="margin:0 0 12px">${esc(it.passage)}</blockquote>` : ''}
        <p style="font-size:18px">${esc(it.q)}</p>
        ${it.choices.map((c, n) => `<label style="display:flex;gap:10px;align-items:center;min-height:46px;cursor:pointer">
          <input type="radio" name="asvc" value="${n}" ${answers[i] === n ? 'checked' : ''} style="width:22px;height:22px">
          <span style="font-size:18px;color:var(--text)"><b>${'ABCD'[n]}.</b> ${esc(c)}</span></label>`).join('')}</div>
      <div class="row" style="gap:8px;justify-content:space-between">
        <button class="btn" id="asvPrev" ${i === 0 ? 'disabled' : ''}>← Back</button>
        ${i < t.items.length - 1 ? '<button class="btn primary" id="asvNext">Next →</button>' : '<button class="btn primary" id="asvDone">Finish and score</button>'}</div>
      <p class="faint">No calculator — the real ASVAB doesn't allow one. Answered <span id="asvCount">${Object.keys(answers).length}</span> of ${t.items.length}.</p>`;
    studyBody.querySelectorAll('[name=asvc]').forEach(r => r.onchange = () => { answers[i] = +r.value; $('#asvCount').textContent = Object.keys(answers).length; });
    $('#asvPrev').onclick = () => { i--; show(); };
    if ($('#asvNext')) $('#asvNext').onclick = () => { i++; show(); };
    if ($('#asvDone')) $('#asvDone').onclick = () => {
      const blank = t.items.length - Object.keys(answers).length;
      if (blank && !confirm(`${blank} question${blank === 1 ? '' : 's'} not answered. Score the test anyway?`)) return;
      submit();
    };
  };
  tick = setInterval(() => {
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    if ($('#asvClock')) $('#asvClock').textContent = asvabTime(left);
    if (!left) submit();
  }, 1000);
  show();
}

function asvabResults(r) {
  const pct = (x) => Math.round(100 * x.right / (x.total || 1));
  const weakest = Object.entries(r.sections).sort((a, b) => pct(a[1]) - pct(b[1]))[0];
  studyBody.innerHTML = `<div class="card flash"><div class="faint">${esc(r.topic)}</div><div class="q">${r.right} / ${r.total}</div>
      <p>${pct(r)}% right · ${asvabTime(r.seconds)} of ${asvabTime(r.limit)}${r.late ? ' · finished after the time limit' : ''}</p></div>
    <div class="card"><h3>By section</h3>${Object.entries(r.sections).map(([s, x]) => `<div style="margin:8px 0">
        <div class="row" style="justify-content:space-between"><b>${esc(r.names[s])} (${s})</b><span>${x.right} / ${x.total} · ${pct(x)}%</span></div>
        <div style="height:8px;background:var(--line);border-radius:4px;margin-top:4px"><div style="height:8px;width:${pct(x)}%;background:var(--tan);border-radius:4px"></div></div></div>`).join('')}
      ${weakest && pct(weakest[1]) < 100 ? `<p><b>Practice next:</b> ${esc(r.names[weakest[0]])}. ${esc(ASVAB_TIPS[weakest[0]])}</p>` : '<p>Perfect score — try the full practice under time.</p>'}
      <p class="faint">This is your exact practice result, not an ASVAB Standard Score or AFQT percentile — those only come from an official test.</p>
      <div class="row" style="gap:8px"><button class="btn primary" id="asvAgain">Practice again</button><button class="btn" id="asvReview">Review answers</button></div></div>
    <div id="asvReviewBox"></div>`;
  $('#asvAgain').onclick = asvabHome;
  $('#asvReview').onclick = () => {
    $('#asvReviewBox').innerHTML = r.review.map((x, n) => `<div class="card"><div class="faint">${n + 1}. ${esc(r.names[x.section])} ${x.ok ? '<b style="color:var(--green)">✓</b>' : '<b style="color:var(--red)">✗</b>'}</div>
      ${x.passage ? `<blockquote style="margin:6px 0">${esc(x.passage)}</blockquote>` : ''}<p>${esc(x.q)}</p>
      <p>Answer: <b>${esc(x.choices[x.answer])}</b>${!x.ok ? ` · you chose ${x.chose == null ? 'nothing' : esc(x.choices[x.chose])}` : ''}</p>
      <p class="faint">${esc(x.why)}</p></div>`).join('');
    $('#asvReview').remove();
  };
}
