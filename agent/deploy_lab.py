"""Instalação com backup do ultron_lab no Hermes local (WSL Debian, root, /root/.hermes).

Uso (dentro do WSL, com o Python do Hermes):
    python deploy_lab.py stage     [--cenario pc|servidor] [--dry-run]
    python deploy_lab.py activate  [--dry-run]

stage   copia plugin, skills e inventário de exemplo (não altera config.yaml).
activate habilita o plugin no config.yaml principal e nos perfis gmail/easysapers.
Nenhuma etapa reinicia o gateway; faça isso pelo procedimento habitual depois.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

PLUGIN = 'ultron_lab'
MARK = '.ultron-lab-managed'
MAIL_PROFILES = ('gmail', 'easysapers')
SKILL_CATEGORY = 'ultron-lab'
TOOLSET_MAIN = 'ultron_lab'
TOOLSET_MAIL = 'ultron_lab_mail'
STAMP = '20260927'


def _append(values, item):
    if item not in values:
        values.append(item)


def activate_main(config, base_home, inventory, mail_contas=()):
    result = copy.deepcopy(config)
    plugins = result.setdefault('plugins', {})
    _append(plugins.setdefault('enabled', []), PLUGIN)
    disabled = plugins.get('disabled')
    if isinstance(disabled, list) and PLUGIN in disabled:
        disabled.remove(PLUGIN)
    settings = plugins.setdefault('entries', {}).setdefault(PLUGIN, {}).setdefault('settings', {})
    settings.setdefault('base_home', str(base_home))
    settings.setdefault('homelab_inventory', str(inventory))
    if mail_contas:
        settings.setdefault('mail_fraud_contas', list(mail_contas))
    for values in result.setdefault('platform_toolsets', {}).values():
        if isinstance(values, list):
            _append(values, TOOLSET_MAIN)
    return result


def activate_profile(config, base_home):
    result = copy.deepcopy(config)
    plugins = result.setdefault('plugins', {})
    _append(plugins.setdefault('enabled', []), PLUGIN)
    plugins.setdefault('entries', {}).setdefault(PLUGIN, {}).setdefault('settings', {}).setdefault(
        'base_home', str(base_home))
    for values in result.setdefault('platform_toolsets', {}).values():
        if isinstance(values, list):
            _append(values, TOOLSET_MAIL)
    return result


def atomic_text(path, content, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.ultron-lab-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fingerprints(home, skip):
    result = {}
    profiles = Path(home) / 'profiles'
    if profiles.is_dir():
        for profile in sorted(p for p in profiles.iterdir() if p.is_dir() and p.name not in skip):
            for filename in ('SOUL.md', 'config.yaml'):
                path = profile / filename
                if path.is_file():
                    result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class Installer:
    def __init__(self, home, source, dry_run=False):
        self.home = Path(home)
        self.source = Path(source)
        self.dry_run = dry_run
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        self.backup = self.home / 'backups' / ('ultron-lab-' + stamp)
        self.manifest = {'backup': str(self.backup), 'dry_run': dry_run, 'changed': [], 'created': [], 'planned': []}
        # Perfis de e-mail do ultron_team são opcionais: sem eles, a checagem por UID fica no Ultron principal.
        self.mail_profiles = [p for p in MAIL_PROFILES if (self.home / 'profiles' / p / 'config.yaml').is_file()]
        accounts = self.home / 'skills' / 'email-manager' / 'scripts' / 'accounts.json'
        self.main_mail = [p for p in MAIL_PROFILES if p not in self.mail_profiles] if accounts.is_file() else []
        self.manifest['perfis_email'] = self.mail_profiles
        self.manifest['email_no_principal'] = self.main_mail

    def _plan(self, text):
        self.manifest['planned'].append(text)
        return self.dry_run

    def preserve(self, path):
        path = Path(path)
        if not path.exists():
            self.manifest['created'].append(str(path))
            return
        self.manifest['changed'].append(str(path))
        if self.dry_run:
            return
        destination = self.backup / path.relative_to(self.home)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
            os.chmod(destination, 0o600)

    def copy_managed(self, source, destination):
        destination = Path(destination)
        if destination.exists() and not (destination / MARK).exists():
            raise RuntimeError('destino_nao_gerenciado: ' + str(destination))
        if self._plan(f'copiar {source} -> {destination}'):
            return
        self.preserve(destination)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'tests'))
        atomic_text(destination / MARK, STAMP + '\n')

    def stage(self, cenario):
        if not (self.home / 'config.yaml').is_file():
            raise RuntimeError('hermes_home_sem_config: ' + str(self.home))
        self.copy_managed(self.source / PLUGIN, self.home / 'plugins' / PLUGIN)
        for name in self.mail_profiles:
            self.copy_managed(self.source / PLUGIN, self.home / 'profiles' / name / 'plugins' / PLUGIN)
        for skill in sorted(p for p in (self.source / 'skills').iterdir() if (p / 'SKILL.md').is_file()):
            self.copy_managed(skill, self.home / 'skills' / SKILL_CATEGORY / skill.name)
        inventory = self.home / 'ultron_lab' / 'homelab.json'
        example = self.source / 'homelab' / 'inventario' / f'homelab.{cenario}.json'
        if not inventory.exists() and not self._plan(f'criar inventário {inventory} a partir de {example.name}'):
            json.loads(example.read_text(encoding='utf-8'))
            atomic_text(inventory, example.read_text(encoding='utf-8'))
            self.manifest['created'].append(str(inventory))

    def activate(self):
        import yaml
        if not (self.home / 'plugins' / PLUGIN / MARK).is_file():
            raise RuntimeError('rode_stage_antes')
        inventory = self.home / 'ultron_lab' / 'homelab.json'

        def update(path, transform):
            config = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
            rendered = yaml.safe_dump(transform(config), sort_keys=False, allow_unicode=True)
            yaml.safe_load(rendered)
            if self._plan(f'atualizar {path}'):
                return
            self.preserve(path)
            atomic_text(path, rendered)
        update(self.home / 'config.yaml', lambda c: activate_main(c, self.home, inventory, self.main_mail))
        for name in self.mail_profiles:
            update(self.home / 'profiles' / name / 'config.yaml', lambda c: activate_profile(c, self.home))

    def run(self, action, cenario='pc'):
        before = fingerprints(self.home, MAIL_PROFILES)
        if not self.dry_run:
            self.backup.mkdir(parents=True, mode=0o700)
        if action == 'stage':
            self.stage(cenario)
        else:
            self.activate()
        after = fingerprints(self.home, MAIL_PROFILES)
        if before != after:
            raise RuntimeError('outros_perfis_alterados_inesperadamente')
        self.manifest['outros_perfis_intactos'] = len(before)
        if not self.dry_run:
            atomic_text(self.backup / 'manifest.json', json.dumps(self.manifest, indent=2, ensure_ascii=False))
        return self.manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['stage', 'activate'])
    parser.add_argument('--home', default='/root/.hermes')
    parser.add_argument('--cenario', choices=['pc', 'servidor'], default='pc')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    manifest = Installer(args.home, Path(__file__).resolve().parent, args.dry_run).run(args.action, args.cenario)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if args.action == 'activate' and not args.dry_run:
        print('\nPronto. Reinicie o gateway do Hermes pelo procedimento habitual para carregar o ultron_lab.')


if __name__ == '__main__':
    main()
