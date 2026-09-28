"""LAN control-center API. Fixed roots and local WSL RPC; no credentials in the browser."""
import local_runtime
import pathlib,json,subprocess,time
ROOT=pathlib.Path(r'C:\Users\yurim\super agentes')
ALLOWED={'flow_session','content_research','home_automations','viral_research','campaigns','home_assistant','connections','kanban','task','task_reply','task_create','task_resume','rag_list','rag_search','knowledge','drive_list','drive_preview','workmail_list','workmail_read','router','agents','preferences'}
def document_path(name):
    path=(ROOT/name).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.suffix.lower() not in ('.md','.txt','.csv') or any(x.startswith('.') or x=='reunioes-privadas' for x in path.relative_to(ROOT).parts):raise ValueError('Documento fora da central')
    return path
def documents(query='',offset=0):
    items=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'name':p.name,'bytes':p.stat().st_size,'modified':p.stat().st_mtime} for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.md','.txt','.csv') and 'reunioes-privadas' not in p.parts and not any(x.startswith('.') for x in p.relative_to(ROOT).parts)]
    items=[x for x in items if query.casefold() in x['path'].casefold()]
    items.sort(key=lambda x:(x['path'].count('/'),-x['modified'],x['name']))
    offset=max(0,int(offset))
    return {'ok':True,'documents':items[offset:offset+60],'total':len(items),'offset':offset,'next_offset':offset+60 if offset+60<len(items) else None}
def dispatch(data):
    action=data.get('action')
    try:
        if action in ('applications','application_choice'):
            import app_inventory
            return app_inventory.snapshot() if action=='applications' else app_inventory.choose(data)
        if action in ('chat_start','chat_status'):
            import hub_jobs
            return hub_jobs.start(data) if action=='chat_start' else hub_jobs.status(data.get('job'))
        if action=='videos':
            import hub_media
            return hub_media.catalog()
        if action=='docs':return documents(str(data.get('query',''))[:150],data.get('offset',0))
        if action=='doc':
            path=document_path(str(data.get('path','')))
            if path.stat().st_size>2*1024*1024:raise ValueError('Documento excede 2 MiB')
            return {'ok':True,'name':path.name,'content':path.read_text(encoding='utf-8-sig')}
        if action not in ALLOWED:return {'ok':False,'error':'Operacao desconhecida'}
        return local_runtime.invoke('hub',data,timeout=100)
    except Exception as exc:return {'ok':False,'error':str(exc) if isinstance(exc,ValueError) else 'Consulta indisponivel: '+type(exc).__name__}
