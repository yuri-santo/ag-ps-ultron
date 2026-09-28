import threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
import requests,librechat_proxy

class StreamingTests(unittest.TestCase):
 def test_browser_user_agent_is_preserved_for_upstream_authentication(self):
  import io
  from types import SimpleNamespace
  from unittest.mock import MagicMock
  headers={'User-Agent':'Mozilla/5.0 test-browser','Accept-Language':'pt-BR','Cookie':'session=test'}
  handler=MagicMock();handler.path='/librechat/api/agents/chat';handler.command='GET';handler.headers=headers;handler.wfile=io.BytesIO()
  response=MagicMock();response.__enter__.return_value=response;response.headers={'Content-Type':'application/json'};response.content=b'{}';response.status_code=200;response.raw.headers.getlist.return_value=[]
  with patch('librechat_proxy.requests.request',return_value=response) as request:
   librechat_proxy.serve(handler)
  self.assertEqual(request.call_args.kwargs['headers']['User-Agent'],headers['User-Agent'])
  self.assertEqual(request.call_args.kwargs['headers']['Accept-Language'],'pt-BR')
 def test_small_initial_event_arrives_before_upstream_closes(self):
  release=threading.Event()
  class Upstream(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
    self.wfile.write(b'data: {"ready":true}\n\n');self.wfile.flush()
    release.wait(5)
  class Proxy(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):librechat_proxy.serve(self)
  upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
  proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
  for server in [upstream,proxy]:threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with patch.object(librechat_proxy,'UPSTREAM',f'http://127.0.0.1:{upstream.server_port}'):
    with requests.get(f'http://127.0.0.1:{proxy.server_port}/librechat/events',stream=True,timeout=(2,1)) as r:
     self.assertEqual(next(r.iter_lines(chunk_size=1)),b'data: {"ready":true}')
     self.assertFalse(release.is_set())
  finally:
   release.set()
   for server in [proxy,upstream]:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
