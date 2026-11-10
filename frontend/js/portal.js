// Área do paciente: dashboard, meus agendamentos e perfil.
import { api } from './api.js';
import { requireAuth } from './auth.js';
import { mountSite } from './site.js';
import { slotPicker } from './pickers.js';
import { applyMasks, calcAge, confirmDialog, empty, errMsg, errorBox, esc, fmtCPF, fmtDate, fmtPhone, fmtTime, icon, modalForm, openModal, parseISO, spinner, statusBadge, toast, setLoading, showFieldErrors } from './ui.js';

const NAV = [['/portal/dashboard.html', 'Início'], ['/portal/meus-agendamentos.html', 'Meus agendamentos'], ['/portal/perfil.html', 'Meus dados'], ['/agendamento.html', 'Novo agendamento']];

export async function bootPortal(page, render) {
  const me = await requireAuth(['paciente']); if (!me) return;
  await mountSite();
  const nav = document.getElementById('portal-nav');
  nav.className = 'portal-nav';
  nav.innerHTML = `<div class="container"><div class="tabs">${NAV.map(([h, l]) => `<a href="${h}"${h === page ? ' aria-current="page"' : ''}>${l}</a>`).join('')}</div></div>`;
  const root = document.getElementById('page'); root.innerHTML = spinner();
  try { await render(root, me); } catch (e) { root.innerHTML = errorBox(errMsg(e)); }
}

function apptCard(a, onChange) {
  const d = parseISO(a.start_at);
  const el = document.createElement('article');
  el.className = 'card appt-card';
  el.innerHTML = `<div class="appt-when"><div class="appt-date"><b>${String(d.getDate()).padStart(2, '0')}</b><span>${d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '')}</span></div>
    <div class="grow"><strong>${esc(a.procedure_name)}</strong><div class="muted small">${fmtTime(a.start_at)} – ${fmtTime(a.end_at)} · ${esc(a.professional_name)}</div></div>${statusBadge(a.status)}</div>
    ${a.cancel_reason ? `<p class="small muted" style="margin:0">Motivo: ${esc(a.cancel_reason)}</p>` : ''}
    ${a.status === 'pendente' ? '<p class="small muted" style="margin:0">Aguardando aprovação da clínica.</p>' : ''}
    ${['pendente', 'confirmado'].includes(a.status) ? `<div class="appt-actions">
      <button class="btn btn-sm btn-outline" data-act="resched" ${a.can_reschedule ? '' : 'disabled title="Fora do prazo de antecedência da clínica"'}>Reagendar</button>
      <button class="btn btn-sm btn-ghost" data-act="cancel" ${a.can_cancel ? '' : 'disabled title="Fora do prazo de antecedência da clínica"'}>Cancelar</button>
      ${!a.can_cancel ? '<span class="small muted">Prazo de alteração encerrado — fale com a clínica.</span>' : ''}</div>` : ''}`;
  el.querySelector('[data-act="cancel"]')?.addEventListener('click', async () => {
    if (!(await confirmDialog('Deseja cancelar esta consulta? O horário será liberado.', { title: 'Cancelar consulta', confirmText: 'Cancelar consulta', danger: true }))) return;
    try { await api(`/agendamentos/${a.id}/cancelar`, { method: 'POST', body: {} }); toast('Consulta cancelada.', 'success'); onChange(); } catch (e) { toast(errMsg(e), 'error'); }
  });
  el.querySelector('[data-act="resched"]')?.addEventListener('click', () => reschedule(a, onChange));
  return el;
}

