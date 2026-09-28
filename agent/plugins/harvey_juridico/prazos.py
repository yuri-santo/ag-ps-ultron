"""Contagem de prazos processuais (CPC arts. 219, 220 e 224; CPP art. 798) com feriados nacionais.

Não conhece feriados estaduais/municipais nem portarias de suspensão dos tribunais: esses
devem ser informados em feriados_extras e sempre conferidos no calendário do tribunal.
"""
from datetime import date, timedelta


def pascoa(ano):
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados(ano, forenses=True):
    p = pascoa(ano)
    lista = {date(ano, 1, 1): 'Confraternização Universal', date(ano, 4, 21): 'Tiradentes', date(ano, 5, 1): 'Dia do Trabalho',
             date(ano, 9, 7): 'Independência', date(ano, 10, 12): 'Nossa Senhora Aparecida', date(ano, 11, 2): 'Finados',
             date(ano, 11, 15): 'Proclamação da República', date(ano, 12, 25): 'Natal',
             p - timedelta(days=2): 'Sexta-feira Santa'}
    if ano >= 2024:
        lista[date(ano, 11, 20)] = 'Dia Nacional de Zumbi e da Consciência Negra (Lei 14.759/2023)'
    if forenses:
        lista[p - timedelta(days=48)] = 'Carnaval (segunda) — sem expediente forense usual'
        lista[p - timedelta(days=47)] = 'Carnaval (terça) — sem expediente forense usual'
        lista[p + timedelta(days=60)] = 'Corpus Christi — ponto facultativo, sem expediente forense usual'
        lista[date(ano, 12, 8)] = 'Dia da Justiça (Lei 5.010/1966) — conferir no tribunal'
    return lista


def _recesso(d):
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)


def nao_util(d, extras, considerar_recesso, forenses=True):
    if d.weekday() >= 5:
        return 'fim de semana'
    motivo = feriados(d.year, forenses).get(d) or extras.get(d)
    if motivo:
        return motivo
    if considerar_recesso and _recesso(d):
        return 'recesso forense / suspensão de prazos (CPC, art. 220)'
    return ''


def _parse(value):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError('data_invalida_use_AAAA-MM-DD') from None


def calcular_prazo(data_inicial, dias, contagem='uteis', disponibilizacao_djen=False, feriados_extras=None,
                   considerar_recesso=True):
    dias = int(dias)
    if not 1 <= dias <= 3650:
        raise ValueError('dias_fora_do_limite')
    if contagem not in ('uteis', 'corridos'):
        raise ValueError('contagem_invalida')
    extras = {_parse(d): 'feriado/suspensão informado' for d in (feriados_extras or [])}
    evento = _parse(data_inicial)
    pulados = []

    def proximo_util(d):
        while True:
            motivo = nao_util(d, extras, considerar_recesso and contagem == 'uteis')
            if not motivo:
                return d
            pulados.append({'data': d.isoformat(), 'motivo': motivo})
            d += timedelta(days=1)

    passos = []
    if disponibilizacao_djen:
        publicacao = proximo_util(evento + timedelta(days=1))
        passos.append(f'Disponibilização {evento.isoformat()}; publicação considerada em {publicacao.isoformat()} (CPC, art. 224, § 2º).')
        evento = publicacao
    inicio = proximo_util(evento + timedelta(days=1))
    passos.append(f'Exclui-se o dia do começo; contagem inicia em {inicio.isoformat()} (CPC, art. 224, caput e § 3º).')
    atual, contados = inicio, 1
    while contados < dias:
        atual += timedelta(days=1)
        if contagem == 'uteis':
            motivo = nao_util(atual, extras, considerar_recesso)
            if motivo:
                pulados.append({'data': atual.isoformat(), 'motivo': motivo})
                continue
        contados += 1
    final = atual
    motivo = nao_util(final, extras, considerar_recesso and contagem == 'uteis')
    if motivo:
        final = proximo_util(final + timedelta(days=1))
        passos.append('Vencimento em dia não útil prorroga para o primeiro dia útil seguinte (CPC, art. 224, § 1º; CPP, art. 798, § 3º).')
    base = 'CPC, art. 219 (dias úteis)' if contagem == 'uteis' else 'contagem contínua (ex.: CPP, art. 798; prazos materiais)'
    return {'status': 'ok', 'data_final': final.isoformat(), 'inicio_contagem': inicio.isoformat(), 'dias': dias,
            'contagem': contagem, 'fundamento': base, 'passos': passos, 'dias_nao_uteis_considerados': pulados[:80],
            'avisos': ['Feriados estaduais/municipais e portarias de suspensão do tribunal NÃO estão incluídos; informe-os em feriados_extras e confira o calendário oficial do tribunal.',
                       'Prazo em dobro (Fazenda, MP, Defensoria, litisconsortes com procuradores distintos em autos físicos) deve ser aplicado antes, dobrando dias.']}
