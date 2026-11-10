import { api } from './api.js';
import { safeNext } from './auth.js';
import { mountSite } from './site.js';
import { applyMasks, calcAge, errMsg, setLoading, showFieldErrors, validCPF, digits } from './ui.js';

(async () => {
  await mountSite();
  const form = document.getElementById('form'), err = document.getElementById('err'), btn = document.getElementById('submit');
  applyMasks(form);
  form.elements.birth_date.max = new Date().toISOString().slice(0, 10);
  form.elements.birth_date.addEventListener('change', () => {   // idade calculada automaticamente
    const v = form.elements.birth_date.value; document.getElementById('age').textContent = v ? `Idade: ${calcAge(v)} anos` : '';
  });

  function validate() {
    const e = [], v = (n) => form.elements[n].value.trim();
    if (v('full_name').length < 3) e.push({ field: 'full_name', message: 'Informe o nome completo.' });
    if (!validCPF(v('cpf'))) e.push({ field: 'cpf', message: 'CPF inválido.' });
    if (!v('birth_date')) e.push({ field: 'birth_date', message: 'Informe a data de nascimento.' });
    else if (new Date(v('birth_date')) > new Date()) e.push({ field: 'birth_date', message: 'A data de nascimento não pode ser futura.' });
    if (![10, 11].includes(digits(v('phone')).length)) e.push({ field: 'phone', message: 'Telefone inválido. Informe DDD e número.' });
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v('email'))) e.push({ field: 'email', message: 'E-mail inválido.' });
    if (v('address').length < 5) e.push({ field: 'address', message: 'Informe o endereço.' });
    const p = form.elements.password.value;
    if (p.length < 8 || !/[A-Za-z]/.test(p) || !/\d/.test(p)) e.push({ field: 'password', message: 'A senha deve ter ao menos 8 caracteres, com letras e números.' });
    if (form.elements.password_confirm.value !== p) e.push({ field: 'password_confirm', message: 'As senhas não conferem.' });
    if (!form.elements.lgpd_consent.checked) e.push({ field: 'lgpd_consent', message: 'É necessário concordar para criar a conta.' });
    return e;
  }

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault(); err.hidden = true;
    const problems = validate();
    if (problems.length) { showFieldErrors(form, { errors: problems }); form.elements[problems[0].field].focus(); return; }
    showFieldErrors(form, { errors: [] });
    setLoading(btn, true);
    try {
      const u = await api('/auth/register', { method: 'POST', body: {
        full_name: form.elements.full_name.value, cpf: form.elements.cpf.value, birth_date: form.elements.birth_date.value, phone: form.elements.phone.value,
        email: form.elements.email.value, address: form.elements.address.value, password: form.elements.password.value,
        password_confirm: form.elements.password_confirm.value, lgpd_consent: form.elements.lgpd_consent.checked } });
      location.href = safeNext(new URLSearchParams(location.search).get('next'), u);
    } catch (e) {
      if (!showFieldErrors(form, e)) { /* erro genérico abaixo */ }
      err.textContent = errMsg(e); err.hidden = false; setLoading(btn, false); err.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
})();
