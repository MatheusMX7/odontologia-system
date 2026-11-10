// Helpers de interface reutilizáveis (HTML/CSS/JS nativos).
import { ApiError } from './api.js';

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ---------- Ícones (SVG inline) ---------- */
const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  tooth: '<path d="M7 3C4.5 3 3 5 3 7.5c0 2 1 3 1.5 5 .6 2.4.7 6 2.2 8 .9 1.2 2 .8 2.4-.6.4-1.6.7-4 2.9-4s2.500 2.400 2.900 4c.4 1.400 1.500 1.800 2.400.6 1.500-2 1.600-5.600 2.200-8 .5-2 1.500-3 1.500-5C21 5 19.500 3 17 3c-1.800 0-2.800.9-5 .9S8.800 3 7 3z"/>',
  clipboard: '<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6M9 16h4"/>',
  userCheck: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  dollar: '<path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
  chart: '<path d="M18 20V10M12 20V4M6 20v-6"/>',
  settings: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  menu: '<path d="M3 12h18M3 6h18M3 18h18"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>', check: '<path d="M20 6 9 17l-5-5"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.800 19.800 0 0 1-8.600-3.100 19.500 19.500 0 0 1-6-6A19.800 19.800 0 0 1 2.100 4.200 2 2 0 0 1 4.100 2h3a2 2 0 0 1 2 1.700c.1 1 .4 1.900.7 2.800a2 2 0 0 1-.5 2.100L8.100 9.900a16 16 0 0 0 6 6l1.300-1.300a2 2 0 0 1 2.100-.4c.9.3 1.800.6 2.800.7a2 2 0 0 1 1.700 2z"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
  pin: '<path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  edit: '<path d="M12 20h9M16.500 3.500a2.100 2.100 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  trash: '<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>',
  smile: '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.500 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/>',
  scissors: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.100 15.900M14.500 14.500 20 20M8.100 8.100 12 12"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
  eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  alert: '<path d="M10.300 3.900 1.800 18a2 2 0 0 0 1.700 3h17a2 2 0 0 0 1.700-3L13.700 3.900a2 2 0 0 0-3.400 0zM12 9v4M12 17h.01"/>',
};
export function icon(name, size = 20) {
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}
export const CATEGORY = {
  geral: { label: 'Procedimentos gerais', icon: 'tooth' }, estetico: { label: 'Procedimentos estéticos', icon: 'smile' },
  cirurgia: { label: 'Cirurgias e extrações', icon: 'scissors' }, ortodontia: { label: 'Ortodontia', icon: 'layers' },
};
export const logoMark = (size = 22) => icon('tooth', size);

/* ---------- Datas, números, status ---------- */
export function parseISO(s) {
  if (!s) return null;
  if (s.length === 10) { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); }
  return new Date(s);
}
export const pad = (n) => String(n).padStart(2, '0');
export const toISODate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const fmtDate = (s) => (s ? parseISO(s).toLocaleDateString('pt-BR') : '—');
export const fmtTime = (s) => { const d = parseISO(s); return d ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : '—'; };
export const fmtDateTime = (s) => (s ? `${fmtDate(s.slice(0, 10))} ${fmtTime(s)}` : '—');
export const fmtMoney = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
export const WEEKDAYS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
export const longDate = (s) => parseISO(s).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' });

export const STATUS = {
  pendente: ['Pendente', 'warning'], confirmado: ['Confirmado', 'info'], em_atendimento: ['Em atendimento', 'purple'],
  concluido: ['Concluído', 'success'], cancelado: ['Cancelado', 'danger'], nao_compareceu: ['Não compareceu', 'muted'],
};
export const statusBadge = (s) => { const [l, c] = STATUS[s] || [s, 'muted']; return `<span class="badge badge-${c}">${esc(l)}</span>`; };
export const METHODS = { dinheiro: 'Dinheiro', pix: 'Pix', cartao_credito: 'Cartão de crédito', cartao_debito: 'Cartão de débito', transferencia: 'Transferência', outro: 'Outro' };
export const PAY_STATUS = { pendente: ['Pendente', 'warning'], pago: ['Pago', 'success'], cancelado: ['Cancelado', 'muted'] };
export const payBadge = (s) => { const [l, c] = PAY_STATUS[s] || [s, 'muted']; return `<span class="badge badge-${c}">${l}</span>`; };

