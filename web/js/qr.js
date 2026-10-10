'use strict';
// A small QR code maker for the class Join screen -- no library, nothing downloaded, works offline.
// Byte mode, error correction level M, versions 1-10 (up to 213 bytes: far more than a classroom address).
// Follows ISO/IEC 18004: Reed-Solomon over GF(256), interleaved blocks, all 8 masks scored, the lowest penalty kept.
const QR = (() => {
  // [total codewords, EC codewords per block, [blocks, data codewords]...] for level M
  const M = [null,
    [26, 10, [1, 16]], [44, 16, [1, 28]], [70, 26, [1, 44]], [100, 18, [2, 32]], [134, 24, [2, 43]],
    [172, 16, [4, 27]], [196, 18, [4, 31]], [242, 22, [2, 38], [2, 39]], [292, 22, [3, 36], [2, 37]],
    [346, 26, [4, 43], [1, 44]]];
  const ALIGN = [null, [], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50]];
  const REMAINDER = [0, 0, 7, 7, 7, 7, 7, 0, 0, 0, 0];

  const mul = (x, y) => {                       // GF(256) with x^8 + x^4 + x^3 + x^2 + 1
    let z = 0;
    for (let i = 7; i >= 0; i--) { z = (z << 1) ^ ((z >>> 7) * 0x11D); z ^= ((y >>> i) & 1) * x; }
    return z;
  };
  const rsDivisor = n => {
    const r = new Array(n).fill(0); r[n - 1] = 1;
    let root = 1;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) { r[j] = mul(r[j], root); if (j + 1 < n) r[j] ^= r[j + 1]; }
      root = mul(root, 2);
    }
    return r;
  };
  const rsRemainder = (data, div) => {
    const r = new Array(div.length).fill(0);
    for (const b of data) {
      const f = b ^ r.shift(); r.push(0);
      div.forEach((d, i) => { r[i] ^= mul(d, f); });
    }
    return r;
  };

  function codewords(bytes, ver) {
    const [total, ecLen, ...groups] = M[ver];
    const dataLen = groups.reduce((s, [n, k]) => s + n * k, 0);
    const bits = [];
    const put = (v, n) => { for (let i = n - 1; i >= 0; i--) bits.push((v >>> i) & 1); };
    put(4, 4); put(bytes.length, ver < 10 ? 8 : 16);
    bytes.forEach(b => put(b, 8));
    put(0, Math.min(4, dataLen * 8 - bits.length));
    while (bits.length % 8) bits.push(0);
    for (let pad = 0xEC; bits.length < dataLen * 8; pad ^= 0xEC ^ 0x11) put(pad, 8);
    const data = [];
    for (let i = 0; i < bits.length; i += 8) data.push(bits.slice(i, i + 8).reduce((a, b) => (a << 1) | b, 0));
    const blocks = [], ecs = [], div = rsDivisor(ecLen);
    let at = 0;
    groups.forEach(([n, k]) => { for (let i = 0; i < n; i++) { const blk = data.slice(at, at + k); at += k; blocks.push(blk); ecs.push(rsRemainder(blk, div)); } });
    const out = [];
    const longest = Math.max(...blocks.map(b => b.length));
    for (let i = 0; i < longest; i++) blocks.forEach(b => { if (i < b.length) out.push(b[i]); });
    for (let i = 0; i < ecLen; i++) ecs.forEach(e => out.push(e[i]));
    if (out.length !== total) throw new Error('QR: codeword count');
    return out;
  }

  function make(text) {
    const bytes = [...new TextEncoder().encode(text)];
    let ver = 1;
    while (ver <= 10) {
      const cap = M[ver].slice(2).reduce((s, [n, k]) => s + n * k, 0) - (ver < 10 ? 2 : 3);
      if (bytes.length <= cap) break;
      ver++;
    }
    if (ver > 10) throw new Error('Too long for a QR code');
    const size = ver * 4 + 17;
    const mod = Array.from({ length: size }, () => new Array(size).fill(false));
    const fn = Array.from({ length: size }, () => new Array(size).fill(false));
    const set = (x, y, dark) => { mod[y][x] = dark; fn[y][x] = true; };

    for (let i = 0; i < size; i++) { set(6, i, i % 2 === 0); set(i, 6, i % 2 === 0); }      // timing
    for (const [cx, cy] of [[3, 3], [size - 4, 3], [3, size - 4]]) {                    // finders + separators
      for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
        const x = cx + dx, y = cy + dy, d = Math.max(Math.abs(dx), Math.abs(dy));
        if (x >= 0 && x < size && y >= 0 && y < size) set(x, y, d !== 2 && d !== 4);
      }
    }
    const al = ALIGN[ver], last = al.length - 1;
    al.forEach((ay, i) => al.forEach((ax, j) => {
      if ((i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0)) return;
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) set(ax + dx, ay + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }));
    const drawFormat = mask => {
      const data = (0 << 3) | mask;              // level M = 00
      let rem = data;
      for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
      const bits = ((data << 10) | rem) ^ 0x5412, bit = i => ((bits >>> i) & 1) === 1;
      for (let i = 0; i <= 5; i++) set(8, i, bit(i));
      set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
      for (let i = 9; i < 15; i++) set(14 - i, 8, bit(i));
      for (let i = 0; i < 8; i++) set(size - 1 - i, 8, bit(i));
      for (let i = 8; i < 15; i++) set(8, size - 15 + i, bit(i));
      set(8, size - 8, true);                     // the dark module
    };
    drawFormat(0);                                // reserves the format areas
    if (ver >= 7) {
      let rem = ver;
      for (let i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1F25);
      const bits = (ver << 12) | rem;
      for (let i = 0; i < 18; i++) {
        const b = ((bits >>> i) & 1) === 1, a = size - 11 + (i % 3), c = Math.floor(i / 3);
        set(a, c, b); set(c, a, b);
      }
    }
    const data = codewords(bytes, ver);
    let i = 0;
    const nbits = data.length * 8 + REMAINDER[ver];
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (let vert = 0; vert < size; vert++) for (let j = 0; j < 2; j++) {
        const x = right - j, up = ((right + 1) & 2) === 0, y = up ? size - 1 - vert : vert;
        if (!fn[y][x] && i < nbits) { mod[y][x] = i < data.length * 8 && ((data[i >>> 3] >>> (7 - (i & 7))) & 1) === 1; i++; }
      }
    }
    const MASKS = [(x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, x => x % 3 === 0, (x, y) => (x + y) % 3 === 0,
      (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0, (x, y) => (x * y) % 2 + (x * y) % 3 === 0,
      (x, y) => ((x * y) % 2 + (x * y) % 3) % 2 === 0, (x, y) => ((x + y) % 2 + (x * y) % 3) % 2 === 0];
    const applyMask = m => { for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (!fn[y][x] && MASKS[m](x, y)) mod[y][x] = !mod[y][x]; };
    const penalty = () => {
      let p = 0, dark = 0;
      const line = get => {                       // runs of 5+ and finder-like patterns, one row or column
        let run = 1;
        for (let k = 1; k <= size; k++) {
          if (k < size && get(k) === get(k - 1)) run++;
          else { if (run >= 5) p += run - 2; run = 1; }
        }
        const s = Array.from({ length: size }, (_, k) => (get(k) ? '1' : '0')).join('');
        for (const pat of ['10111010000', '00001011101']) for (let k = s.indexOf(pat); k >= 0; k = s.indexOf(pat, k + 1)) p += 40;
      };
      for (let k = 0; k < size; k++) { line(x => mod[k][x]); line(y => mod[y][k]); }
      for (let y = 0; y < size - 1; y++) for (let x = 0; x < size - 1; x++) {
        const c = mod[y][x];
        if (c === mod[y][x + 1] && c === mod[y + 1][x] && c === mod[y + 1][x + 1]) p += 3;
      }
      mod.forEach(r => r.forEach(c => { if (c) dark++; }));
      return p + 10 * Math.floor(Math.abs(dark * 20 / (size * size) - 10));
    };
    let best = 0, bestScore = Infinity;
    for (let m = 0; m < 8; m++) {
      applyMask(m); drawFormat(m);
      const s = penalty();
      if (s < bestScore) { best = m; bestScore = s; }
      applyMask(m);                               // undo (XOR)
    }
    applyMask(best); drawFormat(best);
    return mod;
  }

  // An SVG (crisp at any size on a projector) with the 4-module quiet zone the standard asks for.
  function svg(text, px = 320) {
    const m = make(text), n = m.length + 8;
    let d = '';
    m.forEach((row, y) => row.forEach((c, x) => { if (c) d += `M${x + 4},${y + 4}h1v1h-1z`; }));
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${n} ${n}" width="${px}" height="${px}" shape-rendering="crispEdges" role="img" aria-label="QR code">`
      + `<rect width="${n}" height="${n}" fill="#fff"/><path d="${d}" fill="#000"/></svg>`;
  }
  return { make, svg };
})();
if (typeof module !== 'undefined') module.exports = QR;
