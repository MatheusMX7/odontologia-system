ROLES = ("admin", "recepcionista", "dentista", "paciente")
CATEGORIES = ("geral", "estetico", "cirurgia", "ortodontia")

# Status de agendamento
STATUSES = ("pendente", "confirmado", "em_atendimento", "concluido", "cancelado", "nao_compareceu")
# Ocupam a agenda do profissional (cancelado e não compareceu liberam o horário)
ACTIVE_STATUSES = ("pendente", "confirmado", "em_atendimento", "concluido")
# Ocupam a agenda do paciente (consultas ainda por acontecer ou em curso)
OPEN_STATUSES = ("pendente", "confirmado", "em_atendimento")
# Transições manuais permitidas pelo módulo de agendamentos.
# "em_atendimento" e "concluido" só são alcançados pelo módulo de Atendimentos.
MANUAL_TRANSITIONS = {
    "pendente": {"confirmado", "cancelado"},
    "confirmado": {"cancelado", "nao_compareceu"},
}

PAYMENT_METHODS = ("dinheiro", "pix", "cartao_credito", "cartao_debito", "transferencia")
PAYMENT_STATUSES = ("pendente", "pago", "cancelado")
