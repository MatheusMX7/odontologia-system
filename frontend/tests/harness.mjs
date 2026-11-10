// Carrega uma página real do frontend em jsdom, contra o servidor FastAPI, e devolve utilitários.
import { JSDOM, VirtualConsole } from 'jsdom';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import fs from 'node:fs';
register('./loader.mjs', import.meta.url);

const BASE = process.env.BASE_URL || 'http://localhost:8000', FRONT = fileURLToPath(new URL('../', import.meta.url)).replace(/\/$/, '');
export const errors = [];
const realFetch = globalThis.fetch.bind(globalThis);
let inflight = 0; const jar = {};

export async function openPage(path, { login } = {}) {
  const html = fs.readFileSync(FRONT + path.split('?')[0], 'utf8');
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { if (!/Not implemented: (navigation|window\.scrollTo|HTMLCanvas)/.test(e.message)) errors.push('jsdom: ' + e.message); });
  vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));
  const dom = new JSDOM(html.replace(/<script[^>]*type="module"[^>]*><\/script>/g, ''), { url: BASE + path, pretendToBeVisual: true, virtualConsole: vc });
  const w = dom.window;
  w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  w.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new w.Event('close')); };
  w.scrollTo = () => {}; w.Element.prototype.scrollIntoView = () => {};
  for (const k of ['window', 'document', 'location', 'HTMLElement', 'Event', 'URLSearchParams', 'DOMParser']) {
    if (k === 'URLSearchParams') continue;
    Object.defineProperty(globalThis, k, { value: k === 'window' ? w : w[k], configurable: true, writable: true });
  }
  globalThis.fetch = async (url, opts = {}) => {
    const u = new URL(url, BASE); inflight++;
    try {
      const headers = { ...(opts.headers || {}), cookie: Object.entries(jar).map(([k, v]) => `${k}=${v}`).join('; ') };
      const res = await realFetch(u, { ...opts, headers });
      for (const c of res.headers.getSetCookie()) {
        const [kv] = c.split(';'); const i = kv.indexOf('='); const k = kv.slice(0, i), v = kv.slice(i + 1);
        if (/max-age=0/i.test(c)) delete jar[k]; else jar[k] = v;
        if (k === 'csrf_token') document.cookie = `csrf_token=${v}`;
      }
      return res;
    } finally { inflight--; }
  };
  if (login) {
    const r = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(login) });
    if (!r.ok) throw new Error('login falhou: ' + login.email);
  }
  const idle = async (ms = 250) => { const t0 = Date.now(); let quiet = 0; while (Date.now() - t0 < 8000) { await new Promise((r) => setTimeout(r, 40)); quiet = inflight === 0 ? quiet + 40 : 0; if (quiet >= ms) return; } throw new Error('timeout aguardando a página ficar ociosa'); };
  const scripts = [...dom.window.document.querySelectorAll('script[src]')].map((s) => s.getAttribute('src'));
  const srcs = [...html.matchAll(/<script type="module" src="([^"]+)"/g)].map((m) => m[1]);
  for (const s of srcs) await import(pathToFileURL(FRONT + s).href);
  await idle(300);
  const $ = (sel) => document.querySelector(sel), $$ = (sel) => [...document.querySelectorAll(sel)];
  const click = async (el) => { if (!el) throw new Error('elemento não encontrado para clicar'); el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true })); await idle(250); };
  const type = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('input', { bubbles: true })); el.dispatchEvent(new w.Event('change', { bubbles: true })); };
  const submit = async (form) => { form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true })); await idle(300); };
  const text = () => document.body.textContent.replace(/\s+/g, ' ');
  return { dom, $, $$, click, type, submit, idle, text, w };
}

let pass = 0, fail = 0;
export function check(name, cond, extra = '') { if (cond) { pass++; console.log('  ✓', name); } else { fail++; console.log('  ✗', name, extra); } }
export function finish() {
  for (const e of errors) { fail++; console.log('  ✗ erro de runtime:', e); }
  console.log(`  => ${pass} ok, ${fail} falhas`); process.exit(fail ? 1 : 0);
}
process.on('unhandledRejection', (e) => { errors.push('unhandledRejection: ' + (e && e.stack || e)); });
