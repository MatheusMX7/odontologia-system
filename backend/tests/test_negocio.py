import threading
from datetime import datetime, time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.timeutils import now_local
from app.database import SessionLocal
from app.models import Appointment, AuditLog, MedicalRecord, Patient, Payment, Procedure, Professional
from tests.conftest import (IS_PG, future_day, iso, login, make_appt, make_patient, make_procedure, new_client)


def today_appt(clinic, status="confirmado"):
    with SessionLocal() as db:
        a = make_appt(db, db.get(Patient, clinic.pat_a_id), db.get(Professional, clinic.prof_id),
                      db.get(Procedure, clinic.proc_id), datetime.combine(now_local().date(), time(9)), status)
        db.commit()
        return a.id


# ---------- Atendimentos e prontuário ----------
def test_fluxo_de_atendimento_gera_registro_clinico_e_cobranca(clinic, as_dentist, as_recep):
    ap = today_appt(clinic)
    assert as_recep.get("/api/atendimentos/aguardando").json()[0]["appointment_id"] == ap
    assert as_recep.post("/api/atendimentos/iniciar", json={"appointment_id": ap}).status_code == 403
    att = as_dentist.post("/api/atendimentos/iniciar", json={"appointment_id": ap})
    assert att.status_code == 201 and att.json()["status"] == "em_atendimento"
    att_id = att.json()["attendance_id"]
    assert as_dentist.post("/api/atendimentos/iniciar", json={"appointment_id": ap}).status_code == 422
    r = as_dentist.post(f"/api/atendimentos/{att_id}/finalizar", json={"observations": "Cárie no 36 tratada."})
    assert r.status_code == 200 and r.json()["status"] == "concluido"
    assert as_dentist.post(f"/api/atendimentos/{att_id}/finalizar", json={}).status_code == 422
    with SessionLocal() as db:
        pay = db.scalar(select(Payment).where(Payment.appointment_id == ap))
        assert pay.status == "pendente" and float(pay.amount) == 100.0
        assert db.scalar(select(MedicalRecord).where(MedicalRecord.attendance_id == att_id)).content.startswith("Cárie")


def test_nao_inicia_atendimento_pendente_ou_de_outro_dia(clinic, as_dentist):
    assert as_dentist.post("/api/atendimentos/iniciar", json={"appointment_id": today_appt(clinic, "pendente")}).status_code == 422
    with SessionLocal() as db:
        a = make_appt(db, db.get(Patient, clinic.pat_a_id), db.get(Professional, clinic.prof_id), db.get(Procedure, clinic.proc_id),
                      datetime.combine(future_day(), time(9)), "confirmado")
        db.commit(); fid = a.id
    assert as_dentist.post("/api/atendimentos/iniciar", json={"appointment_id": fid}).status_code == 422


def test_prontuario_restrito_e_auditado(clinic, as_dentist, as_recep, as_admin, as_patient_a):
    ap = today_appt(clinic)
    att = as_dentist.post("/api/atendimentos/iniciar", json={"appointment_id": ap}).json()["attendance_id"]
    as_dentist.post(f"/api/atendimentos/{att}/observacoes", json={"content": "Anotação sigilosa"})
    for c in (as_recep, as_patient_a):
        assert c.get(f"/api/pacientes/{clinic.pat_a_id}/prontuario").status_code == 403
        assert c.get(f"/api/atendimentos/{att}/registros").status_code == 403
    recs = as_dentist.get(f"/api/pacientes/{clinic.pat_a_id}/prontuario").json()["records"]
    assert recs[0]["content"] == "Anotação sigilosa"
    with SessionLocal() as db:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "read_medical_record"))
        assert db.scalar(select(AuditLog).where(AuditLog.action == "write_medical_record"))
    # lista de espera e histórico não vazam conteúdo clínico
    assert "Anotação" not in as_recep.get("/api/atendimentos").text + as_recep.get("/api/atendimentos/aguardando").text


