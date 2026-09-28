import local_runtime
"""Bounded asynchronous bridge for real Hermes turns; keeps HTTP requests short."""
import threading,subprocess,json,uuid,time
jobs={};lock=threading.Lock()
def start(data):
    if not str(data.get('text','')).strip() and data.get('listen') is not True:return {'ok':False,'error':'Digite uma mensagem'}
    data=dict(data)
    with lock:
        for key in list(jobs):
            if time.monotonic()-jobs[key]['created']>3600:jobs.pop(key)
        if sum(j['status']=='running' for j in jobs.values())>=2:return {'ok':False,'error':'Duas conversas em andamento. Aguarde.'}
        ident=uuid.uuid4().hex;jobs[ident]={'status':'running','created':time.monotonic()}
    def worker():
        try:
            if data.get('listen') is True:
                import hub_voice
                data['text']=hub_voice.listen()
            result=subprocess.run(local_runtime.command('chat'),input=json.dumps(data).encode(),capture_output=True,timeout=290,creationflags=subprocess.CREATE_NO_WINDOW)
            result.check_returncode();response=json.loads(result.stdout)
            if data.get('listen') is True:response['transcript']=data['text']
        except Exception as exc:response={'ok':False,'error':str(exc) if isinstance(exc,ValueError) else 'Conversa indisponivel: '+type(exc).__name__}
        with lock:jobs[ident].update(status='done',result=response)
    threading.Thread(target=worker,daemon=True).start();return {'ok':True,'job':ident}
def status(ident):
    with lock:
        job=jobs.get(ident)
        return {'ok':True,**job} if job else {'ok':False,'error':'Conversa nao encontrada'}
