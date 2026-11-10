import { api, download } from './api.js';
import { mountShell } from './layout.js';
import { barChart, hBars, lineChart } from './charts.js';
import { METHODS, debounce, empty, errMsg, errorBox, esc, fmtDateTime, fmtMoney, icon, setLoading, spinner, table, toISODate, toast } from './ui.js';

const shell = await mountShell({ active: 'relatorios', title: 'Relatórios', roles: ['admin'] });
if (shell) main(shell);

function main({ content }) {
  const now = new Date(), f = { inicio: toISODate(new Date(now.getFullYear(), now.getMonth(), 1)), fim: toISODate(now) };
  content.innerHTML = `<div class="page-head"><h2>Relatórios</h2><div class="row"><button class="btn btn-outline" id="xlsx">${icon('download', 18)} Excel</button><button class="btn" id="pdf">${icon('download', 18)} PDF</button></div></div>
    <div class="card mb"><div class="toolbar"><div class="field"><label for="i">De</label><input id="i" type="date" value="${f.inicio}"></div><div class="field"><label for="d">Até</label><input id="d" type="date" value="${f.fim}"></div></div></div><div id="body">${spinner()}</div>`;
  const body = content.querySelector('#body');
  const upd = debounce(() => { f.inicio = content.querySelector('#i').value; f.fim = content.querySelector('#d').value; load(); }, 300);
  content.querySelector('.toolbar').addEventListener('change', upd);
  ['pdf', 'xlsx'].forEach((fmt) => content.querySelector('#' + fmt).addEventListener('click', async (e) => {
    const b = e.currentTarget; setLoading(b, true);
    try { await download('/relatorios/exportar', { formato: fmt, inicio: f.inicio, fim: f.fim }, `relatorio.${fmt}`); toast('Relatório gerado.', 'success'); } catch (er) { toast(errMsg(er), 'error'); } finally { setLoading(b, false); }
  }));

  async function load() {
    body.innerHTML = spinner();
    try {
      const r = await api('/relatorios/resumo', { params: { inicio: f.inicio, fim: f.fim } }), sc = r.status_count;
      const card = (i, l, v, k = '') => `<div class="stat"><span class="stat-icon ${k}">${icon(i)}</span><div><div class="stat-value">${v}</div><div class="stat-label">${l}</div></div></div>`;
      body.innerHTML = `<div class="stats">${card('users', 'Total de pacientes', r.total_patients)}${card('plus', 'Novos no período', r.new_patients, 'teal')}${card('calendar', 'Consultas no período', r.total_appointments)}${card('x', 'Canceladas', sc.cancelado, 'red')}${card('alert', 'Faltas', sc.nao_compareceu, 'warn')}${card('dollar', 'Receita', fmtMoney(r.finance.received), 'green')}</div>
        <div class="grid-2 mt"><section class="card"><h3 class="card-title">Evolução dos agendamentos</h3><div id="e"></div></section><section class="card"><h3 class="card-title">Receita por período</h3><div id="rv"></div></section>
        <section class="card"><h3 class="card-title">Procedimentos mais realizados</h3><div id="tp"></div></section>
        <section class="card"><h3 class="card-title">Consultas por situação</h3><div id="st"></div></section></div>
        <section class="card mt"><h3 class="card-title">Produtividade dos profissionais</h3>${table([{ label: 'Profissional', strong: true, render: (p) => esc(p.professional) }, { label: 'Consultas', render: (p) => p.total }, { label: 'Concluídas', render: (p) => p.completed }, { label: 'Canceladas', render: (p) => p.cancelled }, { label: 'Faltas', render: (p) => p.no_show }, { label: '% concluídas', render: (p) => p.completion_rate + '%' }], r.productivity, empty('Sem consultas no período', '', 'users'))}</section>
        <section class="card mt"><h3 class="card-title">Pacientes que não compareceram</h3>${table([{ label: 'Paciente', strong: true, render: (n) => esc(n.patient) }, { label: 'Data', render: (n) => fmtDateTime(n.start_at) }, { label: 'Procedimento', render: (n) => esc(n.procedure) }], r.no_shows, empty('Nenhuma falta no período', '', 'check'))}</section>
        <section class="card mt"><h3 class="card-title">Receita por forma de pagamento</h3>${table([{ label: 'Forma', render: (m) => esc(METHODS[m.method] || m.method) }, { label: 'Total', strong: true, render: (m) => fmtMoney(m.total) }], r.finance.by_method, empty('Sem recebimentos no período', '', 'dollar'))}</section>`;
      barChart(body.querySelector('#e'), r.appointments_series.labels, r.appointments_series.values);
      barChart(body.querySelector('#rv'), r.revenue_series.labels, r.revenue_series.values, { color: '#168a4a', fmt: (v) => 'R$ ' + Math.round(v) });
      hBars(body.querySelector('#tp'), r.top_procedures);
      const names = { pendente: 'Pendentes', confirmado: 'Confirmadas', em_atendimento: 'Em atendimento', concluido: 'Concluídas', cancelado: 'Canceladas', nao_compareceu: 'Não compareceram' };
      hBars(body.querySelector('#st'), Object.entries(sc).filter(([, v]) => v > 0).map(([k, v]) => ({ name: names[k], count: v })));
    } catch (e) { body.innerHTML = errorBox(errMsg(e)); }
  }
  load();
}
