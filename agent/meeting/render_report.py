"""Ata formal de reunião (PDF) com a identidade do Ultron, sem descartar o registro original.

Layout no modelo "Ata formal de reunião": cabeçalho com logotipo e título, e as seções
Chamada, Participantes, Aprovação das Atas Anteriores, Relatórios Apresentados,
Assuntos Pendentes, Deliberações e Encerramento. A análise executiva e a transcrição
integral seguem como anexos, então nada do relatório antigo se perde.

Só usa dados registrados (sessão, convite, consolidação com citações). O que não foi
apurado aparece como "não apurado", nunca inventado.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

try:
    if __package__:
        from .ticket_context import references
    else:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from meeting_copilot.ticket_context import references
except Exception:  # renderer continua útil fora do plugin (testes, reprocessamento)
    def references(sources):
        return '\n'.join(f"{s.get('id', '')} — {s.get('title', '')}".strip(' —') for s in sources or []
                         if str(s.get('id', '')).lower().startswith(('chamado', 'ticket')))

# Identidade Ultron (Stream Deck): acento lilás, tinta quase preta. O lilás puro tem pouco
# contraste em papel branco, então títulos usam o tom profundo da mesma cor.
INK = '#101018'
ACCENT = '#b6a0ff'
ACCENT_DEEP = '#5a45b5'
ACCENT_SOFT = '#f1edff'
MUTED = '#5d5e70'
LINE = '#d9d0ff'
BRT = timezone(timedelta(hours=-3))
NAO_APURADO = 'não apurado pelo registro automático'


def _dt(value):
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), BRT)
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed.astimezone(BRT) if parsed.tzinfo else parsed.replace(tzinfo=BRT)


def _data(dt):
    meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
             'setembro', 'outubro', 'novembro', 'dezembro']
    return f'{dt.day} de {meses[dt.month - 1]} de {dt.year}' if dt else NAO_APURADO


def _hora(dt):
    return dt.strftime('%H:%M') if dt else NAO_APURADO


def _pessoa(value):
    if isinstance(value, dict):
        return value.get('name') or value.get('email') or value.get('address') or ''
    return str(value or '')


def build_minutes(data):
    """Transforma o registro da reunião nos campos da ata. Função pura, testável."""
    session = data.get('session') or {}
    state = session.get('state') or {}
    meeting = state.get('meeting') or {}
    consolidated = data.get('consolidated') or state.get('consolidated') or session.get('consolidated') or {}
    records = data.get('records')
    if records is None:
        records = consolidated.get('records') or []
    inicio = _dt(meeting.get('start')) if meeting.get('start') else _dt(session.get('created'))
    fim = _dt(data.get('ended_at')) or _dt(session.get('ended')) or _dt(state.get('ended'))
    titulo = meeting.get('subject') or session.get('title') or 'Reunião'
    escopo = ' / '.join(x for x in (state.get('ticket_client') or '', state.get('project') or '') if x)
    join_url = str(meeting.get('join_url') or meeting.get('online_meeting_url') or '')
    local = meeting.get('location') or ('Microsoft Teams' if 'teams.' in join_url else '') or 'ambiente virtual (áudio capturado no Saitama)'
    organizador = _pessoa(meeting.get('organizer')) or NAO_APURADO
    presidente = _pessoa(data.get('chair')) or NAO_APURADO
    convocados = [p for p in (_pessoa(a) for a in meeting.get('attendees') or []) if p]
    canais = {e for e in re.findall(r'\] (Yuri — microfone|Reunião — áudio recebido)', data.get('transcript') or '')}
    presentes = []
    eventos = data.get('transcript_events') or []
    if 'Yuri — microfone' in canais or any(ev.get('channel') == 'mic' for ev in eventos):
        presentes.append('Yuri Santos (microfone local)')
    speakers = data.get('speakers') or {}
    rotulos = speakers.get('rotulos') or {}
    vozes = int(speakers.get('vozes') or 0)
    if vozes:
        presentes.append(f"{vozes} voz(es) distinta(s) no áudio da reunião (Participante 1 a {vozes}; "
                         'separadas por diarização local, nomes não identificados automaticamente)')
    elif 'Reunião — áudio recebido' in canais or any(ev.get('channel') == 'loopback' for ev in eventos):
        presentes.append('demais participantes pelo áudio da reunião (identificação nominal não disponível)')
    if speakers.get('source') == 'platform_captions':
        presentes.extend(str(label) + ' (rótulo da plataforma; identidade não verificada)'
                         for label in speakers.get('labels', []))
    citation_labels = {}
    for tid in [str(ev.get('id')) for ev in eventos if ev.get('id')] + [
            str(tid) for record in records for tid in record.get('transcript_ids', [])]:
        if tid not in citation_labels:
            citation_labels[tid] = f'F{len(citation_labels) + 1:03d}'
    transcricao = data.get('transcript') or ''
    if eventos:
        linhas = []
        for ev in eventos:
            quando = _dt(ev.get('at'))
            rotulo = ('Yuri — microfone' if ev.get('channel') == 'mic' else
                      rotulos.get(str(ev.get('id')), 'Reunião — áudio recebido') if ev.get('channel') == 'loopback'
                      else rotulos.get(str(ev.get('id')), str(ev.get('channel') or '')))
            if rotulos and ev.get('channel') == 'loopback' and str(ev.get('id')) in rotulos:
                rotulo += ' (áudio da reunião)'
            aviso = '[Baixa confiança — revisar áudio] ' if ev.get('confidence') == 'low' else ''
            ref = citation_labels.get(str(ev.get('id')), '')
            linhas.append(f"[{ref} · {quando.strftime('%d/%m %H:%M:%S') if quando else ref}] {rotulo}\n{aviso}{ev.get('text', '')}")
        transcricao = '\n\n'.join(linhas)
    decisoes = [r for r in records if r.get('status') == 'confirmed' and r.get('kind') == 'decision']
    acoes = [r for r in records if r.get('status') == 'confirmed' and r.get('kind') == 'action']
    revogadas = [r for r in records if r.get('status') == 'revoked']
    pendentes = list(data.get('pending_findings') or [])
    relatorios = references(data.get('sources') or []) or ''
    return {
        'titulo': titulo, 'escopo': escopo, 'data': _data(inicio), 'inicio': _hora(inicio), 'fim': _hora(fim),
        'local': local, 'presidente': presidente, 'organizador': organizador,
        'secretaria': 'Ultron (secretaria automatizada)',
        'convocados': convocados, 'presentes': presentes, 'decisoes': decisoes, 'acoes': acoes,
        'revogadas': revogadas, 'pendentes': pendentes, 'relatorios': relatorios,
        'sessao': session.get('id', ''), 'report_text': data.get('report_text') or '',
        'transcript': transcricao, 'rotulos': rotulos, 'vozes': vozes, 'rejeitados': data.get('rejected', consolidated.get('rejected', 0)),
        'citation_labels': citation_labels,
        'quality': {'transcript_events': len(eventos),
                    'low_confidence': sum(ev.get('confidence') == 'low' for ev in eventos),
                    'rejected': data.get('rejected', consolidated.get('rejected', 0)),
                    'pending_audio': state.get('pending_audio', 0)},
    }


def citation(record, ata):
    labels = [ata['citation_labels'].get(str(tid), 'referência indisponível')
              for tid in record.get('transcript_ids', [])]
    return ' · '.join(filter(None, [_stamp(record), ', '.join(labels)]))


def executive_lines(ata):
    lines = [f"{len(ata['decisoes'])} decisão(ões) e {len(ata['acoes'])} ação(ões) confirmadas no registro."]
    for record in (ata['decisoes'] + ata['acoes'])[:5]:
        kind = 'Decisão' if record.get('kind') == 'decision' else 'Ação'
        excerpt = str(record.get('text', ''))
        if len(excerpt) > 320:
            excerpt = excerpt[:317] + '...'
        lines.append(f"{kind}: {excerpt} [{citation(record, ata)}]")
    if not ata['decisoes'] and not ata['acoes']:
        lines.append('Não há conclusões confirmadas disponíveis; consultar a análise e as falas.')
    quality = ata['quality']
    lines.append(f"Qualidade: {quality['rejected']} registro(s)/bloco(s) rejeitado(s); "
                 f"{quality['low_confidence']} fala(s) sinalizada(s) com baixa confiança; "
                 f"{quality['pending_audio']} áudio(s) pendente(s).")
    return lines


def quem_falou(record, rotulos):
    nomes = []
    for tid in record.get('transcript_ids', []):
        nome = (rotulos or {}).get(str(tid))
        if nome and nome not in nomes:
            nomes.append(nome)
    return ', '.join(nomes)


def _stamp(record):
    dt = _dt(record.get('at'))
    return dt.strftime('%H:%M') if dt else ''


def _logo(canvas, x, y, size):
    """Ícone hexagonal do Ultron (o mesmo do botão do Stream Deck) desenhado em vetor."""
    from reportlab.lib import colors
    s = size / 24.0

    def pt(px, py):
        return x + px * s, y + (24 - py) * s
    canvas.saveState()
    canvas.setLineJoin(1)
    canvas.setLineCap(1)
    canvas.setFillColor(colors.HexColor(ACCENT_SOFT))
    canvas.setStrokeColor(colors.HexColor(ACCENT_DEEP))
    canvas.setLineWidth(max(1.2, 1.9 * s))
    hexagon = canvas.beginPath()
    for i, (px, py) in enumerate([(12, 2), (21, 7), (21, 17), (12, 22), (3, 17), (3, 7)]):
        (hexagon.moveTo if i == 0 else hexagon.lineTo)(*pt(px, py))
    hexagon.close()
    canvas.drawPath(hexagon, stroke=1, fill=1)
    canvas.setStrokeColor(colors.HexColor(ACCENT))
    inner = canvas.beginPath()
    inner.moveTo(*pt(7, 9)); inner.lineTo(*pt(12, 12)); inner.lineTo(*pt(17, 9))
    inner.moveTo(*pt(12, 12)); inner.lineTo(*pt(12, 18))
    canvas.drawPath(inner, stroke=1, fill=0)
    canvas.restoreState()


def _swoosh(canvas, x0, y0, width):
    """Faixa curva sob o logotipo, como no modelo, em degradê lilás."""
    from reportlab.lib import colors
    canvas.saveState()
    steps = 14
    for i in range(steps):
        t = i / (steps - 1)
        canvas.setStrokeColor(colors.HexColor(ACCENT_DEEP) if t > .6 else colors.HexColor(ACCENT))
        canvas.setStrokeAlpha(.25 + .6 * t)
        canvas.setLineWidth(1.2 + 2.6 * t)
        path = canvas.beginPath()
        path.moveTo(x0 + width * .05, y0 + 2)
        path.curveTo(x0 + width * .35, y0 - 10 - t * 2, x0 + width * .85, y0 - 8, x0 + width, y0 + 14 + t * 6)
        canvas.drawPath(path, stroke=1, fill=0)
    canvas.restoreState()


def render(data, destination):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)
    regular, bold = 'Helvetica', 'Helvetica-Bold'
    for name, candidates in (('AtaRegular', ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf']),
                             ('AtaBold', ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf'])):
        for path in candidates:
            if Path(path).exists():
                pdfmetrics.registerFont(TTFont(name, path))
                if name == 'AtaRegular':
                    regular = name
                else:
                    bold = name
                break

    ata = build_minutes(data)
    body = ParagraphStyle('AtaBody', fontName=regular, fontSize=9.6, leading=15, textColor=colors.HexColor(INK),
                          spaceAfter=3, splitLongWords=True)
    small = ParagraphStyle('AtaSmall', parent=body, fontSize=8, leading=11, textColor=colors.HexColor(MUTED))
    heading = ParagraphStyle('AtaHeading', parent=body, fontName=bold, fontSize=12.5, leading=16,
                             textColor=colors.HexColor(ACCENT_DEEP), spaceBefore=12, spaceAfter=5)
    sub = ParagraphStyle('AtaSub', parent=heading, fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=3)
    mono = ParagraphStyle('AtaMono', parent=body, fontSize=8.2, leading=11.5)
    cell = ParagraphStyle('AtaCell', parent=body, fontSize=8.6, leading=11.5, spaceAfter=0)
    cell_head = ParagraphStyle('AtaCellHead', parent=cell, fontName=bold, textColor=colors.HexColor(ACCENT_DEEP))

    def p(text, style=body):
        return Paragraph(text, style)

    def e(text):
        return escape(str(text))

    def lista(nomes):
        return ', '.join(e(n) for n in nomes) if nomes else NAO_APURADO

    parts = [Spacer(1, 22 * mm), p(e(ata['titulo']), sub), p('Resumo executivo', heading)]
    parts.extend(p(e(line)) for line in executive_lines(ata))
    escopo = f" do {e(ata['escopo'])}" if ata['escopo'] else ''
    nome = '' if ata['titulo'].strip().lower() in ('reunião', 'reuniao', '') else f" <b>{e(ata['titulo'])}</b>"
    parts += [p('Chamada', heading),
              p(f"A reunião{nome}{escopo} foi realizada em {e(ata['data'])}, em "
                f"{e(ata['local'])}. Início registrado: {e(ata['inicio'])}. "
                f"Organizador do convite: {e(ata['organizador'])}. Presidência: {e(ata['presidente'])}.")]
    parts += [p('Participantes', heading),
              p(f"Presença registrada no áudio: {lista(ata['presentes'])}."),
              p(f"Convocados pelo convite: {lista(ata['convocados'])}."),
              p(f"Membros ausentes: {NAO_APURADO} (a captura não confirma presença nominal).")]

    parts.append(p('Assuntos Pendentes', heading))
    if ata['pendentes'] or ata['revogadas']:
        for item in ata['pendentes']:
            claim = item.get('claim') if isinstance(item, dict) else str(item)
            question = item.get('question') if isinstance(item, dict) else ''
            parts.append(p('• ' + e(claim) + (f' <font color="{MUTED}">— pergunta sugerida: {e(question)}</font>' if question else '')))
        for record in ata['revogadas']:
            parts.append(p(f"• Revogado/corrigido: {e(record.get('text', ''))} "
                           f"<font color=\"{MUTED}\">[{e(citation(record, ata))}]</font>"))
        if ata['pendentes']:
            parts.append(p('Itens acima são sugestões do copiloto pendentes de confirmação; não são decisões da reunião.', small))
    else:
        parts.append(p('Nenhum assunto pendente registrado.'))

    parts.append(p('Deliberações', heading))
    if ata['decisoes']:
        for record in ata['decisoes']:
            autor = quem_falou(record, ata['rotulos'])
            parts.append(p(f"• {e(record.get('text', ''))} <font color=\"{MUTED}\">[{_stamp(record)}; "
                           + (f"{e(autor)}; " if autor else '')
                           + f"{e(citation(record, ata))}]</font>"))
    else:
        parts.append(p('Nenhuma decisão confirmada com citação válida.'))
    if ata['acoes']:
        parts.append(p('Encaminhamentos', sub))
        rows = [[p('Ação', cell_head), p('Responsável', cell_head), p('Prazo', cell_head), p('Registro', cell_head)]]
        for record in ata['acoes']:
            rows.append([p(e(record.get('text', '')), cell), p(e(record.get('owner') or 'não informado'), cell),
                         p(e(record.get('deadline') or 'não informado'), cell),
                         p(e(citation(record, ata)), cell)])
        table = Table(rows, colWidths=[78 * mm, 32 * mm, 26 * mm, 34 * mm], repeatRows=1, splitInRow=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ACCENT_SOFT)),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT_DEEP)),
            ('LINEBELOW', (0, 1), (-1, -1), 0.4, colors.HexColor(LINE)),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        parts.append(table)
    if ata['rejeitados']:
        parts.append(p(f"Lacunas de validação: {ata['rejeitados']} registro(s)/bloco(s) rejeitado(s); "
                       'conferir a transcrição integral.', small))

    assinatura = Table([[p('_' * 38, body), p('_' * 38, body)],
                        [p(f"{e(ata['presidente'])}<br/>Presidente", small), p('Ultron<br/>Secretaria', small)]],
                       colWidths=[85 * mm, 85 * mm])
    assinatura.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 0), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    parts.append(KeepTogether([
        p('Encerramento', heading),
        p(f"Fim registrado da captura: {e(ata['fim'])}. Documento gerado a partir dos registros disponíveis; "
          'a aprovação dos participantes não foi verificada.'),
        p(f"Gerado por: Ultron · Revisão: ______________________ · Sessão {e(ata['sessao'])}", small),
        Spacer(1, 9 * mm), assinatura]))

    def texto(title, text, style=body):
        parts.append(p(e(title), heading))
        lines = [piece for line in (text or '').split('\n')
                 for piece in ([line[i:i + 1500] for i in range(0, len(line), 1500)] or [''])]
        for line in lines:
            clean = line.strip()
            if clean.startswith('#'):
                parts.append(p(e(clean.lstrip('#').strip()), sub))
                continue
            clean = e(line)
            clean = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', clean)
            clean = re.sub(r'`([^`]+)`', r'<font face="Courier">\1</font>', clean)
            if line.lstrip().startswith(('- ', '* ')):
                clean = '• ' + clean.lstrip()[2:]
            parts.append(p(clean or '&#160;', style))

    parts.append(PageBreak())
    texto('Anexo I — Análise executiva da reunião', ata['report_text'] or 'Análise indisponível.')
    parts.append(PageBreak())
    texto('Anexo II — Transcrição integral (horários e origem do áudio)', ata['transcript'] or '[Nenhuma fala transcrita]', mono)
    parts.append(PageBreak())
    texto('Índice de referências das falas', '\n'.join(
        f'{label} = {tid}' for tid, label in ata['citation_labels'].items()), mono)
    if ata['relatorios'].strip():
        texto('Contexto consultado — documentos externos à reunião', ata['relatorios'])
    if data.get('include_internal_evidence'):
        if data.get('sources'):
            texto('Anexo III — Referências internas usadas na análise',
                  json.dumps(data['sources'], ensure_ascii=False, indent=2), mono)
        if data.get('full_record'):
            parts.append(PageBreak())
            texto('Registro interno: falas, análises e mensagens privadas', data['full_record'], mono)

    width, height = A4

    def first_page(canvas, document):
        _logo(canvas, 40, height - 92, 46)
        canvas.setFont(bold, 17)
        canvas.setFillColor(colors.HexColor(INK))
        canvas.drawString(94, height - 64, 'ULTRON')
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(95, height - 76, 'COMMAND DECK · SAITAMA')
        _swoosh(canvas, 36, height - 108, 230)
        canvas.setFont(bold, 16)
        canvas.setFillColor(colors.HexColor(ACCENT_DEEP))
        canvas.drawRightString(width - 40, height - 62, 'ATA FORMAL DE REUNIÃO')
        canvas.setFont(regular, 8.5)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawRightString(width - 40, height - 76, ata['data'])
        footer(canvas, document)

    def later_pages(canvas, document):
        _logo(canvas, 40, height - 46, 16)
        canvas.setFont(bold, 8.5)
        canvas.setFillColor(colors.HexColor(ACCENT_DEEP))
        canvas.drawString(60, height - 38, 'ATA FORMAL DE REUNIÃO')
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor(MUTED))
        short_title = ata['titulo']
        while short_title and pdfmetrics.stringWidth(short_title, regular, 8) > width - 275:
            short_title = short_title[:-1]
        if short_title != ata['titulo']:
            short_title = short_title[:-3] + '...'
        canvas.drawRightString(width - 40, height - 38, short_title)
        canvas.setStrokeColor(colors.HexColor(LINE))
        canvas.setLineWidth(.6)
        canvas.line(40, height - 50, width - 40, height - 50)
        footer(canvas, document)

    def footer(canvas, document):
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(40, 22, 'Ultron · ata gerada a partir do registro da reunião; conferir antes de assinar')
        canvas.drawRightString(width - 40, 22, f'Página {document.page}')
        canvas.setStrokeColor(colors.HexColor(ACCENT))
        canvas.setLineWidth(1.2)
        canvas.line(40, 32, width - 40, 32)

    doc = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=40, leftMargin=40, topMargin=58, bottomMargin=46,
                            title='Ata formal de reunião — ' + ata['titulo'], author='Ultron')
    doc.build(parts, onFirstPage=first_page, onLaterPages=later_pages)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('output')
    args = parser.parse_args()
    render(json.loads(Path(args.input).read_text(encoding='utf-8')), args.output)
