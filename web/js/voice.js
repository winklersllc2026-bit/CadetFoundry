'use strict';
// Offline voice: read-aloud and talk-to-Cadet Foundry.

// ── VOICE (offline only) ──
// Read aloud: only the computer's own LOCAL voices (voice.localService), so nothing leaves the device.
const speech = {
  ok: false, auto: false, voice: null,
  init() {
    if (!('speechSynthesis' in window)) return;
    const pick = () => {
      const local = speechSynthesis.getVoices().filter(v => v.localService && v.lang.toLowerCase().startsWith('en'));
      this.voice = local.find(v => /en-US/i.test(v.lang)) || local[0] || null;
      this.ok = !!this.voice;
    };
    pick(); speechSynthesis.onvoiceschanged = pick;
    try { this.auto = localStorage.getItem('vanguard-autoread') === '1'; } catch (e) {}
  },
  btn: null, utter: null,                      // the 🔊 button and the speech of whatever is being read right now
  // One tap reads aloud and the button turns into ⏹; a second tap stops it. Starting another answer stops this one.
  toggle(text, btn) {
    if (btn && this.btn === btn) return this.stop();         // second tap on the same button: stop
    this.say(text, btn);
  },
  say(text, btn) {
    if (!this.ok) return;
    this.stop();
    const clean = text.replace(/\*\*|[*`#>]/g, '').replace(/\s+/g, ' ').slice(0, 3000);
    const u = new SpeechSynthesisUtterance(clean); u.voice = this.voice; u.rate = 1;
    this.utter = u;                            // keep it referenced: browsers can drop it mid-sentence otherwise
    if (btn) {
      this.btn = btn; btn.textContent = '⏹'; btn.title = 'Stop reading'; btn.classList.add('primary');
      u.onend = u.onerror = () => { if (this.utter === u) this.stop(); };
    }
    // After cancel(), Chrome/Edge can leave speech paused, so the next answer never plays or ends ("speaking"
    // forever, button stuck on ⏹). resume() clears it; tested: waiting alone doesn't.
    setTimeout(() => { if (this.utter === u) { speechSynthesis.resume(); speechSynthesis.speak(u); } }, 60);
  },
  stop() {
    this.utter = null;
    speechSynthesis.cancel();
    const b = this.btn; this.btn = null;
    if (b) { b.textContent = '🔊'; b.title = 'Read aloud (on this device)'; b.classList.remove('primary'); }
  },
  setAuto(on) { this.auto = on; try { localStorage.setItem('vanguard-autoread', on ? '1' : ''); } catch (e) {} },
};
speech.init();

// Talk: record 16 kHz mono audio and send it to Cadet Foundry's own offline recognizer (Vosk).
// The browser's built-in speech recognition is NOT used -- it sends audio to cloud servers.
const mic = {
  rec: null,
  async start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const chunks = [];
    proc.onaudioprocess = e => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    src.connect(proc); proc.connect(ctx.destination);
    this.rec = { stream, ctx, proc, chunks, rate: ctx.sampleRate };
  },
  async stop() {
    const r = this.rec; this.rec = null;
    r.proc.disconnect(); r.stream.getTracks().forEach(t => t.stop()); await r.ctx.close();
    const total = r.chunks.reduce((n, c) => n + c.length, 0), all = new Float32Array(total);
    let o = 0; for (const c of r.chunks) { all.set(c, o); o += c.length; }
    const ratio = r.rate / 16000, n = Math.floor(total / ratio), pcm = new Int16Array(n);   // resample to 16 kHz
    for (let i = 0; i < n; i++) { const s = Math.max(-1, Math.min(1, all[Math.floor(i * ratio)])); pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff; }
    let bin = ''; const bytes = new Uint8Array(pcm.buffer);
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  },
};
unlocked.then(async s => {
  if (!s) return;
  const st = await api('/api/status');
  if (!st.voice || !navigator.mediaDevices) return;
  const btn = $('#micBtn'); btn.hidden = false;
  btn.onclick = async () => {
    if (!mic.rec) {
      try { await mic.start(); btn.textContent = '⏹'; btn.classList.add('primary'); $('#msgIn').placeholder = 'Listening… tap ⏹ when done'; }
      catch (e) { alert('The microphone is not available.'); }
      return;
    }
    btn.textContent = '…'; btn.disabled = true;
    const audio = await mic.stop();
    const r = await api('/api/voice', { audio, rate: 16000 });
    btn.textContent = '🎤'; btn.disabled = false; btn.classList.remove('primary'); $('#msgIn').placeholder = 'Ask Cadet Foundry…';
    if (r.text) send(r.text); else if (r.error) alert(r.error); else $('#msgIn').placeholder = "Didn't catch that — try again.";
  };
});
