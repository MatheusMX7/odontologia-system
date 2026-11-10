# Sistema Web de Gestão Odontológica

## Comece aqui

O arquivo principal da aplicação é `backend/app/main.py`. Para iniciar o sistema no Windows:

```powershell
cd C:\caminho\odontologia-system\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Acesse `http://127.0.0.1:8000`.

Antes do primeiro uso, prepare o banco:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m app.seed
```

### Mapa rápido

| Local | Responsabilidade |
|---|---|
| `backend/app/main.py` | cria a API e registra as rotas |
| `backend/app/routers/` | endpoints HTTP, separados por módulo |
| `backend/app/models/` | tabelas e relacionamentos do banco |
| `backend/app/schemas/` | validação dos dados recebidos e enviados |
| `backend/app/services/` | regras de negócio reutilizáveis |
| `backend/app/core/` | configurações, segurança, datas e validadores |
| `backend/migrations/` | histórico de alterações do banco |
| `backend/tests/` | testes automatizados |
| `frontend/` | telas HTML, estilos CSS e scripts JavaScript |

Os arquivos `.db`, `.venv`, `__pycache__` e `.pytest_cache` são arquivos locais gerados; não fazem parte do código-fonte.

Portal do paciente e painel administrativo em uma única aplicação FastAPI. O backend serve também os arquivos do frontend.

- **Frontend:** HTML, CSS e JavaScript puro.
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Alembic e Pydantic.
- **Banco local:** SQLite, sem necessidade de instalar ou configurar PostgreSQL.
- **Banco de produção:** PostgreSQL é recomendado para uso real.

## Executar localmente (Windows — caminho mais simples)

Pré-requisito: Python 3.11 ou mais recente.

No PowerShell, na pasta do projeto:

```powershell
cd C:\caminho\odontologia-system
cd backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Abra `backend/.env` e deixe o banco local assim:

```env
ENVIRONMENT=development
DATABASE_URL=sqlite:///./odonto.db
SECRET_KEY=chave-local-de-desenvolvimento
```

Depois crie as tabelas, os procedimentos e o administrador:

```powershell
alembic upgrade head
python -m app.seed
```

O comando `seed` mostra no terminal a senha gerada para `admin@clinica.com.br`. Para definir uma senha própria antes de executar o seed:

```powershell
$env:ADMIN_EMAIL="admin@clinica.com.br"
$env:ADMIN_PASSWORD="SuaSenhaForte123"
python -m app.seed
```

Para criar contas de demonstração (somente desenvolvimento):

```powershell
python -m app.seed --demo
```

Contas demo:

| Perfil | E-mail | Senha |
|---|---|---|
| Recepcionista | `recepcao@demo.clinica.com.br` | `Demo@12345` |
| Dentista | `dentista@demo.clinica.com.br` | `Demo@12345` |
| Paciente | `paciente@demo.clinica.com.br` | `Demo@12345` |

Inicie o servidor:

```powershell
python -m uvicorn app.main:app --reload
```

Acesse:

- Aplicação: http://127.0.0.1:8000
- Documentação da API: http://127.0.0.1:8000/docs

## Executar com PostgreSQL

Para produção, crie um banco PostgreSQL e configure a URL no `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg2://usuario:senha@localhost:5432/odontologia
ENVIRONMENT=production
SECRET_KEY=uma-chave-longa-e-aleatoria
COOKIE_SECURE=true
```

Depois execute `alembic upgrade head` e `python -m app.seed`. Nunca envie o arquivo `.env` para o GitHub.

## Perfis e permissões

- **Administrador:** usuários, profissionais, procedimentos, financeiro, relatórios e configurações.
- **Recepcionista:** pacientes, agendamentos e fila de atendimento, sem acesso ao conteúdo clínico.
- **Dentista:** própria agenda, pacientes atendidos e prontuários autorizados.
- **Paciente:** própria conta e próprios agendamentos.

As permissões são validadas no backend, não apenas ocultadas no frontend.

## Testes

Backend:

```powershell
cd backend
pytest
```

Testes de interface:

```powershell
cd frontend/tests
npm install
npm test
```

## O que não deve ser enviado ao GitHub

O `.gitignore` já exclui:

- `backend/.env`, que contém configurações e segredos;
- `*.db`, incluindo o banco local `odonto.db`;
- `.venv/`, `node_modules/` e caches;
- arquivos enviados pelos usuários em `backend/uploads/`;
- backups e arquivos `.dump`.

O repositório inclui `backend/.env.example` como modelo de configuração.

## Estrutura

```text
backend/app/        código da API
backend/migrations/ migrações do banco
backend/tests/      testes automatizados
frontend/           telas, estilos e JavaScript
```

## Segurança e operação

Para produção, use HTTPS, uma `SECRET_KEY` forte, `COOKIE_SECURE=true`, PostgreSQL com backups e armazenamento persistente para os uploads. Defina também a política de privacidade, retenção dos prontuários e demais requisitos legais da clínica.