/* ---------- CPF / telefone ---------- */
export const digits = (s) => String(s || '').replace(/\D/g, '');
export function maskCPF(v) { const d = digits(v).slice(0, 11); return d.replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d{1,2})$/, '$1-$2'); }
export function maskPhone(v) { const d = digits(v).slice(0, 11); if (d.length <= 10) return d.replace(/(\d{2})(\d)/, '($1) $2').replace(/(\d{4})(\d)/, '$1-$2'); return d.replace(/(\d{2})(\d)/, '($1) $2').replace(/(\d{5})(\d)/, '$1-$2'); }
export const fmtCPF = (v) => maskCPF(v);
export const fmtPhone = (v) => maskPhone(v);
export function validCPF(v) {
  const d = digits(v);
  if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
  for (const n of [9, 10]) {
    let s = 0; for (let i = 0; i < n; i++) s += Number(d[i]) * (n + 1 - i);
    if (((s * 10) % 11) % 10 !== Number(d[n])) return false;
  }
  return true;
}
export function calcAge(iso) {
  const b = parseISO(iso), t = new Date();
  let a = t.getFullYear() - b.getFullYear();
  if (t.getMonth() < b.getMonth() || (t.getMonth() === b.getMonth() && t.getDate() < b.getDate())) a--;
  return a;
}
export function applyMasks(root = document) {
  root.querySelectorAll('[data-mask]').forEach((el) => {
    if (el.dataset.maskReady) return; el.dataset.maskReady = '1';
    const fn = el.dataset.mask === 'cpf' ? maskCPF : maskPhone;
    el.value = fn(el.value);
    el.addEventListener('input', () => { el.value = fn(el.value); });
  });
}
export function debounce(fn, ms = 300) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

/* ---------- Feedback ---------- */
export function toast(message, type = 'info') {
  let box = document.getElementById('toasts');
  if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.setAttribute('role', 'status'); box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
  const t = document.createElement('div'); t.className = 'toast ' + type;
  t.innerHTML = `${icon(type === 'error' ? 'alert' : type === 'success' ? 'check' : 'eye', 18)}<span>${esc(message)}</span>`;
  box.appendChild(t); setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, type === 'error' ? 6000 : 3500);
}
export const errMsg = (e) => (e instanceof ApiError ? e.message : 'Ocorreu um erro inesperado.');
export const spinner = () => '<div class="spinner" role="status" aria-label="Carregando"></div>';
export const empty = (title, text = '', ic = 'file') => `<div class="empty">${icon(ic, 40)}<strong>${esc(title)}</strong><span>${esc(text)}</span></div>`;
export const errorBox = (msg) => `<div class="alert alert-danger" role="alert">${icon('alert', 18)}<span>${esc(msg)}</span></div>`;
export function setLoading(btn, on) { btn.classList.toggle('loading', on); btn.disabled = on; }

