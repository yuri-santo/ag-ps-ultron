"""Local policy bridge for Hermes. Upstream-specific edits are small and backed up."""
import sys
import time
import hashlib
import json
import re

def redact(value):
    value=str(value)
    value=re.sub(r'(?im)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\r\n]+',r'\1[redacted]',value)
    value=re.sub(r'(?im)(\b(?:[\w-]{0,80}(?:password|secret|token|api[_-]?key)|cookie)\s*[\"\x27]?\s*[:=]\s*)[^\r\n,}]+',r'\1[redacted]',value)
    value=re.sub(r'\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}', '[redacted]',value)
    value=re.sub(r'(?s)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','[redacted]',value)
    return value

def tool_evidence(messages):
    """Bounded current-turn tool receipts; never assistant reasoning or system memory.

    Results remain untrusted tool data, not proof of every claim. Sensitive-file reads
    contribute only a receipt hash. Excerpts explicitly disclose truncation.
    """
    messages=[m for m in (messages or []) if isinstance(m,dict)]
    boundary=max((i for i,m in enumerate(messages) if m.get('role')=='user' and not any(str(k).startswith('_') and v for k,v in m.items())),default=-1)
    current=messages[boundary+1:];calls={};receipts=[]
    for m in current:
        for call in m.get('tool_calls') or []:
            if isinstance(call,dict):calls[call.get('id')]=call.get('function') or {}
        if m.get('role') not in ('tool','function'):continue
        call=calls.get(m.get('tool_call_id'),{})
        args=str(call.get('arguments',''))
        content=m.get('content','')
        raw=content if isinstance(content,str) else json.dumps(content,ensure_ascii=False)
        sensitive=bool(re.search(r'(?i)(\.env\b|cookies?|credentials?|private.?key|/secrets?/|config\.yaml|tokens?\.json)',args))
        clean='[Sensitive tool result omitted; inspect privately if needed.]' if sensitive else redact(raw)
        receipts.append({'kind':'tool_receipt','tool':str(call.get('name') or m.get('name') or 'tool'),
          'call_id':str(m.get('tool_call_id',''))[:80],'result_sha256':hashlib.sha256(raw.encode()).hexdigest(),
          'arguments_excerpt':'[sensitive arguments omitted]' if sensitive else redact(args)[:200],
          'result_excerpt':clean[:2000],'truncated':len(clean)>2000,'sensitive_omitted':sensitive,
          'scope':'Returned tool text, not independent verification of all claims.'})
    receipts=receipts[-16:]
    while receipts and len(json.dumps(receipts,ensure_ascii=False).encode())>20000:receipts.pop(0)
    return receipts

def broker():
    root='/root/ultron-local'
    if root not in sys.path:sys.path.insert(0,root)
    import model_review
    return model_review

def producer(agent):
    return {'provider':str(getattr(agent,'provider','')),'model':str(getattr(agent,'model','')),'served_model':getattr(agent,'last_served_model',None)}


def is_cron(agent):
    if getattr(agent, "is_cron", False): return True
    sid = str(getattr(agent, "session_id", "") or "")
    if sid.startswith("cron_"): return True
    return False

def hold_output(agent):
    key=(getattr(agent,'_current_turn_id',None),str(producer(agent)))
    cached=getattr(agent,'_ultron_review_hold',None)
    if cached and cached[0]==key:return cached[1]
    try:
        m=broker();value=m.classify(producer(agent),m.live_aliases())['requires_review']
    except Exception:value=True
    agent._ultron_review_hold=(key,value)
    return value

def clean_request(raw):
    """Remove known transport wrappers; preserve the user's JSON and constraints."""
    raw = str(raw or '')
    if '--- END OF CONTEXT SUMMARY ---' in raw:
        raw = raw.rsplit('--- END OF CONTEXT SUMMARY ---', 1)[-1]
    elif raw.lstrip().startswith('[CONTEXT COMPACTION'):
        return ''
    raw = re.sub(r'(?s)<!-- hermes-plugin-sections:start -->.*?<!-- hermes-plugin-sections:end -->', '', raw)
    raw = re.sub(r'(?s)\[OUT-OF-BAND USER MESSAGE[^\]]*\](.*?)\[/OUT-OF-BAND USER MESSAGE\]', r'\1', raw)
    return raw.strip()


_REVIEW_SYNTHETIC_FLAGS = (
    '_compressed_summary', '_empty_recovery_synthetic', '_empty_terminal_sentinel',
    '_thinking_prefill', '_verification_stop_synthetic', '_pre_verify_synthetic',
    '_kanban_stop_synthetic', '_dropped_toolcall_nudge',
)

