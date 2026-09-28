"""Executado no venv com yfinance: resumo de um ticker da B3 em JSON."""
import json
import sys

import yfinance as yf

ticker, periodo = sys.argv[1], sys.argv[2]
t = yf.Ticker(ticker)
hist = t.history(period=periodo, auto_adjust=False)
if hist.empty:
    print(json.dumps({'ticker': ticker, 'erro': 'sem_dados'}))
    sys.exit(0)
ultimo = hist.iloc[-1]
anterior = hist.iloc[-2] if len(hist) > 1 else ultimo
ano = t.history(period='1y', auto_adjust=False)
div = t.dividends
div12 = 0.0
if div is not None and len(div):
    corte = div.index.max() - __import__('pandas').Timedelta(days=365)
    div12 = float(div[div.index > corte].sum())
mensal = hist['Close'].resample('ME').last().dropna().tail(24)
out = {
    'ticker': ticker, 'data': str(hist.index[-1].date()), 'moeda': 'BRL',
    'preco': round(float(ultimo['Close']), 2), 'variacao_dia_pct': round((float(ultimo['Close']) / float(anterior['Close']) - 1) * 100, 2),
    'maxima_52s': round(float(ano['High'].max()), 2) if not ano.empty else None,
    'minima_52s': round(float(ano['Low'].min()), 2) if not ano.empty else None,
    'dividendos_12m_por_acao': round(div12, 4),
    'dividend_yield_12m_pct': round(div12 / float(ultimo['Close']) * 100, 2) if div12 else 0.0,
    'volume_medio_20d': int(hist['Volume'].tail(20).mean()) if 'Volume' in hist else None,
    'fechamentos_mensais': [{'mes': str(i.date())[:7], 'fechamento': round(float(v), 2)} for i, v in mensal.items()],
}
print(json.dumps(out, ensure_ascii=False))
