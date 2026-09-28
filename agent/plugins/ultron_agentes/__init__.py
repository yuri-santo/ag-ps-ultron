"""Ferramentas por especialista (somente leitura), registradas pelo worker do ultron_team.

- bigode, buffett, tron: dados oficiais do Banco Central (SGS), BrasilAPI e cotações da B3 (yfinance).
- mrrobot: relatório da auditoria semanal de segurança (Lynis, Trivy, Gitleaks) e status dos backups (restic).
"""
import json

from . import financas, seguranca

PERFIS = {'bigode': 'financas', 'buffett': 'financas', 'tron': 'financas', 'mrrobot': 'seguranca'}

PROMPT_FIN = ('Dados de mercado: use bcb_serie (Banco Central, oficial) para Selic, CDI, IPCA, IGP-M, dólar PTAX; '
              'brasilapi para feriados, CNPJ e taxas; cotacao_b3 para ações/FIIs (.SA, fonte Yahoo, atraso possível). '
              'Sempre informe a data do dado e a fonte; não invente número que a ferramenta não retornou.')
PROMPT_SEG = ('Segurança: use seguranca_relatorio (auditoria semanal Lynis/Trivy/Gitleaks) e backup_status (restic). '
              'Relate data do relatório, severidade e o que corrigir; nunca exponha segredo encontrado, só arquivo e tipo.')


def _add(register, toolset, name, description, properties, required, operation):
    schema = {'name': name, 'description': description,
              'parameters': {'type': 'object', 'properties': properties, 'required': required}}

    def handler(args, **kwargs):
        try:
            # Modelos às vezes mandam campos extras (ex.: 'reason'); só os do schema chegam à função.
            clean = {k: v for k, v in (args or {}).items() if k in properties}
            return json.dumps(operation(**clean), ensure_ascii=False)
        except (ValueError, financas.FonteErro, FileNotFoundError) as exc:
            return json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({'status': 'error', 'error': type(exc).__name__}, ensure_ascii=False)
    register(name=name, toolset=toolset, schema=schema, handler=handler, description=description)


def register_agent_tools(register, profile, home=None, base=None):
    kind = PERFIS.get(profile)
    S = {'type': 'string'}
    if kind == 'financas':
        ts = 'ultron_financas'
        _add(register, ts, 'bcb_serie',
             'Série oficial do Banco Central (SGS): selic, selic_meta, cdi, ipca, igpm, inpc, dolar, euro, tr, poupanca ou código SGS numérico. '
             'Últimos N valores ou período (dd/mm/aaaa).',
             {'serie': S, 'ultimos': {'type': 'integer', 'minimum': 1, 'maximum': 120},
              'data_inicial': S, 'data_final': S}, ['serie'], financas.bcb_serie)
        _add(register, ts, 'brasilapi', 'BrasilAPI: feriados nacionais do ano, dados públicos de CNPJ, taxas (Selic/CDI/IPCA) ou banco pelo código.',
             {'recurso': {'type': 'string', 'enum': ['feriados', 'cnpj', 'taxas', 'banco']}, 'valor': S},
             ['recurso'], financas.brasilapi)
        _add(register, ts, 'cotacao_b3',
             'Cotação e dividendos de ação/FII/ETF da B3 (ex.: PETR4, MXRF11, BOVA11) via Yahoo Finance: último preço, variação, máx/mín 52 semanas, '
             'dividendos 12 meses e fechamentos mensais.',
             {'ticker': S, 'periodo': {'type': 'string', 'enum': ['1mo', '3mo', '6mo', '1y', '2y', '5y']}},
             ['ticker'], financas.cotacao_b3)
        return ts, PROMPT_FIN
    if kind == 'seguranca':
        ts = 'ultron_seguranca'
        _add(register, ts, 'seguranca_relatorio', 'Resumo da última auditoria de segurança (Lynis, Trivy, Gitleaks) do WSL/homelab.',
             {}, [], seguranca.relatorio)
        _add(register, ts, 'backup_status', 'Status dos backups restic (último snapshot, tamanho, verificação).',
             {}, [], seguranca.backup_status)
        return ts, PROMPT_SEG
    raise ValueError('perfil_sem_ferramentas')
