import { CATEGORY, esc, icon } from './ui.js';

export function procCard(p) {
  const c = CATEGORY[p.category] || CATEGORY.geral;
  return `<article class="card proc-card">
    <div class="proc-media">${p.image_url ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy">` : icon(c.icon, 56)}</div>
    <div class="proc-body"><h3>${esc(p.name)}</h3>
      <div class="proc-meta"><span class="badge badge-info">${esc(c.label)}</span><span class="badge badge-muted">${p.duration_minutes} min</span>
        ${p.available ? '<span class="badge badge-success">Disponível</span>' : '<span class="badge badge-warning">Indisponível no momento</span>'}</div>
      <p class="muted small" style="margin:0">${esc(p.description)}</p>
      ${p.guidance ? `<div class="proc-guidance"><strong>Orientações:</strong> ${esc(p.guidance)}</div>` : ''}
      ${p.available ? `<a class="btn btn-sm mt" href="/agendamento.html?procedimento=${p.id}">Agendar</a>` : ''}
    </div></article>`;
}
