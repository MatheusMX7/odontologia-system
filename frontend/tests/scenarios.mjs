import { openPage, check, finish } from './harness.mjs';
const [, , name] = process.argv;
const ADMIN = { email: 'admin@clinica.com.br', password: 'Admin@12345' }, PAC = { email: 'paciente@demo.clinica.com.br', password: 'Demo@12345' },
  DENT = { email: 'dentista@demo.clinica.com.br', password: 'Demo@12345' }, REC = { email: 'recepcao@demo.clinica.com.br', password: 'Demo@12345' };
function nextWeekday(minDays) { const d = new Date(); d.setDate(d.getDate() + minDays); while ([0, 6].includes(d.getDay())) d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); }
const S = {};

S.home = async () => {
  const p = await openPage('/index.html');
  check('cabeçalho renderizado com marca', p.$('.site-header .brand-name'));
  check('seção de procedimentos populares tem cartões (dados do banco)', p.$$('#popular .proc-card').length >= 1, p.$('#popular').textContent);
  check('equipe carregada', p.$$('#team .pro-card').length >= 1);
  check('contato renderizado', p.$$('#contact .feature').length === 4);
  check('CTA de agendamento', p.$('#ctaSchedule').getAttribute('href') === '/agendamento.html');
  check('menu mobile alterna', (await p.click(p.$('#navToggle')), p.$('#siteNav').classList.contains('open')));
};
S.procedimentos = async () => {
  const p = await openPage('/procedimentos.html');
  check('14 procedimentos do catálogo listados', p.$$('.proc-card').length === 14, String(p.$$('.proc-card').length));
  check('4 categorias + todos nas abas', p.$$('#catTabs .tab').length === 5);
  await p.click(p.$$('#catTabs .tab')[4]);
  check('filtro Ortodontia mostra 3', p.$$('.proc-card').length === 3, String(p.$$('.proc-card').length));
};
S.login = async () => {
  const p = await openPage('/login.html');
  p.$('#email').value = 'x@y.com'; p.$('#password').value = 'errada';
  await p.submit(p.$('#form'));
  check('login inválido mostra mensagem', !p.$('#err').hidden && /incorretos/.test(p.$('#err').textContent), p.$('#err').textContent);
  const q = await openPage('/login.html');
};
S.cadastro = async () => {
  const p = await openPage('/cadastro.html');
  await p.submit(p.$('#form'));
  check('cadastro vazio mostra erros por campo', p.$$('.field-error').filter((e) => e.textContent).length >= 6);
  p.$('#full_name').value = 'Fulano de Tal'; p.type(p.$('#cpf'), '11111111111');
  await p.submit(p.$('#form'));
  check('CPF inválido é recusado no frontend', /CPF inválido/.test(p.$('[data-err=cpf]').textContent));
  p.type(p.$('#cpf'), '52998224725'); check('máscara de CPF aplicada', p.$('#cpf').value === '529.982.247-25', p.$('#cpf').value);
  p.type(p.$('#birth_date'), '2000-06-15'); check('idade calculada automaticamente', /Idade: \d+ anos/.test(p.$('#age').textContent));
};
S.portal = async () => {
  const p = await openPage('/portal/dashboard.html', { login: PAC });
  check('dashboard do paciente com saudação', /Olá, \[DEMO\]/.test(p.$('h1').textContent), p.$('h1')?.textContent);
  check('3 cards de indicadores', p.$$('.stat').length === 3);
  const perfil = await openPage('/portal/perfil.html', { login: PAC });
  check('perfil mostra CPF formatado', /529\.982\.247-25/.test(perfil.text()));
};
S.fluxo = async () => {
  const p = await openPage('/agendamento.html', { login: PAC });
  check('etapa 1 lista procedimentos', p.$$('.option').length >= 10, String(p.$$('.option').length));
  check('stepper com 4 etapas', p.$$('.step').length === 4);
  await p.click(p.$$('.option')[0]);
  check('etapa 2 lista profissional + sem preferência', p.$$('.option').length >= 2 && /Sem preferência/.test(p.text()));
  await p.click(p.$$('.option')[0]);
  check('etapa 3 mostra seletor de data', !!p.$('#spDate'));
  p.type(p.$('#spDate'), nextWeekday(3)); await p.idle(400);
  const slots = p.$$('.slot'); check('horários disponíveis carregados do backend', slots.length >= 4, String(slots.length));
  check('botão continuar começa desabilitado', p.$('#next').disabled);
  await p.click(slots[2]); check('selecionar horário habilita continuar', !p.$('#next').disabled);
  await p.click(p.$('#next'));
  check('etapa 4 resume os dados', /Procedimento/.test(p.text()) && /Enviar solicitação/.test(p.text()));
  await p.click(p.$('#send'));
  check('solicitação enviada com sucesso', /Solicitação enviada|Consulta confirmada/.test(p.text()), p.text().slice(-200));
};
S.meus = async () => {
  const p = await openPage('/portal/meus-agendamentos.html', { login: PAC });
  check('lista o agendamento criado', p.$$('.appt-card').length >= 1, p.text().slice(0, 200));
  check('pendente aguardando aprovação', /Aguardando aprovação/.test(p.text()));
  check('botões cancelar/reagendar presentes', p.$('[data-act=cancel]') && p.$('[data-act=resched]'));
  await p.click(p.$('[data-act=resched]'));
  check('modal de reagendamento abre com seletor', !!p.$('dialog[open] #spDate'));
};
S.dashboard = async () => {
  const p = await openPage('/admin/dashboard.html', { login: ADMIN });
  check('menu admin com 9 itens', p.$$('.nav a').length === 9, String(p.$$('.nav a').length));
  check('6 cards de indicadores', p.$$('.stats .stat').length >= 6);
  check('gráficos renderizados (SVG ou estado vazio)', p.$$('.chart svg').length >= 1 && p.$$('#c1,#c2,#c3,#c4,#c5').every((e) => e.children.length > 0));
  check('agenda de hoje presente com filtros', !!p.$('#agTable') && !!p.$('#fq'));
  check('indicadores financeiros (admin)', /Recebido/.test(p.text()));
};
S.dashdent = async () => {
  const d = await openPage('/admin/dashboard.html', { login: DENT });
  check('dentista vê menu reduzido (4)', d.$$('.nav a').length === 4, String(d.$$('.nav a').length));
  check('dentista não vê financeiro', !/Recebido/.test(d.text()));
  check('dentista vê agenda e cards', d.$$('.stats .stat').length >= 6);
};
S.dashrec = async () => {
  const r = await openPage('/admin/dashboard.html', { login: REC });
  check('recepcionista vê menu reduzido (4)', r.$$('.nav a').length === 4, String(r.$$('.nav a').length));
  check('recepcionista não vê financeiro', !/Recebido/.test(r.text()));
};
S.agenda = async () => {
  const p = await openPage('/admin/agendamentos.html', { login: ADMIN });
  check('tabela lista agendamentos', p.$$('.table tbody tr').length >= 1, p.text().slice(0, 300));
  const conf = p.$('[data-act=confirm]'); check('botão confirmar para pendente', !!conf);
  if (conf) { await p.click(conf); await p.idle(400); check('confirmação altera status', /Confirmado/.test(p.text())); }
  await p.click(p.$('[data-v=calendario]'));
  check('calendário mensal renderizado', p.$$('.cal-day').length >= 28);
  check('dia com consultas mostra contador', p.$$('.cal-count').length >= 1);
  await p.click(p.$('#add'));
  check('modal novo agendamento abre', !!p.$('dialog[open] #np') && !!p.$('dialog[open] #ppQ'));
};
S.pacientes = async () => {
  const p = await openPage('/admin/pacientes.html', { login: ADMIN });
  check('lista pacientes', p.$$('.table tbody tr').length >= 1);
  await p.click(p.$('[data-act=ficha]'));
  check('ficha abre com agendamentos e prontuário', /Agendamentos futuros/.test(p.text()) && /Abrir prontuário/.test(p.text()));
  p.$('dialog[open] [data-close]').dispatchEvent(new p.w.MouseEvent('click', { bubbles: true }));
  await p.click(p.$('#add'));
  check('modal novo paciente com 6 campos', p.$$('dialog[open] .field input').length >= 6);
  p.type(p.$('dialog[open] [name=cpf]'), '11111111111'); await p.submit(p.$('dialog[open] form'));
  check('obrigatórios validados no modal', /obrigatório/.test(p.$('dialog[open]').textContent));
};
S.procs = async () => {
  const p = await openPage('/admin/procedimentos.html', { login: ADMIN });
  check('14 procedimentos', p.$$('.table tbody tr').length === 14, String(p.$$('.table tbody tr').length));
  await p.click(p.$('[data-act=edit]'));
  check('edição com campos e vínculo de profissionais', !!p.$('dialog[open] [name=duration_minutes]') && p.$$('dialog[open] input[name=professional_ids]').length >= 1);
};
S.pros = async () => {
  const p = await openPage('/admin/profissionais.html', { login: ADMIN });
  check('lista profissional demo', p.$$('.table tbody tr').length >= 1);
  await p.click(p.$('[data-act=sched]'));
  check('modal de horários com 7 dias', p.$$('dialog[open] [data-day]').length === 7);
};
S.resto = async () => {
  const a = await openPage('/admin/atendimentos.html', { login: ADMIN }); check('atendimentos carrega', /Hoje/.test(a.text()) && /Histórico/.test(a.text()));
  await a.click(a.$$('[data-t]')[1]); check('histórico com filtros', !!a.$('#hi'));
  const f = await openPage('/admin/financeiro.html', { login: ADMIN }); check('financeiro: cards e gráfico', f.$$('.stat').length >= 2 && /Valores por procedimento/.test(f.text()));
  await f.click(f.$('#add')); check('modal de pagamento com busca de paciente', !!f.$('dialog[open] #ppQ'));
  const r = await openPage('/admin/relatorios.html', { login: ADMIN }); check('relatórios: 6 cards + exportações', r.$$('.stat').length >= 6 && !!r.$('#pdf') && !!r.$('#xlsx'));
  const c = await openPage('/admin/configuracoes.html', { login: ADMIN });
  check('configurações: formulário e usuários', !!c.$('#cf') && c.$$('#users .table tbody tr').length >= 1);
  await c.submit(c.$('#cf')); check('salvar configurações funciona', !c.$('#err') || c.$('#err').hidden, c.$('#err')?.textContent);
};
await S[name]();
finish();
