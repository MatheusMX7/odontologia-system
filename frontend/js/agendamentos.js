import { api } from './api.js';
import { mountShell } from './layout.js';
import { patientPicker, slotPicker } from './pickers.js';
import { debounce, empty, errMsg, errorBox, esc, fmtDate, fmtDateTime, fmtTime, icon, longDate, modalForm, openModal, pad, parseISO, setLoading, spinner, statusBadge, table, toISODate, toast, confirmDialog } from './ui.js';

const shell = await mountShell({ active: 'agendamentos', title: 'Agendamentos' });
if (shell) main(shell);

const STATUS_OPTS = [['', 'Todos'], ['pendente', 'Pendente'], ['confirmado', 'Confirmado'], ['em_atendimento', 'Em atendimento'], ['concluido', 'Concluído'], ['cancelado', 'Cancelado'], ['nao_compareceu', 'Não compareceu']];

async function main({ me, clinic, content }) {
  const staffEdit = ['admin', 'recepcionista'].includes(me.role), isDentist = me.role === 'dentista';
  const today = new Date(), plus30 = new Date(); plus30.setDate(plus30.getDate() + 30);
  const f = { view: 'tabela', data_inicio: toISODate(today), data_fim: toISODate(plus30), procedimento_id: '', profissional_id: '', q: '', status: '' };
  let month = new Date(today.getFullYear(), today.getMonth(), 1), selDay = toISODate(today), items = [], procs = [], pros = [];
  try { [procs, pros] = await Promise.all([api('/procedimentos'), api('/profissionais')]); } catch (e) { content.innerHTML = errorBox(errMsg(e)); return; }

  content.innerHTML = `<div class="page-head"><h2>Agenda</h2><div class="row"><div class="tabs" role="tablist" aria-label="Visualização"><button class="tab" role="tab" data-v="tabela">${icon('file', 16)} Tabela</button><button class="tab" role="tab" data-v="calendario">${icon('calendar', 16)} Calendário</button></div>
    ${staffEdit ? `<button class="btn" id="add">${icon('plus', 18)} Novo agendamento</button>` : ''}</div></div>
    <div class="card mb"><div class="toolbar cols-5" id="filters">
      <div class="field" id="rangeA"><label for="di">De</label><input id="di" type="date" value="${f.data_inicio}"></div><div class="field" id="rangeB"><label for="df">Até</label><input id="df" type="date" value="${f.data_fim}"></div>
      <div class="field"><label for="fp">Procedimento</label><select id="fp"><option value="">Todos</option>${procs.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div>
      ${isDentist ? '' : `<div class="field"><label for="fr">Profissional</label><select id="fr"><option value="">Todos</option>${pros.map((p) => `<option value="${p.id}">${esc(p.full_name)}</option>`).join('')}</select></div>`}
      <div class="field"><label for="fs">Status</label><select id="fs">${STATUS_OPTS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></div>
      <div class="field"><label for="fq">Paciente</label><input id="fq" type="search" placeholder="Buscar pelo nome"></div></div></div><div id="view">${spinner()}</div>`;
  const view = content.querySelector('#view');

  const params = () => {
    let di = f.data_inicio, df = f.data_fim;
    if (f.view === 'calendario') { di = toISODate(month); df = toISODate(new Date(month.getFullYear(), month.getMonth() + 1, 0)); }
    return { data_inicio: di, data_fim: df, procedimento_id: f.procedimento_id, profissional_id: f.profissional_id, q: f.q, status: f.status };
  };
  async function load() {
    view.innerHTML = spinner();
    content.querySelector('#rangeA').hidden = content.querySelector('#rangeB').hidden = f.view === 'calendario';
    content.querySelectorAll('[data-v]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.v === f.view)));
    try { items = await api('/agendamentos', { params: params() }); f.view === 'tabela' ? drawTable() : drawCalendar(); } catch (e) { view.innerHTML = errorBox(errMsg(e)); }
  }

  const actions = (a) => {
    const open = ['pendente', 'confirmado'].includes(a.status), past = parseISO(a.start_at) <= new Date();
    return `<button class="btn btn-sm btn-ghost" data-act="det" data-id="${a.id}">Detalhes</button>
      ${staffEdit && a.status === 'pendente' ? `<button class="btn btn-sm" data-act="confirm" data-id="${a.id}">Confirmar</button>` : ''}
      ${staffEdit && open ? `<button class="btn btn-sm btn-outline" data-act="resched" data-id="${a.id}">Reagendar</button>` : ''}
      ${staffEdit && open ? `<button class="btn btn-sm btn-ghost" data-act="cancel" data-id="${a.id}">Cancelar</button>` : ''}
      ${a.status === 'confirmado' && past ? `<button class="btn btn-sm btn-ghost" data-act="noshow" data-id="${a.id}">Registrar falta</button>` : ''}`;
  };
  const cols = [
    { label: 'Data', strong: true, render: (a) => fmtDate(a.start_at.slice(0, 10)) }, { label: 'Horário', render: (a) => `${fmtTime(a.start_at)} – ${fmtTime(a.end_at)}` },
    { label: 'Paciente', render: (a) => esc(a.patient_name) }, { label: 'Idade', render: (a) => `${a.patient_age} anos` }, { label: 'Procedimento', render: (a) => esc(a.procedure_name) },
    { label: 'Profissional', render: (a) => esc(a.professional_name) }, { label: 'Status', render: (a) => statusBadge(a.status) }, { label: 'Ações', actions: true, render: actions }];

  const drawTable = () => { view.innerHTML = table(cols, items, empty('Nenhum agendamento encontrado', 'Ajuste os filtros ou crie um novo agendamento.', 'calendar')); };

  function drawCalendar() {
    const counts = {}; items.forEach((a) => { const k = a.start_at.slice(0, 10); counts[k] = (counts[k] || 0) + (a.status === 'cancelado' ? 0 : 1); });
    const first = new Date(month), lead = (first.getDay() + 6) % 7, days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    let cells = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((d) => `<div class="cal-head">${d}</div>`).join('') + '<div class="cal-day out" aria-hidden="true"></div>'.repeat(lead);
    for (let d = 1; d <= days; d++) {
      const iso = `${month.getFullYear()}-${pad(month.getMonth() + 1)}-${pad(d)}`;
      cells += `<button class="cal-day ${iso === toISODate(today) ? 'today' : ''} ${iso === selDay ? 'sel' : ''}" data-day="${iso}" aria-label="${d} — ${counts[iso] || 0} consulta(s)"><span>${d}</span>${counts[iso] ? `<span class="cal-count">${counts[iso]}</span>` : ''}</button>`;
    }
    view.innerHTML = `<div class="card"><div class="row between mb"><button class="icon-btn" id="pm" aria-label="Mês anterior">${icon('left')}</button><strong style="text-transform:capitalize">${month.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })}</strong><button class="icon-btn" id="nm" aria-label="Próximo mês">${icon('right')}</button></div><div class="cal">${cells}</div></div>
      <h3 class="mt" style="font-size:1.05rem;text-transform:capitalize">${esc(longDate(selDay))}</h3><div id="dayList"></div>`;
    const day = items.filter((a) => a.start_at.startsWith(selDay));
    view.querySelector('#dayList').innerHTML = table(cols.filter((c) => !['Data', 'Idade'].includes(c.label)), day, empty('Sem consultas neste dia', '', 'calendar'));
    view.querySelector('#pm').onclick = () => { month = new Date(month.getFullYear(), month.getMonth() - 1, 1); load(); };
    view.querySelector('#nm').onclick = () => { month = new Date(month.getFullYear(), month.getMonth() + 1, 1); load(); };
    view.querySelectorAll('[data-day]').forEach((b) => b.addEventListener('click', () => { selDay = b.dataset.day; drawCalendar(); }));
  }

  // ---- filtros ----
  const bind = debounce(() => { f.data_inicio = content.querySelector('#di').value; f.data_fim = content.querySelector('#df').value; f.procedimento_id = content.querySelector('#fp').value; f.profissional_id = content.querySelector('#fr')?.value || ''; f.status = content.querySelector('#fs').value; f.q = content.querySelector('#fq').value.trim(); load(); }, 250);
  content.querySelector('#filters').addEventListener('input', bind); content.querySelector('#filters').addEventListener('change', bind);
  content.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => { f.view = b.dataset.v; load(); }));
  content.querySelector('#add')?.addEventListener('click', () => createAppt());

  // ---- ações ----
  view.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-act]'); if (!b) return; const a = items.find((x) => x.id === Number(b.dataset.id));
    if (b.dataset.act === 'det') return details(a);
    if (b.dataset.act === 'confirm') { try { await api(`/agendamentos/${a.id}/status`, { method: 'PATCH', body: { status: 'confirmado' } }); toast('Agendamento confirmado.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); } }
    if (b.dataset.act === 'noshow' && await confirmDialog(`Registrar que ${a.patient_name} não compareceu?`, { title: 'Registrar falta', confirmText: 'Registrar falta' })) {
      try { await api(`/agendamentos/${a.id}/status`, { method: 'PATCH', body: { status: 'nao_compareceu' } }); toast('Falta registrada.', 'success'); load(); } catch (e) { toast(errMsg(e), 'error'); }
    }
    if (b.dataset.act === 'cancel') modalForm({ title: 'Cancelar agendamento', submitText: 'Cancelar agendamento', intro: `<p>${esc(a.patient_name)} — ${esc(a.procedure_name)} em ${fmtDateTime(a.start_at)}. O horário será liberado.</p>`,
      fields: [{ name: 'reason', label: 'Motivo (opcional)', type: 'textarea', full: true, maxlength: 255 }],
      onSubmit: async (v, m) => { await api(`/agendamentos/${a.id}/cancelar`, { method: 'POST', body: { reason: v.reason || null } }); m.close(); toast('Agendamento cancelado.', 'success'); load(); } });
    if (b.dataset.act === 'resched') reschedule(a);
  });

  function details(a) {
    openModal({ title: 'Detalhes do agendamento', body: `<dl class="kv"><div><dt>Paciente</dt><dd>${esc(a.patient_name)} · ${a.patient_age} anos</dd></div><div><dt>Status</dt><dd>${statusBadge(a.status)}</dd></div>
      <div><dt>Procedimento</dt><dd>${esc(a.procedure_name)}</dd></div><div><dt>Profissional</dt><dd>${esc(a.professional_name)}</dd></div><div><dt>Data</dt><dd>${fmtDate(a.start_at.slice(0, 10))}</dd></div><div><dt>Horário</dt><dd>${fmtTime(a.start_at)} – ${fmtTime(a.end_at)}</dd></div>
      ${a.notes ? `<div style="grid-column:1/-1"><dt>Observações do paciente</dt><dd>${esc(a.notes)}</dd></div>` : ''}${a.cancel_reason ? `<div style="grid-column:1/-1"><dt>Motivo do cancelamento</dt><dd>${esc(a.cancel_reason)}</dd></div>` : ''}</dl>` });
  }

  function reschedule(a) {
    const m = openModal({ title: 'Reagendar', body: `<p class="muted small">${esc(a.patient_name)} — ${esc(a.procedure_name)} com ${esc(a.professional_name)}. Atual: ${fmtDateTime(a.start_at)}</p><div id="pk"></div><div class="alert alert-danger mt" id="err" role="alert" hidden></div>`,
      footer: '<button class="btn btn-ghost" data-close>Voltar</button><button class="btn" id="ok" disabled>Confirmar novo horário</button>' });
    const ok = m.dlg.querySelector('#ok'), err = m.dlg.querySelector('#err'); let sel = null;
    slotPicker(m.dlg.querySelector('#pk'), { procedureId: a.procedure_id, professionalId: a.professional_id, excludeId: a.id, maxDays: clinic.max_advance_days, onChange: (s) => { sel = s; ok.disabled = !s; } });
    ok.addEventListener('click', async () => { err.hidden = true; setLoading(ok, true);
      try { await api(`/agendamentos/${a.id}/reagendar`, { method: 'POST', body: { start_at: sel.start, professional_id: sel.professional_id } }); m.close(); toast('Agendamento reagendado.', 'success'); load(); }
      catch (e) { err.textContent = errMsg(e); err.hidden = false; setLoading(ok, false); } });
  }

  function createAppt() {
    const activeProcs = procs.filter((p) => p.is_active);
    const m = openModal({ title: 'Novo agendamento', wide: true, body: `<div class="alert alert-danger mb" id="err" role="alert" hidden></div><div class="stack"><div id="pp"></div>
      <div class="form-grid cols-2"><div class="field"><label for="np">Procedimento <span class="req">*</span></label><select id="np"><option value="">Selecione</option>${activeProcs.map((p) => `<option value="${p.id}">${esc(p.name)} (${p.duration_minutes} min)</option>`).join('')}</select></div>
      <div class="field"><label for="nr">Profissional <span class="req">*</span></label><select id="nr" disabled><option value="">Selecione o procedimento</option></select></div></div><div id="pk"></div>
      <div class="field"><label for="nn">Observações</label><textarea id="nn" maxlength="500"></textarea></div></div>`,
      footer: '<button class="btn btn-ghost" data-close>Cancelar</button><button class="btn" id="ok" disabled>Agendar</button>' });
    const d = m.dlg, ok = d.querySelector('#ok'), err = d.querySelector('#err'), np = d.querySelector('#np'), nr = d.querySelector('#nr'), pk = d.querySelector('#pk');
    let patient = null, sel = null;
    const refresh = () => { ok.disabled = !(patient && sel); };
    patientPicker(d.querySelector('#pp'), { onSelect: (p) => { patient = p; refresh(); } });
    const mountPicker = () => { sel = null; refresh(); pk.innerHTML = ''; if (np.value && nr.value) slotPicker(pk, { procedureId: Number(np.value), professionalId: Number(nr.value), maxDays: clinic.max_advance_days, onChange: (s) => { sel = s; refresh(); } }); };
    np.addEventListener('change', () => {
      const p = activeProcs.find((x) => x.id === Number(np.value)); const opts = p ? pros.filter((x) => x.is_active && p.professional_ids.includes(x.id)) : [];
      nr.disabled = !p; nr.innerHTML = !p ? '<option value="">Selecione o procedimento</option>' : opts.length ? `<option value="">Selecione</option>${opts.map((x) => `<option value="${x.id}">${esc(x.full_name)}</option>`).join('')}` : '<option value="">Nenhum profissional habilitado</option>';
      mountPicker();
    });
    nr.addEventListener('change', mountPicker);
    ok.addEventListener('click', async () => { err.hidden = true; setLoading(ok, true);
      try { await api('/agendamentos', { method: 'POST', body: { patient_id: patient.id, procedure_id: Number(np.value), professional_id: sel.professional_id, start_at: sel.start, notes: d.querySelector('#nn').value.trim() || null } }); m.close(); toast('Agendamento criado e confirmado.', 'success'); load(); }
      catch (e) { err.textContent = errMsg(e); err.hidden = false; setLoading(ok, false); } });
  }
  load();
}
