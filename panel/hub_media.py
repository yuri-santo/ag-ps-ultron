"""Read-only video library with bounded byte ranges; never exposes arbitrary files."""
import pathlib,hashlib,re
ROOT=pathlib.Path(r'C:\Users\yurim\agent-tools\video-use-tests-20260916')
EXTRA_ROOTS=(ROOT.parent/'video-use-tests-20260923', pathlib.Path(r'C:\Users\yurim\super agentes\Flow-20260925'))

def files():
    result={}
    for root in (ROOT,*EXTRA_ROOTS):
        for p in root.rglob('*.mp4'):
            if not p.resolve().is_relative_to(root.resolve()):continue
            identity=str(p.relative_to(root)) if root==ROOT else root.name+'/'+str(p.relative_to(root))
            result[hashlib.sha256(identity.encode()).hexdigest()[:24]]=p
    return result
def catalog():
    entries=[]
    for key,p in files().items():
        root=next(r for r in (ROOT,*EXTRA_ROOTS) if p.is_relative_to(r))
        entries.append({'id':key,'name':p.name,'folder':root.name+'/'+str(p.parent.relative_to(root)),'bytes':p.stat().st_size})
    return {'ok':True,'videos':entries}
def resolve(key):
    if not re.fullmatch('[a-f0-9]{24}',key):raise ValueError('Video invalido')
    path=files().get(key)
    if path is None:raise ValueError('Video inexistente')
    return path
def bounds(header,size):
    if not header:return 0,size-1,False
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
    if not match or not any(match.groups()):raise ValueError('Range invalido')
    left,right=match.groups()
    if not left:start=max(0,size-int(right));end=size-1
    else:start=int(left);end=min(size-1,int(right)) if right else size-1
    if start<0 or start>end or start>=size:raise ValueError('Range fora do arquivo')
    return start,end,True
def serve(handler,key):
    try:
        path=resolve(key);size=path.stat().st_size;start,end,partial=bounds(handler.headers.get('Range'),size)
    except ValueError:
        handler._send(416,'{}');return
    handler.send_response(206 if partial else 200)
    handler.send_header('Content-Type','video/mp4');handler.send_header('Accept-Ranges','bytes');handler.send_header('Content-Length',str(end-start+1));handler.send_header('Cache-Control','private, max-age=60')
    if partial:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
    handler.end_headers()
    try:
        with path.open('rb') as source:
            source.seek(start);remaining=end-start+1
            while remaining:
                block=source.read(min(65536,remaining))
                if not block:break
                handler.wfile.write(block);remaining-=len(block)
    except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
