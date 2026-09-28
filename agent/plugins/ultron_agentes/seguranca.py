"""Leitura dos relatórios gerados pelos timers de segurança e backup (sem executar nada)."""
import json
from pathlib import Path

DIR = Path('/root/ultron-local/seguranca')


def _ler(nome):
    path = DIR / nome
    if not path.is_file():
        raise FileNotFoundError(f'{nome}_ainda_nao_gerado')
    return json.loads(path.read_text(encoding='utf-8'))


def relatorio():
    data = _ler('auditoria.json')
    data['status'] = 'ok'
    return data


def backup_status():
    data = _ler('backup.json')
    data['status'] = 'ok'
    return data
