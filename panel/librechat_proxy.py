"""Same-origin LibreChat view; credentials and user sessions stay separate."""
import re
from urllib.parse import urlsplit
import requests
PREFIX='/librechat'
UPSTREAM='http://127.0.0.1:3080'
def serve(handler):
 parsed=urlsplit(handler.path);path=handler.path[len(PREFIX):] or '/'
 if not parsed.path.startswith(PREFIX+'/') or path.startswith('//'):
  handler._send(400,'{}');return
 origin=handler.headers.get('Origin')
 if handler.command not in ('GET','HEAD') and origin and urlsplit(origin).netloc!=handler.headers.get('Host'):
  handler._send(403,'{}');return
 try:length=int(handler.headers.get('Content-Length','0'))
 except ValueError:handler._send(400,'{}');return
 if not 0<=length<=32*1024*1024:handler._send(413,'{}');return
 headers={k:handler.headers[k] for k in ['Content-Type','Authorization','Cookie','Accept','Last-Event-ID','User-Agent','Accept-Language'] if handler.headers.get(k)}
 raw=handler.rfile.read(length) if length else None
 try:
  response=requests.request(handler.command,UPSTREAM+path,data=raw,headers=headers,timeout=(4,330),allow_redirects=False,stream=True)
 except requests.RequestException:
  handler._send(503,'LibreChat local indisponivel.','text/plain; charset=utf-8');return
 with response:
  content_type=response.headers.get('Content-Type','application/octet-stream')
  streamed='text/event-stream' in content_type
  body=None if streamed else response.content
  if body is not None and 'text/html' in content_type:
   text=body.decode('utf-8')
   text=text.replace('<base href="/">','<base href="/librechat/">')
   text=re.sub(r'(href|src)="(/(?!/|librechat/)[^"]*)"',lambda m:m[1]+'="'+PREFIX+m[2]+'"',text)
   body=text.encode()
  handler.send_response(response.status_code);handler.send_header('Content-Type',content_type)
  handler.send_header('Cache-Control','no-store' if streamed or '/api/' in path else 'private, max-age=60')
  handler.send_header('X-Frame-Options','SAMEORIGIN')
  if body is not None:handler.send_header('Content-Length',str(len(body)))
  else:handler.send_header('Connection','close');handler.close_connection=True
  for cookie in response.raw.headers.getlist('Set-Cookie'):
   handler.send_header('Set-Cookie',re.sub(r'Path=/(?:;|$)',lambda m:'Path=/librechat/'+(';' if m[0].endswith(';') else ''),cookie))
  location=response.headers.get('Location')
  if location:handler.send_header('Location',PREFIX+location if location.startswith('/') and not location.startswith(PREFIX+'/') else location)
  handler.end_headers()
  try:
   if streamed:
    # Initial job/session events can be much smaller than 1 KiB.
    # Deliver each SSE line immediately; blank lines terminate events.
    for line in response.iter_lines(chunk_size=1):
     handler.wfile.write(line+b'\n');handler.wfile.flush()
   elif handler.command!='HEAD':handler.wfile.write(body)
  except (OSError,requests.RequestException):pass
