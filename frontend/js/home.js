import { api } from './api.js';
import { mountSite } from './site.js';
import { errorBox, errMsg, esc, fmtPhone, icon, empty } from './ui.js';
import { procCard } from './proc-card.js';

const FEATURES = [
  ['calendar', 'Agendamento online', 'Escolha procedimento, profissional e horário em poucos toques, a qualquer hora.'],
  ['shield', 'Dados protegidos', 'Suas informações são tratadas com segurança, conforme a LGPD.'],
  ['userCheck', 'Profissionais habilitados', 'Equipe registrada no conselho de classe e atualizada.'],
  ['clock', 'Acompanhe suas consultas', 'Veja próximas consultas, histórico e status das solicitações.'],
  ['smile', 'Cuidado para todas as idades', 'Do atendimento infantil à estética do sorriso.'],
  ['phone', 'Lembrete de regras claras', 'Cancele ou reagende dentro das regras da clínica, sem burocracia.'],
];

(async () => {
  const { clinic } = await mountSite({ active: '/index.html' });
  document.getElementById('features').innerHTML = FEATURES.map(([i, t, d]) => `<div class="feature"><span class="stat-icon teal">${icon(i)}</span><div><h3 style="margin:0 0 .2rem">${t}</h3><p class="muted small" style="margin:0">${d}</p></div></div>`).join('');

  const pop = document.getElementById('popular');
  try {
    const list = await api('/publico/procedimentos', { params: { populares: 6 } });
    pop.innerHTML = list.length ? list.map(procCard).join('') : empty('Procedimentos em breve', 'A clínica ainda não publicou procedimentos.');
  } catch (e) { pop.innerHTML = errorBox(errMsg(e)); }

  const team = document.getElementById('team');
  try {
    const pros = await api('/publico/profissionais');
    team.innerHTML = pros.length ? pros.map((p) => `<div class="card pro-card"><div class="pro-avatar" aria-hidden="true">${esc(p.full_name.replace(/^(Dr\.?a?|\[DEMO\])\s*/i, '').trim()[0] || '?').toUpperCase()}</div>
      <h3 style="margin:0">${esc(p.full_name)}</h3><p class="muted small" style="margin:.2rem auto 0">${esc(p.specialty)}${p.cro ? '<br>' + esc(p.cro) : ''}</p></div>`).join('')
      : empty('Equipe em breve', 'Os profissionais serão apresentados aqui.', 'users');
  } catch (e) { team.innerHTML = errorBox(errMsg(e)); }

  const maps = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(clinic.address || clinic.name);
  document.getElementById('contact').innerHTML = [
    ['pin', 'Endereço', clinic.address ? `${esc(clinic.address)}<br><a href="${maps}" target="_blank" rel="noopener noreferrer">Abrir no mapa</a>` : 'Não informado.'],
    ['phone', 'Telefone', clinic.phone ? esc(fmtPhone(clinic.phone)) : 'Não informado.'],
    ['mail', 'E-mail', clinic.email ? `<a href="mailto:${esc(clinic.email)}">${esc(clinic.email)}</a>` : 'Não informado.'],
    ['clock', 'Horário de funcionamento', esc(clinic.opening_hours || 'Consulte a clínica.')],
  ].map(([i, t, d]) => `<div class="feature"><span class="stat-icon">${icon(i)}</span><div><h3 style="margin:0 0 .2rem">${t}</h3><p class="muted small" style="margin:0">${d}</p></div></div>`).join('');
})();
