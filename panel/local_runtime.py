"""Bounded Windows -> Debian WSL execution. No dependency on a VPS tunnel."""
import subprocess,json,os,time
DISTRO=os.environ.get('ULTRON_WSL_DISTRO','Debian')
SCRIPTS={
 'hub':('/usr/local/lib/hermes-agent/venv/bin/python','/root/ultron-local/deck_hub.py'),
 'chat':('/usr/local/lib/hermes-agent/venv/bin/python','/root/ultron-local/deck_chat.py'),
 'transcribe':('/usr/local/lib/hermes-agent/venv/bin/python','/root/ultron-local/deck_transcribe.py'),
 'workmail':('/root/tools/venv/bin/python','/root/ultron-local/deck_workmail.py'),
 'meeting':('/usr/local/lib/hermes-agent/venv/bin/python','/root/.hermes/plugins/meeting_copilot/control.py'),
 'status':('/usr/bin/python3','/root/ultron-local/status.py'),
}
def command(name):return ['wsl.exe','-d',DISTRO,'-u','root','--exec',*SCRIPTS[name]]
READ_ACTIONS={'agents','kanban','task','knowledge','rag_list','rag_search','drive_list','drive_preview','workmail_list','workmail_read','router','preferences','connections'}
def _read_only(name,payload):
 if name=='status':return True
 if name=='hub':return (payload or {}).get('action') in READ_ACTIONS
 if name=='meeting':return (payload or {}).get('action') in ('status','records')
 return False

def invoke(name,payload=None,timeout=100):
 attempts=2 if _read_only(name,payload) else 1
 deadline=time.monotonic()+timeout
 for attempt in range(attempts):
  result=subprocess.run(command(name),input=json.dumps(payload or {}).encode(),capture_output=True,timeout=max(.1,deadline-time.monotonic()),creationflags=subprocess.CREATE_NO_WINDOW)
  if result.returncode and attempt+1<attempts:
   output=(result.stdout or b'')+(result.stderr or b'')
   message=output.decode('utf-16-le' if b'\x00' in output else 'utf-8',errors='replace').lower()
   if 'wsl/service/0x8007274c' in message and deadline-time.monotonic()>1:
    time.sleep(.3);continue
  result.check_returncode();return json.loads(result.stdout)