def test_dentista_nao_acessa_paciente_de_outro_profissional(clinic, as_dentist):
    with SessionLocal() as db:
        stranger = make_patient(db); db.commit(); sid = stranger.id
    assert as_dentist.get(f"/api/pacientes/{sid}").status_code == 403
    assert as_dentist.get(f"/api/pacientes/{sid}/prontuario").status_code == 403
    assert as_dentist.get("/api/pacientes").json()["total"] == 0


# ---------- Procedimentos / portal ----------
def proc_body(**over):
    b = dict(name="Profilaxia Nova", category="geral", description="Teste", guidance="Orientação",
             duration_minutes=30, price="150.00", is_active=True, professional_ids=[])
    b.update(over); return b


def test_procedimento_cadastrado_aparece_no_portal_e_desativado_some(clinic, as_admin):
    r = as_admin.post("/api/procedimentos", json=proc_body(professional_ids=[clinic.prof_id]))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    pub = new_client().get("/api/publico/procedimentos").json()
    assert pid in [p["id"] for p in pub] and next(p for p in pub if p["id"] == pid)["available"] is True
    assert "price" not in pub[0]
    as_admin.put(f"/api/procedimentos/{pid}", json=proc_body(name="Profilaxia Editada", is_active=False))
    assert pid not in [p["id"] for p in new_client().get("/api/publico/procedimentos").json()]
    assert new_client().get(f"/api/publico/procedimentos/{pid}/profissionais").status_code == 404


def test_procedimento_so_admin_e_validacoes(clinic, as_recep, as_admin):
    assert as_recep.post("/api/procedimentos", json=proc_body()).status_code == 403
    assert as_admin.post("/api/procedimentos", json=proc_body(category="x")).status_code == 422
    assert as_admin.post("/api/procedimentos", json=proc_body(duration_minutes=0)).status_code == 422
    assert as_admin.post("/api/procedimentos", json=proc_body(price="-5")).status_code == 422
    assert as_admin.post("/api/procedimentos", json=proc_body(professional_ids=[9999])).status_code == 422
    assert as_admin.post("/api/procedimentos", json=proc_body()).status_code == 201
    assert as_admin.post("/api/procedimentos", json=proc_body()).status_code == 409


def test_exclusao_logica_e_integridade(clinic, as_admin):
    today_appt(clinic)
    assert as_admin.delete(f"/api/procedimentos/{clinic.proc_id}").status_code == 409
    assert as_admin.delete(f"/api/profissionais/{clinic.prof_id}").status_code == 409
    pid = as_admin.post("/api/procedimentos", json=proc_body()).json()["id"]
    assert as_admin.delete(f"/api/procedimentos/{pid}").status_code == 204
    assert as_admin.get(f"/api/procedimentos/{pid}").status_code == 404
    with SessionLocal() as db:
        assert db.get(Procedure, pid).deleted_at is not None   # registro preservado


def test_upload_de_imagem_valida_conteudo(clinic, as_admin):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    ok = as_admin.post(f"/api/procedimentos/{clinic.proc_id}/imagem", files={"file": ("a.png", png, "image/png")})
    assert ok.status_code == 200 and ok.json()["image_url"].startswith("/uploads/procedimentos/")
    bad = as_admin.post(f"/api/procedimentos/{clinic.proc_id}/imagem", files={"file": ("a.png", b"<script>x</script>", "image/png")})
    assert bad.status_code == 422
    assert as_admin.post(f"/api/procedimentos/{clinic.proc_id}/imagem", files={"file": ("a.svg", b"<svg/>", "image/svg+xml")}).status_code == 422


