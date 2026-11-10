import { api } from './api.js';
import { mountShell } from './layout.js';
import { CATEGORY, confirmDialog, empty, errMsg, errorBox, esc, fmtMoney, icon, modalForm, spinner, table, toast } from './ui.js';

const shell = await mountShell({ active: 'procedimentos', title: 'Procedimentos', roles: ['admin'] });
if (shell) main(shell);

function main({ content }) {
  content.innerHTML = `<div class="page-head"><h2>Procedimentos</h2><button class="btn" id="add">${icon('plus', 18)} Novo procedimento</button></div>
    <p class="muted small">As alterações feitas aqui aparecem imediatamente no portal do paciente. Procedimentos desativados deixam de ser exibidos e não podem ser agendados.</p><div id="list">${spinner()}</div>`;
  const list = content.querySelector('#list'); let items = [], pros = [];
  content.querySelector('#add').addEventListener('click', () => form());

  async function load() {
    try {
      [items, pros] = await Promise.all([api('/procedimentos'), api('/profissionais', { params: { incluir_inativos: false } })]);
      list.innerHTML = table([
        { label: 'Imagem', render: (p) => p.image_url ? `<img class="thumb" src="${esc(p.image_url)}" alt="">` : `<span class="thumb">${icon(CATEGORY[p.category].icon, 20)}</span>` },
        { label: 'Procedimento', strong: true, render: (p) => esc(p.name) }, { label: 'Categoria', render: (p) => esc(CATEGORY[p.category].label) },
        { label: 'Duração', render: (p) => `${p.duration_minutes} min` }, { label: 'Valor', render: (p) => fmtMoney(p.price) },
        { label: 'Profissionais', render: (p) => p.professionals_count || '<span class="badge badge-warning">Nenhum</span>' },
        { label: 'Situação', render: (p) => p.is_active ? '<span class="badge badge-success">Ativo</span>' : '<span class="badge badge-muted">Desativado</span>' },
        { label: 'Ações', actions: true, render: (p) => `<button class="btn btn-sm btn-outline" data-act="edit" data-id="${p.id}">Editar</button><button class="btn btn-sm btn-ghost" data-act="toggle" data-id="${p.id}">${p.is_active ? 'Desativar' : 'Ativar'}</button><button class="btn btn-sm btn-ghost" data-act="del" data-id="${p.id}" aria-label="Excluir ${esc(p.name)}">${icon('trash', 16)}</button>` }],
        items, empty('Nenhum procedimento cadastrado', 'Cadastre o primeiro procedimento.', 'clipboard'));
    } catch (e) { list.innerHTML = errorBox(errMsg(e)); }
  }
  const find = (id) => items.find((p) => p.id === Number(id));
  const body = (p, over = {}) => ({ name: p.name, category: p.category, description: p.description, guidance: p.guidance, duration_minutes: p.duration_minutes, price: Number(p.price), is_active: p.is_active, professional_ids: p.professional_ids.map(Number), ...over });

  list.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-act]'); if (!b) return; const p = find(b.dataset.id);
    if (b.dataset.act === 'edit') form(p);
    if (b.dataset.act === 'toggle') {
      try { await api(`/procedimentos/${p.id}`, { method: 'PUT', body: body(p, { is_active: !p.is_active }) }); toast(p.is_active ? 'Procedimento desativado.' : 'Procedimento ativado.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); }
    }
    if (b.dataset.act === 'del' && await confirmDialog(`Excluir "${p.name}"? Se houver histórico de agendamentos, a exclusão é bloqueada e você deve desativá-lo.`, { title: 'Excluir procedimento', confirmText: 'Excluir', danger: true })) {
      try { await api(`/procedimentos/${p.id}`, { method: 'DELETE' }); toast('Procedimento excluído.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); }
    }
  });

  function form(p) {
    const fields = [
      { name: 'name', label: 'Nome', required: true, full: true, maxlength: 120 },
      { name: 'category', label: 'Categoria', type: 'select', required: true, options: Object.entries(CATEGORY).map(([value, c]) => ({ value, label: c.label })) },
      { name: 'duration_minutes', label: 'Duração estimada (min)', type: 'number', required: true, min: 5, max: 480, step: 5 },
      { name: 'price', label: 'Valor (R$)', type: 'number', required: true, min: 0, step: '0.01' },
      { name: 'is_active', label: 'Disponível para agendamento', type: 'checkbox' },
      { name: 'description', label: 'Descrição', type: 'textarea', full: true, maxlength: 2000 },
      { name: 'guidance', label: 'Orientações ao paciente', type: 'textarea', full: true, maxlength: 2000 },
      { name: 'image', label: 'Imagem ilustrativa (PNG, JPG ou WEBP até 2 MB)', type: 'file', full: true },
      { name: 'professional_ids', label: 'Profissionais habilitados', type: 'checkboxes', options: pros.map((x) => ({ value: x.id, label: x.full_name })) },
    ];
    modalForm({ title: p ? 'Editar procedimento' : 'Novo procedimento', fields, wide: true, values: p ? { ...p, price: Number(p.price) } : { is_active: true, duration_minutes: 30, price: 0, category: 'geral', professional_ids: [] },
      onSubmit: async (v, m) => {
        const { image, ...rest } = v; rest.professional_ids = rest.professional_ids.map(Number); if (rest.price === null) rest.price = 0;
        const saved = await api(p ? `/procedimentos/${p.id}` : '/procedimentos', { method: p ? 'PUT' : 'POST', body: rest });
        if (image) { const fd = new FormData(); fd.append('file', image); try { await api(`/procedimentos/${saved.id}/imagem`, { method: 'POST', formData: fd }); } catch (e) { toast('Salvo, mas a imagem não foi enviada: ' + errMsg(e), 'error'); } }
        m.close(); toast('Procedimento salvo.', 'success'); load();
      } });
  }
  load();
}
