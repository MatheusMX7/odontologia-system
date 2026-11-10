import { api } from './api.js';
import { requireAuth } from './auth.js';
import { mountSite } from './site.js';
import { slotPicker } from './pickers.js';
import { CATEGORY, errMsg, esc, fmtDate, fmtTime, icon, longDate, spinner, setLoading, empty, errorBox } from './ui.js';

const STEPS = ['Procedimento', 'Profissional', 'Data e horário', 'Confirmação'];
const state = { procedure: null, professional: null, selection: null, step: 0 };
let clinic, patient, procedures = [];

const stage = document.getElementById('stage'), stepper = document.getElementById('stepper');
const drawStepper = () => { stepper.innerHTML = STEPS.map((s, i) => `<div class="step ${i < state.step ? 'done' : i === state.step ? 'current' : ''}" ${i === state.step ? 'aria-current="step"' : ''}>${'<span>' + (i + 1) + '. </span>'}<span style="display:inline">${s}</span></div>`).join(''); };
const go = (n) => { state.step = n; drawStepper(); [stepProcedure, stepProfessional, stepSlot, stepConfirm][n](); window.scrollTo({ top: 0, behavior: 'smooth' }); };

function stepProcedure() {
  const items = procedures.filter((p) => p.available);
  if (!items.length) { stage.innerHTML = empty('Nenhum procedimento disponível no momento', 'Entre em contato com a clínica.', 'clipboard'); return; }
  const groups = Object.entries(CATEGORY).map(([k, v]) => {
    const l = items.filter((p) => p.category === k);
    return l.length ? `<h3 class="mt">${esc(v.label)}</h3><div class="option-list">${l.map((p) => `<button type="button" class="option" data-id="${p.id}" aria-pressed="${state.procedure?.id === p.id}"><span class="stat-icon teal">${icon(v.icon)}</span><span><strong>${esc(p.name)}</strong><small>${p.duration_minutes} min · ${esc(p.description)}</small></span></button>`).join('')}</div>` : '';
  }).join('');
  stage.innerHTML = `<h2 style="font-size:1.25rem">1. Qual procedimento você deseja?</h2>${groups}`;
  stage.querySelectorAll('.option').forEach((b) => b.addEventListener('click', () => { state.procedure = procedures.find((p) => p.id === Number(b.dataset.id)); state.professional = null; state.selection = null; go(1); }));
}

async function stepProfessional() {
  stage.innerHTML = `<h2 style="font-size:1.25rem">2. Escolha o profissional</h2>${spinner()}`;
  try {
    const pros = await api(`/publico/procedimentos/${state.procedure.id}/profissionais`);
    if (!pros.length) { stage.innerHTML = `<h2 style="font-size:1.25rem">2. Escolha o profissional</h2>${empty('Nenhum profissional disponível para este procedimento', 'Escolha outro procedimento.', 'users')}<button class="btn btn-outline" id="back">Voltar</button>`; stage.querySelector('#back').onclick = () => go(0); return; }
    const sel = state.professional?.id ?? 0;
    stage.innerHTML = `<h2 style="font-size:1.25rem">2. Escolha o profissional</h2><p class="muted small">${esc(state.procedure.name)}</p>
      <div class="option-list"><button type="button" class="option" data-id="0" aria-pressed="${sel === 0}"><span class="stat-icon">${icon('users')}</span><span><strong>Sem preferência</strong><small>Mostrar todos os horários livres</small></span></button>
      ${pros.map((p) => `<button type="button" class="option" data-id="${p.id}" aria-pressed="${sel === p.id}"><span class="pro-avatar" style="width:44px;height:44px;margin:0;font-size:1rem">${esc(p.full_name.replace(/^(Dr\.?a?|\[DEMO\])\s*/i, '').trim()[0] || '?').toUpperCase()}</span><span><strong>${esc(p.full_name)}</strong><small>${esc(p.specialty)}${p.cro ? ' · ' + esc(p.cro) : ''}</small></span></button>`).join('')}</div>
      <div class="row mt"><button class="btn btn-ghost" id="back">Voltar</button></div>`;
    stage.querySelector('#back').onclick = () => go(0);
    stage.querySelectorAll('.option').forEach((b) => b.addEventListener('click', () => { const id = Number(b.dataset.id); state.professional = id ? pros.find((p) => p.id === id) : null; state.selection = null; go(2); }));
  } catch (e) { stage.innerHTML = errorBox(errMsg(e)); }
}

