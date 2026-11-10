import { api } from './api.js';
import { mountShell } from './layout.js';
import { confirmDialog, debounce, empty, errMsg, errorBox, esc, fmtCPF, fmtDate, fmtDateTime, fmtPhone, icon, modalForm, openModal, spinner, statusBadge, table, toast } from './ui.js';

const shell = await mountShell({ active: 'pacientes', title: 'Pacientes' });
if (shell) main(shell);

const FIELDS = [
  { name: 'full_name', label: 'Nome completo', required: true, full: true, maxlength: 150 },
  { name: 'cpf', label: 'CPF', required: true, mask: 'cpf' }, { name: 'birth_date', label: 'Data de nascimento', type: 'date', required: true },
  { name: 'phone', label: 'Telefone', type: 'tel', required: true, mask: 'phone' }, { name: 'email', label: 'E-mail', type: 'email', required: true },
  { name: 'address', label: 'Endereço', required: true, full: true, maxlength: 255 },
];

function main({ me, content }) {
  const canEdit = ['admin', 'recepcionista'].includes(me.role), canClinical = ['admin', 'dentista'].includes(me.role), isAdmin = me.role === 'admin';
  let q = '', page = 1; const limit = 20;
  content.innerHTML = `<div class="page-head"><h2>Pacientes</h2>${canEdit ? `<button class="btn" id="add">${icon('plus', 18)} Novo paciente</button>` : ''}</div>
    <div class="toolbar"><div class="field"><label for="q">Buscar por nome ou CPF</label><input id="q" type="search" placeholder="Ex.: Maria ou 123.456"></div></div><div id="list">${spinner()}</div><div class="pager" id="pager"></div>`;
  const list = content.querySelector('#list'), pager = content.querySelector('#pager');
  content.querySelector('#q').addEventListener('input', debounce((e) => { q = e.target.value; page = 1; load(); }, 300));
  content.querySelector('#add')?.addEventListener('click', () => form());

  async function load() {
    try {
      const r = await api('/pacientes', { params: { q, limite: limit, pagina: page } });
      list.innerHTML = table([
        { label: 'Nome', strong: true, render: (p) => esc(p.full_name) }, { label: 'CPF', render: (p) => esc(fmtCPF(p.cpf)) }, { label: 'Idade', render: (p) => `${p.age} anos` },
        { label: 'Telefone', render: (p) => esc(fmtPhone(p.phone)) }, { label: 'E-mail', render: (p) => esc(p.email) },
        { label: 'Ações', actions: true, render: (p) => `<button class="btn btn-sm btn-outline" data-act="ficha" data-id="${p.id}">Ficha</button>${canEdit ? `<button class="btn btn-sm btn-ghost" data-act="edit" data-id="${p.id}" aria-label="Editar ${esc(p.full_name)}">${icon('edit', 16)}</button>` : ''}${isAdmin ? `<button class="btn btn-sm btn-ghost" data-act="del" data-id="${p.id}" aria-label="Excluir ${esc(p.full_name)}">${icon('trash', 16)}</button>` : ''}` }],
        r.items, empty(q ? 'Nenhum paciente encontrado' : 'Nenhum paciente cadastrado', q ? 'Tente outro nome ou CPF.' : 'Cadastre o primeiro paciente.', 'users'));
      list.dataset.items = JSON.stringify(r.items);
      const pages = Math.max(1, Math.ceil(r.total / limit));
      pager.innerHTML = r.total > limit ? `<button class="btn btn-outline btn-sm" id="prev" ${page <= 1 ? 'disabled' : ''}>${icon('left', 16)} Anterior</button><span class="small muted">Página ${page} de ${pages} · ${r.total} pacientes</span><button class="btn btn-outline btn-sm" id="next" ${page >= pages ? 'disabled' : ''}>Próxima ${icon('right', 16)}</button>` : `<span class="small muted">${r.total} paciente(s)</span>`;
      pager.querySelector('#prev')?.addEventListener('click', () => { page--; load(); }); pager.querySelector('#next')?.addEventListener('click', () => { page++; load(); });
    } catch (e) { list.innerHTML = errorBox(errMsg(e)); }
  }
  const find = (id) => JSON.parse(list.dataset.items || '[]').find((p) => p.id === Number(id));

  list.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-act]'); if (!b) return; const p = find(b.dataset.id);
    if (b.dataset.act === 'edit') form(p);
    if (b.dataset.act === 'ficha') ficha(p);
    if (b.dataset.act === 'del' && await confirmDialog(`Excluir o cadastro de ${p.full_name}? O histórico será preservado, mas o paciente perderá o acesso.`, { title: 'Excluir paciente', confirmText: 'Excluir', danger: true })) {
      try { await api(`/pacientes/${p.id}`, { method: 'DELETE' }); toast('Paciente excluído.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); }
    }
  });

  function form(p) {
    modalForm({ title: p ? 'Editar paciente' : 'Novo paciente', fields: FIELDS, values: p ? { ...p, cpf: fmtCPF(p.cpf), phone: fmtPhone(p.phone) } : {}, wide: true,
      onSubmit: async (v, m) => { await api(p ? `/pacientes/${p.id}` : '/pacientes', { method: p ? 'PUT' : 'POST', body: v }); m.close(); toast(p ? 'Paciente atualizado.' : 'Paciente cadastrado.', 'success'); load(); } });
  }

  async function ficha(p) {
    const m = openModal({ title: p.full_name, wide: true, body: spinner() });
    try {
      const h = await api(`/pacientes/${p.id}/agendamentos`);
      const cols = [{ label: 'Data', strong: true, render: (a) => fmtDateTime(a.start_at) }, { label: 'Procedimento', render: (a) => esc(a.procedure_name) }, { label: 'Profissional', render: (a) => esc(a.professional_name) }, { label: 'Status', render: (a) => statusBadge(a.status) }];
      m.body.innerHTML = `<h4 class="card-title">Dados pessoais</h4><dl class="kv"><div><dt>CPF</dt><dd>${esc(fmtCPF(p.cpf))}</dd></div><div><dt>Nascimento</dt><dd>${fmtDate(p.birth_date)} · ${p.age} anos</dd></div>
        <div><dt>Telefone</dt><dd>${esc(fmtPhone(p.phone))}</dd></div><div><dt>E-mail</dt><dd>${esc(p.email)}</dd></div><div><dt>Endereço</dt><dd>${esc(p.address)}</dd></div><div><dt>Acesso ao portal</dt><dd>${p.has_account ? 'Sim' : 'Não'}</dd></div></dl>
        <h4 class="card-title mt-2">Agendamentos futuros</h4>${table(cols, h.futuros, empty('Sem agendamentos futuros', '', 'calendar'))}
        <h4 class="card-title mt-2">Histórico de consultas</h4>${table(cols, h.historico, empty('Sem histórico', '', 'clock'))}
        ${canClinical ? `<h4 class="card-title mt-2">${icon('lock', 18)} Informações clínicas</h4><p class="small muted">Dados sensíveis de saúde. O acesso é restrito e fica registrado em auditoria.</p><button class="btn btn-outline" id="pront">Abrir prontuário</button><div id="prontBox" class="mt"></div>` : ''}`;
      m.body.querySelector('#pront')?.addEventListener('click', async (e) => {
        const box = m.body.querySelector('#prontBox'); box.innerHTML = spinner(); e.target.hidden = true;
        try {
          const r = await api(`/pacientes/${p.id}/prontuario`);
          box.innerHTML = r.records.length ? r.records.map((x) => `<div class="card card-flat mb"><div class="small muted">${fmtDateTime(x.created_at)} · ${esc(x.professional_name)}</div><p style="margin:.4rem 0 0;white-space:pre-wrap">${esc(x.content)}</p></div>`).join('') : empty('Nenhum registro clínico', '', 'file');
        } catch (er) { box.innerHTML = errorBox(errMsg(er)); }
      });
    } catch (e) { m.body.innerHTML = errorBox(errMsg(e)); }
  }
  load();
}
