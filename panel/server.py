import ipaddress
import base64
import ctypes
import json
import os
import re
import subprocess
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import deck_runtime
import meeting_controls
import hub_api
import audio_controls
from deck_auth import AuthenticatedHandler, DeviceGuard

BASE_DIR = Path(__file__).resolve().parent
PORT = 8090

# ---------------------------------------------------------------------------
# Action catalog
# ---------------------------------------------------------------------------

def run(cmd, timeout=8, cwd=None):
    try:
        subprocess.Popen(cmd, shell=True, cwd=cwd,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return {"ok": True, "cmd": cmd}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def launch_store_app(package):
    return run(f"explorer.exe shell:AppsFolder\\{package}!App")


_NIRCMD_CACHE = None


def has_nircmd():
    global _NIRCMD_CACHE
    if _NIRCMD_CACHE is None:
        # fixed literal command, no user input involved - not an injection sink
        _NIRCMD_CACHE = os.system("where nircmd >nul 2>&1") == 0
    return _NIRCMD_CACHE


def set_volume(pct):
    pct = max(0, min(100, int(pct)))
    if has_nircmd():
        return run(f'nircmd setsysvolume {int(pct * 655.35)}')
    for _ in range(50):media_key(0xAE)
    for _ in range(round(pct/2)):media_key(0xAF)
    return {"ok":True,"volume":round(pct/2)*2}


def media_key(key):
    ctypes.windll.user32.keybd_event(key,0,0,0)
    ctypes.windll.user32.keybd_event(key,0,2,0)


def volume_step(direction):
    """direction: +1 sobe, -1 desce. nircmd funciona mesmo com a sessao travada; SendKeys nao."""
    if has_nircmd():
        return run(f'nircmd changesysvolume {6553 * direction}')
    for _ in range(5):media_key(0xAF if direction>0 else 0xAE)
    return {"ok":True}


def volume_mute():
    if has_nircmd():
        return run('nircmd mutesysvolume 2')
    media_key(0xAD)
    return {"ok":True}


ACTIONS = {
    "hermes_desktop": lambda: run('powershell -NoProfile -ExecutionPolicy Bypass -File "C:\\HermesDesktop\\scripts\\Abrir-Hermes.ps1"'),
    "agent_docs": lambda: run('explorer.exe "C:\\Users\\yurim\\super agentes"'),
    "video_tests": lambda: run('explorer.exe "C:\\Users\\yurim\\agent-tools\\video-use-tests-20260916"'),
    # Apps / ferramentas
    "vscode": lambda: run('start "" "C:\\Users\\yurim\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"'),
    "notepadpp": lambda: run('start "" "C:\\Program Files\\Notepad++\\notepad++.exe"'),
    "obsidian": lambda: run('start "" "C:\\Users\\yurim\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe"'),
    "outlook": lambda: run('start "" "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE" /select outlook:inbox'),
    "outlook_cal": lambda: run('start "" "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE" /select outlook:calendar'),
    "whatsapp": lambda: launch_store_app("5319275A.WhatsAppDesktop_cv1g1gvanyjgm"),
    "telegram": lambda: run('start "" "C:\\Users\\yurim\\AppData\\Local\\Microsoft\\WindowsApps\\Telegram.exe"'),
    "xbox": lambda: launch_store_app("Microsoft.XboxGamingOverlay_8wekyb3d8bbwe"),
    # RDP
    "rdp_trader": lambda: run(f'start "" mstsc /v:rdp-trader.example.com'),
    "rdp_honda": lambda: run(f'start "" mstsc /v:rdp-host.example.com'),
    "rdp_vps_rafael": lambda: run(f'start "" mstsc /v:rdp-host.example.com'),
    # OBS (abre com working dir correto para achar o locale)
    "obs": lambda: run('"C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"',
                       cwd="C:\\Program Files\\obs-studio\\bin\\64bit"),
    # Volume
    "vol_up": lambda: audio_controls.volume("up"),
    "vol_down": lambda: audio_controls.volume("down"),
    "vol_mute": lambda: audio_controls.volume("mute"),
    "vol_set": lambda v=None: audio_controls.volume("set",v if v is not None else 50),
    # Comandos rápidos
    "ping_vps": lambda: run('ping -n 1 203.0.113.10'),
    "cmd": lambda: run('start cmd'),
}


def send_to_ultron(text):
    """Envia texto ao Ultron (VPS) via hermes send no Telegram."""
    text = text.strip()
    if not text:
        return {"ok": False, "error": "vazio"}
    cmd=['wsl.exe','-d','Debian','-u','root','--exec','/root/.local/bin/hermes','send','--to','telegram',text]
    try:
        p = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=30,
                          creationflags=subprocess.CREATE_NO_WINDOW)
        return {"ok": p.returncode == 0, "output": (p.stdout + p.stderr).strip()[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def vps_status():
    return deck_runtime.status()

def get_calendar(day=None, window=7):
    """Busca compromissos do WorkMail (VPS) de Yuri e Rafael, expandindo recorrências."""
    import urllib.parse as _up
    cmd = "cd /root/tools && ./venv/bin/python cal_daily2.py"
    if day and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(day)):
        return {"ok":False,"error":"Data invalida"}
    if day:
        cmd += f" {day}"
    try:
        p = subprocess.run(
            ['wsl.exe','-d','Debian','-u','root','--exec','/root/tools/venv/bin/python','/root/tools/cal_daily2.py',*([day] if day else [])],
            capture_output=True, timeout=130, creationflags=subprocess.CREATE_NO_WINDOW)
        data = json.loads(p.stdout.decode("utf-8", errors="replace").strip() or "{}")
        return {"ok": True, **data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Network scanner (ARP + nmap + mDNS)
# ---------------------------------------------------------------------------

def get_lan_cidr():
    """Detecta o CIDR da rede local (primeiro adaptador com gateway)."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like '192.168.*'} | "
         "Select-Object -First 1 -ExpandProperty IPAddress"],
        capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    ip = out.stdout.strip()
    if not ip:
        return None
    if ip.startswith("192.168."):
        return "192.168.1.0/24"
    parts = ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"


_OUI_CACHE = None


def load_oui():
    """Carrega o banco de fabricantes do nmap (WSL Kali) uma única vez."""
    global _OUI_CACHE
    if _OUI_CACHE is not None:
        return _OUI_CACHE
    oui = {}
    try:
        r = subprocess.run(["wsl", "-d", "Debian", "--", "cat", "/usr/share/nmap/nmap-mac-prefixes"],
                           capture_output=True, text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and len(parts[0]) == 6 and parts[0].isdigit():
                oui[parts[0]] = parts[1].strip()
    except Exception:
        pass
    _OUI_CACHE = oui
    return oui


def mac_vendor(mac):
    """Retorna o fabricante a partir do MAC (via OUI)."""
    mac = mac.replace("-", "").replace(":", "").upper()
    if len(mac) < 6:
        return None
    oui = load_oui()
    return oui.get(mac[:6])


def resolve_mdns():
    """Resolve nomes mDNS (.local) da rede via Kali (avahi)."""
    try:
        r = subprocess.run(
            ["wsl", "-d", "Debian", "--", "bash", "-c",
             "timeout 8 avahi-browse -art 2>/dev/null | grep -iE '=.*IPv4' | grep -iE ':_(airplay|smb|http|https|web|ssh|googlecast|raop|companion-link|hap|_device-info)' | head -40"],
            capture_output=True, text=True, timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
        result = {}
        for line in r.stdout.splitlines():
            # formato: = wlan0 IPv4 Samsung_TV._airplay._tcp local
            parts = line.split()
            if len(parts) >= 5:
                name = parts[2].rstrip(".")
                host = parts[3].split("/")[-1]
                result.setdefault(host, set()).add(name)
        return {k: "; ".join(sorted(v)) for k, v in result.items()}
    except Exception:
        return {}


def scan_network():
    """Escaneia a rede via nmap (WSL Kali) + ARP do Windows e retorna lista de hosts."""
    cidr = get_lan_cidr()
    hosts = []
    alive = set()

    # 1) nmap do WSL Kali - detecção de hosts (muito melhor que arp)
    try:
        nmap_cmd = "wsl -d Debian -- nmap -sn --host-timeout 5s 192.168.1.0/24"
        nmap = subprocess.run(nmap_cmd, shell=True, capture_output=True, text=True, timeout=120,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        for line in nmap.stdout.splitlines():
            m = re.search(r"scan report for ([\d.]+)", line)
            if m:
                ip = m.group(1)
                if ip.startswith("192.168."):
                    alive.add(ip)
    except Exception:
        pass

    # 2) ARP do Windows - MACs + hosts
    try:
        arp = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW).stdout
        for line in arp.splitlines():
            m = re.match(r"\s*([\d.]+)\s+([0-9a-f-]{17})\s+(\S+)", line, re.IGNORECASE)
            if m:
                ip, mac, type_ = m.group(1), m.group(2).upper(), m.group(3).lower()
                if ip.startswith("192.168.") and not ip.endswith(".255"):
                    hosts.append({"ip": ip, "mac": mac, "type": type_})
                    alive.add(ip)
    except Exception:
        pass

    # 3) hosts do nmap sem MAC -> MAC vazio
    for ip in alive:
        if not any(h["ip"] == ip for h in hosts):
            hosts.append({"ip": ip, "mac": "", "type": "nmap"})

    # 4) mDNS names
    mdns = resolve_mdns()

    # dedupe + sort
    seen = set()
    uniq = []
    for h in hosts:
        if h["ip"] not in seen:
            seen.add(h["ip"])
            uniq.append(h)
    uniq.sort(key=lambda x: [int(p) for p in x["ip"].split(".")])

    # fabricante + nome mDNS + hostname
    def resolve(ip):
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"[System.Net.Dns]::GetHostEntry('{ip}').HostName"],
                               capture_output=True, text=True, timeout=4,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            name = r.stdout.strip()
            if name and name != ip and not name.startswith("Unhandled"):
                return name
        except Exception:
            pass
        return None

    threads = []
    for h in uniq:
        def work(host=h):
            host["vendor"] = mac_vendor(host["mac"]) if host.get("mac") else None
            host["mdns"] = mdns.get(host["ip"])
            host["name"] = resolve(host["ip"])
        t = threading.Thread(target=work)
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=8)

    return {"cidr": cidr, "hosts": uniq, "count": len(uniq)}


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class Handler(AuthenticatedHandler, BaseHTTPRequestHandler):
    guard = DeviceGuard()
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_DELETE(self):
        import librechat_proxy
        if self.path.startswith('/librechat/'):librechat_proxy.serve(self)
        else:self._send(404,'{}')

    do_PUT=do_DELETE
    do_PATCH=do_DELETE

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path.startswith('/flow/'):
            import flow_proxy
            flow_proxy.serve(self);return
        if urllib.parse.urlparse(self.path).path.startswith('/librechat/'):
            import librechat_proxy
            librechat_proxy.serve(self);return
        if urllib.parse.urlparse(self.path).path.startswith('/finance/'):
            import finance_proxy
            finance_proxy.serve(self);return
        if urllib.parse.urlparse(self.path).path.startswith('/media/'):
            import hub_media
            hub_media.serve(self,urllib.parse.urlparse(self.path).path.removeprefix('/media/'));return
        if urllib.parse.urlparse(self.path).path in ('/hub.js','/hub.css','/cockpit.js','/cockpit.css','/cockpit-immersion.js','/cockpit-immersion.css','/abrir-local.js'):
            name=urllib.parse.urlparse(self.path).path[1:]
            self._send(200,(BASE_DIR/name).read_bytes(),'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8');return
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html", "/panel"):
            html = (BASE_DIR / "deck.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")

        elif path == "/deck-status":
            self._send(200,json.dumps(deck_runtime.status()))
        elif path == "/meetings":
            self._send(200,json.dumps(meeting_controls.meetings()))
        elif path == "/inbox":
            self._send(200,json.dumps(meeting_controls.inbox()))
        elif path == "/meeting/status":
            self._send(200,json.dumps(meeting_controls.status()))
        elif path == "/meeting/records":
            self._send(200,json.dumps(meeting_controls.records(),ensure_ascii=False))
        elif path == "/volume":
            self._send(200,json.dumps(audio_controls.volume()))
        elif path == "/weather":
            query=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self._send(200,json.dumps(deck_runtime.weather(query.get('city',[''])[0])))
        elif path == "/manifest.json":
            manifest = (BASE_DIR / "manifest.json").read_bytes()
            self._send(200, manifest, "application/manifest+json")
        elif path == "/icon.png":
            self._send(404, "{}")
        elif path == "/health":
            self._send(200, json.dumps({"ok": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path.startswith('/librechat/'):
            import librechat_proxy
            librechat_proxy.serve(self);return
        if urllib.parse.urlparse(self.path).path.startswith('/finance/'):
            import finance_proxy
            finance_proxy.serve(self);return
        origin=self.headers.get('Origin')
        if origin and urllib.parse.urlparse(origin).netloc != self.headers.get('Host'):
            self._send(403,json.dumps({"ok":False,"error":"Origem nao autorizada"}));return
        path = urllib.parse.urlparse(self.path).path
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) > 1:
            self._send(400, '{"ok":false,"error":"Invalid request framing"}');return
        try:length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send(400, '{"ok":false,"error":"Invalid length"}');return
        if length<0 or length>65536:
            self._send(413,json.dumps({"ok":False,"error":"Conteudo excede limite"}));return
        raw = self.rfile.read(length) if length else b""
        data = {}
        if raw:
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeError):
                self._send(400, '{"ok":false,"error":"Invalid JSON"}');return
            if not isinstance(data, dict):
                self._send(400, '{"ok":false,"error":"JSON object required"}');return

        if path == "/hub":
            self._send(200,json.dumps(hub_api.dispatch(data),ensure_ascii=False))
        elif path == "/meeting/join":
            self._send(200,json.dumps(meeting_controls.join(data.get('key'))))
        elif path == "/open":
            # Links tocados no celular abrem no Saitama; o celular não navega.
            import desktop_open
            self._send(200,json.dumps(desktop_open.open_url(data.get('url')),ensure_ascii=False))
        elif path == "/meeting/start":
            self._send(200,json.dumps(meeting_controls.start(data.get('key'),data.get('request_id'))))
        elif path in ("/meeting/stop","/meeting/pause","/meeting/resume"):
            method=getattr(meeting_controls,path.rsplit("/",1)[1])
            self._send(200,json.dumps(method(data.get("session_id"),data.get("request_id"))))
        elif path in ('/meeting/project','/meeting/client','/meeting/mute','/meeting/unmute',
                      '/meeting/tickets','/meeting/feedback','/meeting/select_event','/meeting/prepare'):
            self._send(200,json.dumps(meeting_controls.unified(path.rsplit('/',1)[1],
                session_id=data.get('session_id'),request_id=data.get('request_id'),value=data.get('value','')),ensure_ascii=False))
        elif path == "/meeting/leave":
            self._send(200,json.dumps(meeting_controls.end_meeting()))
        elif path == "/meeting/decline":
            self._send(200,json.dumps(meeting_controls.decline(data.get('key'),data.get('confirmed'))))
        elif path == "/power":
            self._send(200,json.dumps(meeting_controls.power(data.get('action'),data.get('confirmed'))))
        elif path == "/action":
            action = data.get("action", "")
            payload = data.get("payload")
            if action not in ACTIONS:
                self._send(404, json.dumps({"ok": False, "error": f"unknown action: {action}"}))
                return
            fn = ACTIONS[action]
            result = fn(payload) if payload is not None and action == "vol_set" else fn()
            self._send(200, json.dumps(result))
        elif path == "/ultron":
            text = data.get("text", "")
            result = send_to_ultron(text)
            self._send(200, json.dumps(result))
        elif path == "/network":
            result = scan_network()
            self._send(200, json.dumps(result))
        elif path == "/vps-status":
            result = vps_status()
            self._send(200, json.dumps(result))
        elif path == "/calendar":
            result = get_calendar(data.get("day"), data.get("window", 7))
            self._send(200, json.dumps(result))
        elif path == "/health":
            self._send(200, json.dumps({"ok": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


def main():
    import app_inventory
    app_inventory.start()
    import threading
    # SSH/VPN forwarding enters a distinct loopback listener with no admin bypass.
    class RelayHandler(Handler):
        guard = DeviceGuard(store=Handler.guard.store, allow_loopback_bootstrap=False, external_port=PORT)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    relay = ThreadingHTTPServer(("127.0.0.1", 18090), RelayHandler)
    threading.Thread(target=relay.serve_forever, daemon=True, name="deck-vpn-relay").start()
    print(f"Stream Deck server on http://0.0.0.0:{PORT}; paired relay on loopback:18090")
    try:
        server.serve_forever()
    finally:
        relay.shutdown()
        relay.server_close()
        server.server_close()


if __name__ == "__main__":
    main()
