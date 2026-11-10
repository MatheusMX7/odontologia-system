import { api } from './api.js';
import { mountShell } from './layout.js';
import { barChart, hBars, lineChart } from './charts.js';
import { empty, errorBox, errMsg, esc, fmtMoney, fmtTime, icon, spinner, statusBadge, table } from './ui.js';

const shell = await mountShell({ active: 'dashboard', title: 'Dashboard' });
if (shell) main(shell);

async function main({ me, content }) {
  let dias = 30, data;
  const f = { q: '', turno: '', proc: '', prof: '' };
  content.innerHTML = `<div class="page-head"><h2>Visão geral</h2><div class="field" style="min-width:190px"><label class="sr-only" for="dias">Período</label>
    <select id="dias"><option value="7">Últimos 7 dias</option><option value="30" selected>Últimos 30 dias</option><option value="90">Últimos 90 dias</option></select></div></div><div id="body">${spinner()}</div>`;
  const body = content.querySelector('#body');
  content.querySelector('#dias').addEventListener('change', (e) => { dias = Number(e.target.value); load(); });

  async function load() {
    body.innerHTML = spinner();
    try { data = await api('/dashboard', { params: { dias } }); draw(); } catch (e) { body.innerHTML = errorBox(errMsg(e)); }
  }

  function draw() {
    const c = data.cards;
    const cards = [['users', 'Pacientes cadastrados', c.total_patients, ''], ['calendar', 'Consultas hoje', c.today_appointments, 'teal'], ['check', `Concluídas (${dias}d)`, c.completed, 'green'],
      ['clock', 'Pendentes', c.pending, 'warn'], ['x', `Canceladas (${dias}d)`, c.cancelled, 'red'], ['plus', me.role === 'dentista' ? `Pacientes atendidos (${dias}d)` : `Novos pacientes (${dias}d)`, c.new_patients, 'teal']];
    body.innerHTML = `<div class="stats">${cards.map(([i, l, v, k]) => `<div class="stat"><span class="stat-icon ${k}">${icon(i)}</span><div><div class="stat-value">${v}</div><div class="stat-label">${esc(l)}</div></div></div>`).join('')}</div>
      <section class="card mt" aria-labelledby="agTitle"><div class="row between"><h3 class="card-title" id="agTitle">Agenda de hoje</h3></div>
        <div class="toolbar cols-4" id="agFilters"></div><div id="agTable"></div></section>
      <div class="grid-2 mt"><section class="card"><h3 class="card-title">Agendamentos por período</h3><div id="c1"></div></section>
        <section class="card"><h3 class="card-title">Procedimentos mais solicitados</h3><div id="c2"></div></section>
        <section class="card"><h3 class="card-title">Atendimentos realizados</h3><div id="c3"></div></section>
        <section class="card"><h3 class="card-title">Evolução dos agendamentos (6 meses)</h3><div id="c4"></div></section></div>
      ${data.finance ? `<section class="card mt"><h3 class="card-title">Indicadores financeiros</h3><div class="stats cols-3 mb"><div class="stat"><span class="stat-icon green">${icon('dollar')}</span><div><div class="stat-value">${fmtMoney(data.finance.received)}</div><div class="stat-label">Recebido (${dias}d)</div></div></div>
        <div class="stat"><span class="stat-icon warn">${icon('clock')}</span><div><div class="stat-value">${fmtMoney(data.finance.pending)}</div><div class="stat-label">Pendente (${dias}d)</div></div></div></div><div id="c5"></div></section>` : ''}`;
    barChart(body.querySelector('#c1'), data.appointments_series.labels, data.appointments_series.values);
    hBars(body.querySelector('#c2'), data.top_procedures);
    barChart(body.querySelector('#c3'), data.attendances_series.labels, data.attendances_series.values, { color: '#14b8a6' });
    lineChart(body.querySelector('#c4'), data.evolution.labels, [{ name: 'Agendamentos', values: data.evolution.total, color: '#2f7be5' }, { name: 'Concluídos', values: data.evolution.completed, color: '#14b8a6' }]);
    if (data.finance) barChart(body.querySelector('#c5'), data.finance.monthly.labels, data.finance.monthly.values, { color: '#168a4a', fmt: (v) => 'R$ ' + Math.round(v) });
    drawFilters(); drawAgenda();
  }

  function drawFilters() {
    const ag = data.today_agenda;
    const uniq = (k, n) => [...new Map(ag.map((a) => [a[k], a[n]])).entries()];
    const box = body.querySelector('#agFilters');
    box.innerHTML = `<div class="field"><label for="fq">Buscar paciente</label><input id="fq" type="search" placeholder="Nome" value="${esc(f.q)}"></div>
      <div class="field"><label for="ft">Horário</label><select id="ft"><option value="">Todos</option><option value="m">Manhã (até 12h)</option><option value="t">Tarde (12h–18h)</option><option value="n">Noite (após 18h)</option></select></div>
      <div class="field"><label for="fp">Procedimento</label><select id="fp"><option value="">Todos</option>${uniq('procedure_id', 'procedure_name').map(([id, n]) => `<option value="${id}">${esc(n)}</option>`).join('')}</select></div>
      ${me.role === 'dentista' ? '' : `<div class="field"><label for="fr">Profissional</label><select id="fr"><option value="">Todos</option>${uniq('professional_id', 'professional_name').map(([id, n]) => `<option value="${id}">${esc(n)}</option>`).join('')}</select></div>`}`;
    box.querySelector('#ft').value = f.turno; box.querySelector('#fp').value = f.proc; if (box.querySelector('#fr')) box.querySelector('#fr').value = f.prof;
    const upd = () => { f.q = box.querySelector('#fq').value; f.turno = box.querySelector('#ft').value; f.proc = box.querySelector('#fp').value; f.prof = box.querySelector('#fr')?.value || ''; drawAgenda(); };
    box.addEventListener('input', upd); box.addEventListener('change', upd);
  }

  function drawAgenda() {
    const q = f.q.trim().toLowerCase();
    const rows = data.today_agenda.filter((a) => {
      const h = Number(fmtTime(a.start_at).slice(0, 2));
      return (!q || a.patient_name.toLowerCase().includes(q)) && (!f.turno || (f.turno === 'm' ? h < 12 : f.turno === 't' ? h >= 12 && h < 18 : h >= 18))
        && (!f.proc || String(a.procedure_id) === f.proc) && (!f.prof || String(a.professional_id) === f.prof);
    });
    body.querySelector('#agTable').innerHTML = table([
      { label: 'Horário', strong: true, render: (a) => `${fmtTime(a.start_at)} – ${fmtTime(a.end_at)}` }, { label: 'Paciente', render: (a) => esc(a.patient_name) },
      { label: 'Idade', render: (a) => `${a.patient_age} anos` }, { label: 'Procedimento', render: (a) => esc(a.procedure_name) },
      { label: 'Profissional', render: (a) => esc(a.professional_name) }, { label: 'Status', render: (a) => statusBadge(a.status) }], rows,
      empty(data.today_agenda.length ? 'Nenhum resultado para os filtros' : 'Nenhuma consulta para hoje', data.today_agenda.length ? 'Ajuste a busca.' : 'Os agendamentos de hoje aparecem aqui.', 'calendar'));
  }
  load();
}
