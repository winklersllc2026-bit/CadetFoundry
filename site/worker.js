// vanguard.winklers-llc.com — Vanguard's public page (since 0.2.2). Downloads come from the public
// Vanguard-releases repo on GitHub; this site only serves the page and its screenshots.
// Optional password: set the Worker secret VANGUARD_PAGE_PASSWORD to require one for every request
// (npx wrangler secret put VANGUARD_PAGE_PASSWORD); while it's set, search engines are told not to list the page.
// Public (the default): npx wrangler secret delete VANGUARD_PAGE_PASSWORD

const REALM = 'Vanguard (private)';

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

export default {
  async fetch(request, env) {
    // RFC 9116: where to report a security problem (always public, even if a page password is set)
    if (new URL(request.url).pathname === '/.well-known/security.txt') {
      return new Response('Contact: mailto:support@winklers-llc.com\nExpires: 2027-10-11T00:00:00.000Z\n'
        + 'Preferred-Languages: en\nCanonical: https://vanguard.winklers-llc.com/.well-known/security.txt\n'
        + 'Policy: https://vanguard.winklers-llc.com/privacy\n',
        { headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'public, max-age=86400' } });
    }
    const secret = env.VANGUARD_PAGE_PASSWORD;
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

    const res = await env.ASSETS.fetch(request);
    const out = new Response(res.body, res);
    const path = new URL(request.url).pathname;
    // screenshots rarely change: cache them a day; the page itself always fresh
    out.headers.set('Cache-Control', path.startsWith('/shots/') ? 'public, max-age=86400' : 'no-cache');
    if (secret) out.headers.set('X-Robots-Tag', 'noindex, nofollow');
    out.headers.set('X-Frame-Options', 'DENY');
    out.headers.set('Referrer-Policy', 'no-referrer');
    // Installer, zip and signature: always save as a file, never open in the tab.
    const name = path.split('/').pop();
    if (res.ok && /\.(exe|zip|sig)$/i.test(name)) {
      out.headers.set('Content-Disposition', `attachment; filename="${name}"`);
      out.headers.set('Content-Type', 'application/octet-stream');
    }
    return out;
  },
};