# ---------- Profissionais e pacientes ----------
def test_profissional_crud_com_acesso_e_horarios(clinic, as_admin):
    body = dict(full_name="Dr. Novo Nome", cpf="529.982.247-25", cro="CRO-PE 123", specialty="Ortodontia",
                phone="(81) 98888-0000", email="novo.dentista@teste.com", procedure_ids=[clinic.proc_id],
                create_account=True, password="Senha123")
    r = as_admin.post("/api/profissionais", json=body)
    assert r.status_code == 201 and r.json()["has_account"] is True, r.text
    pid = r.json()["id"]
    assert as_admin.post("/api/profissionais", json=body).status_code == 409
    sched = [{"weekday": 0, "start_time": "08:00", "end_time": "12:00"}]
    assert as_admin.put(f"/api/profissionais/{pid}/horarios", json=sched).json()["schedules"][0]["weekday"] == 0
    assert as_admin.put(f"/api/profissionais/{pid}/horarios", json=[{"weekday": 0, "start_time": "12:00", "end_time": "08:00"}]).status_code == 422
    c = new_client(); assert login(c, "novo.dentista@teste.com")["role"] == "dentista"
    as_admin.patch(f"/api/profissionais/{pid}/status", json={"is_active": False})
    assert new_client().post("/api/auth/login", json={"email": "novo.dentista@teste.com", "password": "Senha123"}).status_code == 401
    assert pid not in [p["id"] for p in new_client().get("/api/publico/profissionais").json()]


def test_paciente_crud_busca_por_nome_e_cpf(clinic, as_recep):
    body = dict(full_name="João Pereira Lima", cpf="390.533.447-05", birth_date="1988-07-01", phone="81977770000",
                email="joao@teste.com", address="Av. Central, 50")
    r = as_recep.post("/api/pacientes", json=body)
    assert r.status_code == 201 and r.json()["age"] >= 37
    assert as_recep.post("/api/pacientes", json=body).status_code == 409
    assert as_recep.get("/api/pacientes", params={"q": "pereira"}).json()["total"] == 1
    assert as_recep.get("/api/pacientes", params={"q": "390.533"}).json()["total"] == 1
    pid = r.json()["id"]
    assert as_recep.put(f"/api/pacientes/{pid}", json={"phone": "81966660000"}).json()["phone"] == "81966660000"
    assert as_recep.delete(f"/api/pacientes/{pid}").status_code == 403    # exclusão só admin


def test_paciente_atualiza_so_telefone_e_endereco(clinic, as_patient_a):
    r = as_patient_a.put("/api/pacientes/me", json={"phone": "(81) 90000-1111", "address": "Rua Nova, 9", "cpf": "00000000000", "full_name": "Hack"})
    assert r.status_code == 200 and r.json()["phone"] == "81900001111" and r.json()["full_name"] != "Hack"


# ---------- Financeiro, relatórios, dashboard, configurações ----------
def test_financeiro_baixa_e_resumo(clinic, as_admin, as_dentist):
    ap = today_appt(clinic)
    att = as_dentist.post("/api/atendimentos/iniciar", json={"appointment_id": ap}).json()["attendance_id"]
    as_dentist.post(f"/api/atendimentos/{att}/finalizar", json={})
    pend = as_admin.get("/api/financeiro/pagamentos", params={"situacao": "pendente"}).json()
    assert len(pend) == 1
    assert as_admin.patch(f"/api/financeiro/pagamentos/{pend[0]['id']}/pagar", json={"method": "ouro"}).status_code == 422
    assert as_admin.patch(f"/api/financeiro/pagamentos/{pend[0]['id']}/pagar", json={"method": "pix"}).json()["status"] == "pago"
    assert as_admin.patch(f"/api/financeiro/pagamentos/{pend[0]['id']}/pagar", json={"method": "pix"}).status_code == 422
    s = as_admin.get("/api/financeiro/resumo").json()
    assert s["received"] == 100.0 and s["by_method"][0]["method"] == "pix"
    assert as_admin.post("/api/financeiro/pagamentos", json={"patient_id": clinic.pat_a_id, "amount": "50", "status": "pago"}).status_code == 422


def test_dashboard_usa_dados_reais(clinic, as_admin, as_dentist):
    empty = as_admin.get("/api/dashboard").json()
    assert empty["cards"]["completed"] == 0 and empty["today_agenda"] == []
    ap = today_appt(clinic)
    att = as_dentist.post("/api/atendimentos/iniciar", json={"appointment_id": ap}).json()["attendance_id"]
    as_dentist.post(f"/api/atendimentos/{att}/finalizar", json={})
    d = as_admin.get("/api/dashboard").json()
    assert d["cards"]["completed"] == 1 and d["cards"]["total_patients"] == 2
    assert d["today_agenda"][0]["patient_age"] >= 30 and d["top_procedures"][0]["count"] == 1
    assert sum(d["appointments_series"]["values"]) == 1 and d["finance"] is not None
    assert as_dentist.get("/api/dashboard").json()["finance"] is None


