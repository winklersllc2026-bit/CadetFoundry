// recruit.winklers-llc.com — Joshua's page for Cursiv Recruit builds.
// Password: set the Worker secret RECRUIT_PAGE_PASSWORD to require one for every request
// (npx wrangler secret put RECRUIT_PAGE_PASSWORD). Delete it to make the page open to anyone with the
// address (npx wrangler secret delete RECRUIT_PAGE_PASSWORD). Search engines are told not to list it either way.

const REALM = 'Cursiv Recruit (private)';

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
    const secret = env.RECRUIT_PAGE_PASSWORD;
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
    out.headers.set('Cache-Control', 'no-store');
    out.headers.set('X-Robots-Tag', 'noindex, nofollow');
    out.headers.set('X-Frame-Options', 'DENY');
    out.headers.set('Referrer-Policy', 'no-referrer');
    // Installer, zip and signature: always save as a file, never open in the tab.
    const name = new URL(request.url).pathname.split('/').pop();
    if (res.ok && /\.(exe|zip|sig)$/i.test(name)) {
      out.headers.set('Content-Disposition', `attachment; filename="${name}"`);
      out.headers.set('Content-Type', 'application/octet-stream');
    }
    return out;
  },
};
