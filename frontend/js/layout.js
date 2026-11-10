// Estrutura do painel administrativo: menu lateral (fixo no desktop, compacto no tablet, gaveta no celular).
import { requireAuth, logout } from './auth.js';
import { api } from './api.js';
import { esc, icon, logoMark } from './ui.js';

const ROLE_LABEL = { admin: 'Administrador', recepcionista: 'Recepcionista', dentista: 'Dentista' };
const MENU = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', href: '/admin/dashboard.html', roles: ['admin', 'recepcionista', 'dentista'] },
  { id: 'agendamentos', label: 'Agendamentos', icon: 'calendar', href: '/admin/agendamentos.html', roles: ['admin', 'recepcionista', 'dentista'] },
  { id: 'pacientes', label: 'Pacientes', icon: 'users', href: '/admin/pacientes.html', roles: ['admin', 'recepcionista', 'dentista'] },
  { id: 'procedimentos', label: 'Procedimentos', icon: 'clipboard', href: '/admin/procedimentos.html', roles: ['admin'] },
  { id: 'profissionais', label: 'Profissionais', icon: 'userCheck', href: '/admin/profissionais.html', roles: ['admin'] },
  { id: 'atendimentos', label: 'Atendimentos', icon: 'activity', href: '/admin/atendimentos.html', roles: ['admin', 'recepcionista', 'dentista'] },
  { id: 'financeiro', label: 'Financeiro', icon: 'dollar', href: '/admin/financeiro.html', roles: ['admin'] },
  { id: 'relatorios', label: 'Relatórios', icon: 'chart', href: '/admin/relatorios.html', roles: ['admin'] },
  { id: 'configuracoes', label: 'Configurações', icon: 'settings', href: '/admin/configuracoes.html', roles: ['admin'] },
];

export async function mountShell({ active, title, roles = ['admin', 'recepcionista', 'dentista'] }) {
  const me = await requireAuth(roles);
  if (!me) return null;
  let clinic = { name: 'Clínica', logo_url: null };
  try { clinic = await api('/publico/clinica'); } catch { /* usa padrão */ }
  document.title = `${title} — ${clinic.name}`;
  const items = MENU.filter((m) => m.roles.includes(me.role));
  const root = document.getElementById('shell-root');
  root.innerHTML = `<div class="shell">
    <aside class="sidebar" id="sidebar" aria-label="Menu principal">
      <a class="brand" href="/admin/dashboard.html"><span class="brand-mark">${clinic.logo_url ? `<img src="${esc(clinic.logo_url)}" alt="">` : logoMark()}</span><span class="brand-name">${esc(clinic.name)}</span></a>
      <nav class="nav">${items.map((m) => `<a href="${m.href}" title="${esc(m.label)}"${m.id === active ? ' aria-current="page"' : ''}>${icon(m.icon)}<span>${esc(m.label)}</span></a>`).join('')}</nav>
      <div class="nav-foot"><button class="btn btn-outline btn-block" id="logoutBtn" title="Sair">${icon('logout', 18)}<span>Sair</span></button></div>
    </aside>
    <div class="shell-overlay" id="overlay"></div>
    <div class="shell-main">
      <header class="topbar">
        <button class="icon-btn" id="menuBtn" aria-label="Abrir menu" aria-controls="sidebar" aria-expanded="false">${icon('menu')}</button>
        <h1>${esc(title)}</h1>
        <div class="user-chip"><span class="avatar" aria-hidden="true">${esc(me.full_name.trim()[0] || '?').toUpperCase()}</span>
          <span class="who">${esc(me.full_name)}<small>${ROLE_LABEL[me.role] || ''}</small></span></div>
      </header>
      <main class="content" id="content"></main>
    </div></div>`;
  const sb = document.getElementById('sidebar'), ov = document.getElementById('overlay'), btn = document.getElementById('menuBtn');
  const toggle = (open) => { sb.classList.toggle('open', open); ov.classList.toggle('show', open); btn.setAttribute('aria-expanded', String(open)); };
  btn.addEventListener('click', () => toggle(!sb.classList.contains('open')));
  ov.addEventListener('click', () => toggle(false));
  sb.addEventListener('click', (e) => { if (e.target.closest('a')) toggle(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') toggle(false); });
  document.getElementById('logoutBtn').addEventListener('click', logout);
  return { me, clinic, content: document.getElementById('content') };
}
