import { api } from './api.js';

let cached;
export async function getMe(force = false) {
  if (cached !== undefined && !force) return cached;
  try { cached = await api('/auth/me'); } catch { cached = null; }
  return cached;
}
export const homeFor = (me) => (me && me.role === 'paciente' ? '/portal/dashboard.html' : '/admin/dashboard.html');

export function safeNext(next, me) {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : homeFor(me);
}

/** Protege a página: sem sessão -> login; perfil sem permissão -> página inicial do perfil. */
export async function requireAuth(roles) {
  const me = await getMe(true);
  if (!me) { location.replace('/login.html?next=' + encodeURIComponent(location.pathname + location.search)); return null; }
  if (roles && !roles.includes(me.role)) { location.replace(homeFor(me)); return null; }
  return me;
}

export async function logout() {
  try { await api('/auth/logout', { method: 'POST' }); } catch { /* ignore */ }
  cached = null; location.href = '/login.html';
}
