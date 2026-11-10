# Sistema Web de Gestão Odontológica

Portal do paciente + painel administrativo, com o mesmo backend e banco de dados.

- **Frontend:** HTML5, CSS3 e JavaScript puro (módulos ES nativos). Sem frameworks, sem jQuery, sem Bootstrap/Tailwind. Gráficos em SVG próprio, nenhuma biblioteca externa (apenas a fonte Manrope, do Google Fonts, com *fallback* de sistema).
- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, API REST (documentação automática em `/docs`).
- **Banco:** PostgreSQL.

## Como executar

Requisitos: Python 3.11+ e PostgreSQL 14+.

```bash
# 1. Banco
createdb odontologia            # ou: psql -c "CREATE DATABASE odontologia;"

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ajuste DATABASE_URL e gere um SECRET_KEY forte
alembic upgrade head            # cria as tabelas
python -m app.seed              # perfis, configurações, catálogo de procedimentos e 1 administrador
uvicorn app.main:app --reload
```

Abra **http://localhost:8000** (o próprio FastAPI serve a pasta `frontend/`; a API fica em `/api`, a documentação em `/docs`).

O `seed` imprime a senha do administrador (e-mail padrão `admin@clinica.com.br`). Para definir você mesmo:
`ADMIN_EMAIL=voce@clinica.com.br ADMIN_PASSWORD='SenhaForte123' python -m app.seed`.

**Dados de demonstração (somente desenvolvimento):** `python -m app.seed --demo` cria recepcionista, dentista (com agenda seg–sex) e paciente, todos identificados com `[DEMO]` e senha `Demo@12345`. Nunca use em produção.

> Os procedimentos do catálogo são criados com **valor R$ 0,00**. Defina os valores em *Painel → Procedimentos* (o valor gera a cobrança ao finalizar um atendimento). Cadastre também os profissionais, os horários de cada um e os dados da clínica em *Configurações*.

## Perfis e permissões (RBAC aplicado no backend)

| Perfil | Pode |
|---|---|
| Administrador | tudo: usuários, profissionais, procedimentos, financeiro, relatórios, configurações |
| Recepcionista | pacientes, agendamentos (criar, confirmar, reagendar, cancelar), fila de atendimento (sem conteúdo clínico) |
| Dentista | a própria agenda, pacientes que atende, iniciar/finalizar atendimentos, prontuário dos seus pacientes |
| Paciente | apenas a própria conta e os próprios agendamentos |

Ocultar menus no frontend é só conveniência: **cada endpoint valida o perfil** (`require_roles`). Paciente acessando dado de outro recebe 404/403.

## Regras de agendamento

Os horários livres são calculados **no servidor**: jornada do profissional, intervalo de almoço, bloqueios (férias/feriados), duração do procedimento, dias de atendimento da clínica, antecedência máxima, passado e reservas existentes. Cancelado e "não compareceu" liberam o horário.

Reservas simultâneas são protegidas em **duas camadas**: `SELECT … FOR UPDATE` no profissional (serializa as transações) e um **índice único parcial** no banco `(profissional, início) WHERE status ativo`. Há teste com 8 requisições simultâneas para o mesmo horário: 1 vence, 7 recebem 409.

Paciente: cancelamento/reagendamento respeitam a antecedência mínima configurada. Confirmação automática ou manual é configurável; agendamento feito pela recepção já nasce confirmado. Início e conclusão de atendimento só acontecem pelo módulo *Atendimentos* (agendamento e atendimento são registros distintos).

## Segurança e LGPD — o que já está implementado

