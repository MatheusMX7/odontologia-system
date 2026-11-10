import { api } from './api.js';
import { mountShell } from './layout.js';
import { debounce, empty, errMsg, errorBox, esc, fmtDateTime, fmtTime, icon, modalForm, openModal, setLoading, spinner, statusBadge, table, toISODate, toast } from './ui.js';

const shell = await mountShell({ active: 'atendimentos', title: 'Atendimentos' });
if (shell) main(shell);

function main({ me, content }) {
  const clinical = ['admin', 'dentista'].includes(me.role);
  let tab = 'aguardando'; const h = { inicio: toISODate(new Date(Date.now() - 30 * 864e5)), fim: toISODate(new Date()), q: '' };
  content.innerHTML = `<div class="page-head"><h2>Atendimentos</h2></div><div class="alert alert-info mb">${icon('shield', 18)}<span>Agendamento e atendimento são etapas diferentes: o atendimento começa quando o paciente é chamado e termina com o registro clínico. ${clinical ? '' : 'Registros clínicos são restritos aos profissionais.'}</span></div>
    <div class="tabs mb" role="tablist"><button class="tab" role="tab" data-t="aguardando">Hoje</button><button class="tab" role="tab" data-t="historico">Histórico</button></div><div id="box"></div>`;
  const box = content.querySelector('#box');
  content.querySelectorAll('[data-t]').forEach((b) => b.addEventListener('click', () => { tab = b.dataset.t; load(); }));

  async function load() {
    content.querySelectorAll('[data-t]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.t === tab)));
    box.innerHTML = spinner();
    try { tab === 'aguardando' ? await waiting() : await history(); } catch (e) { box.innerHTML = errorBox(errMsg(e)); }
  }

  async function waiting() {
    const rows = await api('/atendimentos/aguardando');
    box.innerHTML = table([
      { label: 'Horário', strong: true, render: (r) => fmtTime(r.start_at) }, { label: 'Paciente', render: (r) => esc(r.patient_name) }, { label: 'Idade', render: (r) => `${r.patient_age} anos` },
      { label: 'Procedimento', render: (r) => esc(r.procedure_name) }, { label: 'Profissional', render: (r) => esc(r.professional_name) }, { label: 'Status', render: (r) => statusBadge(r.status) },
      { label: 'Ações', actions: true, render: (r) => !clinical ? '<span class="small muted">—</span>' : r.status === 'confirmado'
        ? `<button class="btn btn-sm btn-teal" data-act="start" data-id="${r.appointment_id}">Iniciar atendimento</button>`
        : `<button class="btn btn-sm btn-outline" data-act="records" data-att="${r.attendance_id}">Registros clínicos</button><button class="btn btn-sm" data-act="finish" data-att="${r.attendance_id}">Finalizar</button>` }],
      rows, empty('Nenhum paciente aguardando', 'Consultas confirmadas de hoje aparecem aqui.', 'activity'));
    box.onclick = async (ev) => {
      const b = ev.target.closest('[data-act]'); if (!b) return;
      if (b.dataset.act === 'start') { try { await api('/atendimentos/iniciar', { method: 'POST', body: { appointment_id: Number(b.dataset.id) } }); toast('Atendimento iniciado.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); } }
      if (b.dataset.act === 'records') records(Number(b.dataset.att), true);
      if (b.dataset.act === 'finish') modalForm({ title: 'Finalizar atendimento', submitText: 'Finalizar', intro: '<p class="small muted">As observações ficam no prontuário, com acesso restrito e auditado. Uma cobrança pendente será gerada para o financeiro.</p>',
        fields: [{ name: 'observations', label: 'Observações clínicas', type: 'textarea', full: true, maxlength: 5000 }],
        onSubmit: async (v, m) => { await api(`/atendimentos/${b.dataset.att}/finalizar`, { method: 'POST', body: { observations: v.observations || null } }); m.close(); toast('Atendimento finalizado.', 'success'); load(); } });
    };
  }

  async function history() {
    box.innerHTML = `<div class="card mb"><div class="toolbar cols-3" id="hf"><div class="field"><label for="hi">De</label><input id="hi" type="date" value="${h.inicio}"></div><div class="field"><label for="hd">Até</label><input id="hd" type="date" value="${h.fim}"></div><div class="field"><label for="hq">Paciente</label><input id="hq" type="search" value="${esc(h.q)}" placeholder="Buscar pelo nome"></div></div></div><div id="hl">${spinner()}</div>`;
    const hl = box.querySelector('#hl');
    const draw = async () => {
      try {
        const rows = await api('/atendimentos', { params: { data_inicio: h.inicio, data_fim: h.fim, q: h.q } });
        hl.innerHTML = table([{ label: 'Início', strong: true, render: (r) => fmtDateTime(r.started_at) }, { label: 'Fim', render: (r) => (r.finished_at ? fmtTime(r.finished_at) : '—') }, { label: 'Paciente', render: (r) => esc(r.patient_name) },
          { label: 'Procedimento', render: (r) => esc(r.procedure_name) }, { label: 'Profissional', render: (r) => esc(r.professional_name) }, { label: 'Status', render: (r) => statusBadge(r.status) },
          { label: 'Ações', actions: true, render: (r) => clinical ? `<button class="btn btn-sm btn-outline" data-att="${r.attendance_id}">Registros clínicos</button>` : '<span class="small muted">—</span>' }], rows, empty('Nenhum atendimento no período', '', 'activity'));
        hl.querySelectorAll('[data-att]').forEach((b) => b.addEventListener('click', () => records(Number(b.dataset.att), false)));
      } catch (e) { hl.innerHTML = errorBox(errMsg(e)); }
    };
    const upd = debounce(() => { h.inicio = box.querySelector('#hi').value; h.fim = box.querySelector('#hd').value; h.q = box.querySelector('#hq').value.trim(); draw(); }, 300);
    box.querySelector('#hf').addEventListener('input', upd); draw();
  }

  async function records(attId, canAdd) {
    const m = openModal({ title: 'Registros clínicos', wide: true, body: spinner() });
    async function draw() {
      try {
        const rs = await api(`/atendimentos/${attId}/registros`);
        m.body.innerHTML = `<p class="small muted">${icon('lock', 14)} Acesso restrito e registrado em auditoria.</p>${rs.length ? rs.map((r) => `<div class="card card-flat mb"><div class="small muted">${fmtDateTime(r.created_at)} · ${esc(r.professional_name)}</div><p style="margin:.4rem 0 0;white-space:pre-wrap">${esc(r.content)}</p></div>`).join('') : empty('Nenhum registro ainda', '', 'file')}
          ${canAdd ? `<form id="nf" class="mt" novalidate><div class="field"><label for="nc">Nova observação</label><textarea id="nc" maxlength="5000" required></textarea></div><button class="btn mt" type="submit" id="nb">Adicionar ao prontuário</button></form>` : ''}`;
        m.body.querySelector('#nf')?.addEventListener('submit', async (e) => { e.preventDefault(); const t = m.body.querySelector('#nc').value.trim(); if (!t) return; const btn = m.body.querySelector('#nb'); setLoading(btn, true);
          try { await api(`/atendimentos/${attId}/observacoes`, { method: 'POST', body: { content: t } }); draw(); } catch (er) { toast(errMsg(er), 'error'); setLoading(btn, false); } });
      } catch (e) { m.body.innerHTML = errorBox(errMsg(e)); }
    }
    draw();
  }
  load();
}