function reschedule(a, onChange) {
  const m = openModal({ title: 'Reagendar consulta', body: `<p class="muted small">${esc(a.procedure_name)} com ${esc(a.professional_name)}. A nova data volta para aprovação da clínica, se a confirmação for manual.</p><div id="pk"></div><div class="alert alert-danger mt" id="err" role="alert" hidden></div>`,
    footer: '<button class="btn btn-ghost" data-close>Voltar</button><button class="btn" id="ok" disabled>Confirmar novo horário</button>' });
  const ok = m.dlg.querySelector('#ok'), err = m.dlg.querySelector('#err'); let sel = null;
  slotPicker(m.dlg.querySelector('#pk'), { procedureId: a.procedure_id, professionalId: a.professional_id, excludeId: a.id, onChange: (s) => { sel = s; ok.disabled = !s; } });
  ok.addEventListener('click', async () => {
    err.hidden = true; setLoading(ok, true);
    try { await api(`/agendamentos/${a.id}/reagendar`, { method: 'POST', body: { start_at: sel.start, professional_id: sel.professional_id } }); m.close(); toast('Consulta reagendada.', 'success'); onChange(); }
    catch (e) { err.textContent = errMsg(e); err.hidden = false; setLoading(ok, false); }
  });
}

export function renderDashboard(root, me) {
  return (async () => {
    const [list, patient] = await Promise.all([api('/agendamentos'), api('/pacientes/me')]);
    const now = new Date();
    const upcoming = list.filter((a) => parseISO(a.start_at) >= now && ['pendente', 'confirmado'].includes(a.status));
    const pending = list.filter((a) => a.status === 'pendente');
    root.innerHTML = `<h1 style="font-size:clamp(1.5rem,4vw,2rem)">Olá, ${esc(patient.full_name.split(' ')[0])}!</h1>
      <div class="stats cols-3 mb" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
        <div class="stat"><span class="stat-icon">${icon('calendar')}</span><div><div class="stat-value">${upcoming.length}</div><div class="stat-label">Próximas consultas</div></div></div>
        <div class="stat"><span class="stat-icon warn">${icon('clock')}</span><div><div class="stat-value">${pending.length}</div><div class="stat-label">Aguardando aprovação</div></div></div>
        <div class="stat"><span class="stat-icon green">${icon('check')}</span><div><div class="stat-value">${list.filter((a) => a.status === 'concluido').length}</div><div class="stat-label">Concluídas</div></div></div></div>
      <div class="row between mb"><h2 style="font-size:1.2rem;margin:0">Próximas consultas</h2><a class="btn" href="/agendamento.html">${icon('plus', 18)} Nova consulta</a></div><div class="stack" id="up"></div>`;
    const up = root.querySelector('#up');
    if (!upcoming.length) up.innerHTML = `<div class="card">${empty('Você não tem consultas agendadas', 'Que tal marcar uma avaliação?', 'calendar')}</div>`;
    else upcoming.slice(0, 5).forEach((a) => up.appendChild(apptCard(a, () => bootRefresh())));
  })();
}
const bootRefresh = () => location.reload();

export function renderAppointments(root) {
  return (async () => {
    const list = await api('/agendamentos');
    const now = new Date();
    const groups = { proximas: list.filter((a) => parseISO(a.start_at) >= now && ['pendente', 'confirmado', 'em_atendimento'].includes(a.status)),
      historico: list.filter((a) => !(parseISO(a.start_at) >= now && ['pendente', 'confirmado', 'em_atendimento'].includes(a.status))).reverse(), todas: [...list].reverse() };
    let tab = 'proximas';
    root.innerHTML = `<div class="row between mb"><h1 style="font-size:clamp(1.5rem,4vw,2rem);margin:0">Meus agendamentos</h1><a class="btn" href="/agendamento.html">${icon('plus', 18)} Nova consulta</a></div>
      <div class="tabs mb" role="tablist">${[['proximas', 'Próximas'], ['historico', 'Histórico'], ['todas', 'Todas']].map(([k, l]) => `<button class="tab" role="tab" data-t="${k}">${l}</button>`).join('')}</div><div class="stack" id="items"></div>`;
    const items = root.querySelector('#items');
    const draw = () => {
      root.querySelectorAll('.tab').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.t === tab)));
      items.innerHTML = ''; const l = groups[tab];
      if (!l.length) items.innerHTML = `<div class="card">${empty('Nada por aqui', tab === 'proximas' ? 'Você não tem consultas futuras.' : 'Nenhum registro.', 'calendar')}</div>`;
      l.forEach((a) => items.appendChild(apptCard(a, bootRefresh)));
    };
    root.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => { tab = b.dataset.t; draw(); }));
    draw();
  })();
}

