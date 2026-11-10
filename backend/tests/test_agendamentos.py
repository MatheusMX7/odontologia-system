from datetime import datetime, time, timedelta

from sqlalchemy import select

from app.core.timeutils import now_local
from app.database import SessionLocal
from app.models import Appointment, ClinicSettings, Procedure, Professional, ScheduleBlock
from tests.conftest import (future_day, iso, login, make_appt, make_patient, make_procedure, make_professional,
                            new_client)


def slots(client, clinic, day, **extra):
    r = client.get("/api/agendamentos/disponibilidade", params={"procedimento_id": clinic.proc_id, "data": day.isoformat(), **extra})
    assert r.status_code == 200, r.text
    return r.json()


def book(client, clinic, day, hh, mm=0, **extra):
    return client.post("/api/agendamentos", json={"procedure_id": clinic.proc_id, "professional_id": clinic.prof_id,
                                                   "start_at": iso(day, hh, mm), **extra})


def test_horarios_respeitam_jornada_intervalo_e_duracao(clinic):
    day = future_day()
    times = [s["time"] for s in slots(new_client(), clinic, day)]
    assert times[0] == "08:00" and times[-1] == "17:30"      # jornada 08–18, procedimento de 30 min
    assert not any("12:00" <= t < "14:00" for t in times)      # intervalo de almoço
    assert "11:30" in times and "14:00" in times


def test_duracao_do_procedimento_limita_ultimo_horario(clinic):
    with SessionLocal() as db:
        db.get(Procedure, clinic.proc_id).duration_minutes = 60
        db.commit()
    times = [s["time"] for s in slots(new_client(), clinic, future_day())]
    assert times[-1] == "17:00" and "11:30" not in times       # 11:30 + 60 invadiria o intervalo


def test_nao_ha_horarios_em_dias_passados_nem_horarios_ja_passados(clinic):
    assert slots(new_client(), clinic, now_local().date() - timedelta(days=1)) == []
    for s in slots(new_client(), clinic, now_local().date()):
        assert datetime.fromisoformat(s["start"]) > now_local()


def test_dia_fora_do_atendimento_da_clinica(clinic):
    with SessionLocal() as db:
        db.get(ClinicSettings, 1).working_days = "0,1,2,3,4"
        db.commit()
    d = future_day()
    while d.weekday() != 6:
        d += timedelta(days=1)
    assert slots(new_client(), clinic, d) == []


def test_paciente_agenda_aguardando_aprovacao_e_horario_some(clinic, as_patient_a):
    day = future_day()
    r = book(as_patient_a, clinic, day, 9)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["status"] == "pendente" and a["patient_age"] >= 30 and a["end_at"].endswith("09:30:00")
    assert "09:00" not in [s["time"] for s in slots(as_patient_a, clinic, day)]


def test_confirmacao_automatica_configuravel(clinic, as_patient_a):
    with SessionLocal() as db:
        db.get(ClinicSettings, 1).auto_confirm = True
        db.commit()
    assert book(as_patient_a, clinic, future_day(), 9).json()["status"] == "confirmado"


def test_reserva_duplicada_retorna_409(clinic, as_patient_a, as_patient_b):
    day = future_day()
    assert book(as_patient_a, clinic, day, 10).status_code == 201
    r = book(as_patient_b, clinic, day, 10)
    assert r.status_code == 409 and "horário" in r.json()["detail"].lower()


def test_sobreposicao_parcial_por_duracao_e_bloqueada(clinic, as_patient_a, as_patient_b):
    with SessionLocal() as db:
        db.get(Procedure, clinic.proc_id).duration_minutes = 60
        db.commit()
    day = future_day()
    assert book(as_patient_a, clinic, day, 10).status_code == 201     # 10:00–11:00
    assert book(as_patient_b, clinic, day, 10, 30).status_code == 409  # começa dentro do atendimento anterior


def test_paciente_nao_agenda_dois_horarios_simultaneos(clinic, as_patient_a):
    with SessionLocal() as db:
        other = make_professional(db, [db.get(Procedure, clinic.proc_id)])
        db.commit(); other_id = other.id
    day = future_day()
    assert book(as_patient_a, clinic, day, 10).status_code == 201
    r = as_patient_a.post("/api/agendamentos", json={"procedure_id": clinic.proc_id, "professional_id": other_id, "start_at": iso(day, 10)})
    assert r.status_code == 409 and "já possui" in r.json()["detail"]


def test_data_passada_recusada(clinic, as_patient_a):
    r = book(as_patient_a, clinic, now_local().date() - timedelta(days=1), 10)
    assert r.status_code == 422 and "passad" in r.json()["detail"]


def test_horario_fora_da_jornada_e_intervalo_recusados(clinic, as_patient_a):
    day = future_day()
    assert book(as_patient_a, clinic, day, 7).status_code == 409
    assert book(as_patient_a, clinic, day, 12, 30).status_code == 409
    assert book(as_patient_a, clinic, day, 9, 15).status_code == 409  # fora da grade de 30 min


