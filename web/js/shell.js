// Vanguard shell: the Lead, Serve, Progress and Instructor pages. Lead, Progress and Instructor are the frames
// later phases fill in; Serve already holds Explore Military Service (pay, letters, PCS, leave, Army jobs).
'use strict';

const SOON = (what, phase) => `<p class="faint">${what} <b>Coming in a later update</b> (${phase}). Until then your instructor leads this part in class.</p>`;

loaders.lead = () => {
  $('#leadBody').innerHTML = `<h2>Lead</h2>
    <div class="card"><h3>🧭 Leadership scenarios</h3>
      <p>Real situations a Cadet leader meets — a team behind schedule, two Cadets arguing, someone who stopped
      participating. You choose what to do, see what happened and why, and write what you'd do next time.</p>
      ${SOON('Scenarios and your leadership log are being built.', 'Phase 5')}</div>`;
};

loaders.serve = () => {
  // data-go="view[:pane]" -- the page's security policy blocks inline onclick handlers
  const go = (v, pane) => `data-go="${v}${pane ? ':' + pane : ''}"`;
  $('#serveBody').innerHTML = `<h2>Serve</h2>
    <div class="card"><h3>🤝 Service learning</h3>
      <p>Track your service projects: date, hours, organization, your role, and what you learned. Your instructor
      verifies them.</p>${SOON('The service log is being built.', 'Phase 7')}</div>
    <div class="card" id="exploreMil"><h3>🎖️ Explore Military Service</h3>
      <p class="faint">For Cadets who want to learn what military service is like. Information only — nothing here
      signs you up or shares anything with a recruiter. Numbers come straight from official tables.</p>
      <div class="row" style="flex-wrap:wrap;gap:6px">
        <button class="btn small" ${go('logbook', 'money')}>💵 Military pay and budgeting</button>
        <button class="btn small" ${go('study')}>🪖 Army jobs explorer (in Learn)</button>
        <button class="btn small" ${go('logbook', 'leave')}>🏖️ How military leave works</button>
        <button class="btn small" ${go('logbook', 'pcs')}>📦 Moving with the military (PCS)</button>
        <button class="btn small" ${go('logbook', 'letters')}>✉️ Letters to family, service members and veterans</button>
      </div>
      <p class="faint">Ask questions like "What does an E-4 with 3 years make?" or "What is the ETS box on a pay
      statement?" with 💬 Ask.</p></div>`;
  $('#serveBody').querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => {
    const [v, pane] = b.dataset.go.split(':'); openView(v, pane);
  }));
};

loaders.progress = () => {
  $('#progressBody').innerHTML = `<h2>My Progress</h2>
    <div class="card"><h3>📈 Your growth over time</h3>
      <p>Lessons and quiz mastery, leadership scenarios and reflections, fitness improvement, service hours, and
      recognition — in one place, with a portfolio you can print.</p>
      ${SOON('Your progress page is being built.', 'Phase 8')}
      <p class="faint">Already here: your quiz progress in Learn and your fitness history in Train.</p></div>`;
};

loaders.instructor = () => {
  $('#instructorBody').innerHTML = `<h2>Instructor</h2>
    <div class="card"><h3>🎓 Instructor tools</h3>
      <p>Classes, platoons and squads; lessons and assignments; leadership scenarios for classroom discussion;
      the class dashboard and reports; pilot tools.</p>
      ${SOON('Instructor tools are being built.', 'Phases 3–10')}
      <p>Available now in 👤 Me: the <b>Instructor PIN</b> and the <b>AI setting</b> (Off / Library only /
      Library + AI) for every profile on this device.</p></div>`;
};