def test_relatorios_exportam_pdf_e_excel(clinic, as_admin):
    j = as_admin.get("/api/relatorios/resumo").json()
    assert {"top_procedures", "productivity", "no_shows", "finance"} <= set(j)
    pdf = as_admin.get("/api/relatorios/exportar", params={"formato": "pdf"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    xl = as_admin.get("/api/relatorios/exportar", params={"formato": "xlsx"})
    assert xl.status_code == 200 and xl.content[:2] == b"PK"
    assert as_admin.get("/api/relatorios/exportar", params={"formato": "exe"}).status_code == 422
    assert as_admin.get("/api/relatorios/resumo", params={"inicio": "2026-05-02", "fim": "2026-05-01"}).status_code == 422


def test_configuracoes_afetam_a_grade_de_horarios(clinic, as_admin):
    cfg = as_admin.get("/api/configuracoes").json()
    cfg["slot_minutes"] = 60
    assert as_admin.put("/api/configuracoes", json=cfg).status_code == 200
    times = [s["time"] for s in new_client().get("/api/agendamentos/disponibilidade", params={"procedimento_id": clinic.proc_id, "data": future_day().isoformat()}).json()]
    assert times[:3] == ["08:00", "09:00", "10:00"]
    cfg["slot_minutes"] = 7
    assert as_admin.put("/api/configuracoes", json=cfg).status_code == 422
    cfg.update(slot_minutes=30, email="invalido")
    assert as_admin.put("/api/configuracoes", json=cfg).status_code == 422


# ---------- Integridade no banco e concorrência ----------
def test_indice_unico_parcial_barra_duplicidade_no_banco(clinic):
    start = datetime.combine(future_day(), time(9))
    with SessionLocal() as db:
        p, prof, proc = db.get(Patient, clinic.pat_a_id), db.get(Professional, clinic.prof_id), db.get(Procedure, clinic.proc_id)
        first = make_appt(db, p, prof, proc, start, "confirmado"); db.commit()
        with pytest.raises(IntegrityError):
            make_appt(db, p, prof, proc, start, "pendente")
        db.rollback()
        first = db.get(Appointment, first.id); first.status = "cancelado"; db.commit()
        make_appt(db, p, prof, proc, start, "pendente"); db.commit()   # cancelado não ocupa o horário


@pytest.mark.skipif(not IS_PG, reason="concorrência real exige PostgreSQL (TEST_DATABASE_URL)")
def test_reservas_simultaneas_apenas_uma_vence(clinic):
    with SessionLocal() as db:
        emails = [make_patient(db).email for _ in range(8)]; db.commit()
    day, results, barrier = future_day(), [], threading.Barrier(8)

    def worker(email):
        c = new_client(); login(c, email); barrier.wait()
        results.append(c.post("/api/agendamentos", json={"procedure_id": clinic.proc_id, "professional_id": clinic.prof_id, "start_at": iso(day, 9)}).status_code)

    ts = [threading.Thread(target=worker, args=(e,)) for e in emails]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(results) == [201] + [409] * 7, results
    with SessionLocal() as db:
        assert len(db.scalars(select(Appointment)).all()) == 1


def test_portal_lista_mais_procurados_por_agendamentos_reais(clinic, as_patient_a):
    with SessionLocal() as db:
        outro = make_procedure(db, "Outro"); db.commit(); outro_id = outro.id
    pub = new_client().get("/api/publico/procedimentos", params={"populares": 1}).json()
    assert len(pub) == 1
    today_appt(clinic)                                   # agenda o procedimento padrão
    pub = new_client().get("/api/publico/procedimentos", params={"populares": 1}).json()
    assert pub[0]["id"] == clinic.proc_id and pub[0]["id"] != outro_id
