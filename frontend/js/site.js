// Cabeçalho e rodapé do portal público (dados da clínica vêm do banco).
import { api } from './api.js';
import { getMe, homeFor, logout } from './auth.js';
import { esc, fmtPhone, icon, logoMark } from './ui.js';

const LINKS = [['/index.html', 'Início'], ['/procedimentos.html', 'Procedimentos'], ['/index.html#profissionais', 'Profissionais'], ['/index.html#contato', 'Contato']];

export async function mountSite({ active } = {}) {
  let clinic = { name: 'Clínica Odontológica', logo_url: null, address: '', phone: '', email: '', opening_hours: '' };
  try { clinic = await api('/publico/clinica'); } catch { /* mantém padrão */ }
  const me = await getMe();
  document.title = document.title.replace('{clinica}', clinic.name);
  const mark = clinic.logo_url ? `<img src="${esc(clinic.logo_url)}" alt="">` : logoMark();
  const header = document.getElementById('site-header');
  if (header) {
    header.className = 'site-header';
    header.innerHTML = `<div class="container inner">
      <a class="brand" href="/index.html"><span class="brand-mark">${mark}</span><span class="brand-name">${esc(clinic.name)}</span></a>
      <button class="icon-btn nav-toggle" id="navToggle" aria-label="Abrir menu" aria-expanded="false" aria-controls="siteNav">${icon('menu')}</button>
      <nav class="site-nav" id="siteNav" aria-label="Navegação principal">
        ${LINKS.map(([h, l]) => `<a href="${h}"${active === h ? ' aria-current="page"' : ''}>${l}</a>`).join('')}
        ${me ? `<a href="${homeFor(me)}">${me.role === 'paciente' ? 'Minha área' : 'Painel'}</a><button class="btn btn-outline btn-sm" id="siteLogout">Sair</button>`
             : `<a href="/login.html">Entrar</a><a class="btn btn-sm" href="/agendamento.html">Agendar consulta</a>`}
      </nav></div>`;
    const t = header.querySelector('#navToggle'), n = header.querySelector('#siteNav');
    t.addEventListener('click', () => { const o = n.classList.toggle('open'); t.setAttribute('aria-expanded', String(o)); });
    const lo = header.querySelector('#siteLogout'); if (lo) lo.addEventListener('click', logout);
  }
  const footer = document.getElementById('site-footer');
  if (footer) {
    footer.className = 'site-footer';
    footer.innerHTML = `<div class="container"><div class="footer-grid">
      <div><h4>${esc(clinic.name)}</h4><p class="small">Cuidado odontológico com agendamento online simples e seguro.</p></div>
      <div><h4>Contato</h4><p class="small">${clinic.phone ? esc(fmtPhone(clinic.phone)) + '<br>' : ''}${esc(clinic.email)}<br>${esc(clinic.address)}</p></div>
      <div><h4>Links</h4><p class="small"><a href="/procedimentos.html">Procedimentos</a><br><a href="/agendamento.html">Agendar consulta</a><br><a href="/login.html">Área do paciente</a></p></div>
    </div><div class="footer-bottom">© ${new Date().getFullYear()} ${esc(clinic.name)}. Seus dados são tratados conforme a Lei Geral de Proteção de Dados (LGPD).</div></div>`;
  }
  return { clinic, me };
}
