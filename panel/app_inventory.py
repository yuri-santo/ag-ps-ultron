"""Local program inventory and foreground duration. Never reads titles or keystrokes."""
import ctypes,json,os,pathlib,sqlite3,threading,time,winreg
ROOT=pathlib.Path(os.environ['LOCALAPPDATA'])/'UltronDeck';ROOT.mkdir(exist_ok=True)
DB=ROOT/'applications.sqlite'
LOCK=threading.Lock()
GROUPS={'notes':['obsidian','onenote','notepad','notion'], 'editor':['visual studio code','code','notepad++','sublime'],
        'communication':['teams','telegram','outlook','thunderbird','whatsapp'],'browser':['chrome','edge','firefox','brave'],
        'creation':['obs studio','blender','davinci','capcut','shotcut','gimp','inkscape']}
def group(name):
 for category,terms in GROUPS.items():
  if any(t in name.lower() for t in terms):return category
 return 'other'
def db():
 con=sqlite3.connect(DB,timeout=10);con.row_factory=sqlite3.Row
 con.executescript('''CREATE TABLE IF NOT EXISTS apps (id TEXT PRIMARY KEY,name TEXT,category TEXT,present INTEGER,last_seen REAL);
 CREATE TABLE IF NOT EXISTS usage (name TEXT PRIMARY KEY,seconds INTEGER,last_seen REAL);
 CREATE TABLE IF NOT EXISTS choices (missing TEXT PRIMARY KEY,replacement TEXT,decided REAL);''');return con
def installed():
 found={}
 for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
  for location in (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'):
   try:
    with winreg.OpenKey(hive,location) as root:
     for i in range(winreg.QueryInfoKey(root)[0]):
      try:
       key=winreg.EnumKey(root,i)
       with winreg.OpenKey(root,key) as item:name=winreg.QueryValueEx(item,'DisplayName')[0]
       if name and len(name)<200:found[name.casefold()]={'name':name,'category':group(name)}
      except OSError:continue
   except OSError:continue
 return found
def scan():
 data=installed()
 if not data:raise RuntimeError('Inventário vazio; estado anterior preservado')
 with LOCK,db() as con:
  con.execute('UPDATE apps SET present=0')
  for key,item in data.items():con.execute('INSERT INTO apps VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,category=excluded.category,present=1,last_seen=excluded.last_seen',(key,item['name'],item['category'],1,time.time()))
 return len(data)
def foreground():
 user=ctypes.windll.user32;kernel=ctypes.windll.kernel32
 pid=ctypes.c_ulong();user.GetWindowThreadProcessId(user.GetForegroundWindow(),ctypes.byref(pid))
 kernel.OpenProcess.restype=ctypes.c_void_p;kernel.CloseHandle.argtypes=[ctypes.c_void_p]
 kernel.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
 handle=kernel.OpenProcess(0x1000,False,pid.value)
 if not handle:return None
 try:
  buffer=ctypes.create_unicode_buffer(32768);length=ctypes.c_ulong(len(buffer))
  if kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(length)):return pathlib.Path(buffer.value).stem
 finally:kernel.CloseHandle(handle)
def snapshot():
 with db() as con:
  apps=[dict(r) for r in con.execute('SELECT * FROM apps ORDER BY name')]
  usage=[dict(r) for r in con.execute('SELECT * FROM usage ORDER BY seconds DESC LIMIT 20')]
  choices={r['missing']:r['replacement'] for r in con.execute('SELECT * FROM choices')}
 missing=[]
 for app in apps:
  if app['present'] or app['id'] in choices:continue
  candidates=[a for a in apps if a['present'] and a['category']==app['category'] and app['category']!='other'][:5]
  missing.append({'id':app['id'],'name':app['name'],'candidates':[{'id':a['id'],'name':a['name']} for a in candidates]})
 return {'ok':True,'apps':apps,'frequent':usage,'needs_input':missing,'notice':'Uso medido a partir da ativação, por aplicativo em primeiro plano; sem títulos, conteúdo ou teclas. Inventário do Windows atualizado a cada hora.'}
def choose(data):
 missing=data.get('missing');replacement=data.get('replacement')
 with LOCK,db() as con:
  old=con.execute('SELECT * FROM apps WHERE id=? AND present=0',(missing,)).fetchone()
  new=con.execute('SELECT * FROM apps WHERE id=? AND present=1',(replacement,)).fetchone()
  if not old or (replacement!='ignore' and not new):return {'ok':False,'error':'Atualize o inventário antes de escolher'}
  con.execute('INSERT OR REPLACE INTO choices VALUES(?,?,?)',(missing,replacement,time.time()))
 return {'ok':True,'notice':'Preferência registrada. Nenhum programa foi instalado ou desinstalado.'}
def worker():
 last_scan=0
 while True:
  try:
   if time.time()-last_scan>3600:scan();last_scan=time.time()
   name=foreground()
   if name:
    with db() as con:con.execute('INSERT INTO usage VALUES(?,15,?) ON CONFLICT(name) DO UPDATE SET seconds=seconds+15,last_seen=excluded.last_seen',(name,time.time()))
  except Exception:pass
  time.sleep(15)
def start():threading.Thread(target=worker,name='app-inventory',daemon=True).start()