- Senhas com **Argon2id**; nunca em texto puro. Política: 8+ caracteres com letras e números.
- Sessão em cookie **HttpOnly + SameSite** (`Secure` via `COOKIE_SECURE=true`), **proteção CSRF** (token assinado dentro do JWT, enviado em `X-CSRF-Token`).
- Bloqueio temporário após tentativas de login falhas; mensagem de erro não revela se o e-mail existe.
- SQL Injection: apenas ORM/consultas parametrizadas. XSS: toda saída é escapada no frontend + CSP restritiva + validação de entrada (rejeita `<` `>` em nomes).
- Upload de imagens valida extensão, tamanho (2 MB) e a assinatura real do arquivo.
- Consentimento LGPD registrado no cadastro (`lgpd_consent_at`); coleta mínima de dados.
- **Prontuário (dado sensível de saúde):** só dentista responsável e administrador; recepção e pacientes não acessam. Toda leitura/escrita gera registro em `audit_logs`, assim como login, alterações cadastrais, cancelamentos, pagamentos etc.
- Exclusão **lógica** (histórico preservado). Procedimento/profissional com histórico não podem ser excluídos, apenas desativados.

### O que depende de você (operação)

- **HTTPS em produção** (proxy reverso, ex.: nginx/Caddy), `COOKIE_SECURE=true`, `ENVIRONMENT=production` e `SECRET_KEY` forte (a aplicação recusa iniciar em produção com a chave padrão).
- **Backups:** `backend/scripts/backup.sh` (`pg_dump` + rotação por `KEEP_DAYS`); agende no cron e teste a restauração.
- **Retenção e descarte:** defina com a clínica por quanto tempo guardar prontuários e logs e descarte com segurança. Prontuários odontológicos normalmente têm prazo legal mínimo de guarda; confirme com o conselho profissional/jurídico.
- **Base legal, política de privacidade, encarregado (DPO) e termos** precisam ser definidos pela clínica com apoio jurídico. O sistema oferece o registro do consentimento, mas não substitui essa análise.
- Limitador de login é em memória (1 processo). Com vários *workers*, use Redis ou limite no proxy.

Exemplo mínimo de nginx (frontend estático + API):
```nginx
location /api/     { proxy_pass http://127.0.0.1:8000; proxy_set_header X-Forwarded-For $remote_addr; }
location /uploads/ { proxy_pass http://127.0.0.1:8000; }
location /         { root /caminho/frontend; try_files $uri $uri/ =404; }
```

## Testes

```bash
cd backend
pytest                                            # SQLite (rápido, portátil)
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/odontologia_test pytest   # PostgreSQL (inclui o teste de concorrência)

# Interface (Node + jsdom, carrega as páginas reais contra o servidor): requer `seed --demo`
cd frontend/tests && npm install && bash run.sh
```

72 testes de backend (regras de negócio, RBAC, CSRF, auditoria, concorrência, exportações) e 61 verificações de interface. Os testes de interface usam jsdom: validam estrutura, fluxos e dados, **mas não substituem uma conferência visual em navegador real**. A responsividade foi construída *mobile-first* (7 `@media (min-width)`, nenhuma `max-width`), mas vale abrir no celular/tablet e redimensionar a janela.

## Estrutura

```
backend/app/{core,models,schemas,routers,services,dependencies}  ·  migrations/  ·  tests/  ·  scripts/
frontend/{index,login,cadastro,agendamento,procedimentos}.html  ·  portal/  ·  admin/  ·  css/  ·  js/  ·  tests/
```

## Limitações conhecidas

- Datas/horas da agenda são horário local da clínica (`TIMEZONE`, padrão `America/Recife`), sem fuso por registro.
- Paciente cadastrado pela recepção não consegue "assumir" o cadastro pelo portal (CPF/e-mail já existem). Evita sequestro de cadastro; resolver exige um fluxo de verificação por e-mail, não incluído.
- Não há envio de e-mail/WhatsApp (lembretes, recuperação de senha). Recuperação de senha hoje é feita por um administrador.
- Imagens enviadas ficam em disco local (`backend/uploads`); em produção use volume persistente ou armazenamento de objetos.
- O dashboard agrega em Python (adequado para uma clínica; para volumes muito grandes, mova para SQL/materializações).
