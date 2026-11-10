// Cliente HTTP: Fetch API + JSON, cookie HttpOnly de sessão e cabeçalho CSRF.
const API_BASE = '/api';

export class ApiError extends Error {
  constructor(message, status, errors) { super(message); this.status = status; this.errors = errors || []; }
}

function cookie(name) {
  const hit = document.cookie.split('; ').find((r) => r.startsWith(name + '='));
  return hit ? decodeURIComponent(hit.split('=')[1]) : '';
}

function buildUrl(path, params) {
  const qs = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.append(k, v); });
  const s = qs.toString();
  return API_BASE + path + (s ? '?' + s : '');
}

async function request(path, { method = 'GET', body, params, formData } = {}) {
  const headers = {};
  const opts = { method, headers, credentials: 'same-origin' };
  if (formData) opts.body = formData;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  if (method !== 'GET') { const t = cookie('csrf_token'); if (t) headers['X-CSRF-Token'] = t; }
  let res;
  try { res = await fetch(buildUrl(path, params), opts); }
  catch { throw new ApiError('Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.', 0); }
  return res;
}

export async function api(path, options = {}) {
  const res = await request(path, options);
  if (res.status === 204) return null;
  const isJson = (res.headers.get('content-type') || '').includes('application/json');
  const data = isJson ? await res.json() : null;
  if (!res.ok) {
    const expected401 = path.startsWith('/auth/login') || path === '/auth/me';
    if (res.status === 401 && !expected401) {
      location.href = '/login.html?expirou=1&next=' + encodeURIComponent(location.pathname + location.search);
    }
    throw new ApiError((data && data.detail) || 'Ocorreu um erro inesperado. Tente novamente.', res.status, data && data.errors);
  }
  return data;
}

export async function download(path, params, fallbackName) {
  const res = await request(path, { params });
  if (!res.ok) {
    let msg = 'Não foi possível gerar o arquivo.';
    try { msg = (await res.json()).detail || msg; } catch { /* ignore */ }
    throw new ApiError(msg, res.status);
  }
  const blob = await res.blob();
  const cd = res.headers.get('content-disposition') || '';
  const name = (cd.match(/filename="?([^"]+)"?/) || [])[1] || fallbackName;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
