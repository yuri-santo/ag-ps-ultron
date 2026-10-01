"""Local staged installation. No network, credential output, service control or posts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import site

from native_patch import patch_sources, SOURCE_SHA256


ROSTER = {
    'cerebro': 'Conversa casual, raciocinio, decomposicao e estrategia; sem operar sistemas.',
    'cris': 'Email profissional, localizacao de mensagens corporativas e rascunhos locais.',
    'greg': 'Email pessoal, compras e entregas; consulta de mensagens e rascunhos locais.',
    'dona': 'Agenda, compromissos e organizacao pessoal.',
    'maquiavel': 'Reunioes, atas, decisoes e transcricoes.',
    'bigode': 'Financas, orcamento, custos e negocios.',
    'buffett': 'Investimentos de longo prazo e fundamentos.',
    'tron': 'Analise de mercado, nunca executar ordens.',
    'harvey': 'Direito brasileiro, fontes juridicas e riscos legais.',
    'jesus': 'Saude e bem-estar; reconhecer rotina sem alterar medicamentos.',
    'botura': 'Nutricao e alimentacao.', 'arnold': 'Treino e atividade fisica.',
    'thor': 'Consultoria SAP, somente com intencao SAP explicita, nunca por UID ou datas.',
    'hercules': 'Engenharia de backend e integracoes.', 'perseu': 'Frontend e interfaces.',
    'ironman': 'Arquitetura e validacao sistemica.', 'mrrobot': 'Infraestrutura, rede e seguranca.',
    'tanos': 'Auditoria de evidencias e completude; nao executar mudancas.',
    'money': 'Conteudo, marketing e roteiros; sem publicar autonomamente por esta fila.',
    'pink': 'Memoria e organizacao do conhecimento.', 'napoleon': 'Cultura, filosofia e objetivos pessoais.',
}
AUTHORS = {key: key.capitalize() for key in ROSTER}
AUTHORS.update(cerebro='Cerebro', mrrobot='Mr. Robot', ironman='Iron Man')
REVIEW_ROUTE = {'model': 'nvidia/nvidia/nemotron-3-ultra-550b-a55b', 'tier': 2}


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.topic-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def stage(runtime, home, destination):
    """Copy executable package and back up originals, leaving all live hooks unchanged."""
    import yaml
    from dotenv import dotenv_values
    runtime, home, destination = map(lambda p: Path(p).resolve(), (runtime, home, destination))
    assert runtime == Path('/opt/hermes-agent-20260924') and home == Path('/root/.hermes')
    assert destination.is_relative_to(Path('/root/ultron-local/maintenance'))
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    original = {name: (runtime / name).read_text() for name in SOURCE_SHA256}
    patched = patch_sources(original)
    for name, content in original.items():
        atomic(destination / 'backup' / 'native' / name, content.encode())
    for name, content in patched.items():
        atomic(destination / 'patched' / name, content.encode())
    for path in (home / 'config.yaml', home.parent / 'ultron-local/review-policy.json'):
        atomic(destination / 'backup' / path.name, path.read_bytes())
    package = destination / 'package' / 'ultron_topic_queue'
    package.mkdir(parents=True, mode=0o700)
    for path in Path(__file__).parent.glob('*.py'):
        if not path.name.startswith(('test_', 'install_', 'probe_')):
            atomic(package / path.name, path.read_bytes())
    atomic(package / '__init__.py', b'"""Private local Hermes gateway integration."""\n')
    env = dotenv_values(home / '.env')
    token = env.get('TELEGRAM_BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN', '')
    allowed = env.get('TELEGRAM_ALLOWED_USERS') or os.environ.get('TELEGRAM_ALLOWED_USERS', '')
    users = [x.strip() for x in allowed.split(',') if x.strip()]
    assert ':' in token and token.split(':')[0].isdigit() and len(users) == 1 and users[0].isdigit(), 'Cannot infer unique owner scope'
    config = dict(enabled=False, scopes=[dict(platform='telegram', account_id=token.split(':')[0],
        owner_id=users[0], chat_id=users[0], thread_id='')], roster=ROSTER, authors=AUTHORS,
        reviewer_routes=[REVIEW_ROUTE], max_stage_attempts=4)
    atomic(destination / 'queue-config.json', json.dumps(config, ensure_ascii=False, indent=2).encode())
    report = dict(status='staged_not_activated', backup=str(destination / 'backup'),
                  files={name: hashlib.sha256(text.encode()).hexdigest() for name, text in original.items()})
    atomic(destination / 'manifest.json', json.dumps(report, indent=2).encode())
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage')
    parser.add_argument('--install')
    parser.add_argument('--enable', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if args.stage:
        print(json.dumps(stage('/opt/hermes-agent-20260924', '/root/.hermes', args.stage)))
    elif args.install:
        print(json.dumps(install(args.install, enable=args.enable)))
    else:
        parser.error('--stage or --install is required')


def install(staged, *, enable=False):
    import yaml
    runtime, home = Path('/opt/hermes-agent-20260924'), Path('/root/.hermes')
    staged = Path(staged).resolve()
    assert staged.is_relative_to(Path('/root/ultron-local/maintenance'))
    status = subprocess.run(['systemctl', 'is-active', 'hermes-gateway.service'], capture_output=True, text=True)
    assert status.stdout.strip() == 'inactive', 'Gateway must be stopped before installation'
    original = {name: (runtime / name).read_text() for name in SOURCE_SHA256}
    patched = patch_sources(original)
    manifest = json.loads((staged / 'manifest.json').read_text())
    assert all(hashlib.sha256(text.encode()).hexdigest() == manifest['files'][name]
               for name, text in original.items()), 'Runtime changed after backup'
    assert (home / 'config.yaml').read_bytes() == (staged / 'backup/config.yaml').read_bytes(), 'Config changed after backup'
    policy_path = home.parent / 'ultron-local/review-policy.json'
    assert policy_path.read_bytes() == (staged / 'backup/review-policy.json').read_bytes(), 'Review policy changed after backup'
    target = runtime / 'ultron_topic_queue'
    assert not target.exists(), 'Package already exists; use audited upgrade'
    config_path = home / 'topic-queue/config.json'
    assert not config_path.exists(), 'Queue already configured'
    modified = []
    try:
        target.mkdir(mode=0o700)
        # Current tested sources, not a stale staged copy.
        for source in Path(__file__).parent.glob('*.py'):
            if not source.name.startswith(('test_', 'install_', 'probe_')):
                content = source.read_bytes()
                compile(content, str(source), 'exec')
                atomic(target / source.name, content)
        atomic(target / '__init__.py', b'"""Local topic queue."""\n')
        expose_package(runtime)
        for name, content in patched.items():
            atomic(runtime / name, content.encode())
            modified.append(name)
        config = yaml.safe_load((home / 'config.yaml').read_text())
        config.setdefault('kanban', {}).update(dispatch_in_gateway=True, dispatch_interval_seconds=5,
            max_in_progress=None, max_in_progress_per_profile=1, dispatch_profiles=list(ROSTER))
        config.setdefault('display', {}).update(busy_input_mode='queue', busy_text_mode='queue', busy_ack_enabled=False)
        atomic(home / 'config.yaml', yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode())
        policy = json.loads(policy_path.read_text())
        if not any(r['model'] == REVIEW_ROUTE['model'] for r in policy['reviewers']):
            policy['reviewers'].insert(0, REVIEW_ROUTE)
        atomic(policy_path, json.dumps(policy, ensure_ascii=False, indent=2).encode())
        queue_config = json.loads((staged / 'queue-config.json').read_text())
        queue_config['enabled'] = enable
        atomic(config_path, json.dumps(queue_config, ensure_ascii=False, indent=2).encode())
        return dict(status='installed', admission_enabled=enable, gateway='stopped', backup=str(staged / 'backup'))
    except Exception:
        for name in modified:
            atomic(runtime / name, original[name].encode())
        atomic(home / 'config.yaml', (staged / 'backup/config.yaml').read_bytes())
        atomic(policy_path, (staged / 'backup/review-policy.json').read_bytes())
        if config_path.exists():
            config_path.unlink()
        # Keep new package for forensics; original hooks do not import it.
        raise


def expose_package(runtime):
    runtime = Path(runtime).resolve()
    assert runtime == Path('/opt/hermes-agent-20260924')
    package = runtime / 'ultron_topic_queue'
    assert package.is_dir() and not package.is_symlink()
    site_root = Path(site.getsitepackages()[0]).resolve()
    assert site_root.is_relative_to(runtime / 'venv')
    link = site_root / 'ultron_topic_queue'
    if link.is_symlink():
        assert link.resolve() == package
    else:
        assert not link.exists()
        link.symlink_to(package, target_is_directory=True)


if __name__ == '__main__':
    main()