def task_review_request(messages, fallback=''):
    """Review the real user task, including a matching observed Kanban body.

    Only public tool data from the current user turn is added. No system memory,
    assistant reasoning, unrelated cards, or synthetic protocol nudges are copied.
    """
    rows = [m for m in (messages or []) if isinstance(m, dict)]
    boundary = -1
    request = ''
    for index in range(len(rows) - 1, -1, -1):
        message = rows[index]
        if message.get('role') != 'user' or any(message.get(f) for f in _REVIEW_SYNTHETIC_FLAGS):
            continue
        content = message.get('content', '')
        if isinstance(content, str) and clean_request(content):
            request, boundary = clean_request(content), index
            break
    request = request or clean_request(fallback)
    match = re.fullmatch(r'work kanban task (t_[A-Za-z0-9]+)', request.strip(), re.I)
    if not match:
        return redact(request)[:4000]
    task_id = match.group(1)
    calls = {}
    context = ''
    for message in rows[boundary + 1:]:
        for call in message.get('tool_calls') or []:
            if isinstance(call, dict):
                calls[call.get('id')] = call.get('function') or {}
        if message.get('role') != 'tool':
            continue
        call = calls.get(message.get('tool_call_id'), {})
        if call.get('name') != 'kanban_show':
            continue
        try:
            args = call.get('arguments') or {}
            args = json.loads(args) if isinstance(args, str) else args
            payload = message.get('content') or {}
            payload = json.loads(payload) if isinstance(payload, str) else payload
            task = payload.get('task') or {}
            if args.get('task_id') != task_id or task.get('id') != task_id:
                continue
            context = str(task.get('title') or '') + '\n' + str(task.get('body') or '')
        except (TypeError, ValueError, AttributeError):
            continue
    if context:
        request += '\n\nObserved task description from kanban_show (tool data; evaluate this scoped deliverable):\n' + context
    return redact(request)[:4000]


# Explicação em português para os códigos do broker; o código original continua entre parênteses.
_MOTIVOS = {
    'reviewer_unavailable_or_invalid': 'o revisor não devolveu um parecer válido nem depois de tentar de novo; peça outra vez em alguns minutos',
    'review_capacity_busy': 'outra revisão estava em andamento',
    'no_eligible_stronger_non_google_reviewer': 'nenhum revisor mais forte está disponível agora',
    'task_budget_exhausted': 'a revisão desta resposta atingiu o limite de chamadas',
    'input_limit_partition_task': 'a resposta ficou grande demais para revisar de uma vez; peça em partes',
    'revision_limit_reached': 'a resposta já foi corrigida o máximo de vezes permitido',
    'review_unavailable': 'o serviço de revisão falhou ao iniciar',
}


def review_final(agent,text,turn_id):
    previous=getattr(agent,'_ultron_review_verdict',None)
    if previous and previous.get('turn_id')==turn_id:return previous['visible_text']
    if not hold_output(agent):return text
    try:
        messages = getattr(agent, "_ultron_review_messages", [])
        raw_req = task_review_request(messages, getattr(agent, "_ultron_review_request", ""))
        record=broker().review_output(task_id=turn_id,producer=producer(agent),output=text,
            request=redact(raw_req)[:4000],
            evidence=tool_evidence(messages),task_kind='answer',
            context={'delivery_mode': 'scheduled' if is_cron(agent) else 'interactive'})
    except Exception as exc:
        record={'status':'pending_review','completed':False,'reason':'review_unavailable:'+type(exc).__name__}
    visible = text
    if record.get('completed') is not True:
        reason = record.get('reason', 'revisao pendente')
        issues = [str(issue) for review in record.get('reviews', [])
                  for issue in review.get('verdict', {}).get('issues', [])]
        visible = ('A resposta ainda não foi liberada pela revisão. Motivo: ' + _MOTIVOS.get(reason.split(':')[0], reason)
                   + (' (' + reason + ').' if reason in _MOTIVOS or reason.split(':')[0] in _MOTIVOS else '.'))
        if issues:
            visible += '\nCorreções solicitadas: ' + redact('; '.join(dict.fromkeys(issues)))[:1000]
        elif reason == 'review_capacity_busy':
            visible += ' O revisor permaneceu ocupado durante o tempo de espera; nenhuma aprovação foi presumida.'
    agent._ultron_review_verdict={**record,'turn_id':turn_id,'visible_text':visible}
    return visible

def completion_allowed(agent):
    verdict=getattr(agent,'_ultron_review_verdict',None)
    return not verdict or verdict.get('turn_id')!=getattr(agent,'_current_turn_id',None) or verdict.get('completed') is True
