"""Subject-scoped delivery review. Availability is never content approval.

This policy only releases a completed informational deliverable. It cannot
authorize tools, payments, publication or replay a failed execution.
"""
from concurrent.futures import ThreadPoolExecutor
import re
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower())
                   if not unicodedata.combining(c))


def pertinent_profiles(request, author, roster):
    # Deliberately use request spans, never quoted context, dates or note IDs.
    text = normalized(str(request))
    rules = {
        'thor': r'\b(sap|abap|s4hana|s/4hana|ecc)\b',
        'bigode': r'\b(orcamento|financas|fatura|contas a pagar|fluxo de caixa)\b',
        'harvey': r'\b(juridic\w*|contrato|processo judicial|legislacao)\b',
        'jesus': r'\b(saude|remedio|medicamento|dose|carvedilol|carverdiol|vitamina)\b',
        'maquiavel': r'\b(reuniao|transcricao|ata de reuniao)\b',
        'dona': r'\b(agenda|compromisso|calendario|lembrete)\b',
        'money': r'\b(tiktok|youtube|roteiro|marketing|video|anuncio)\b',
        'pink': r'\b(memoria|notebooklm|base de conhecimento)\b',
        'mrrobot': r'\b(seguranca|wireguard|firewall|rede|servidor)\b',
        'hercules': r'\b(backend|api|python|integracao)\b',
        'perseu': r'\b(frontend|interface|css|react)\b',
        'buffett': r'\b(investimento|dividendos|valuation)\b',
        'tron': r'\b(trading|trader|day trade)\b',
        'botura': r'\b(dieta|nutricao|macros)\b',
        'arnold': r'\b(treino|musculacao|corrida)\b',
        'tanos': r'\b(auditoria|audite)\b',
        'ironman': r'\b(arquitetura|validacao sistemica)\b',
    }
    found = [name for name, pattern in rules.items() if name in roster and re.search(pattern, text)]
    if re.search(r'\b(e-?mails?|gmail|mensagens corporativas)\b', text):
        mail = 'cris' if re.search(r'\b(profissional|corporativ\w*|easysapers|saint-gobain)\b', text) else 'greg'
        if mail in roster:
            found.append(mail)
    return sorted(set(found)) or [author if author in roster else 'ultron']


def technical_failure(exc):
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    code = (getattr(exc, 'status_code', None) or getattr(exc, 'code', None) or
            getattr(getattr(exc, 'response', None), 'status_code', None))
    if isinstance(code, int) and 400 <= code <= 599:
        return True
    if isinstance(exc, RuntimeError) and re.fullmatch(
            r'Auxiliary [\w -]+: provider returned a timeout shim instead of a completion', str(exc)):
        return True
    return type(exc).__name__ in {
        'APITimeoutError', 'APIConnectionError', 'ConnectTimeout', 'ReadTimeout',
        'ConnectError', 'RemoteProtocolError', 'RateLimitError', 'ServiceUnavailableError',
    }


def warning(votes):
    missing = sorted(name for name, vote in votes.items() if vote.get('verdict') == 'unavailable')
    if not missing:
        return ''
    names = ', '.join(name.capitalize() for name in missing)
    return ('\n\nConfianca limitada: revisao incompleta. Nao validado por ' + names +
            ' por indisponibilidade tecnica do modelo. O fluxo de aprovacao nao foi concluido.')


def collect(prepared, request, profiles, *, home, proof_id, context='', attempt=0, call=None):
    if call is None:
        from .reviewer import review_final
        call = review_final

    def one(profile):
        try:
            return call(prepared, request, profile=profile, home=home,
                        proof_id=proof_id + ':' + profile, context=context, attempt=attempt)
        except Exception as exc:
            if not technical_failure(exc):
                raise
            return dict(verdict='unavailable', completed=False, technical_error=type(exc).__name__,
                        served_identity=None, issues=[], checks=[])

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='delivery-review') as pool:
        return dict(zip(profiles, pool.map(one, profiles)))
