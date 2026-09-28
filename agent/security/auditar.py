"""Auditoria semanal de segurança do WSL/homelab: Lynis (hardening), Trivy (vulnerabilidades) e Gitleaks (segredos).

Grava /root/ultron-local/seguranca/auditoria.json (lido pela ferramenta seguranca_relatorio do Mr Robot)
e avisa no Telegram quando há achado crítico ou alto novo. Não corrige nada sozinho.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

OUT = Path('/root/ultron-local/seguranca')
TRIVY_ALVOS = ['/opt/agent-stacks', '/root/ultron-local', '/root/.hermes/plugins']
GITLEAKS_ALVOS = ['/root/ultron-local', '/mnt/c/Users/yurim/ultron-team-20260913']


def run(cmd, timeout):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return subprocess.CompletedProcess(cmd, 127, '', type(exc).__name__)


def lynis():
    report = OUT / 'lynis-report.dat'
    proc = run(['lynis', 'audit', 'system', '--quiet', '--no-colors', '--report-file', str(report), '--logfile', str(OUT / 'lynis.log')], 900)
    if not report.is_file():
        return {'erro': (proc.stderr or 'lynis_falhou')[-200:]}
    dados = report.read_text(errors='replace').splitlines()
    val = lambda k: next((l.split('=', 1)[1] for l in dados if l.startswith(k + '=')), None)
    avisos = [l.split('=', 1)[1].split('|')[:2] for l in dados if l.startswith('warning[]=')]
    sugestoes = [l.split('=', 1)[1].split('|')[:2] for l in dados if l.startswith('suggestion[]=')]
    return {'indice_hardening': int(val('hardening_index') or 0), 'avisos': [' — '.join(a) for a in avisos][:20],
            'sugestoes_total': len(sugestoes), 'sugestoes_principais': [' — '.join(s) for s in sugestoes][:10]}


def trivy():
    resultado = {}
    for alvo in TRIVY_ALVOS:
        if not Path(alvo).exists():
            continue
        proc = run(['trivy', 'fs', '--quiet', '--scanners', 'vuln,misconfig', '--severity', 'HIGH,CRITICAL',
                    '--format', 'json', '--skip-dirs', '**/node_modules', alvo], 1200)
        try:
            data = json.loads(proc.stdout or '{}')
        except ValueError:
            resultado[alvo] = {'erro': (proc.stderr or 'trivy_falhou')[-200:]}
            continue
        crit, high, itens = 0, 0, []
        for res in data.get('Results') or []:
            for v in res.get('Vulnerabilities') or []:
                sev = v.get('Severity')
                crit += sev == 'CRITICAL'
                high += sev == 'HIGH'
                itens.append({'alvo': res.get('Target'), 'pacote': v.get('PkgName'), 'versao': v.get('InstalledVersion'),
                              'id': v.get('VulnerabilityID'), 'severidade': sev, 'corrigido_em': v.get('FixedVersion') or ''})
            for m in res.get('Misconfigurations') or []:
                sev = m.get('Severity')
                crit += sev == 'CRITICAL'
                high += sev == 'HIGH'
                itens.append({'alvo': res.get('Target'), 'id': m.get('ID'), 'severidade': sev, 'titulo': (m.get('Title') or '')[:120]})
        itens.sort(key=lambda i: i['severidade'] != 'CRITICAL')
        resultado[alvo] = {'critical': crit, 'high': high, 'principais': itens[:15]}
    return resultado


def gitleaks():
    resultado = {}
    for alvo in GITLEAKS_ALVOS:
        if not Path(alvo).exists():
            continue
        rep = OUT / ('gitleaks-' + re.sub(r'\W+', '_', alvo) + '.json')
        run(['gitleaks', 'detect', '--no-git', '--redact', '--no-banner', '--source', alvo,
             '--report-format', 'json', '--report-path', str(rep)], 900)
        try:
            achados = json.loads(rep.read_text() or '[]')
        except (OSError, ValueError):
            resultado[alvo] = {'erro': 'gitleaks_falhou'}
            continue
        por = {}
        for a in achados:
            chave = (a.get('File', '').replace(alvo, '').lstrip('/'), a.get('RuleID'))
            por[chave] = por.get(chave, 0) + 1
        resultado[alvo] = {'total': len(achados), 'arquivos': [{'arquivo': f, 'regra': r, 'ocorrencias': n}
                                                               for (f, r), n in sorted(por.items(), key=lambda x: -x[1])][:25]}
        rep.unlink(missing_ok=True)  # não guardar nem o relatório redigido
    return resultado


def resumo(data):
    crit = sum(v.get('critical', 0) for v in data['trivy'].values())
    high = sum(v.get('high', 0) for v in data['trivy'].values())
    segredos = sum(v.get('total', 0) for v in data['gitleaks'].values())
    return crit, high, segredos


def main():
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    inicio = time.time()
    anterior = {}
    if (OUT / 'auditoria.json').is_file():
        anterior = json.loads((OUT / 'auditoria.json').read_text())
    data = {'data': time.strftime('%Y-%m-%dT%H:%M:%S'), 'lynis': lynis(), 'trivy': trivy(), 'gitleaks': gitleaks()}
    data['duracao_s'] = int(time.time() - inicio)
    crit, high, segredos = resumo(data)
    data['resumo'] = {'vulnerabilidades_criticas': crit, 'vulnerabilidades_altas': high, 'possiveis_segredos': segredos,
                      'indice_hardening_lynis': data['lynis'].get('indice_hardening')}
    tmp = OUT / '.auditoria.tmp'
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    os.chmod(tmp, 0o600)
    os.replace(tmp, OUT / 'auditoria.json')
    antes = (anterior.get('resumo') or {})
    novidade = (crit > antes.get('vulnerabilidades_criticas', 0) or segredos > antes.get('possiveis_segredos', 0)
                or high > antes.get('vulnerabilidades_altas', 0) + 5)
    print(json.dumps(data['resumo'], ensure_ascii=False))
    if novidade and '--sem-telegram' not in sys.argv:
        sys.path.insert(0, '/root/.hermes/plugins')
        try:
            from ultron_lab.monitor import telegram_from_env
            tg = telegram_from_env('/root/.hermes')
            if tg:
                tg.send(f"Auditoria de segurança (Mr Robot): {crit} crítica(s), {high} alta(s), {segredos} possível(is) segredo(s) "
                        f"em arquivo; hardening Lynis {data['lynis'].get('indice_hardening')}. Peça ao Mr Robot o detalhe.")
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
