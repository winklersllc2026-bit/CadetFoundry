'use strict';
// Videos (0.2): official military videos. DVIDS videos saved on this device play right here, offline. YouTube
// entries are links to the service's own channel -- they open YouTube in a new tab and need internet; Cadet Foundry
// never embeds YouTube (that would connect every Cadet's device to Google). Listeners in JS.
const VIDEO_ICON = { army: '⭐', navy: '⚓', air_force: '✈️', marine_corps: '🦅', space_force: '🚀', joint: '🎖️' };

async function videosHome(service = '') {
  const r = await api('/api/videos');
  const svcName = s => s === 'joint' ? 'All services' : (STATUS.services || {})[s] || s;
  const have = [...new Set(r.videos.map(v => v.service))];
  const list = r.videos.filter(v => !service || v.service === service);
  const chip = (val, label) => `<button class="chip" data-vsvc="${esc(val)}" style="cursor:pointer;${val === service ? 'border-color:var(--tan);color:var(--tan2)' : ''}">${label}</button>`;
  const row = v => `<div class="card" data-vid="${esc(v.id)}" style="cursor:pointer;margin:8px 0">
      <div class="row" style="justify-content:space-between;gap:8px;flex-wrap:nowrap">
        <b>${VIDEO_ICON[v.service] || ''} ${esc(v.title)}</b>
        <span class="faint" style="white-space:nowrap">${v.kind === 'youtube' ? '▶ YouTube' : v.local ? `▶ ${esc(v.length)}` : esc(v.length)}</span></div>
      <div class="faint">${esc(svcName(v.service))} · ${esc(v.topic)}${v.kind === 'youtube' ? ` · ${esc(v.channel)} (online)` : v.local ? ' · on this device' : ' · not saved yet'}${v.footage ? ' · raw footage, no narration' : ''}</div></div>`;
  const topics = [...new Set(list.map(v => v.topic))];
  studyBody.innerHTML = `<button class="btn small" id="backStudy">← Learn</button>
    <div class="card" style="margin-top:12px"><h3>🎬 Videos</h3>
      <p class="faint">Official military videos. Saved videos play here with no internet. YouTube videos come from each service's own channel and open YouTube (internet needed).</p>
      <div>${chip('', 'All')}${have.map(s => chip(s, `${VIDEO_ICON[s] || ''} ${esc(svcName(s))}`)).join('')}</div>
      ${r.saved < r.dvids ? `<p class="faint" style="margin-top:8px">${r.saved} of ${r.dvids} official DVIDS videos are saved on this device. An administrator adds the rest once with <code>python tools/fetch_videos.py</code> (needs internet and a free DVIDS key).</p>` : ''}</div>
    ${topics.map(t => `<h3 style="margin:16px 0 4px">${esc(t)}</h3>${list.filter(v => v.topic === t).map(row).join('')}`).join('') || '<div class="empty">No videos yet.</div>'}`;
  $('#backStudy').onclick = loaders.study;
  studyBody.querySelectorAll('[data-vsvc]').forEach(b => { b.onclick = () => videosHome(b.dataset.vsvc); });
  studyBody.querySelectorAll('[data-vid]').forEach(c => { c.onclick = () => videoPlay(r.videos.find(v => v.id === c.dataset.vid), service); });
}

function videoPlay(v, service) {
  const credit = v.kind === 'youtube' ? `${esc(v.channel)}, the service's official YouTube channel`
    : `Official video${v.credit ? ` by ${esc(v.credit)}` : ''}, ${esc(v.date)} · public domain · via DVIDS (dvidshub.net)`;
  studyBody.innerHTML = `<button class="btn small" id="backVideos">← Videos</button>
    <div class="card" style="margin-top:12px"><h2 style="margin-top:0">${esc(v.title)}</h2>
      ${v.local ? `<video controls preload="metadata" playsinline src="${esc(v.src)}" style="width:100%;max-height:70vh;background:#000;border-radius:8px"></video>`
        : v.kind === 'youtube' ? `<p>This video is on YouTube. It opens in a new tab and needs internet.</p>
            <a class="btn primary" href="${esc(v.url)}" target="_blank" rel="noopener noreferrer">▶ Watch on YouTube</a>`
        : `<p>This video isn't saved on this device yet.</p>
            <a class="btn" href="${esc(v.url)}" target="_blank" rel="noopener noreferrer">Watch it on DVIDS (needs internet)</a>
            <p class="faint">Your instructor can save it for offline use with <code>python tools/fetch_videos.py</code>.</p>`}
      <p class="faint" style="margin-top:10px">${credit}${v.footage ? ' · raw footage without narration' : ''}${v.length ? ` · ${esc(v.length)}` : ''}</p>
      <p class="faint">Information only — training changes over time. Your instructor and official sources come first.</p></div>`;
  $('#backVideos').onclick = () => videosHome(service);
}
