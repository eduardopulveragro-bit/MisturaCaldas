"""Geração do PDF de ordem de mistura usando ReportLab."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

_LARANJA = colors.HexColor("#E65100")
_VERMELHO = colors.HexColor("#C62828")
_AZUL_ESCURO = colors.HexColor("#1A237E")
_CINZA_CLARO = colors.HexColor("#F5F5F5")
_AMARELO = colors.HexColor("#FFF9C4")


def _estilos():
    base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle("titulo", parent=base["Heading1"], fontSize=13,
                                  textColor=_AZUL_ESCURO, spaceAfter=4),
        "subtitulo": ParagraphStyle("subtitulo", parent=base["Heading2"], fontSize=10,
                                     textColor=_AZUL_ESCURO, spaceAfter=2),
        "normal": ParagraphStyle("normal", parent=base["Normal"], fontSize=9, spaceAfter=2),
        "alerta": ParagraphStyle("alerta", parent=base["Normal"], fontSize=9,
                                  textColor=_VERMELHO, spaceAfter=2),
        "aprovacao": ParagraphStyle("aprovacao", parent=base["Normal"], fontSize=11,
                                     textColor=_VERMELHO, fontName="Helvetica-Bold",
                                     alignment=1, spaceAfter=4),
        "pendente": ParagraphStyle("pendente", parent=base["Normal"], fontSize=9,
                                    textColor=_LARANJA, spaceAfter=2),
    }
    return estilos


def gerar_pdf(
    fazenda: dict,
    itens_ordenados: list[dict],
    taxa_L_ha: float,
    ha_por_carga: float,
    ponta_info: dict,
    alertas: list[dict],
) -> bytes:
    """
    Gera o PDF e retorna os bytes.
    Campos obrigatórios em fazenda: nome, maquina, volume_tanque_L.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    estilos = _estilos()
    story = []
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # --- Cabeçalho ---
    story.append(Paragraph("ORDEM DE MISTURA NA CALDA", estilos["titulo"]))
    story.append(Paragraph(
        f"<b>Fazenda:</b> {fazenda.get('nome', '—')} &nbsp;&nbsp; "
        f"<b>Máquina:</b> {fazenda.get('maquina', '—')} &nbsp;&nbsp; "
        f"<b>Gerado em:</b> {agora}",
        estilos["normal"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=_AZUL_ESCURO, spaceAfter=6))

    # --- Aviso de aprovação ---
    story.append(Paragraph(
        "⚠  SUGERIDO — AGUARDANDO APROVAÇÃO DO RESPONSÁVEL TÉCNICO  ⚠",
        estilos["aprovacao"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    # --- Cálculos ---
    story.append(Paragraph("PARÂMETROS DE APLICAÇÃO", estilos["subtitulo"]))
    dados_calc = [
        ["Taxa de aplicação", f"{taxa_L_ha} L/ha"],
        ["Volume do tanque", f"{fazenda.get('volume_tanque_L', '—')} L"],
        ["Área coberta por carga", f"{ha_por_carga} ha"],
        ["Velocidade", f"{fazenda.get('velocidade_km_h', '—')} km/h"],
        ["Faixa", f"{fazenda.get('faixa_m', '—')} m"],
    ]
    tabela_calc = Table(dados_calc, colWidths=[7 * cm, 5 * cm])
    tabela_calc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), _CINZA_CLARO),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tabela_calc)
    story.append(Spacer(1, 0.4 * cm))

    # --- Sugestão de ponta ---
    story.append(Paragraph("SUGESTÃO DE PONTA E PRESSÃO", estilos["subtitulo"]))
    if ponta_info.get("sugestao") == "SUGERIDO - AGUARDANDO APROVAÇÃO":
        dados_ponta = [
            ["Ponta", ponta_info["ponta"]],
            ["Pressão sugerida", f"{ponta_info['pressao_bar']} bar"],
            ["Classe de gota", ponta_info["classe_gota"]],
            ["Status", "SUGERIDO — AGUARDANDO APROVAÇÃO"],
        ]
        tabela_ponta = Table(dados_ponta, colWidths=[7 * cm, 8 * cm])
        tabela_ponta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), _CINZA_CLARO),
            ("BACKGROUND", (0, 3), (-1, 3), _AMARELO),
            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
    else:
        dados_ponta = [["Sugestão de ponta", "pendente — " + ponta_info.get("observacao", "")]]
        tabela_ponta = Table(dados_ponta, colWidths=[7 * cm, 9 * cm])
        tabela_ponta.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (1, 0), (1, 0), _LARANJA),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
    story.append(tabela_ponta)
    story.append(Spacer(1, 0.4 * cm))

    # --- Ordem de adição ---
    story.append(Paragraph("ORDEM DE ADIÇÃO NA CALDA", estilos["subtitulo"]))
    cabecalho = [["Pos.", "Produto", "Formulação", "Dose", "Unid.", "Base", "Qtd/Carga", "Fonte"]]
    linhas = []
    for it in itens_ordenados:
        pos_str = "??" if it["posicao"] == 999 else str(it["posicao"])
        dose_str = str(it.get("dose", "—"))
        qtd_str = str(it.get("qtd_por_carga", "—"))
        linhas.append([
            pos_str,
            it["produto"],
            it.get("formulacao", "—"),
            dose_str,
            it.get("unidade", "—"),
            it.get("base", "—"),
            qtd_str,
            it.get("fonte", "—"),
        ])

    tabela_ordem = Table(cabecalho + linhas,
                          colWidths=[1 * cm, 4.5 * cm, 2.2 * cm, 1.5 * cm, 1.3 * cm, 1.5 * cm, 2 * cm, 2.5 * cm])
    estilo_tabela = [
        ("BACKGROUND", (0, 0), (-1, 0), _AZUL_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _CINZA_CLARO]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    # Destacar produtos pendentes em laranja
    for i, it in enumerate(itens_ordenados, start=1):
        if it.get("pendente"):
            estilo_tabela.append(("TEXTCOLOR", (0, i), (-1, i), _LARANJA))
    tabela_ordem.setStyle(TableStyle(estilo_tabela))
    story.append(tabela_ordem)
    story.append(Spacer(1, 0.4 * cm))

    # --- Pendências ---
    pendentes = [it for it in itens_ordenados if it.get("pendente")]
    if pendentes:
        story.append(Paragraph("PENDÊNCIAS", estilos["subtitulo"]))
        for it in pendentes:
            story.append(Paragraph(
                f"• {it['produto']}: {it.get('alerta_pendente', 'formulação não cadastrada')}",
                estilos["pendente"],
            ))
        story.append(Spacer(1, 0.3 * cm))

    # --- Alertas da extração ---
    if alertas:
        story.append(Paragraph("ALERTAS", estilos["subtitulo"]))
        for a in alertas:
            story.append(Paragraph(
                f"• [{a.get('tipo', '').upper()}] {a.get('descricao', '')} "
                f"— {a.get('item', '')}",
                estilos["alerta"],
            ))
        story.append(Spacer(1, 0.3 * cm))

    # --- Assinatura ---
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=8))
    dados_ass = [
        ["Responsável Técnico (nome/CREA):", "", "Data/Hora aprovação:"],
        [" " * 60, "", " " * 30],
    ]
    tabela_ass = Table(dados_ass, colWidths=[8 * cm, 1 * cm, 7 * cm])
    tabela_ass.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 1), (0, 1), 0.5, colors.black),
        ("LINEBELOW", (2, 1), (2, 1), 0.5, colors.black),
    ]))
    story.append(tabela_ass)

    doc.build(story)
    return buffer.getvalue()
