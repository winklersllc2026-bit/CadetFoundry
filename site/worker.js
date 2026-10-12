// cadetfoundry.org — Cadet Foundry's public page (since 0.2.2).
// Downloads (0.2.7, owner 2026-10-12): the installer and update files are given out with an ACCESS CODE, one per
// instructor, made by the owner with tools/pilot_access.py. The files live in Cloudflare R2 (binding DOWNLOADS); the
// codes live in D1 (binding DB) only as SHA-256 hashes, and a download records which code and when -- no IP address,
// no name (the names behind the codes stay on the owner's computer). The page itself stays public.
// Optional page password: set the Worker secret CADETFOUNDRY_PAGE_PASSWORD to require one for every request
// (npx wrangler secret put CADETFOUNDRY_PAGE_PASSWORD); while it's set, search engines are told not to list the page.

const REALM = 'Cadet Foundry (private)';
// what a code can download: the installer, and the signed update for "Me -> Install an update"
const FILES = { setup: 'setup', update: 'zip', sig: 'sig' };

function unauthorized(msg = 'Password required') {
  return new Response(msg, {
    status: 401,
    headers: { 'WWW-Authenticate': `Basic realm="${REALM}", charset="UTF-8"`, 'Cache-Control': 'no-store' },
  });
}

// Constant-time comparison so the password can't be guessed from response timing.
function same(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(a), y = enc.encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}

// An access code as people type it ("rivera-7k2m q9x4h") -> "RIVERA7K2MQ9X4H"; tools/pilot_access.py does the same.
export function normCode(c) {
  return String(c || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 40);
}

export async function sha256hex(text) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('');
}

const back = (why) => Response.redirect(`https://cadetfoundry.org/download?${why}=1`, 303);

// POST /download: code + which file. The file streams straight from R2 as an attachment.
export async function download(request, env) {
  if (!env.DB || !env.DOWNLOADS) return back('closed');
  let form;
  try { form = await request.formData(); } catch { return back('bad'); }
  const code = normCode(form.get('code'));
  const which = String(form.get('file') || 'setup');
  if (!FILES[which] || code.length < 8) return back('bad');
  const row = await env.DB.prepare('SELECT id, active FROM codes WHERE hash = ?').bind(await sha256hex(code)).first();
  if (!row || !row.active) {
    await new Promise(r => setTimeout(r, 400));             // a slower answer for a wrong code
    return back(row ? 'off' : 'bad');
  }
  const latest = await env.DOWNLOADS.get('latest.json');     // which file is current: written by build.py --release
  const names = latest ? await latest.json() : {};
  const name = names[FILES[which]];
  const obj = name ? await env.DOWNLOADS.get(name) : null;
  if (!obj) return back('missing');
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB.prepare('INSERT INTO downloads (code_id, at, file) VALUES (?, ?, ?)').bind(row.id, now, name),
    env.DB.prepare('UPDATE codes SET uses = uses + 1, last_used = ? WHERE id = ?').bind(now, row.id),
  ]);
  return new Response(obj.body, {
    headers: {
      'Content-Type': 'application/octet-stream',
      'Content-Disposition': `attachment; filename="${name}"`,
      'Cache-Control': 'no-store',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'no-referrer',
    },
  });
}

export default {
  async fetch(request, env) {
    // One address: www and the address used before the rename forward to cadetfoundry.org (same page, same path)
    const here = new URL(request.url);
    if (here.hostname === 'www.cadetfoundry.org' || here.hostname === 'vanguard.winklers-llc.com') {
      return Response.redirect('https://cadetfoundry.org' + here.pathname + here.search, 301);
    }
    // RFC 9116: where to report a security problem (always public, even if a page password is set)
    if (here.pathname === '/.well-known/security.txt') {
      return new Response('Contact: mailto:support@cadetfoundry.org\nExpires: 2027-10-11T00:00:00.000Z\n'
        + 'Preferred-Languages: en\nCanonical: https://cadetfoundry.org/.well-known/security.txt\n'
        + 'Policy: https://cadetfoundry.org/privacy\n',
        { headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'public, max-age=86400' } });
    }
    const secret = env.CADETFOUNDRY_PAGE_PASSWORD;
    if (secret) {
      const auth = request.headers.get('Authorization') || '';
      if (!auth.startsWith('Basic ')) return unauthorized();
      let pass = '';
      try {
        const decoded = atob(auth.slice(6));
        pass = decoded.slice(decoded.indexOf(':') + 1);      // any username; only the password matters
      } catch {
        return unauthorized();
      }
      if (!same(pass, secret)) return unauthorized('Wrong password');
    }
    if (here.pathname === '/download' && request.method === 'POST') return download(request, env);
    // The installer and update files are never served from the page's own files (they aren't uploaded with it).
    if (/\.(exe|zip|sig)$/i.test(here.pathname)) {
      return new Response('Downloads need an access code: https://cadetfoundry.org/download', { status: 404 });
    }

    const res = await env.ASSETS.fetch(request);
    const out = new Response(res.body, res);
    // screenshots and artwork rarely change: cache them a day; pages always fresh
    const still = here.pathname.startsWith('/shots/') || here.pathname.startsWith('/img/');
    out.headers.set('Cache-Control', still ? 'public, max-age=86400' : 'no-cache');
    if (secret) out.headers.set('X-Robots-Tag', 'noindex, nofollow');
    out.headers.set('X-Frame-Options', 'DENY');
    out.headers.set('Referrer-Policy', 'no-referrer');
    return out;
  },
};
