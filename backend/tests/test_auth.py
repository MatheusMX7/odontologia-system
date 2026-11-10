from sqlalchemy import select

from app.database import SessionLocal
from app.models import AuditLog, Patient, User
from tests.conftest import PASSWORD, _cpf, new_client, uniq

def payload(**over):
    n = uniq()
    base = dict(full_name="Maria da Silva", cpf=_cpf(n), birth_date="1992-04-10", phone="(81) 99999-0000",
                email=f"maria{n}@teste.com", address="Rua das Flores, 100", password=PASSWORD,
                password_confirm=PASSWORD, lgpd_consent=True)
    base.update(over)
    return base


def test_cadastro_ok_define_cookies_seguros_e_senha_argon2():
    c = new_client()
    body = payload()
    r = c.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "paciente" and r.json()["patient_id"]
    set_cookie = " ".join(r.headers.get_list("set-cookie")).lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == body["email"]))
        assert u.password_hash.startswith("$argon2id$")  # nunca texto puro
        p = db.scalar(select(Patient).where(Patient.user_id == u.id))
        assert p.cpf.isdigit() and len(p.cpf) == 11 and p.lgpd_consent_at is not None
        assert db.scalar(select(AuditLog).where(AuditLog.action == "register"))


def test_cadastro_validacoes():
    c = new_client()
    cases = [
        (dict(cpf="111.111.111-11"), "CPF"),
        (dict(email="nao-e-email"), "E-mail"),
        (dict(password="curta1", password_confirm="curta1"), "senha"),
        (dict(password_confirm="Outra1234"), "senhas"),
        (dict(lgpd_consent=False), "consentimento|tratamento"),
        (dict(birth_date="2999-01-01"), "futura"),
        (dict(phone="123"), "Telefone"),
        (dict(full_name="<script>alert(1)</script>"), "não permitidos"),
    ]
    import re
    for over, expected in cases:
        r = c.post("/api/auth/register", json=payload(**over))
        assert r.status_code == 422, (over, r.text)
        assert re.search(expected, r.json()["detail"], re.I), (over, r.json())


def test_cadastro_duplicidade_cpf_e_email():
    c = new_client()
    body = payload()
    assert c.post("/api/auth/register", json=body).status_code == 201
    assert c.post("/api/auth/register", json=payload(cpf=body["cpf"])).status_code == 409
    r = c.post("/api/auth/register", json=payload(email=body["email"]))
    assert r.status_code == 409 and "e-mail" in r.json()["detail"].lower()


def test_login_me_logout(clinic):
    c = new_client()
    r = c.post("/api/auth/login", json={"email": clinic.pat_a_email, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["role"] == "paciente"
    assert c.get("/api/auth/me").json()["email"] == clinic.pat_a_email
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401


def test_login_erro_nao_revela_se_email_existe(clinic):
    c = new_client()
    r1 = c.post("/api/auth/login", json={"email": clinic.pat_a_email, "password": "Errada123"})
    r2 = c.post("/api/auth/login", json={"email": "naoexiste@teste.com", "password": "Errada123"})
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()


def test_bloqueio_apos_varias_tentativas(clinic):
    c = new_client()
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": clinic.pat_a_email, "password": "Errada123"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": clinic.pat_a_email, "password": PASSWORD})
    assert r.status_code == 429  # mesmo com a senha certa, enquanto bloqueado


def test_usuario_inativo_nao_entra(clinic):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == clinic.pat_a_email)); u.is_active = False; db.commit()
    assert new_client().post("/api/auth/login", json={"email": clinic.pat_a_email, "password": PASSWORD}).status_code == 401


def test_sem_login_retorna_401(clinic):
    c = new_client()
    for path in ("/api/pacientes", "/api/agendamentos", "/api/dashboard", "/api/financeiro/resumo", "/api/configuracoes"):
        assert c.get(path).status_code == 401, path


def test_csrf_obrigatorio_em_metodos_que_alteram_dados(clinic):
    c = new_client()
    c.post("/api/auth/login", json={"email": clinic.admin_email, "password": PASSWORD})  # sem header CSRF
    r = c.post("/api/usuarios", json={"full_name": "Nova Recepção", "email": "nova@teste.com", "password": PASSWORD, "role": "recepcionista"})
    assert r.status_code == 403
    c.headers["X-CSRF-Token"] = "token-falso"
    assert c.post("/api/usuarios", json={"full_name": "Nova Recepção", "email": "nova@teste.com", "password": PASSWORD, "role": "recepcionista"}).status_code == 403
    c.headers["X-CSRF-Token"] = c.cookies.get("csrf_token")
    assert c.post("/api/usuarios", json={"full_name": "Nova Recepção", "email": "nova@teste.com", "password": PASSWORD, "role": "recepcionista"}).status_code == 201


def test_rbac_paciente_nao_acessa_area_da_equipe(as_patient_a):
    for path in ("/api/pacientes", "/api/financeiro/resumo", "/api/relatorios/resumo", "/api/configuracoes",
                 "/api/usuarios", "/api/dashboard", "/api/atendimentos/aguardando", "/api/procedimentos", "/api/profissionais"):
        assert as_patient_a.get(path).status_code == 403, path


def test_rbac_recepcao_nao_acessa_financeiro_nem_config(as_recep):
    for path in ("/api/financeiro/resumo", "/api/relatorios/resumo", "/api/configuracoes", "/api/usuarios"):
        assert as_recep.get(path).status_code == 403, path
    assert as_recep.get("/api/pacientes").status_code == 200


def test_troca_de_senha(as_patient_a, clinic):
    assert as_patient_a.post("/api/auth/senha", json={"current_password": "errada", "new_password": "NovaSenha1"}).status_code == 422
    assert as_patient_a.post("/api/auth/senha", json={"current_password": PASSWORD, "new_password": "fraca"}).status_code == 422
    assert as_patient_a.post("/api/auth/senha", json={"current_password": PASSWORD, "new_password": "NovaSenha1"}).status_code == 204
    c = new_client()
    assert c.post("/api/auth/login", json={"email": clinic.pat_a_email, "password": "NovaSenha1"}).status_code == 200


def test_login_aceita_dominio_incomum_ja_cadastrado():
    with SessionLocal() as db:
        from tests.conftest import make_user
        make_user(db, "admin", "admin@clinica.local"); db.commit()   # domínio reservado, mas existente
    c = new_client()
    assert c.post("/api/auth/login", json={"email": "  Admin@Clinica.local ", "password": PASSWORD}).status_code == 200  # normaliza caixa/espaços
    assert c.post("/api/auth/login", json={"email": "admin@clinica.local", "password": PASSWORD}).status_code == 200
