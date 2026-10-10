// Home (0.2): the first screen a Cadet sees -- anything the instructor started in class, what's due, the Daily 10,
// and progress at a glance. Most days a Cadet never needs to leave it. Listeners in JS (no inline handlers).
'use strict';

let homePoll = null;
const homeDue = d => {
  if (!d) return '';
  const days = Math.round((new Date(d + 'T00:00') - new Date(new Date().toDateString())) / 86400000);
  return days < 0 ? `<span style="color:var(--red)">overdue</span>` : days === 0 ? 'due today' : days === 1 ? 'due tomorrow' : `due ${esc(d)}`;
};

async function homeLive() {
  const box = $('#homeLive');
  if (!box || STATUS.kind !== 'cadet') return;
  const [lv, lq] = await Promise.all([api('/api/live'), api('/api/live/quiz')]);
  const what = lq && lq.id ? (lq.answered ? '' : '🎯 Your instructor asked a live question') : lv && lv.scenario && !lv.my_vote && !lv.revealed ? '🗳️ Your instructor started a class vote' : '';
  box.innerHTML = what ? `<div class="card" style="border-color:var(--tan)"><div class="row" style="justify-content:space-between;gap:10px">
      <b>${what}</b><button class="btn primary" id="homeLiveGo">Answer now</button></div></div>` : '';
  if ($('#homeLiveGo')) $('#homeLiveGo').addEventListener('click', () => openView('lead'));
}

loaders.home = async () => {
  const body = $('#homeBody');
  const kind = STATUS.kind || 'cadet';
  const lock = await api('/api/lock');
  const first = (lock.current && lock.current.name) || '';   // the whole name: many start with a title (Cadet, Ms.)
  if (kind === 'instructor') {
    body.innerHTML = `<h2>Hi${first ? ', ' + esc(first) : ''}</h2>
      <div class="card"><h3>🎓 Your class</h3><p class="faint">Lessons, Cadets, scenarios and reports are in your instructor tools.</p>
        <button class="btn primary" id="homeInst">Open instructor tools</button></div>`;
    $('#homeInst').addEventListener('click', () => openView('instructor'));
    return;
  }
  const cadet = kind === 'cadet';
  const [dly, ls, pg] = await Promise.all([api('/api/daily'), cadet ? api('/api/lessons') : { assignments: [] },
    cadet ? api('/api/progress') : {}]);
  const st = dly.status || {};
  const due = (ls.assignments || []).filter(a => a.state !== 'complete');
  const ac = pg.academics, stat = (n, label) => `<div><div style="font-size:24px;font-weight:700">${n}</div><div class="faint">${label}</div></div>`;
  const title = STATUS.cadet_title || {};
  body.innerHTML = `<h2 style="margin-bottom:2px">Hi${first ? ', ' + esc(first) : ''}</h2>
    ${title.rank || title.billet ? `<p class="faint" style="margin:0 0 12px">${[title.rank, title.billet].filter(Boolean).map(esc).join(' · ')}</p>` : ''}
    <div id="homeLive"></div>
    ${cadet ? `<div class="card"><h3>📋 Due</h3>
      ${due.length ? due.slice(0, 4).map(a => `<div class="row" style="justify-content:space-between;gap:10px;margin:8px 0">
          <span><b>${esc(a.title)}</b> <span class="faint">${homeDue(a.due)}${a.state === 'in_progress' ? ' · started' : ''}</span></span>
          <button class="btn small primary" data-home-lesson="${esc(a.id)}">Open</button></div>`).join('')
        + (due.length > 4 ? `<p class="faint">${due.length - 4} more in 📘 Learn → My assignments.</p>` : '')
        : '<p class="faint">Nothing due right now — nice work.</p>'}</div>` : ''}
    <div class="card"><div class="row" style="justify-content:space-between;gap:10px">
      <div><h3>🔥 Daily 10</h3><div class="faint">${st.done_today ? `Done today: ${st.today_score.right}/${st.today_score.total}. ` : 'Ten questions, every day. '}Streak: <b>${st.streak || 0}</b> day${st.streak === 1 ? '' : 's'}</div></div>
      <button class="btn primary" id="homeDaily">${st.done_today ? 'Again' : 'Start'}</button></div></div>
    ${ac ? `<div class="card"><div class="row" style="justify-content:space-between;gap:10px;align-items:flex-start">
        <h3 style="margin:0">📈 My progress</h3><button class="btn small" id="homeProgress">See all</button></div>
      <div class="row" style="flex-wrap:wrap;gap:22px;margin-top:10px">${stat(ac.lessons_completed, 'lessons')}${stat(pg.leadership.scenarios_completed, 'scenarios')}
        ${stat(pg.service.verified_hours, 'service hours')}${stat(ac.cards_mastered, 'cards mastered')}</div></div>` : ''}
    <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn" id="homeLearn">📘 Keep learning</button><button class="btn" id="homeAsk">💬 Ask a question</button></div>`;
  body.querySelectorAll('[data-home-lesson]').forEach(b => b.addEventListener('click', () => { openView('lesson'); openLesson(b.dataset.homeLesson); }));
  $('#homeDaily').addEventListener('click', () => { openView('study'); chooseQuiz('', true); });
  if ($('#homeProgress')) $('#homeProgress').addEventListener('click', () => openView('progress'));
  $('#homeLearn').addEventListener('click', () => openView('study'));
  $('#homeAsk').addEventListener('click', () => openView('ask'));
  homeLive();
  clearInterval(homePoll);
  if (cadet) homePoll = setInterval(() => {                    // a live question shows up without a reload
    if (!$('#home').classList.contains('on')) { clearInterval(homePoll); return; }
    homeLive().catch(() => clearInterval(homePoll));
  }, 8000);
};
