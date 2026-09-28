"""Presentation of the existing monthly/yearly engine data on a movable canvas."""
from dash import html
from finance_engine import brl, mes_corrente

MONTHS = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
          'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')


def viewport(stage, key, label):
    def button(text, action, title):
        return html.Button(text, type='button', title=title,
                           **{'data-canvas-action': action, 'aria-label': title})
    return html.Div([
        html.Div([
            html.Div([html.Strong(label), html.Span('Arraste para explorar · roda ou gesto de pinça para ampliar')],
                     className='canvas-caption'),
            html.Div([button('−', 'out', 'Diminuir zoom'),
                      html.Output('100%', className='canvas-zoom', **{'aria-label': 'Nível de zoom'}),
                      button('+', 'in', 'Aumentar zoom'),
                      button('Enquadrar', 'fit', 'Enquadrar todo o mapa'),
                      button('Início', 'reset', 'Restaurar a posição inicial')],
                     className='canvas-tools', role='toolbar', **{'aria-label': 'Navegação do mapa'}),
        ], className='canvas-toolbar'),
        html.Div(stage, className='mapa-scroll canvas-viewport', tabIndex=0, role='region',
                 **{'data-canvas-key': key, 'aria-label': label + '. Setas movem; + e − ampliam; F enquadra; 0 restaura.'}),
    ], className='canvas-shell')


def annual_board(lines, year):
    current = mes_corrente()
    cards = []
    for index, row in enumerate(lines):
        month = row['mes']
        forecast = month > current
        status = ('Sem renda lançada' if row['sem_dados'] else 'Previsão' if forecast
                  else 'Em andamento' if month == current else 'Registrado')
        def value(label, amount, tone):
            return html.Div([html.Span(label), html.Strong('R$ ' + brl(amount))],
                            className='annual-flow-node ' + tone)
        cards.append(html.Div([
            html.Div([html.H3(MONTHS[index]), html.Span(status, className='annual-status')],
                     className='annual-month-heading'),
            html.Div([
                value('Entradas', row['entrada'], 'income'), html.Span('→', className='annual-arrow'),
                value('Saídas', row['saida'], 'expense'), html.Span('→', className='annual-arrow'),
                html.Div([html.Span('Saldo do mês'),
                          html.Strong('Sem dados' if row['sem_dados'] else 'R$ ' + brl(row['sobra']))],
                         className='annual-flow-node balance ' + ('negative' if row['sobra'] < 0 else 'positive')),
            ], className='annual-flow'),
            html.Div('Contas R$ %s · faturas R$ %s · variáveis R$ %s' %
                     (brl(row['fixas']), brl(row['fatura']), brl(row['variaveis'])), className='annual-breakdown'),
            html.Button('Abrir decisões de ' + MONTHS[index].lower(),
                        id={'type': 'mapa-mes-abrir', 'mes': month}, n_clicks=0,
                        className='annual-open', type='button'),
        ], className='annual-month ' + ('forecast' if forecast else 'recorded'),
            style={'left': '%dpx' % (32 + (index % 3) * 544), 'top': '%dpx' % (32 + (index // 3) * 256)},
            **{'data-month': month, 'data-status': status}))
    stage = html.Div(cards, className='mapa-palco annual-stage', style={'width': '1672px', 'height': '1056px'})
    return viewport(stage, 'ano:' + str(year), 'Fluxos mensais · ' + str(year))
