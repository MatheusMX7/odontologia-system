import { api } from './api.js';
import { mountShell } from './layout.js';
import { patientPicker } from './pickers.js';
import { METHODS, debounce, empty, errMsg, errorBox, esc, fmtDate, fmtMoney, icon, modalForm, openModal, payBadge, setLoading, spinner, table, toISODate, toast, confirmDialog } from './ui.js';
import { barChart } from './charts.js';

const shell = await mountShell({ active: 'financeiro', title: 'Financeiro', roles: ['admin'] });
if (shell) main(shell);

function main({ content }) {
  const now = new Date(), f = { inicio: toISODate(new Date(now.getFullYear(), now.getMonth(), 1)), fim: toISODate(now), situacao: '', q: '' };
  let procs = [];
  const methodOpts = Object.entries(METHODS).filter(([k]) => k !== 'outro').map(([value, label]) => ({ value, label }));
  content.innerHTML = `<div class="page-head"><h2>Financeiro</h2><button class="btn" id="add">${icon('plus', 18)} Registrar pagamento</button></div>
    <div class="card mb"><div class="toolbar cols-4" id="flt"><div class="field"><label for="i">De</label><input id="i" type="date" value="${f.inicio}"></div><div class="field"><label for="d">Até</label><input id="d" type="date" value="${f.fim}"></div>
      <div class="field"><label for="s">Situação</label><select id="s"><option value="">Todas</option><option value="pendente">Pendente</option><option value="pago">Pago</option><option value="cancelado">Cancelado</option></select></div>
      <div class="field"><label for="q">Paciente</label><input id="q" type="search" placeholder="Buscar pelo nome"></div></div></div><div id="body">${spinner()}</div>`;
  const body = content.querySelector('#body');
  const upd = debounce(() => { f.inicio = content.querySelector('#i').value; f.fim = content.querySelector('#d').value; f.situacao = content.querySelector('#s').value; f.q = content.querySelector('#q').value.trim(); load(); }, 300);
  content.querySelector('#flt').addEventListener('input', upd); content.querySelector('#flt').addEventListener('change', upd);
  content.querySelector('#add').addEventListener('click', () => create());

  async function load() {
    body.innerHTML = spinner();
    try {
      const [sum, pays, pr] = await Promise.all([api('/financeiro/resumo', { params: { inicio: f.inicio, fim: f.fim } }), api('/financeiro/pagamentos', { params: { inicio: f.inicio, fim: f.fim, situacao: f.situacao, q: f.q } }), api('/procedimentos')]);
      procs = pr;
      body.innerHTML = `<div class="stats cols-3 mb"><div class="stat"><span class="stat-icon green">${icon('dollar')}</span><div><div class="stat-value">${fmtMoney(sum.received)}</div><div class="stat-label">Recebido no período (${sum.paid_count} pagamentos)</div></div></div>
        <div class="stat"><span class="stat-icon warn">${icon('clock')}</span><div><div class="stat-value">${fmtMoney(sum.pending)}</div><div class="stat-label">Pendente (criado no período)</div></div></div></div>
        <div class="grid-2 mb"><section class="card"><h3 class="card-title">Receita por período</h3><div id="rev"></div></section>
        <section class="card"><h3 class="card-title">Receita por forma de pagamento</h3>${sum.by_method.length ? sum.by_method.map((m) => `<div class="row between" style="padding:.4rem 0;border-bottom:1px solid var(--line)"><span>${esc(METHODS[m.method] || m.method)}</span><strong>${fmtMoney(m.total)}</strong></div>`).join('') : empty('Sem recebimentos', '', 'dollar')}</section></div>
        <h3 class="card-title">Pagamentos</h3><div id="pays"></div>
        <section class="card mt-2"><h3 class="card-title">Valores por procedimento</h3><p class="small muted">Defina os valores em Procedimentos. O valor é usado ao gerar a cobrança ao finalizar um atendimento.</p>${table([{ label: 'Procedimento', strong: true, render: (p) => esc(p.name) }, { label: 'Valor', render: (p) => fmtMoney(p.price) }, { label: 'Situação', render: (p) => (p.is_active ? 'Ativo' : 'Desativado') }], procs, empty('Sem procedimentos'))}</section>`;
      barChart(body.querySelector('#rev'), sum.revenue_series.labels, sum.revenue_series.values, { color: '#168a4a', fmt: (v) => 'R$ ' + Math.round(v) });
      const pe = body.querySelector('#pays');
      pe.innerHTML = table([{ label: 'Data', strong: true, render: (p) => fmtDate(p.created_at.slice(0, 10)) }, { label: 'Paciente', render: (p) => esc(p.patient_name) }, { label: 'Procedimento', render: (p) => esc(p.procedure_name || '—') },
        { label: 'Valor', render: (p) => fmtMoney(p.amount) }, { label: 'Forma', render: (p) => esc(METHODS[p.method] || '—') }, { label: 'Situação', render: (p) => payBadge(p.status) }, { label: 'Pago em', render: (p) => (p.paid_at ? fmtDate(p.paid_at.slice(0, 10)) : '—') },
        { label: 'Ações', actions: true, render: (p) => p.status === 'pendente' ? `<button class="btn btn-sm" data-act="pay" data-id="${p.id}">Dar baixa</button><button class="btn btn-sm btn-ghost" data-act="cancel" data-id="${p.id}">Cancelar</button>` : '<span class="small muted">—</span>' }], pays, empty('Nenhum pagamento no período', 'Pagamentos são gerados ao finalizar atendimentos ou registrados manualmente.', 'dollar'));
      pe.onclick = async (ev) => {
        const b = ev.target.closest('[data-act]'); if (!b) return; const p = pays.find((x) => x.id === Number(b.dataset.id));
        if (b.dataset.act === 'pay') modalForm({ title: 'Dar baixa no pagamento', submitText: 'Confirmar pagamento', intro: `<p>${esc(p.patient_name)} — <strong>${fmtMoney(p.amount)}</strong></p>`, fields: [{ name: 'method', label: 'Forma de pagamento', type: 'select', required: true, placeholder: 'Selecione', options: methodOpts, full: true }],
          onSubmit: async (v, m) => { await api(`/financeiro/pagamentos/${p.id}/pagar`, { method: 'PATCH', body: { method: v.method } }); m.close(); toast('Pagamento registrado.', 'success'); load(); } });
        if (b.dataset.act === 'cancel' && await confirmDialog('Cancelar esta cobrança pendente?', { title: 'Cancelar cobrança', confirmText: 'Cancelar cobrança', danger: true })) { try { await api(`/financeiro/pagamentos/${p.id}/cancelar`, { method: 'PATCH' }); toast('Cobrança cancelada.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); } }
      };
    } catch (e) { body.innerHTML = errorBox(errMsg(e)); }
  }

  function create() {
    const m = openModal({ title: 'Registrar pagamento', wide: true, body: `<div class="alert alert-danger mb" id="err" role="alert" hidden></div><div class="stack"><div id="pp"></div><div class="form-grid cols-2">
      <div class="field"><label for="pc">Procedimento</label><select id="pc"><option value="">Nenhum</option>${procs.map((p) => `<option value="${p.id}" data-price="${p.price}">${esc(p.name)}</option>`).join('')}</select></div>
      <div class="field"><label for="am">Valor (R$) <span class="req">*</span></label><input id="am" type="number" min="0" step="0.01" required></div>
      <div class="field"><label for="st">Situação</label><select id="st"><option value="pendente">Pendente</option><option value="pago">Pago</option></select></div>
      <div class="field"><label for="me">Forma de pagamento</label><select id="me"><option value="">—</option>${methodOpts.map((o) => `<option value="${o.value}">${esc(o.label)}</option>`).join('')}</select></div>
      <div class="field full"><label for="no">Observação</label><input id="no" maxlength="255"></div></div></div>`, footer: '<button class="btn btn-ghost" data-close>Cancelar</button><button class="btn" id="ok">Registrar</button>' });
    const d = m.dlg, err = d.querySelector('#err'), ok = d.querySelector('#ok'); let patient = null;
    patientPicker(d.querySelector('#pp'), { onSelect: (p) => { patient = p; } });
    d.querySelector('#pc').addEventListener('change', (e) => { const o = e.target.selectedOptions[0]; if (o.dataset.price) d.querySelector('#am').value = Number(o.dataset.price); });
    ok.addEventListener('click', async () => {
      err.hidden = true;
      if (!patient) { err.textContent = 'Selecione o paciente.'; err.hidden = false; return; }
      const amount = d.querySelector('#am').value; if (amount === '') { err.textContent = 'Informe o valor.'; err.hidden = false; return; }
      setLoading(ok, true);
      try { await api('/financeiro/pagamentos', { method: 'POST', body: { patient_id: patient.id, procedure_id: Number(d.querySelector('#pc').value) || null, amount: Number(amount), status: d.querySelector('#st').value, method: d.querySelector('#me').value || null, notes: d.querySelector('#no').value.trim() || null } }); m.close(); toast('Pagamento registrado.', 'success'); load(); }
      catch (e) { err.textContent = errMsg(e); err.hidden = false; setLoading(ok, false); }
    });
  }
  load();
}