def test_procedimento_desativado_nao_pode_ser_agendado(clinic, as_patient_a):
    with SessionLocal() as db:
        db.get(Procedure, clinic.proc_id).is_active = False
        db.commit()
    assert book(as_patient_a, clinic, future_day(), 9).status_code == 422
    r = new_client().get("/api/agendamentos/disponibilidade", params={"procedimento_id": clinic.proc_id, "data": future_day().isoformat()})
    assert r.status_code == 404


def test_profissional_sem_vinculo_com_procedimento_recusado(clinic, as_patient_a):
    with SessionLocal() as db:
        outro = make_procedure(db, "Outro")
        prof2 = make_professional(db, [outro]); db.commit(); pid = prof2.id
    r = as_patient_a.post("/api/agendamentos", json={"procedure_id": clinic.proc_id, "professional_id": pid, "start_at": iso(future_day(), 9)})
    assert r.status_code == 422


def test_profissional_desativado_nao_tem_horarios(clinic):
    with SessionLocal() as db:
        db.get(Professional, clinic.prof_id).is_active = False
        db.commit()
    assert slots(new_client(), clinic, future_day()) == []


def test_bloqueio_de_agenda_remove_horarios(clinic):
    day = future_day()
    with SessionLocal() as db:
        db.add(ScheduleBlock(professional_id=clinic.prof_id, start_at=datetime.combine(day, time(9)),
                             end_at=datetime.combine(day, time(11)), reason="Reunião"))
        db.commit()
    times = [s["time"] for s in slots(new_client(), clinic, day)]
    assert "08:30" in times and "09:00" not in times and "10:30" not in times and "11:00" in times


def test_cancelado_libera_o_horario_para_outro_paciente(clinic, as_patient_a, as_patient_b):
    day = future_day()
    a = book(as_patient_a, clinic, day, 10).json()
    assert as_patient_a.post(f"/api/agendamentos/{a['id']}/cancelar", json={"reason": "Imprevisto"}).json()["status"] == "cancelado"
    assert "10:00" in [s["time"] for s in slots(as_patient_b, clinic, day)]
    assert book(as_patient_b, clinic, day, 10).status_code == 201


def test_paciente_ve_somente_os_proprios_agendamentos(clinic, as_patient_a, as_patient_b):
    day = future_day()
    a = book(as_patient_a, clinic, day, 9).json()
    b = book(as_patient_b, clinic, day, 10).json()
    ids_a = [x["id"] for x in as_patient_a.get("/api/agendamentos").json()]
    assert ids_a == [a["id"]]
    assert as_patient_a.get(f"/api/agendamentos/{b['id']}").status_code == 404
    assert as_patient_a.post(f"/api/agendamentos/{b['id']}/cancelar", json={}).status_code == 404
    assert as_patient_a.post(f"/api/agendamentos/{b['id']}/reagendar", json={"start_at": iso(day, 15)}).status_code == 404
    assert as_patient_a.get(f"/api/pacientes/{clinic.pat_b_id}").status_code == 403


def test_paciente_nao_agenda_em_nome_de_outro(clinic, as_patient_a):
    r = book(as_patient_a, clinic, future_day(), 9, patient_id=clinic.pat_b_id)
    assert r.status_code == 201 and r.json()["patient_id"] == clinic.pat_a_id


def test_cancelamento_respeita_antecedencia_minima(clinic, as_patient_a):
    with SessionLocal() as db:
        ap = make_appt(db, db.get(__import__("app.models", fromlist=["Patient"]).Patient, clinic.pat_a_id),
                       db.get(Professional, clinic.prof_id), db.get(Procedure, clinic.proc_id),
                       now_local() + timedelta(hours=2), "confirmado")
        db.commit(); ap_id = ap.id
    got = as_patient_a.get(f"/api/agendamentos/{ap_id}").json()
    assert got["can_cancel"] is False
    r = as_patient_a.post(f"/api/agendamentos/{ap_id}/cancelar", json={})
    assert r.status_code == 422 and "24h" in r.json()["detail"]
    assert as_patient_a.post(f"/api/agendamentos/{ap_id}/reagendar", json={"start_at": iso(future_day(), 9)}).status_code == 422


def test_recepcao_pode_cancelar_mesmo_perto_do_horario(clinic, as_recep):
    with SessionLocal() as db:
        from app.models import Patient
        ap = make_appt(db, db.get(Patient, clinic.pat_a_id), db.get(Professional, clinic.prof_id),
                       db.get(Procedure, clinic.proc_id), now_local() + timedelta(hours=2), "confirmado")
        db.commit(); ap_id = ap.id
    assert as_recep.post(f"/api/agendamentos/{ap_id}/cancelar", json={"reason": "Pedido do paciente"}).json()["status"] == "cancelado"


