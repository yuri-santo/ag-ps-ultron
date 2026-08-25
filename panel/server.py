import ipaddress
import json
import os
import re
import subprocess
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PORT = 8090

# Evita que cada ação (RDP, volume, ping, ssh...) abra uma janela de console
# visível no Windows quando o servidor roda "headless" via pythonw.exe.
NOWIN = subprocess.CREATE_NO_WINDOW

# ---------------------------------------------------------------------------
# Action catalog
# ---------------------------------------------------------------------------

def run(cmd, timeout=8, cwd=None):
    try:
        subprocess.Popen(cmd, shell=True, cwd=cwd,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=NOWIN)
        return {"ok": True, "cmd": cmd}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def launch_store_app(package):
    return run(f"explorer.exe shell:AppsFolder\\{package}!App")


_NIRCMD_CACHE = None


def has_nircmd():
    # fixed literal command, no user input involved - not an injection sink
    global _NIRCMD_CACHE
    if _NIRCMD_CACHE is None:
        _NIRCMD_CACHE = os.system("where nircmd >nul 2>&1") == 0
    return _NIRCMD_CACHE


def set_volume(pct):
    pct = max(0, min(100, int(pct)))
    if has_nircmd():
        return run(f'nircmd setsysvolume {int(pct * 655.35)}')
    return run(
        f'powershell -NoProfile -Command '
        f'$w=New-Object -ComObject WScript.Shell; '
        f'$w.SendKeys([string][char]0); '
        f'for($i=0;$i -lt {pct};$i++){{$w.SendKeys([string][char]175)}}'
    )


def volume_step(direction):
    """direction: +1 sobe, -1 desce. nircmd funciona com a sessão travada; SendKeys não."""
    if has_nircmd():
        return run(f'nircmd changesysvolume {6553 * direction}')
    key = 175 if direction > 0 else 174
    return run(
        f'powershell -NoProfile -Command '
        f'$w=New-Object -ComObject WScript.Shell; '
        f'for($i=0;$i -lt 10;$i++){{$w.SendKeys([string][char]{key})}}'
    )


def volume_mute():
    if has_nircmd():
        return run('nircmd mutesysvolume 2')
    return run(
        'powershell -NoProfile -Command '
        '"$w=New-Object -ComObject WScript.Shell; $w.SendKeys([string][char]173)"'
    )


# NOTE: personalize este dicionário com seus próprios atalhos.
# Cada chave é o "action" que o botão do painel envia via POST /action.
ACTIONS = {
    # Apps / ferramentas
    "vscode": lambda: run('start "" "C:\\Users\\SEU_USUARIO\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"'),
    "notepadpp": lambda: run('start "" "C:\\Program Files\\Notepad++\\notepad++.exe"'),
    "notion": lambda: run('start "" "C:\\Users\\SEU_USUARIO\\AppData\\Local\\Programs\\Notion\\Notion.exe"'),
    "outlook": lambda: run('start "" "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE" /select outlook:calendar'),
    "outlook_cal": lambda: run('start "" "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE" /select outlook:calendar'),
    "whatsapp": lambda: launch_store_app("5319275A.WhatsAppDesktop_cv1g1gvanyjgm"),
    "telegram": lambda: run('start "" "C:\\Users\\SEU_USUARIO\\AppData\\Local\\Microsoft\\WindowsApps\\Telegram.exe"'),
    "xbox": lambda: launch_store_app("Microsoft.XboxGamingOverlay_8wekyb3d8bbwe"),
    # RDP (substitua pelos seus próprios hosts/IPs)
    "rdp_host1": lambda: run(f'start "" mstsc /v:10.0.0.10'),
    "rdp_host2": lambda: run(f'start "" mstsc /v:seu-servidor-1.exemplo.com'),
    "rdp_host3": lambda: run(f'start "" mstsc /v:seu-servidor-2.exemplo.com'),
    "rdp_arquivo_rdp": lambda: run(f'start "" "C:\\Users\\SEU_USUARIO\\Downloads\\conexao.rdp"'),
    # OBS (abre com working dir correto para achar o locale)
    "obs": lambda: run('"C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"',
                       cwd="C:\\Program Files\\obs-studio\\bin\\64bit"),
    # Volume
    "vol_up": lambda: volume_step(1),
    "vol_down": lambda: volume_step(-1),
    "vol_mute": lambda: volume_mute(),
    "vol_set": lambda v=None: set_volume(v if v is not None else 50),
    # Comandos rápidos
    "ping_vps": lambda: run('ping -n 1 SEU.IP.PUBLICO.AQUI'),
    "cmd": lambda: run('start cmd'),
}


