"""Authenticated panel gateway to the Docker-only Flow display, fixed upstream."""
import http.client
import select
import socket
from urllib.parse import urlsplit

def serve(h):
    target=urlsplit(h.path)
    path=target.path.removeprefix('/flow/')
    if not path:path='vnc.html'
    if path.startswith('/') or '..' in path.split('/') or '\\' in path:
        h._send(400,'{}');return
    upstream='/'+path+('?' + target.query if target.query else '')
    if h.headers.get('Upgrade','').lower()=='websocket':
        remote=socket.create_connection(('127.0.0.1',6080),timeout=10)
        try:
            fields=['GET '+upstream+' HTTP/1.1','Host: 127.0.0.1:6080','Connection: Upgrade','Upgrade: websocket']
            for key in ('Sec-WebSocket-Key','Sec-WebSocket-Version','Sec-WebSocket-Protocol'):
                if h.headers.get(key):fields.append(key+': '+h.headers[key])
            remote.sendall(('\r\n'.join(fields)+'\r\n\r\n').encode())
            h.connection.settimeout(15);remote.settimeout(15)
            while True:
                ready,_,_=select.select([h.connection,remote],[],[],30)
                if not ready:continue
                for source in ready:
                    chunk=source.recv(65536)
                    if not chunk:return
                    (remote if source is h.connection else h.connection).sendall(chunk)
        finally:
            remote.close();h.close_connection=True
        return
    connection=http.client.HTTPConnection('127.0.0.1',6080,timeout=10)
    try:
        connection.request('GET',upstream,headers={'Host':'127.0.0.1:6080'})
        response=connection.getresponse();body=response.read(4*1024*1024)
        h._send(response.status,body,response.getheader('Content-Type','application/octet-stream'))
    except OSError:h._send(503,'{"ok":false,"error":"Sessao Docker indisponivel"}')
    finally:connection.close()
