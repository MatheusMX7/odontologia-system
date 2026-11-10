// Gráficos em SVG puro (sem bibliotecas). Valores sempre vêm da API (dados reais).
import { esc, empty } from './ui.js';

const W = 600, H = 230, M = { t: 14, r: 12, b: 30, l: 38 };
function niceMax(v) { if (v <= 4) return 4; const p = 10 ** Math.floor(Math.log10(v)); const n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; }
function frame(labels, max, fmt) {
  const ticks = 4; let g = '';
  for (let i = 0; i <= ticks; i++) {
    const y = M.t + ((H - M.t - M.b) * i) / ticks, val = max - (max * i) / ticks;
    g += `<line class="grid-line" x1="${M.l}" x2="${W - M.r}" y1="${y}" y2="${y}"/><text x="${M.l - 6}" y="${y + 4}" text-anchor="end">${esc(fmt(val))}</text>`;
  }
  const step = Math.max(1, Math.ceil(labels.length / 8));
  labels.forEach((l, i) => {
    if (i % step) return;
    const x = M.l + ((W - M.l - M.r) * (i + 0.5)) / labels.length;
    g += `<text x="${x}" y="${H - 8}" text-anchor="middle">${esc(l)}</text>`;
  });
  return g;
}
const compact = (v) => (v >= 1000 ? (v / 1000).toFixed(v % 1000 ? 1 : 0).replace('.', ',') + 'k' : String(Math.round(v * 10) / 10).replace('.', ','));

export function barChart(el, labels, values, { color = '#2f7be5', fmt = compact, unit = '' } = {}) {
  if (!values.some((v) => v > 0)) { el.innerHTML = empty('Sem dados no período', 'Os registros aparecerão aqui.', 'chart'); return; }
  const max = niceMax(Math.max(...values)), n = values.length, bw = Math.min(34, ((W - M.l - M.r) / n) * 0.62);
  let bars = '';
  values.forEach((v, i) => {
    const h = ((H - M.t - M.b) * v) / max, x = M.l + ((W - M.l - M.r) * (i + 0.5)) / n - bw / 2, y = H - M.b - h;
    bars += `<rect x="${x}" y="${y}" width="${bw}" height="${Math.max(h, 0)}" rx="4" fill="${color}"><title>${esc(labels[i])}: ${esc(fmt(v))}${unit}</title></rect>`;
  });
  el.innerHTML = `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de barras">${frame(labels, max, fmt)}${bars}</svg></div>`;
}

export function lineChart(el, labels, series, { fmt = compact } = {}) {
  if (!series.some((s) => s.values.some((v) => v > 0))) { el.innerHTML = empty('Sem dados no período', 'Os registros aparecerão aqui.', 'chart'); return; }
  const max = niceMax(Math.max(...series.flatMap((s) => s.values))), n = labels.length;
  const px = (i) => M.l + ((W - M.l - M.r) * (i + 0.5)) / n, py = (v) => H - M.b - ((H - M.t - M.b) * v) / max;
  let out = frame(labels, max, fmt);
  series.forEach((s) => {
    const pts = s.values.map((v, i) => `${px(i)},${py(v)}`).join(' ');
    out += `<polygon points="${px(0)},${H - M.b} ${pts} ${px(n - 1)},${H - M.b}" fill="${s.color}" opacity=".08"/><polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`;
    s.values.forEach((v, i) => { out += `<circle cx="${px(i)}" cy="${py(v)}" r="4" fill="#fff" stroke="${s.color}" stroke-width="2.5"><title>${esc(s.name)} — ${esc(labels[i])}: ${esc(fmt(v))}</title></circle>`; });
  });
  const legend = series.length > 1 ? `<div class="row small" style="margin-top:.4rem">${series.map((s) => `<span class="row" style="gap:.35rem"><i style="width:10px;height:10px;border-radius:3px;background:${s.color};display:inline-block"></i>${esc(s.name)}</span>`).join('')}</div>` : '';
  el.innerHTML = `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de linhas">${out}</svg>${legend}</div>`;
}

export function hBars(el, items) {
  if (!items.length) { el.innerHTML = empty('Sem dados no período', 'Os registros aparecerão aqui.', 'chart'); return; }
  const max = Math.max(...items.map((i) => i.count));
  el.innerHTML = items.map((i) => `<div class="hbar"><span>${esc(i.name)}</span><strong>${i.count}</strong><div class="hbar-track"><div class="hbar-fill" style="width:${(i.count / max) * 100}%"></div></div></div>`).join('');
}