export function renderProfile(root, me) {
  return (async () => {
    const p = await api('/pacientes/me');
    root.innerHTML = `<h1 style="font-size:clamp(1.5rem,4vw,2rem)">Meus dados</h1><div class="grid-2" style="display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr))">
      <section class="card"><h2 class="card-title">Dados cadastrais</h2>
        <dl class="kv"><div><dt>Nome</dt><dd>${esc(p.full_name)}</dd></div><div><dt>CPF</dt><dd>${esc(fmtCPF(p.cpf))}</dd></div><div><dt>Nascimento</dt><dd>${fmtDate(p.birth_date)} (${p.age} anos)</dd></div><div><dt>E-mail</dt><dd>${esc(p.email)}</dd></div></dl>
        <p class="small muted mt">Para alterar nome, CPF, nascimento ou e-mail, procure a clínica.</p>
        <form id="pf" class="mt" novalidate><div class="alert alert-danger mb" id="pfErr" role="alert" hidden></div><div class="form-grid">
          <div class="field"><label for="phone">Telefone</label><input id="phone" name="phone" data-mask="phone" value="${esc(fmtPhone(p.phone))}" required><span class="field-error" data-err="phone" role="alert"></span></div>
          <div class="field"><label for="address">Endereço</label><input id="address" name="address" value="${esc(p.address)}" required maxlength="255"><span class="field-error" data-err="address" role="alert"></span></div></div>
          <button class="btn mt" type="submit" id="pfBtn">Salvar alterações</button></form></section>
      <section class="card"><h2 class="card-title">Alterar senha</h2>
        <form id="pw" novalidate><div class="alert alert-danger mb" id="pwErr" role="alert" hidden></div><div class="form-grid">
          <div class="field"><label for="cur">Senha atual</label><input id="cur" name="current_password" type="password" autocomplete="current-password" required></div>
          <div class="field"><label for="new">Nova senha</label><input id="new" name="new_password" type="password" autocomplete="new-password" required><span class="field-help">Mínimo de 8 caracteres, com letras e números.</span><span class="field-error" data-err="new_password" role="alert"></span></div></div>
          <button class="btn mt" type="submit" id="pwBtn">Alterar senha</button></form>
        <hr style="border:0;border-top:1px solid var(--line);margin:1.4rem 0"><h2 class="card-title">${icon('shield', 18)} Privacidade (LGPD)</h2>
        <p class="small muted">Seus dados são usados apenas para cadastro, agendamento e atendimento. Dados de saúde só são acessados pelos profissionais responsáveis, com registro de acesso.</p></section></div>`;
    applyMasks(root);
    const form = root.querySelector('#pf'), err = root.querySelector('#pfErr'), btn = root.querySelector('#pfBtn');
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); err.hidden = true; setLoading(btn, true);
      try { await api('/pacientes/me', { method: 'PUT', body: { phone: form.elements.phone.value, address: form.elements.address.value.trim() } }); showFieldErrors(form, { errors: [] }); toast('Dados atualizados.', 'success'); }
      catch (x) { showFieldErrors(form, x); err.textContent = errMsg(x); err.hidden = false; } finally { setLoading(btn, false); }
    });
    const pw = root.querySelector('#pw'), pwErr = root.querySelector('#pwErr'), pwBtn = root.querySelector('#pwBtn');
    pw.addEventListener('submit', async (e) => {
      e.preventDefault(); pwErr.hidden = true; setLoading(pwBtn, true);
      try { await api('/auth/senha', { method: 'POST', body: { current_password: pw.elements.current_password.value, new_password: pw.elements.new_password.value } }); pw.reset(); toast('Senha alterada com sucesso.', 'success'); }
      catch (x) { showFieldErrors(pw, x); pwErr.textContent = errMsg(x); pwErr.hidden = false; } finally { setLoading(pwBtn, false); }
    });
  })();
}