/* ---------- Tabela responsiva (vira cartões no celular) ---------- */
export function table(columns, rows, emptyHtml) {
  if (!rows.length) return emptyHtml || empty('Nenhum registro encontrado');
  const head = columns.map((c) => `<th scope="col">${esc(c.label)}</th>`).join('');
  const body = rows.map((r) => `<tr>${columns.map((c) => {
    const cls = [c.actions ? 'actions' : '', c.strong ? 'strong' : ''].filter(Boolean).join(' ');
    return `<td data-label="${esc(c.label)}"${cls ? ` class="${cls}"` : ''}>${c.render(r)}</td>`;
  }).join('')}</tr>`).join('');
  return `<div class="table-wrap"><table class="table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

/* ---------- Modal nativo (<dialog>) ---------- */
export function openModal({ title, body = '', footer = '', wide = false }) {
  const dlg = document.createElement('dialog');
  dlg.className = 'modal' + (wide ? ' wide' : '');
  dlg.innerHTML = `<div class="modal-head"><h3>${esc(title)}</h3><button type="button" class="icon-btn" data-close aria-label="Fechar">${icon('x')}</button></div>
    <div class="modal-body">${body}</div>${footer ? `<div class="modal-foot">${footer}</div>` : ''}`;
  document.body.appendChild(dlg);
  const close = () => { dlg.close(); };
  dlg.addEventListener('click', (e) => { if (e.target === dlg || e.target.closest('[data-close]')) close(); });
  dlg.addEventListener('close', () => dlg.remove());
  dlg.showModal();
  return { dlg, close, body: dlg.querySelector('.modal-body'), foot: dlg.querySelector('.modal-foot') };
}

export function confirmDialog(message, { title = 'Confirmar', confirmText = 'Confirmar', danger = false } = {}) {
  return new Promise((resolve) => {
    const m = openModal({ title, body: `<p>${esc(message)}</p>`, footer: `<button class="btn btn-ghost" data-close>Voltar</button><button class="btn ${danger ? 'btn-danger' : ''}" id="cfOk">${esc(confirmText)}</button>` });
    let done = false;
    m.dlg.querySelector('#cfOk').addEventListener('click', () => { done = true; m.close(); });
    m.dlg.addEventListener('close', () => resolve(done));
  });
}

/* Formulário em modal gerado a partir de definição de campos */
export function fieldHTML(f, value) {
  const v = value ?? f.value ?? '';
  const id = 'f_' + f.name, req = f.required ? ' <span class="req" aria-hidden="true">*</span>' : '';
  const common = `id="${id}" name="${f.name}"${f.required ? ' required' : ''}`;
  let input;
  if (f.type === 'select') input = `<select ${common}>${f.placeholder !== undefined ? `<option value="">${esc(f.placeholder)}</option>` : ''}${f.options.map((o) => `<option value="${esc(o.value)}"${String(o.value) === String(v) ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
  else if (f.type === 'textarea') input = `<textarea ${common}${f.maxlength ? ` maxlength="${f.maxlength}"` : ''}>${esc(v)}</textarea>`;
  else if (f.type === 'checkbox') return `<div class="field ${f.full ? 'full' : ''}"><label class="check"><input type="checkbox" name="${f.name}"${v ? ' checked' : ''}> <span>${esc(f.label)}</span></label></div>`;
  else if (f.type === 'checkboxes') {
    const sel = new Set((v || []).map(String));
    return `<div class="field full"><span class="label">${esc(f.label)}</span><div class="checks">${f.options.length ? f.options.map((o) => `<label class="check"><input type="checkbox" name="${f.name}" value="${esc(o.value)}"${sel.has(String(o.value)) ? ' checked' : ''}> <span>${esc(o.label)}</span></label>`).join('') : '<span class="muted small">Nenhum item disponível.</span>'}</div></div>`;
  } else if (f.type === 'file') input = `<input ${common.replace(' required', '')} type="file" accept="${f.accept || 'image/png,image/jpeg,image/webp'}">`;
  else input = `<input ${common} type="${f.type || 'text'}" value="${esc(v)}"${f.mask ? ` data-mask="${f.mask}"` : ''}${f.min !== undefined ? ` min="${f.min}"` : ''}${f.max !== undefined ? ` max="${f.max}"` : ''}${f.step ? ` step="${f.step}"` : ''}${f.maxlength ? ` maxlength="${f.maxlength}"` : ''}${f.autocomplete ? ` autocomplete="${f.autocomplete}"` : ''}>`;
  return `<div class="field ${f.full ? 'full' : ''}"><label for="${id}">${esc(f.label)}${req}</label>${input}${f.help ? `<span class="field-help">${esc(f.help)}</span>` : ''}<span class="field-error" data-err="${f.name}" role="alert"></span></div>`;
}

export function collectForm(form, fields) {
  const out = {};
  fields.forEach((f) => {
    if (f.type === 'checkbox') out[f.name] = form.elements[f.name].checked;
    else if (f.type === 'checkboxes') out[f.name] = [...form.querySelectorAll(`input[name="${f.name}"]:checked`)].map((i) => i.value);
    else if (f.type === 'file') out[f.name] = form.elements[f.name].files[0] || null;
    else if (f.type === 'number') out[f.name] = form.elements[f.name].value === '' ? null : Number(form.elements[f.name].value);
    else out[f.name] = form.elements[f.name].value.trim();
  });
  return out;
}

export function showFieldErrors(form, e) {
  form.querySelectorAll('[aria-invalid]').forEach((i) => i.removeAttribute('aria-invalid'));
  form.querySelectorAll('.field-error').forEach((s) => { s.textContent = ''; });
  let any = false;
  (e.errors || []).forEach((er) => {
    const slot = form.querySelector(`[data-err="${er.field}"]`);
    if (slot) { slot.textContent = er.message; const inp = form.elements[er.field]; if (inp && inp.setAttribute) inp.setAttribute('aria-invalid', 'true'); any = true; }
  });
  return any;
}

export function modalForm({ title, fields, values = {}, submitText = 'Salvar', onSubmit, wide = false, intro = '' }) {
  const body = `${intro}<form id="mf" novalidate><div class="alert alert-danger" id="mfErr" role="alert" hidden></div><div class="form-grid cols-2 ${intro ? 'mt' : ''}">${fields.map((f) => fieldHTML(f, values[f.name])).join('')}</div></form>`;
  const m = openModal({ title, body, wide, footer: `<button type="button" class="btn btn-ghost" data-close>Cancelar</button><button type="submit" class="btn" form="mf" id="mfSave">${esc(submitText)}</button>` });
  const form = m.dlg.querySelector('#mf'), err = m.dlg.querySelector('#mfErr'), btn = m.dlg.querySelector('#mfSave');
  applyMasks(form);
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault(); err.hidden = true;
    for (const f of fields) {
      if (f.required && f.type !== 'checkbox' && f.type !== 'checkboxes' && f.type !== 'file' && !form.elements[f.name].value.trim()) {
        showFieldErrors(form, { errors: [{ field: f.name, message: `${f.label} é obrigatório.` }] }); form.elements[f.name].focus(); return;
      }
    }
    setLoading(btn, true);
    try { await onSubmit(collectForm(form, fields), m); }
    catch (e) {
      if (!showFieldErrors(form, e) || !(e.errors || []).length) { err.textContent = errMsg(e); err.hidden = false; }
      else { err.textContent = e.message; err.hidden = false; }
    } finally { setLoading(btn, false); }
  });
  return m;
}
