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
    messages, boundary = current_user_turn(messages)
    if boundary < 0:
        return []
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
    requested = str(getattr(agent, 'model', ''))
    served = getattr(agent, 'last_served_model', None)
    return {'provider': str(getattr(agent, 'provider', '')), 'model': served or requested,
            'requested_model': requested, 'served_model': served}


def is_cron(agent):
    if getattr(agent, "is_cron", False): return True
    if str(getattr(agent, "platform", "") or "") == "cron": return True
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
    '_kanban_stop_synthetic', '_dropped_toolcall_nudge', '_review_stop_synthetic',
)


def current_user_turn(messages):
    """Persistence metadata is not a synthetic user turn (notably _row_id)."""
    rows = [m for m in (messages or []) if isinstance(m, dict)]
    boundary = next((i for i in range(len(rows) - 1, -1, -1)
                     if rows[i].get('role') == 'user'
                     and not any(rows[i].get(f) for f in _REVIEW_SYNTHETIC_FLAGS)), -1)
    return rows, boundary


def request_text(content):
    if isinstance(content, str):
        return clean_request(content)
    if isinstance(content, list):
        texts = [part['text'] for part in content
                 if isinstance(part, dict) and part.get('type') in ('text', 'input_text')
                 and isinstance(part.get('text'), str)]
        return '[Multimodal user request; attachments require inspection.]\n' + '\n'.join(texts)
    return ''


def task_review_request(messages, fallback=''):
    """Review the real user task, including a matching observed Kanban body.

    Only public tool data from the current user turn is added. No system memory,
    assistant reasoning, unrelated cards, or synthetic protocol nudges are copied.
    """
    rows, boundary = current_user_turn(messages)
    request = (request_text(rows[boundary].get('content')) if boundary >= 0
               else clean_request(fallback))
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


_SOCIAL_REPLIES = (
    (r'(?:(?:oi|ol[aá])[,! ]+)?(?:voc[eê] )?(?:t[aá]|est[aá]) (?:por )?a[ií]',
     'Tô aqui. O que manda?'),
    (r'(?:oi|ol[aá]|e a[ií])', 'Oi! Como posso ajudar?'),
    (r'(?:bom dia|boa tarde|boa noite)', None),
    (r'(?:tudo bem(?: com voc[eê])?|como (?:voc[eê] )?est[aá]|como vai voc[eê])',
     'Tudo bem por aqui. E com você?'),
    (r'(?:obrigad[oa]|valeu)', 'Por nada!'),
)


def triage_request(request):
    """Only a complete standalone social utterance admits local validation."""
    normalized = re.sub(r'\s+', ' ', str(request or '').strip().lower())
    normalized = normalized.strip(' \t\r\n!?.,')
    return 'social' if any(re.fullmatch(pattern, normalized) for pattern, _ in _SOCIAL_REPLIES) else 'review'


def social_response(request, candidate):
    """Use a closed response set, never approve arbitrary short model output."""
    normalized = re.sub(r'\s+', ' ', str(request or '').strip().lower()).strip(' \t\r\n!?.,')
    fallback = next((reply or normalized.capitalize() + '! Como posso ajudar?'
                     for pattern, reply in _SOCIAL_REPLIES if re.fullmatch(pattern, normalized)),
                    'Oi! Como posso ajudar?')
    return fallback


def review_final(agent,text,turn_id):
    messages = getattr(agent, "_ultron_review_messages", [])
    rows, boundary = current_user_turn(messages)
    source = rows[boundary].get('content') if boundary >= 0 else None
    current = rows[boundary + 1:] if boundary >= 0 else rows
    tool_attempt = any(m.get('role') in ('tool', 'function')
                       or m.get('tool_calls') or m.get('function_call') for m in current)
    raw_req = task_review_request(messages, getattr(agent, "_ultron_review_request", ""))
    if is_cron(agent) and getattr(agent, '_ultron_cron_task', None):
        raw_req = redact(agent._ultron_cron_task)[:4000]
    evidence = tool_evidence(messages)
    if is_cron(agent):
        evidence += [item for item in (getattr(agent, '_ultron_cron_evidence', None) or [])
                     if isinstance(item, dict)][:8]
    input_hash = hashlib.sha256(json.dumps(
        [source, raw_req, text, evidence, bool(tool_attempt), producer(agent), is_cron(agent)],
        sort_keys=True, ensure_ascii=True, default=str).encode()).hexdigest()
    previous = getattr(agent, '_ultron_review_verdict', None)
    if previous and previous.get('turn_id') == turn_id and previous.get('input_sha256') == input_hash:
        return previous['visible_text']
    # Inspect the full original input, not the truncated/redacted reviewer excerpt.
    if (not is_cron(agent) and isinstance(source, str)
            and triage_request(source) == 'social' and not tool_attempt):
        visible = social_response(source, text)
        agent._ultron_review_verdict = {
            'turn_id': turn_id, 'status': 'approved', 'completed': True,
            'reason': 'local_social_validation', 'validator': 'standalone_social_v1',
            'request_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'output_sha256': hashlib.sha256(visible.encode()).hexdigest(),
            'input_sha256': input_hash, 'visible_text': visible,
        }
        return visible
    agent._ultron_review_verdict = None
    if not hold_output(agent):return text
    try:
        record=broker().review_output(task_id=turn_id,producer=producer(agent),output=text,
            request=redact(raw_req)[:4000],
            evidence=evidence,task_kind='answer',
            context={'delivery_mode': 'scheduled' if is_cron(agent) else 'interactive'})
    except Exception as exc:
        record={'status':'pending_review','completed':False,'reason':'review_unavailable:'+type(exc).__name__}
    visible = text
    if record.get('completed') is not True:
        visible = 'Não consegui concluir a revisão desta resposta. A entrega ainda não está pronta; tente novamente em instantes.'
    agent._ultron_review_verdict={**record,'turn_id':turn_id,'input_sha256':input_hash,'visible_text':visible}
    return visible


def review_stop_feedback(agent, text, messages, turn_id):
    """Review before persistence and return reviewer findings only to the agent loop."""
    agent._ultron_review_messages = messages
    review_final(agent, text, turn_id)
    verdict = getattr(agent, '_ultron_review_verdict', None) or {}
    if verdict.get('status') != 'revision_required':
        return None
    issues = [str(issue) for review in verdict.get('reviews', [])
              for issue in review.get('verdict', {}).get('issues', [])]
    return redact('; '.join(dict.fromkeys(issues)))[:1500] or 'A resposta não atende ao pedido original.'

def completion_allowed(agent):
    verdict=getattr(agent,'_ultron_review_verdict',None)
    return not verdict or verdict.get('turn_id')!=getattr(agent,'_current_turn_id',None) or verdict.get('completed') is True
