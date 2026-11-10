import { api } from './api.js';
import { mountSite } from './site.js';
import { CATEGORY, empty, errorBox, errMsg, esc } from './ui.js';
import { procCard } from './proc-card.js';

(async () => {
  await mountSite({ active: '/procedimentos.html' });
  const tabs = document.getElementById('catTabs'), list = document.getElementById('list');
  let all = [], current = 'todos';
  const render = () => {
    tabs.innerHTML = [['todos', 'Todos'], ...Object.entries(CATEGORY).map(([k, v]) => [k, v.label])]
      .map(([k, l]) => `<button class="tab" role="tab" data-cat="${k}" aria-selected="${k === current}">${esc(l)}</button>`).join('');
    const shown = current === 'todos' ? all : all.filter((p) => p.category === current);
    if (!shown.length) { list.innerHTML = empty('Nenhum procedimento nesta categoria', 'Volte em breve.', 'clipboard'); return; }
    if (current !== 'todos') { list.innerHTML = `<div class="cards c3">${shown.map(procCard).join('')}</div>`; return; }
    list.innerHTML = Object.entries(CATEGORY).map(([k, v]) => {
      const items = shown.filter((p) => p.category === k);
      return items.length ? `<h2 class="mt-2" style="font-size:1.35rem">${esc(v.label)}</h2><div class="cards c3">${items.map(procCard).join('')}</div>` : '';
    }).join('');
  };
  tabs.addEventListener('click', (e) => { const b = e.target.closest('[data-cat]'); if (b) { current = b.dataset.cat; render(); } });
  try { all = await api('/publico/procedimentos'); render(); } catch (e) { list.innerHTML = errorBox(errMsg(e)); }
})();
