import { api } from './api.js';
import { getMe, homeFor, safeNext } from './auth.js';
import { mountSite } from './site.js';
import { errMsg, setLoading, showFieldErrors } from './ui.js';

(async () => {
  await mountSite();
  const qs = new URLSearchParams(location.search), next = qs.get('next');
  if (qs.get('expirou')) document.getElementById('expired').hidden = false;
  if (next) document.getElementById('toSignup').href = '/cadastro.html?next=' + encodeURIComponent(next);
  const me = await getMe(); if (me) { location.replace(safeNext(next, me)); return; }
  const form = document.getElementById('form'), err = document.getElementById('err'), btn = document.getElementById('submit');
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault(); err.hidden = true;
    const email = form.elements.email.value.trim(), password = form.elements.password.value;
    if (!email || !password) { showFieldErrors(form, { errors: [{ field: email ? 'password' : 'email', message: 'Campo obrigatório.' }] }); return; }
    setLoading(btn, true);
    try { const u = await api('/auth/login', { method: 'POST', body: { email, password } }); location.href = safeNext(next, u); }
    catch (e) { err.textContent = errMsg(e); err.hidden = false; setLoading(btn, false); }
  });
})();
