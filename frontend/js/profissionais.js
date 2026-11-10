import { api } from './api.js';
import { mountShell } from './layout.js';
import { WEEKDAYS, confirmDialog, empty, errMsg, errorBox, esc, fmtCPF, fmtDateTime, fmtPhone, icon, modalForm, openModal, setLoading, spinner, table, toast } from './ui.js';

const shell = await mountShell({ active: 'profissionais', title: 'Profissionais', roles: ['admin'] });
if (shell) main(shell);

function main({ content }) {
  content.innerHTML = `<div class="page-head"><h2>Profissionais</h2><button class="btn" id="add">${icon('plus', 18)} Novo profissional</button></div><div id="list">${spinner()}</div>`;
  const list = content.querySelector('#list'); let items = [], procs = [];
  content.querySelector('#add').addEventListener('click', () => form());

  async function load() {
    try {
      [items, procs] = await Promise.all([api('/profissionais'), api('/procedimentos')]);
      list.innerHTML = table([
        { label: 'Nome', strong: true, render: (p) => esc(p.full_name) }, { label: 'CRO', render: (p) => esc(p.cro || '—') }, { label: 'Especialidade', render: (p) => esc(p.specialty) },
        { label: 'Contato', render: (p) => `${esc(fmtPhone(p.phone))}<br><span class="small muted">${esc(p.email)}</span>` },
        { label: 'Atende', render: (p) => p.schedules.length ? p.schedules.map((s) => WEEKDAYS[s.weekday].slice(0, 3)).join(', ') : '<span class="badge badge-warning">Sem horários</span>' },
        { label: 'Procedimentos', render: (p) => p.procedure_ids.length || '<span class="badge badge-warning">Nenhum</span>' },
        { label: 'Situação', render: (p) => p.is_active ? '<span class="badge badge-success">Ativo</span>' : '<span class="badge badge-muted">Inativo</span>' },
        { label: 'Ações', actions: true, render: (p) => `<button class="btn btn-sm btn-outline" data-act="edit" data-id="${p.id}">Editar</button><button class="btn btn-sm btn-outline" data-act="sched" data-id="${p.id}">Horários</button><button class="btn btn-sm btn-ghost" data-act="blocks" data-id="${p.id}">Bloqueios</button><button class="btn btn-sm btn-ghost" data-act="toggle" data-id="${p.id}">${p.is_active ? 'Desativar' : 'Ativar'}</button><button class="btn btn-sm btn-ghost" data-act="del" data-id="${p.id}" aria-label="Excluir ${esc(p.full_name)}">${icon('trash', 16)}</button>` }],
        items, empty('Nenhum profissional cadastrado', 'Cadastre o primeiro profissional.', 'userCheck'));
    } catch (e) { list.innerHTML = errorBox(errMsg(e)); }
  }
  const find = (id) => items.find((p) => p.id === Number(id));
  list.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-act]'); if (!b) return; const p = find(b.dataset.id);
    if (b.dataset.act === 'edit') form(p);
    if (b.dataset.act === 'sched') schedule(p);
    if (b.dataset.act === 'blocks') blocks(p);
    if (b.dataset.act === 'toggle') {
      try { await api(`/profissionais/${p.id}/status`, { method: 'PATCH', body: { is_active: !p.is_active } }); toast(p.is_active ? 'Cadastro desativado.' : 'Cadastro ativado.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); }
    }
    if (b.dataset.act === 'del' && await confirmDialog(`Excluir ${p.full_name}? Com histórico de agendamentos a exclusão é bloqueada: desative o cadastro.`, { title: 'Excluir profissional', confirmText: 'Excluir', danger: true })) {
      try { await api(`/profissionais/${p.id}`, { method: 'DELETE' }); toast('Profissional excluído.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); }
    }
  });

  function form(p) {
    const fields = [
      { name: 'full_name', label: 'Nome completo', required: true, full: true, maxlength: 150 },
      { name: 'cpf', label: 'CPF', required: true, mask: 'cpf' }, { name: 'cro', label: 'CRO (quando aplicável)', maxlength: 20 },
      { name: 'specialty', label: 'Especialidade', required: true, maxlength: 100 }, { name: 'phone', label: 'Telefone', type: 'tel', required: true, mask: 'phone' },
      { name: 'email', label: 'E-mail', type: 'email', required: true, full: true },
      { name: 'procedure_ids', label: 'Procedimentos realizados', type: 'checkboxes', options: procs.map((x) => ({ value: x.id, label: x.name })) },
      ...(p ? [] : [{ name: 'create_account', label: 'Criar acesso ao painel (login do dentista)', type: 'checkbox', full: true },
        { name: 'password', label: 'Senha inicial', type: 'password', autocomplete: 'new-password', help: 'Necessária apenas se criar acesso. Mínimo 8 caracteres, com letras e números.', full: true }]),
    ];
    modalForm({ title: p ? 'Editar profissional' : 'Novo profissional', fields, wide: true, values: p ? { ...p, cpf: fmtCPF(p.cpf), phone: fmtPhone(p.phone) } : { procedure_ids: [] },
      onSubmit: async (v, m) => {
        v.procedure_ids = v.procedure_ids.map(Number); if (!v.cro) v.cro = null;
        if (!p) { if (!v.create_account) delete v.password; else if (!v.password) throw Object.assign(new Error('Informe a senha inicial.'), { errors: [{ field: 'password', message: 'Informe a senha inicial.' }] }); }
        await api(p ? `/profissionais/${p.id}` : '/profissionais', { method: p ? 'PUT' : 'POST', body: v });
        m.close(); toast('Profissional salvo.', 'success'); load();
      } });
  }

  function schedule(p) {
    const by = Object.fromEntries(p.schedules.map((s) => [s.weekday, s]));
    const t = (v) => (v ? v.slice(0, 5) : '');
    const rows = WEEKDAYS.map((d, i) => { const s = by[i]; return `<div class="card card-flat mb" data-day="${i}"><label class="check"><input type="checkbox" name="on" ${s ? 'checked' : ''}> <span>${d}</span></label>
      <div class="form-grid cols-2 mt" style="grid-template-columns:repeat(auto-fit,minmax(120px,1fr))"><div class="field"><label>Início</label><input type="time" name="start" value="${t(s?.start_time) || '08:00'}"></div><div class="field"><label>Fim</label><input type="time" name="end" value="${t(s?.end_time) || '18:00'}"></div>
      <div class="field"><label>Intervalo (início)</label><input type="time" name="bs" value="${t(s?.break_start)}"></div><div class="field"><label>Intervalo (fim)</label><input type="time" name="be" value="${t(s?.break_end)}"></div></div></div>`; }).join('');
    const m = openModal({ title: `Horários — ${p.full_name}`, wide: true, body: `<p class="muted small">Marque os dias de atendimento. O intervalo (almoço) é opcional e não gera horários.</p><div class="alert alert-danger mb" id="err" role="alert" hidden></div>${rows}`,
      footer: '<button class="btn btn-ghost" data-close>Cancelar</button><button class="btn" id="save">Salvar horários</button>' });
    const save = m.dlg.querySelector('#save'), err = m.dlg.querySelector('#err');
    save.addEventListener('click', async () => {
      const body = [...m.dlg.querySelectorAll('[data-day]')].filter((r) => r.querySelector('[name=on]').checked).map((r) => ({
        weekday: Number(r.dataset.day), start_time: r.querySelector('[name=start]').value, end_time: r.querySelector('[name=end]').value,
        break_start: r.querySelector('[name=bs]').value || null, break_end: r.querySelector('[name=be]').value || null }));
      err.hidden = true; setLoading(save, true);
      try { await api(`/profissionais/${p.id}/horarios`, { method: 'PUT', body }); m.close(); toast('Horários salvos.', 'success'); load(); }
      catch (e) { err.textContent = errMsg(e); err.hidden = false; setLoading(save, false); }
    });
  }

  async function blocks(p) {
    const m = openModal({ title: `Bloqueios de agenda — ${p.full_name}`, wide: true, body: spinner() });
    async function draw() {
      try {
        const bl = await api(`/profissionais/${p.id}/bloqueios`);
        m.body.innerHTML = `<p class="muted small">Períodos em que o profissional não atende (férias, feriados, reuniões). Os horários somem do agendamento.</p>
          ${table([{ label: 'Início', render: (b) => fmtDateTime(b.start_at) }, { label: 'Fim', render: (b) => fmtDateTime(b.end_at) }, { label: 'Motivo', render: (b) => esc(b.reason || '—') },
            { label: 'Ações', actions: true, render: (b) => `<button class="btn btn-sm btn-ghost" data-del="${b.id}" aria-label="Remover bloqueio">${icon('trash', 16)}</button>` }], bl, empty('Nenhum bloqueio futuro', '', 'calendar'))}
          <h4 class="card-title mt-2">Novo bloqueio</h4><div class="alert alert-danger mb" id="berr" role="alert" hidden></div>
          <form id="bf" class="form-grid cols-2" novalidate><div class="field"><label for="bs">Início</label><input id="bs" type="datetime-local" required></div><div class="field"><label for="be">Fim</label><input id="be" type="datetime-local" required></div>
          <div class="field full"><label for="br">Motivo</label><input id="br" maxlength="200"></div><div class="full"><button class="btn" type="submit" id="bsave">Adicionar bloqueio</button></div></form>`;
        m.body.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', async () => { try { await api(`/profissionais/${p.id}/bloqueios/${b.dataset.del}`, { method: 'DELETE' }); draw(); } catch (e) { toast(errMsg(e), 'error'); } }));
        const bf = m.body.querySelector('#bf'), berr = m.body.querySelector('#berr');
        bf.addEventListener('submit', async (e) => {
          e.preventDefault(); berr.hidden = true; const btn = m.body.querySelector('#bsave'); setLoading(btn, true);
          try { await api(`/profissionais/${p.id}/bloqueios`, { method: 'POST', body: { start_at: bf.elements.bs.value, end_at: bf.elements.be.value, reason: bf.elements.br.value } }); toast('Bloqueio criado.', 'success'); draw(); }
          catch (er) { berr.textContent = errMsg(er); berr.hidden = false; setLoading(btn, false); }
        });
      } catch (e) { m.body.innerHTML = errorBox(errMsg(e)); }
    }
    draw();
  }
  load();
}