def test_reagendamento_libera_horario_antigo_e_volta_para_pendente(clinic, as_patient_a, as_patient_b):
    with SessionLocal() as db:
        db.get(ClinicSettings, 1).auto_confirm = True
        db.commit()
    day = future_day()
    a = book(as_patient_a, clinic, day, 9).json()
    assert a["status"] == "confirmado"
    with SessionLocal() as db:
        db.get(ClinicSettings, 1).auto_confirm = False
        db.commit()
    r = as_patient_a.post(f"/api/agendamentos/{a['id']}/reagendar", json={"start_at": iso(day, 15)})
    assert r.status_code == 200, r.text
    assert r.json()["start_at"].startswith(f"{day}T15:00") and r.json()["status"] == "pendente"
    times = [s["time"] for s in slots(as_patient_b, clinic, day)]
    assert "09:00" in times and "15:00" not in times
    assert book(as_patient_b, clinic, day, 15).status_code == 409


def test_reagendar_para_horario_ocupado_falha(clinic, as_patient_a, as_patient_b):
    day = future_day()
    a = book(as_patient_a, clinic, day, 9).json()
    book(as_patient_b, clinic, day, 10)
    assert as_patient_a.post(f"/api/agendamentos/{a['id']}/reagendar", json={"start_at": iso(day, 10)}).status_code == 409


def test_recepcao_agenda_para_paciente_ja_confirmado(clinic, as_recep):
    r = as_recep.post("/api/agendamentos", json={"procedure_id": clinic.proc_id, "professional_id": clinic.prof_id,
                                                 "start_at": iso(future_day(), 9), "patient_id": clinic.pat_a_id})
    assert r.status_code == 201 and r.json()["status"] == "confirmado" and r.json()["patient_id"] == clinic.pat_a_id
    assert as_recep.post("/api/agendamentos", json={"procedure_id": clinic.proc_id, "professional_id": clinic.prof_id,
                                                    "start_at": iso(future_day(), 10)}).status_code == 422  # sem paciente


def test_transicoes_de_status(clinic, as_recep, as_patient_a, as_dentist):
    a = book(as_patient_a, clinic, future_day(), 9).json()
    url = f"/api/agendamentos/{a['id']}/status"
    assert as_recep.patch(url, json={"status": "concluido"}).status_code == 422          # só pelo módulo de Atendimentos
    assert as_recep.patch(url, json={"status": "em_atendimento"}).status_code == 422
    assert as_dentist.patch(url, json={"status": "confirmado"}).status_code == 403       # dentista não confirma
    assert as_patient_a.patch(url, json={"status": "confirmado"}).status_code == 403     # paciente não muda status
    assert as_recep.patch(url, json={"status": "confirmado"}).json()["status"] == "confirmado"
    assert as_recep.patch(url, json={"status": "nao_compareceu"}).status_code == 422     # consulta ainda no futuro


def test_registro_de_falta_apos_o_horario(clinic, as_recep, as_dentist):
    with SessionLocal() as db:
        from app.models import Patient
        ap = make_appt(db, db.get(Patient, clinic.pat_a_id), db.get(Professional, clinic.prof_id), db.get(Procedure, clinic.proc_id),
                       now_local() - timedelta(days=1), "confirmado")
        db.commit(); ap_id = ap.id
    assert as_dentist.patch(f"/api/agendamentos/{ap_id}/status", json={"status": "nao_compareceu"}).json()["status"] == "nao_compareceu"
    # falta libera o horário na grade
    assert as_recep.patch(f"/api/agendamentos/{ap_id}/status", json={"status": "confirmado"}).status_code == 422


def test_dentista_ve_apenas_a_propria_agenda(clinic, as_dentist, as_patient_a):
    with SessionLocal() as db:
        other = make_professional(db, [db.get(Procedure, clinic.proc_id)]); db.commit()
        other_email = db.get(__import__("app.models", fromlist=["User"]).User, other.user_id).email
    day = future_day()
    mine = book(as_patient_a, clinic, day, 9).json()
    other_c = new_client(); login(other_c, other_email)
    assert other_c.get("/api/agendamentos").json() == []
    assert other_c.get(f"/api/agendamentos/{mine['id']}").status_code == 403
    assert [x["id"] for x in as_dentist.get("/api/agendamentos").json()] == [mine["id"]]


def test_filtros_da_listagem(clinic, as_recep, as_patient_a, as_patient_b):
    day = future_day()
    book(as_patient_a, clinic, day, 9); book(as_patient_b, clinic, day, 10)
    base = {"data_inicio": day.isoformat(), "data_fim": day.isoformat()}
    assert len(as_recep.get("/api/agendamentos", params=base).json()) == 2
    assert len(as_recep.get("/api/agendamentos", params={**base, "procedimento_id": clinic.proc_id}).json()) == 2
    assert len(as_recep.get("/api/agendamentos", params={**base, "profissional_id": clinic.prof_id + 99}).json()) == 0
    assert len(as_recep.get("/api/agendamentos", params={**base, "status": "confirmado"}).json()) == 0
    name = as_recep.get("/api/agendamentos", params=base).json()[0]["patient_name"]
    assert len(as_recep.get("/api/agendamentos", params={**base, "q": name[:8]}).json()) >= 1
    assert as_recep.get("/api/agendamentos", params={"data_inicio": (day + timedelta(days=1)).isoformat()}).json() == []
