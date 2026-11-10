import { api } from './api.js';
import { mountShell } from './layout.js';
import { WEEKDAYS, applyMasks, empty, errMsg, errorBox, esc, fmtDateTime, fmtPhone, icon, modalForm, setLoading, showFieldErrors, spinner, table, toast } from './ui.js';

const shell = await mountShell({ active: 'configuracoes', title: 'Configurações', roles: ['admin'] });
if (shell) main(shell);

const ROLE = { admin: 'Administrador', recepcionista: 'Recepcionista', dentista: 'Dentista' };

async function main({ me, content }) {
  content.innerHTML = spinner();
  let cfg; try { cfg = await api('/configuracoes'); } catch (e) { content.innerHTML = errorBox(errMsg(e)); return; }
  content.innerHTML = `<div class="page-head"><h2>Configurações da clínica</h2></div>
    <form class="card" id="cf" novalidate><div class="alert alert-danger mb" id="err" role="alert" hidden></div><div class="form-grid cols-2">
      <div class="field full"><label for="name">Nome da clínica <span class="req">*</span></label><input id="name" name="name" value="${esc(cfg.name)}" required maxlength="150"><span class="field-error" data-err="name" role="alert"></span></div>
      <div class="field full"><label for="address">Endereço</label><input id="address" name="address" value="${esc(cfg.address)}" maxlength="255"><span class="field-error" data-err="address" role="alert"></span></div>
      <div class="field"><label for="phone">Telefone</label><input id="phone" name="phone" data-mask="phone" value="${esc(fmtPhone(cfg.phone))}"><span class="field-error" data-err="phone" role="alert"></span></div>
      <div class="field"><label for="email">E-mail</label><input id="email" name="email" type="email" value="${esc(cfg.email)}"><span class="field-error" data-err="email" role="alert"></span></div>
      <div class="field full"><label for="opening_hours">Horários de funcionamento (texto exibido no site)</label><input id="opening_hours" name="opening_hours" value="${esc(cfg.opening_hours)}" maxlength="255"></div>
      <div class="field full"><span class="label">Dias de atendimento</span><div class="row">${WEEKDAYS.map((d, i) => `<label class="check"><input type="checkbox" name="wd" value="${i}" ${cfg.working_days.includes(i) ? 'checked' : ''}> <span>${d.slice(0, 3)}</span></label>`).join('')}</div><span class="field-error" data-err="working_days" role="alert"></span></div>
      <div class="field"><label for="slot_minutes">Duração padrão dos horários</label><select id="slot_minutes" name="slot_minutes">${[10, 15, 20, 30, 40, 45, 60].map((m) => `<option value="${m}" ${m === cfg.slot_minutes ? 'selected' : ''}>${m} minutos</option>`).join('')}</select><span class="field-help">Intervalo entre os horários oferecidos.</span></div>
      <div class="field"><label for="cancel_min_hours">Antecedência para cancelar/reagendar (horas)</label><input id="cancel_min_hours" name="cancel_min_hours" type="number" min="0" max="720" value="${cfg.cancel_min_hours}"><span class="field-error" data-err="cancel_min_hours" role="alert"></span></div>
      <div class="field"><label for="max_advance_days">Agendar com até (dias de antecedência)</label><input id="max_advance_days" name="max_advance_days" type="number" min="1" max="365" value="${cfg.max_advance_days}"><span class="field-error" data-err="max_advance_days" role="alert"></span></div>
      <div class="field"><span class="label">Confirmação de agendamentos</span><label class="check"><input type="checkbox" name="auto_confirm" ${cfg.auto_confirm ? 'checked' : ''}> <span>Confirmar automaticamente as solicitações dos pacientes</span></label><span class="field-help">Desmarcado: a recepção aprova manualmente.</span></div>
      <div class="field full"><label for="policy_text">Políticas de agendamento e cancelamento (exibidas ao paciente)</label><textarea id="policy_text" name="policy_text" maxlength="3000">${esc(cfg.policy_text)}</textarea></div></div>
      <button class="btn mt" type="submit" id="save">Salvar configurações</button></form>
    <section class="card mt"><h3 class="card-title">Logotipo</h3><div class="row"><span class="brand-mark" style="width:64px;height:64px" id="logoPrev">${cfg.logo_url ? `<img src="${esc(cfg.logo_url)}" alt="Logotipo atual">` : icon('tooth', 30)}</span>
      <input type="file" id="logo" accept="image/png,image/jpeg,image/webp" aria-label="Escolher logotipo"><button class="btn btn-outline" id="upl">Enviar logotipo</button></div><p class="small muted mt">PNG, JPG ou WEBP até 2 MB.</p></section>
    <section class="card mt"><div class="row between mb"><h3 class="card-title" style="margin:0">Usuários do painel</h3><button class="btn btn-sm" id="addUser">${icon('plus', 16)} Novo usuário</button></div><div id="users">${spinner()}</div></section>`;
  const form = content.querySelector('#cf'), err = content.querySelector('#err'), save = content.querySelector('#save');
  applyMasks(form);
  form.addEventListener('submit', async (e) => {
    e.preventDefault(); err.hidden = true; setLoading(save, true);
    try {
      const out = await api('/configuracoes', { method: 'PUT', body: { name: form.elements.name.value, address: form.elements.address.value, phone: form.elements.phone.value, email: form.elements.email.value, opening_hours: form.elements.opening_hours.value,
        working_days: [...form.querySelectorAll('[name=wd]:checked')].map((c) => Number(c.value)), slot_minutes: Number(form.elements.slot_minutes.value), cancel_min_hours: Number(form.elements.cancel_min_hours.value),
        max_advance_days: Number(form.elements.max_advance_days.value), auto_confirm: form.elements.auto_confirm.checked, policy_text: form.elements.policy_text.value } });
      cfg = out; showFieldErrors(form, { errors: [] }); toast('Configurações salvas.', 'success');
    } catch (x) { showFieldErrors(form, x); err.textContent = errMsg(x); err.hidden = false; err.scrollIntoView({ block: 'center', behavior: 'smooth' }); } finally { setLoading(save, false); }
  });
  content.querySelector('#upl').addEventListener('click', async (e) => {
    const file = content.querySelector('#logo').files[0]; if (!file) { toast('Escolha uma imagem primeiro.', 'error'); return; }
    const fd = new FormData(); fd.append('file', file); setLoading(e.currentTarget, true);
    try { const out = await api('/configuracoes/logo', { method: 'POST', formData: fd }); content.querySelector('#logoPrev').innerHTML = `<img src="${esc(out.logo_url)}" alt="Logotipo atual">`; toast('Logotipo atualizado.', 'success'); } catch (x) { toast(errMsg(x), 'error'); } finally { setLoading(e.currentTarget, false); }
  });

  const box = content.querySelector('#users');
  async function loadUsers() {
    try {
      const us = await api('/usuarios');
      box.innerHTML = table([{ label: 'Nome', strong: true, render: (u) => esc(u.full_name) }, { label: 'E-mail', render: (u) => esc(u.email) }, { label: 'Perfil', render: (u) => ROLE[u.role] }, { label: 'Último acesso', render: (u) => (u.last_login_at ? fmtDateTime(u.last_login_at) : 'Nunca') },
        { label: 'Situação', render: (u) => (u.is_active ? '<span class="badge badge-success">Ativo</span>' : '<span class="badge badge-muted">Inativo</span>') },
        { label: 'Ações', actions: true, render: (u) => u.id === me.id ? '<span class="small muted">Você</span>' : `<button class="btn btn-sm btn-ghost" data-id="${u.id}" data-on="${u.is_active ? 0 : 1}">${u.is_active ? 'Desativar' : 'Ativar'}</button>` }], us, empty('Nenhum usuário', '', 'users'));
      box.querySelectorAll('[data-id]').forEach((b) => b.addEventListener('click', async () => { try { await api(`/usuarios/${b.dataset.id}/status`, { method: 'PATCH', body: { is_active: b.dataset.on === '1' } }); loadUsers(); } catch (x) { toast(errMsg(x), 'error'); } }));
    } catch (x) { box.innerHTML = errorBox(errMsg(x)); }
  }
  content.querySelector('#addUser').addEventListener('click', () => modalForm({ title: 'Novo usuário do painel', fields: [
    { name: 'full_name', label: 'Nome completo', required: true, full: true }, { name: 'email', label: 'E-mail', type: 'email', required: true, full: true },
    { name: 'role', label: 'Perfil', type: 'select', required: true, options: [{ value: 'recepcionista', label: 'Recepcionista' }, { value: 'admin', label: 'Administrador' }] },
    { name: 'password', label: 'Senha inicial', type: 'password', required: true, autocomplete: 'new-password', help: 'Mínimo 8 caracteres, com letras e números.' }],
    onSubmit: async (v, m) => { await api('/usuarios', { method: 'POST', body: v }); m.close(); toast('Usuário criado.', 'success'); loadUsers(); } }));
  loadUsers();
}
