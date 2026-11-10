"""Dados iniciais.

  python -m app.seed                 -> perfis, configurações e catálogo de procedimentos + 1 administrador
  python -m app.seed --demo          -> adiciona usuários/dados de DEMONSTRAÇÃO (somente desenvolvimento)

O administrador usa ADMIN_EMAIL / ADMIN_PASSWORD do ambiente. Sem ADMIN_PASSWORD, uma senha aleatória é gerada
e exibida uma única vez.
"""
import os
import secrets
import sys
from datetime import date, time

from sqlalchemy import select

from .core.config import get_settings
from .core.constants import ROLES
from .core.security import hash_password
from .database import SessionLocal
from .models import ClinicSettings, Patient, Procedure, Professional, Role, Schedule, User

CATALOGO = [
    # (nome, categoria, duração em min, descrição, orientações)
    ("Avaliação odontológica", "geral", 30, "Exame clínico completo da saúde bucal para definir o plano de cuidados.", "Traga exames anteriores, se tiver, e informe medicamentos em uso."),
    ("Limpeza dentária", "geral", 40, "Remoção de placa e tártaro e polimento dos dentes.", "Escove os dentes normalmente antes da consulta."),
    ("Restauração", "geral", 45, "Reconstrução do dente afetado por cárie ou fratura.", "Evite mastigar do lado tratado até o fim do efeito da anestesia."),
    ("Aplicação de flúor", "geral", 20, "Fortalecimento do esmalte e prevenção de cáries.", "Evite comer e beber por cerca de 30 minutos após a aplicação."),
    ("Clareamento dental", "estetico", 60, "Clareamento supervisionado por dentista, com avaliação prévia.", "Informe se tem sensibilidade nos dentes."),
    ("Lentes dentárias", "estetico", 60, "Lâminas finas que melhoram forma, cor e alinhamento dos dentes.", "A indicação depende de avaliação clínica prévia."),
    ("Estética do sorriso", "estetico", 45, "Planejamento e ajustes para harmonizar o sorriso.", "Leve fotos de sorrisos de que gosta, se quiser."),
    ("Extração dentária", "cirurgia", 45, "Remoção segura de dente comprometido.", "Siga as orientações pós-operatórias e evite esforço no dia."),
    ("Extração de dentes de leite", "cirurgia", 30, "Remoção de dentes decíduos com acompanhamento do responsável.", "Menores devem vir acompanhados de um responsável."),
    ("Extração de dentes sisos", "cirurgia", 60, "Remoção de sisos (terceiros molares) com planejamento cirúrgico.", "Pode ser necessário exame de imagem. Venha acompanhado, se possível."),
    ("Cirurgias odontológicas", "cirurgia", 90, "Procedimentos cirúrgicos orais conforme avaliação do profissional.", "Siga o jejum e as orientações enviadas pela clínica."),
    ("Aparelhos ortodônticos", "ortodontia", 60, "Instalação de aparelho para alinhamento dos dentes.", "Após a instalação é normal haver desconforto nos primeiros dias."),
    ("Manutenção de aparelhos", "ortodontia", 30, "Ajustes periódicos e troca de elásticos do aparelho.", "Mantenha a higiene bucal e traga o estojo do aparelho removível."),
    ("Avaliação ortodôntica", "ortodontia", 30, "Análise da mordida e do alinhamento para indicar o melhor tratamento.", "Leve radiografias anteriores, se houver."),
]


def _cpf_valido(base9: str) -> str:
    d = [int(c) for c in base9]
    for n in (9, 10):
        s = sum(d[i] * (n + 1 - i) for i in range(n))
        d.append((s * 10 % 11) % 10)
    return "".join(map(str, d))


def run(demo: bool = False) -> None:
    get_settings()
    db = SessionLocal()
    try:
        for name in ROLES:
            if not db.scalar(select(Role).where(Role.name == name)):
                db.add(Role(name=name))
        db.flush()
        if not db.get(ClinicSettings, 1):
            db.add(ClinicSettings(id=1, name="Clínica Odontológica", policy_text=(
                "Cancelamentos e reagendamentos podem ser feitos pelo portal com a antecedência mínima definida pela clínica. "
                "Faltas sem aviso podem limitar novos agendamentos online.")))
        if not db.scalar(select(Procedure.id).limit(1)):
            for nome, cat, dur, desc, orient in CATALOGO:
                db.add(Procedure(name=nome, category=cat, duration_minutes=dur, description=desc, guidance=orient, price=0))
        db.flush()

        admin_email = os.getenv("ADMIN_EMAIL", "admin@clinica.com.br").lower()
        if not db.scalar(select(User).where(User.email == admin_email)):
            pwd = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(12) + "a1"
            role = db.scalar(select(Role).where(Role.name == "admin"))
            db.add(User(email=admin_email, full_name="Administrador", password_hash=hash_password(pwd), role_id=role.id))
            print(f"\n  Administrador criado:\n    e-mail: {admin_email}\n    senha : {pwd}\n  (altere a senha após o primeiro acesso)\n")

        if demo:
            _demo(db)
        db.commit()
        print("Seed concluído.")
    finally:
        db.close()


def _demo(db) -> None:
    pwd = os.getenv("DEMO_PASSWORD", "Demo@12345")
    roles = {r.name: r for r in db.scalars(select(Role))}

    def user(email, name, role):
        u = db.scalar(select(User).where(User.email == email))
        if not u:
            u = User(email=email, full_name=name, password_hash=hash_password(pwd), role_id=roles[role].id)
            db.add(u)
            db.flush()
        return u

    user("recepcao@demo.clinica.com.br", "[DEMO] Recepcionista", "recepcionista")
    du = user("dentista@demo.clinica.com.br", "[DEMO] Dra. Dentista", "dentista")
    if not db.scalar(select(Professional).where(Professional.user_id == du.id)):
        prof = Professional(user_id=du.id, full_name="[DEMO] Dra. Dentista", cpf=_cpf_valido("111444777"), cro="CRO-DEMO 0000",
                            specialty="Clínica geral (demonstração)", phone="81999990000", email="dentista@demo.clinica.com.br")
        prof.procedures = list(db.scalars(select(Procedure)))
        for wd in range(5):
            prof.schedules.append(Schedule(weekday=wd, start_time=time(8), end_time=time(18), break_start=time(12), break_end=time(14)))
        db.add(prof)
    pu = user("paciente@demo.clinica.com.br", "[DEMO] Paciente", "paciente")
    if not db.scalar(select(Patient).where(Patient.user_id == pu.id)):
        db.add(Patient(user_id=pu.id, full_name="[DEMO] Paciente", cpf=_cpf_valido("529982247"), birth_date=date(1995, 5, 20),
                       phone="81988880000", email="paciente@demo.clinica.com.br", address="Rua de Demonstração, 100 (dados fictícios)"))
    print(f"  Usuários DEMO (senha {pwd}): recepcao@demo.clinica.com.br, dentista@demo.clinica.com.br, paciente@demo.clinica.com.br")


if __name__ == "__main__":
    run(demo="--demo" in sys.argv)
