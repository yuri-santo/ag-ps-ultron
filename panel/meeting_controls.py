import local_runtime
import datetime,json,os,pathlib,subprocess,threading,queue,wave,time,urllib.parse
import deck_runtime
_state={'recording':False};_lock=threading.Lock();_stop=None;_worker=None;_meeting_cache={}

def remote(action,**kwargs):
    request={'action':action,**kwargs}
    try:
        response=subprocess.run(local_runtime.command('workmail'),input=json.dumps(request).encode(),capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        response.check_returncode();return json.loads(response.stdout)
    except Exception as e:return {'ok':False,'error':type(e).__name__}

def meetings():
    def load():
        result=remote('meetings')
        if result.get('ok'):_meeting_cache.update({m['key']:m for m in result.get('meetings',[])})
        return result
    return deck_runtime.cached('meetings',60,load)

def inbox():return deck_runtime.cached('inbox',90,lambda:remote('inbox'))

def join(key):
    meetings();meeting=_meeting_cache.get(key)
    if not meeting:return {'ok':False,'error':'Atualize a agenda antes de entrar.'}
    # Abre no Saitama: Teams/Zoom pelo app instalado; Meet, Webex e outros no navegador do desktop.
    # O celular só recebe a confirmação e continua onde estava.
    import desktop_open
    result=desktop_open.open_meeting(meeting.get('join_url'),opener=os.startfile)
    if result.get('ok'):
        result.update(status='teams_open_requested' if result.get('provider')=='teams' else 'meeting_open_requested',subject=meeting['subject'])
    return result

def decline(key,confirmed):
    if confirmed is not True:return {'ok':False,'error':'Confirme a recusa deste convite.'}
    result=remote('decline',key=key,confirmed=True)
    if result.get('ok'):deck_runtime._cache.pop('meetings',None)
    return result

def unified(action,session_id=None,request_id=None,title='',value=''):
    import uuid
    payload={'action':action}
    if action not in ('status','records'):
        payload.update(request_id=request_id or uuid.uuid4().hex,title=title)
        if value:payload['value']=value
        if session_id:payload['session_id']=session_id
    try:
        proc=subprocess.run(local_runtime.command('meeting'),
            input=json.dumps(payload).encode(),capture_output=True,timeout=24,creationflags=subprocess.CREATE_NO_WINDOW)
        proc.check_returncode();return json.loads(proc.stdout)
    except Exception as exc:return {'ok':False,'error':'Ponte de reunião indisponível: '+type(exc).__name__}

def status():return unified('status')
def records():return unified('records')
def start(key=None,request_id=None):
    title=''
    if key:
        meetings();meeting=_meeting_cache.get(key)
        if not meeting:return {'ok':False,'error':'Atualize a agenda antes de iniciar.'}
        title=meeting['subject']
    return unified('start',request_id=request_id,title=title)
def pause(session_id=None,request_id=None):return unified('pause',session_id,request_id)
def resume(session_id=None,request_id=None):return unified('resume',session_id,request_id)
def stop(session_id=None,request_id=None):return unified('stop',session_id,request_id)

def end_meeting():
    recording=stop()
    try:
        response=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(pathlib.Path(__file__).with_name('leave-teams.ps1'))],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        teams=json.loads(response.stdout)
    except Exception as exc:teams={'ok':False,'status':type(exc).__name__}
    return {'ok':recording.get('ok',False),'recording':recording,'teams':teams}

def power(action,confirmed=False):
    if action=='cancel':args=['shutdown.exe','/a']
    elif action=='shutdown' and confirmed is True:args=['shutdown.exe','/s','/t','30','/c','Desligamento solicitado no Ultron Deck. Voce tem 30 segundos para cancelar.']
    else:return {'ok':False,'error':'Confirme o desligamento.'}
    result=subprocess.run(args,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    return {'ok':result.returncode==0,'scheduled_seconds':30 if action=='shutdown' else 0}