def send_to_agent(text):
    """Envia texto ao agente remoto (VPS) via um CLI próprio exposto por SSH.

    Requer um alias SSH configurado em ~/.ssh/config (ex: 'minha-vps') e,
    do lado da VPS, um binário/CLI que receba texto e faça algo com ele
    (ex: encaminhar para um bot de Telegram, um LLM, etc).
    """
    text = text.strip()
    if not text:
        return {"ok": False, "error": "vazio"}
    encoded = text.replace('"', '\\"').replace("`", "\\`")
    cmd = f'ssh -o BatchMode=yes -o ConnectTimeout=8 minha-vps "/root/.local/bin/meu-agente-cli send --to telegram \\"{encoded}\\""'
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30,
                          creationflags=NOWIN)
        return {"ok": p.returncode == 0, "output": (p.stdout + p.stderr).strip()[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def agent_status():
    """Consulta o estado real da VPS: o agente remoto, o gateway de IA e os containers docker."""
    out = {"agent": None, "ai_gateway": None, "dockers": [], "error": None}
    try:
        p = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "minha-vps",
             "/root/.local/bin/meu-agente-cli status 2>&1"],
            capture_output=True, timeout=40, creationflags=NOWIN)
        txt = p.stdout.decode("utf-8", errors="replace")
        gw = "running" if "Gateway Service" in txt and re.search(r"Status:\s+✓\s*running", txt) else "unknown"
        out["agent"] = {
            "gateway": gw,
            "model": re.search(r"Model:\s+(\S+)", txt).group(1) if re.search(r"Model:\s+(\S+)", txt) else None,
            "telegram": "ok" if "Telegram" in txt and "configured" in txt else "check",
            "sessions": re.search(r"Active:\s+(\d+)", txt).group(1) if re.search(r"Active:\s+(\d+)", txt) else "?",
            "last_activity": re.search(r"Last activity:\s+([\w ]+)", txt).group(1).strip() if re.search(r"Last activity:\s+([\w ]+)", txt) else "?",
            "cron_jobs": re.search(r"Jobs:\s+(\d+)", txt).group(1) if re.search(r"Jobs:\s+(\d+)", txt) else "?",
        }
    except Exception as e:
        out["error"] = f"agente: {e}"

    try:
        p = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "minha-vps",
             "curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:20128/v1/models 2>&1"],
            capture_output=True, text=True, timeout=20, creationflags=NOWIN)
        code = p.stdout.strip()
        out["ai_gateway"] = "ok" if code in ("401", "200") else f"check ({code})"
    except Exception as e:
        out["ai_gateway"] = f"erro: {e}"

    try:
        p = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "minha-vps",
             "docker ps --format '{{.Names}}|{{.Status}}' 2>/dev/null | sort"],
            capture_output=True, text=True, timeout=30, creationflags=NOWIN)
        for line in p.stdout.splitlines():
            parts = line.split("|")
            if len(parts) == 2:
                name, status = parts[0].strip(), parts[1].strip()
                ok = "Up" in status and "unhealthy" not in status and "restarting" not in status
                out["dockers"].append({"name": name, "status": status, "ok": ok})
    except Exception as e:
        out["error"] = (out.get("error") or "") + f" | docker: {e}"

    return out


def get_calendar(day=None, window=7):
    """Busca compromissos de um ou mais calendários (WorkMail/Exchange) via um script
    remoto na VPS que já sabe expandir recorrências e devolve JSON pronto."""
    cmd = "cd /root/tools && ./venv/bin/python cal_daily2.py"
    if day:
        cmd += f" {day}"
    try:
        p = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "minha-vps", cmd],
            capture_output=True, timeout=130, creationflags=NOWIN)
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
        capture_output=True, text=True, timeout=15, creationflags=NOWIN)
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
        r = subprocess.run(["wsl", "-d", "kali-linux", "--", "cat", "/usr/share/nmap/nmap-mac-prefixes"],
                           capture_output=True, text=True, timeout=20, creationflags=NOWIN)
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
            ["wsl", "-d", "kali-linux", "--", "bash", "-c",
             "timeout 8 avahi-browse -art 2>/dev/null | grep -iE '=.*IPv4' | grep -iE ':_(airplay|smb|http|https|web|ssh|googlecast|raop|companion-link|hap|_device-info)' | head -40"],
            capture_output=True, text=True, timeout=25, creationflags=NOWIN)
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
        nmap_cmd = "wsl -d kali-linux -- nmap -sn --host-timeout 5s 192.168.1.0/24"
        nmap = subprocess.run(nmap_cmd, shell=True, capture_output=True, text=True, timeout=120,
                             creationflags=NOWIN)
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
                            creationflags=NOWIN).stdout
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
                               capture_output=True, text=True, timeout=4, creationflags=NOWIN)
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

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html", "/panel"):
            html = (BASE_DIR / "panel.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
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
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        data = {}
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                data = {}

        if path == "/action":
            action = data.get("action", "")
            payload = data.get("payload")
            if action not in ACTIONS:
                self._send(404, json.dumps({"ok": False, "error": f"unknown action: {action}"}))
                return
            fn = ACTIONS[action]
            result = fn(payload) if payload is not None and action == "vol_set" else fn()
            self._send(200, json.dumps(result))
        elif path == "/agent":
            text = data.get("text", "")
            result = send_to_agent(text)
            self._send(200, json.dumps(result))
        elif path == "/network":
            result = scan_network()
            self._send(200, json.dumps(result))
        elif path == "/agent-status":
            result = agent_status()
            self._send(200, json.dumps(result))
        elif path == "/calendar":
            result = get_calendar(data.get("day"), data.get("window", 7))
            self._send(200, json.dumps(result))
        elif path == "/health":
            self._send(200, json.dumps({"ok": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Stream Deck server on http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
