import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

STATUS_PT = {"pendente": "Pendente", "confirmado": "Confirmado", "em_atendimento": "Em atendimento",
             "concluido": "Concluído", "cancelado": "Cancelado", "nao_compareceu": "Não compareceu"}
METHOD_PT = {"dinheiro": "Dinheiro", "pix": "Pix", "cartao_credito": "Cartão de crédito",
             "cartao_debito": "Cartão de débito", "transferencia": "Transferência", "outro": "Outro"}


def _fmt_dt(v) -> str:
    return v.strftime("%d/%m/%Y %H:%M") if hasattr(v, "strftime") else str(v)


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _tables(stats: dict, finance: dict, revenue: dict, no_shows: list[dict]) -> list[tuple[str, list[str], list[list]]]:
    sc = stats["status_count"]
    return [
        ("Resumo", ["Indicador", "Valor"], [
            ["Total de pacientes cadastrados", stats["total_patients"]],
            ["Novos pacientes no período", stats["new_patients"]],
            ["Total de consultas no período", stats["total_appointments"]],
            *[[f"Consultas — {STATUS_PT[k]}", v] for k, v in sc.items()],
            ["Receita recebida", _brl(finance["received"])],
            ["Pagamentos pendentes", _brl(finance["pending"])],
        ]),
        ("Procedimentos mais realizados", ["Procedimento", "Quantidade"],
         [[p["name"], p["count"]] for p in stats["top_procedures"]]),
        ("Produtividade dos profissionais", ["Profissional", "Total", "Concluídas", "Canceladas", "Faltas", "% concluídas"],
         [[p["professional"], p["total"], p["completed"], p["cancelled"], p["no_show"], f'{p["completion_rate"]}%']
          for p in stats["productivity"]]),
        ("Receita por período", ["Período", "Receita"],
         [[l, _brl(v)] for l, v in zip(revenue["labels"], revenue["values"])]),
        ("Receita por forma de pagamento", ["Forma", "Total"],
         [[METHOD_PT.get(m["method"], m["method"]), _brl(m["total"])] for m in finance["by_method"]]),
        ("Pacientes que não compareceram", ["Paciente", "Telefone", "Data", "Procedimento"],
         [[n["patient"], n["phone"], _fmt_dt(n["start_at"]), n["procedure"]] for n in no_shows]),
        ("Evolução dos agendamentos", ["Período", "Agendamentos"],
         [[l, v] for l, v in zip(stats["appointments_series"]["labels"], stats["appointments_series"]["values"])]),
    ]


def build_xlsx(clinic: str, start: date, end: date, stats, finance, revenue, no_shows) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    head_fill = PatternFill("solid", fgColor="1F6FD8")
    for title, headers, rows in _tables(stats, finance, revenue, no_shows):
        ws = wb.create_sheet(title[:31])
        ws.append([f"{clinic} — {title} ({start:%d/%m/%Y} a {end:%d/%m/%Y})"])
        ws["A1"].font = Font(bold=True, size=12)
        ws.append([])
        ws.append(headers)
        for c in ws[3]:
            c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), head_fill, Alignment(horizontal="center")
        for r in rows:
            ws.append(r)
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max(14, width + 2), 48)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_pdf(clinic: str, start: date, end: date, stats, finance, revenue, no_shows) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.6 * cm,
                            bottomMargin=1.6 * cm, title="Relatório gerencial")
    st = getSampleStyleSheet()
    el = [Paragraph(f"{clinic}", st["Title"]),
          Paragraph(f"Relatório gerencial — {start:%d/%m/%Y} a {end:%d/%m/%Y}", st["Heading3"]), Spacer(1, 8)]
    for title, headers, rows in _tables(stats, finance, revenue, no_shows):
        el.append(Paragraph(title, st["Heading2"]))
        if not rows:
            el += [Paragraph("Sem registros no período.", st["Normal"]), Spacer(1, 6)]
            continue
        data = [headers] + [[Paragraph(str(c), st["BodyText"]) if isinstance(c, str) else c for c in r] for r in rows]
        t = Table(data, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F6FD8")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D6E4")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F8FD")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        el += [t, Spacer(1, 10)]
    doc.build(el)
    return buf.getvalue()