function stepSlot() {
  stage.innerHTML = `<h2 style="font-size:1.25rem">3. Escolha a data e o horário</h2><p class="muted small">${esc(state.procedure.name)}${state.professional ? ' · ' + esc(state.professional.full_name) : ''}</p>
    <div id="picker"></div><div class="row between mt"><button class="btn btn-ghost" id="back">Voltar</button><button class="btn" id="next" disabled>Continuar</button></div>`;
  const next = stage.querySelector('#next');
  stage.querySelector('#back').onclick = () => go(1);
  slotPicker(stage.querySelector('#picker'), { procedureId: state.procedure.id, professionalId: state.professional?.id ?? null, maxDays: clinic.max_advance_days,
    onChange: (s) => { state.selection = s; next.disabled = !s; } });
  next.onclick = () => go(3);
}

function stepConfirm() {
  const s = state.selection, auto = clinic.auto_confirm;
  stage.innerHTML = `<h2 style="font-size:1.25rem">4. Confirme seus dados</h2>
    <dl class="kv card card-flat"><div><dt>Procedimento</dt><dd>${esc(state.procedure.name)}</dd></div><div><dt>Profissional</dt><dd>${esc(s.professional_name)}</dd></div>
      <div><dt>Data</dt><dd>${esc(longDate(s.start.slice(0, 10)))}</dd></div><div><dt>Horário</dt><dd>${fmtTime(s.start)} (${state.procedure.duration_minutes} min)</dd></div>
      <div><dt>Paciente</dt><dd>${esc(patient.full_name)} · ${patient.age} anos</dd></div><div><dt>Contato</dt><dd>${esc(patient.email)}</dd></div></dl>
    <div class="field mt"><label for="notes">Observações (opcional)</label><textarea id="notes" maxlength="500" placeholder="Ex.: sinto dor no lado direito"></textarea></div>
    <div class="alert alert-info mt">${icon('clock', 18)}<span>${auto ? 'Sua consulta será confirmada automaticamente.' : 'Sua solicitação ficará aguardando aprovação da clínica.'} ${clinic.policy_text ? esc(clinic.policy_text) : `Cancelamentos e reagendamentos exigem ${clinic.cancel_min_hours}h de antecedência.`}</span></div>
    <div class="alert alert-danger mt" id="err" role="alert" hidden></div>
    <div class="row between mt"><button class="btn btn-ghost" id="back">Voltar</button><button class="btn btn-teal btn-lg" id="send">Enviar solicitação</button></div>`;
  stage.querySelector('#back').onclick = () => go(2);
  const send = stage.querySelector('#send'), err = stage.querySelector('#err');
  send.onclick = async () => {
    err.hidden = true; setLoading(send, true);
    try {
      const a = await api('/agendamentos', { method: 'POST', body: { procedure_id: state.procedure.id, professional_id: s.professional_id, start_at: s.start, notes: stage.querySelector('#notes').value.trim() || null } });
      done(a);
    } catch (e) {
      err.textContent = errMsg(e); err.hidden = false; setLoading(send, false);
      if (e.status === 409) { err.textContent += ' Volte e escolha outro horário.'; }
    }
  };
}

function done(a) {
  stepper.innerHTML = STEPS.map((s) => `<div class="step done"><span style="display:inline">${s}</span></div>`).join('');
  const ok = a.status === 'confirmado';
  stage.innerHTML = `<div class="center" style="padding:1rem 0"><span class="stat-icon green" style="width:64px;height:64px;margin:0 auto 1rem;border-radius:50%">${icon('check', 32)}</span>
    <h2 style="font-size:1.4rem">${ok ? 'Consulta confirmada!' : 'Solicitação enviada!'}</h2>
    <p class="muted" style="margin-inline:auto">${ok ? 'Seu horário está reservado.' : 'Sua solicitação está <strong>aguardando aprovação</strong>. Acompanhe o status na sua área.'}</p>
    <p><strong>${esc(a.procedure_name)}</strong><br>${esc(longDate(a.start_at.slice(0, 10)))} às ${fmtTime(a.start_at)}<br><span class="muted small">com ${esc(a.professional_name)}</span></p>
    <div class="row" style="justify-content:center"><a class="btn" href="/portal/meus-agendamentos.html">Ver meus agendamentos</a><a class="btn btn-outline" href="/index.html">Início</a></div></div>`;
}

(async () => {
  const me = await requireAuth(['paciente', 'admin', 'recepcionista', 'dentista']);
  if (!me) return;
  await mountSite();
  if (me.role !== 'paciente') { stage.innerHTML = `<div class="alert alert-info">${icon('alert', 18)}<span>Você está logado como equipe da clínica. Para agendar para um paciente, use o painel em <a href="/admin/agendamentos.html">Agendamentos</a>.</span></div>`; return; }
  try {
    [clinic, patient, procedures] = await Promise.all([api('/publico/clinica'), api('/pacientes/me'), api('/publico/procedimentos')]);
  } catch (e) { stage.innerHTML = errorBox(errMsg(e)); return; }
  const pre = Number(new URLSearchParams(location.search).get('procedimento'));
  const found = procedures.find((p) => p.id === pre && p.available);
  if (found) { state.procedure = found; go(1); } else go(0);
})();
