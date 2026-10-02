"""Checksum-guarded local profile upgrade; backs up every modified private file."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import yaml

from install_gateway import atomic
from native_patch import SOURCE_SHA256, patch_sources

RUNTIME = Path('/opt/hermes-agent-20260924')
HOME = Path('/root/.hermes')
PRIOR = Path('/root/ultron-local/maintenance/topic-gateway-20261001')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def changes():
    manifest = json.loads((PRIOR / 'refresh-manifest.json').read_text())
    for name, expected in manifest['installed'].items():
        if digest((RUNTIME / name).read_bytes()) != expected:
            raise ValueError('Concurrent runtime change: ' + name)
    originals = {p: (PRIOR / 'backup/native' / p).read_text() for p in SOURCE_SHA256}
    updates = {RUNTIME / p: text.encode() for p, text in patch_sources(originals).items()}
    for source in Path(__file__).parent.glob('*.py'):
        if not source.name.startswith(('test_', 'probe_', 'install_', 'manage_')):
            compile(source.read_bytes(), str(source), 'exec')
            updates[RUNTIME / 'ultron_topic_queue' / source.name] = source.read_bytes()
    config_path = HOME / 'topic-queue/config.json'
    config = json.loads(config_path.read_text())
    config['persistent_profiles'] = True
    config['roster'] = dict(ultron='Perfil principal, conversa, ferramentas e orquestracao. Consulta especialistas quando necessario.',
                             **{k:v for k,v in config['roster'].items() if k != 'ultron'})
    config['roster']['cerebro'] = 'Estrategia, decomposicao e causa raiz quando escolhido pelo titular.'
    config['authors']['ultron'] = 'Ultron'
    updates[config_path] = json.dumps(config, ensure_ascii=False, indent=2).encode()
    root_config = yaml.safe_load((HOME / 'config.yaml').read_text())
    dispatch = root_config.setdefault('kanban', {}).setdefault('dispatch_profiles', [])
    if 'default' not in dispatch:
        dispatch.append('default')
    updates[HOME / 'config.yaml'] = yaml.safe_dump(root_config, allow_unicode=True, sort_keys=False).encode()
    updates[HOME / 'active_profile'] = b'default\n'
    personas = json.loads(Path(__file__).with_name('personas.json').read_text())
    general = ('\n\nEstas diretrizes atualizam o estilo de conversa com Yuri, preservando '
        'as demais regras da alma e o tom profissional dos documentos para terceiros. '
        'Conversa direta: responda naturalmente ao pedido, com seu nome real. '
        'Campos veredicto/evidencia/premissas/riscos/confianca/proxima_acao sao para pareceres '
        'formais de conselho, nao para saudacoes ou conversas comuns. '
        'Se Yuri perguntar qual perfil esta ativo, diga seu nome; nao confunda autor com revisor. '
        'Bordoes sao ocasionais, curtos e opcionais: nunca em toda resposta, erros serios, '
        'saude, sofrimento, risco juridico ou financeiro, nem dentro de documentos para terceiros. '
        'Frases autorais nao devem ser atribuidas como citacoes famosas. Sem emojis. '
        'A personalidade nao altera permissoes, ferramentas, evidencias ou autorizacoes.\n')
    for profile, text in personas.items():
        directory = HOME if profile == 'ultron' else HOME / 'profiles' / profile
        if not (directory / 'SOUL.md').is_file():
            raise ValueError('Missing profile SOUL: ' + profile)
        soul = (directory / 'SOUL.md').read_text()
        soul = re.sub(r'\n<!-- PROFILE-VOICE v1 -->[\s\S]*?<!-- /PROFILE-VOICE -->\n?', '', soul)
        # Retain all existing private content; only clarify the scope of the old
        # unconditional council formatting instruction.
        soul = soul.replace('Retorne sempre:', 'Em parecer formal de conselho, retorne:')
        soul += '\n<!-- PROFILE-VOICE v1 -->\n## Voz e conversa com Yuri\n\n' + text + general + '<!-- /PROFILE-VOICE -->\n'
        updates[directory / 'SOUL.md'] = soul.encode()
        metadata_path = directory / 'profile.yaml'
        metadata = yaml.safe_load(metadata_path.read_text()) if metadata_path.is_file() else {}
        metadata = metadata or {}
        metadata['display_name'] = config['authors'].get(profile, profile.capitalize())
        updates[metadata_path] = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).encode()
    return updates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    updates = changes()
    if not args.apply:
        print(json.dumps({'checked_files': len(updates), 'writes': False}))
        return
    state = subprocess.run(['systemctl', 'is-active', 'hermes-gateway.service'], capture_output=True, text=True).stdout.strip()
    if state != 'inactive':
        raise RuntimeError('Gateway must be stopped')
    backup = Path('/root/ultron-local/maintenance') / ('profile-commands-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    previous = {str(p): p.read_bytes() if p.exists() else None for p in updates}
    for path, content in previous.items():
        if content is not None:
            atomic(backup / 'before' / path.lstrip('/'), content)
    records = {str(p): dict(before=digest(previous[str(p)]) if previous[str(p)] is not None else None,
                           after=digest(content)) for p, content in updates.items()}
    atomic(backup / 'manifest.json', json.dumps(records, indent=2).encode())
    try:
        for path, content in updates.items():
            atomic(path, content)
    except Exception:
        for path, content in previous.items():
            if content is not None:
                atomic(Path(path), content)
        raise
    installed = {str(p.relative_to(RUNTIME)): digest(v) for p, v in updates.items() if p.is_relative_to(RUNTIME)}
    old = json.loads((PRIOR / 'refresh-manifest.json').read_text())
    atomic(backup / 'previous-refresh-manifest.json', json.dumps(old, indent=2).encode())
    old['installed'].update(installed)
    atomic(PRIOR / 'refresh-manifest.json', json.dumps(old, indent=2).encode())
    print(json.dumps({'installed_files': len(updates), 'backup': str(backup), 'restart_required': True}))


if __name__ == '__main__':
    main()
