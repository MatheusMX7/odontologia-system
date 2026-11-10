import { api } from './api.js';
import { debounce, empty, errMsg, esc, fmtDate, longDate, spinner, toISODate, toast } from './ui.js';

/** Seletor de data + horários. Os horários vêm do backend (jornada, intervalos, bloqueios e reservas). */
export function slotPicker(container, { procedureId, professionalId = null, excludeId = null, maxDays = 60, onChange = () => {} }) {
  const today = new Date(), max = new Date(); max.setDate(max.getDate() + maxDays);
  container.innerHTML = `<div class="form-grid cols-2"><div class="field"><label for="spDate">Data</label>
    <input type="date" id="spDate" min="${toISODate(today)}" max="${toISODate(max)}"></div></div>
    <div id="spSlots" class="mt" aria-live="polite"><p class="muted small">Escolha uma data para ver os horários disponíveis.</p></div>`;
  const dateEl = container.querySelector('#spDate'), box = container.querySelector('#spSlots');
  let selected = null, seq = 0;

  async function load() {
    selected = null; onChange(null);
    if (!dateEl.value) return;
    const my = ++seq; box.innerHTML = spinner();
    try {
      const list = await api('/agendamentos/disponibilidade', { params: { procedimento_id: procedureId, data: dateEl.value, profissional_id: professionalId, excluir_agendamento_id: excludeId } });
      if (my !== seq) return;
      const byTime = new Map();
      list.forEach((s) => { if (!byTime.has(s.time)) byTime.set(s.time, s); });  // sem preferência: usa o 1º profissional livre
      const slots = [...byTime.values()];
      if (!slots.length) { box.innerHTML = empty('Sem horários nesta data', 'Escolha outro dia — a clínica pode não atender nesta data.', 'clock'); return; }
      box.innerHTML = `<p class="small muted" style="margin-bottom:.6rem">${esc(longDate(dateEl.value))}</p><div class="slots" role="group" aria-label="Horários disponíveis">${slots.map((s) => `<button type="button" class="slot" aria-pressed="false" data-start="${s.start}" data-prof="${s.professional_id}" data-pname="${esc(s.professional_name)}">${s.time}</button>`).join('')}</div>`;
    } catch (e) { if (my === seq) box.innerHTML = `<div class="alert alert-danger">${esc(errMsg(e))}</div>`; }
  }
  dateEl.addEventListener('change', load);
  box.addEventListener('click', (ev) => {
    const b = ev.target.closest('.slot'); if (!b) return;
    box.querySelectorAll('.slot').forEach((x) => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true');
    selected = { start: b.dataset.start, professional_id: Number(b.dataset.prof), professional_name: b.dataset.pname }; onChange(selected);
  });
  return { get selection() { return selected; }, reload: load };
}

/** Busca de paciente (equipe). Retorna controlador com o paciente escolhido. */
export function patientPicker(container, { onSelect = () => {} } = {}) {
  container.innerHTML = `<div class="field"><label for="ppQ">Paciente <span class="req">*</span></label>
    <input id="ppQ" type="search" placeholder="Digite nome ou CPF para buscar" autocomplete="off"><select id="ppSel" size="4" aria-label="Resultados" hidden></select>
    <span class="field-help" id="ppInfo"></span><span class="field-error" data-err="patient_id" role="alert"></span></div>`;
  const q = container.querySelector('#ppQ'), sel = container.querySelector('#ppSel'), info = container.querySelector('#ppInfo');
  let chosen = null, list = [];
  const search = debounce(async () => {
    const term = q.value.trim(); chosen = null; onSelect(null);
    if (term.length < 2) { sel.hidden = true; info.textContent = ''; return; }
    try {
      const r = await api('/pacientes', { params: { q: term, limite: 10 } }); list = r.items;
      sel.innerHTML = list.map((p) => `<option value="${p.id}">${esc(p.full_name)} — ${p.age} anos</option>`).join('');
      sel.hidden = !list.length; info.textContent = list.length ? 'Selecione o paciente na lista.' : 'Nenhum paciente encontrado.';
    } catch (e) { toast(errMsg(e), 'error'); }
  }, 300);
  q.addEventListener('input', search);
  sel.addEventListener('change', () => { chosen = list.find((p) => String(p.id) === sel.value); if (chosen) { info.textContent = `Selecionado: ${chosen.full_name}`; onSelect(chosen); } });
  return { get patient() { return chosen; } };
}
