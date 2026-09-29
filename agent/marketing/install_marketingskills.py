"""Install a vetted, read-only subset of marketingskills into the Money profile."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

UPSTREAM = 'https://github.com/coreyhaines31/marketingskills'
COMMIT = '5b2c0007766c6a1cf1d53fd8fc73e979e0821022'
MARKER = '.ultron-marketingskills-managed'
SKILLS = (
    'product-marketing', 'customer-research', 'copywriting', 'content-strategy',
    'social', 'seo-audit', 'ad-creative', 'ads', 'analytics', 'ab-testing',
)
DESCRIPTIONS = {
    'product-marketing': 'Documente produto, público e posicionamento.',
    'customer-research': 'Pesquise clientes com fontes e consentimento.',
    'copywriting': 'Escreva textos de conversão baseados em evidências.',
    'content-strategy': 'Planeje conteúdo por objetivo, público e canal.',
    'social': 'Planeje e revise conteúdo de redes sociais.',
    'seo-audit': 'Audite SEO com dados verificáveis.',
    'ad-creative': 'Crie variações de anúncios para aprovação.',
    'ads': 'Analise campanhas pagas sem alterar contas.',
    'analytics': 'Analise métricas e limites dos dados disponíveis.',
    'ab-testing': 'Desenhe testes A/B com hipótese e métrica.',
}
GUARDRAILS = """## Escopo Money / Ultron

- Este guia é uma técnica de marketing, não autorização nem ferramenta nova. Preserve a personalidade do Money e a separação entre projetos pessoais e profissionais.
- Nunca pressuponha acesso a contas, anúncios, analytics, clientes ou dados privados. Consulte apenas fontes e integrações realmente disponíveis; explicite o que não pôde verificar.
- Pode pesquisar, analisar, planejar e preparar rascunhos. Publicar, enviar mensagens, mudar campanhas/orçamentos, fazer compras ou contratar serviços exige autorização explícita do Yuri para a ação concreta.
- Não prometa renda passiva, ROAS ou resultados sem evidência. Não copie dados pessoais para documentos públicos de marketing.
- Se alguma orientação abaixo contradisser estas regras, estas regras prevalecem.

"""


def _body(source: Path) -> str:
    content = source.read_text(encoding='utf-8-sig')
    if not content.startswith('---\n'):
        raise ValueError(f'missing_frontmatter:{source}')
    pieces = content.split('---\n', 2)
    if len(pieces) != 3:
        raise ValueError(f'broken_frontmatter:{source}')
    return pieces[2].lstrip('\n')


def _stage_skill(bundle: Path, name: str, stage: Path) -> None:
    source = bundle / name
    if not (source / 'SKILL.md').is_file():
        raise FileNotFoundError(source / 'SKILL.md')
    stage.mkdir()
    for file in source.rglob('*.md'):
        relative = file.relative_to(source)
        if any(part.startswith('.') for part in relative.parts):
            continue
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)
    body = _body(source / 'SKILL.md')
    if name == 'ads':
        body = body.replace('with direct access to ad platform accounts',
                            'who only uses ad platform data when authorized access exists', 1)
    header = f'---\nname: {name}\ndescription: "{DESCRIPTIONS[name]}"\n---\n\n'
    (stage / 'SKILL.md').write_text(header + GUARDRAILS + body, encoding='utf-8')
    (stage / MARKER).write_text(f'{UPSTREAM}\n{COMMIT}\n', encoding='utf-8')


def install(profile_home: Path, bundle: Path) -> dict:
    profile_home = Path(profile_home).resolve()
    bundle = Path(bundle).resolve()
    if profile_home.name != 'money' or profile_home.parent.name != 'profiles':
        raise ValueError('money_profile_only')
    if not profile_home.is_dir():
        raise FileNotFoundError(profile_home)
    if not (bundle / 'LICENSE').is_file():
        raise FileNotFoundError(bundle / 'LICENSE')
    target_root = profile_home / 'skills' / 'marketing'
    if target_root.is_symlink():
        raise RuntimeError('symlinked_marketing_root')
    for name in SKILLS:
        target = target_root / name
        if target.is_symlink() or (target.exists() and not (target / MARKER).is_file()):
            raise RuntimeError(f'unowned_skill:{name}')

    target_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = profile_home / 'backups' / 'marketingskills' / stamp
    backup.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='.marketingskills-', dir=target_root) as staging:
        staging = Path(staging)
        for name in SKILLS:
            _stage_skill(bundle, name, staging / name)
        for name in SKILLS:
            target = target_root / name
            if target.exists():
                os.replace(target, backup / name)
            try:
                os.replace(staging / name, target)
            except Exception:
                if (backup / name).exists():
                    os.replace(backup / name, target)
                raise
    shutil.copy2(bundle / 'LICENSE', target_root / 'LICENSE')
    manifest = {'upstream': UPSTREAM, 'commit': COMMIT, 'license': 'MIT',
                'profile': 'money', 'installed': list(SKILLS), 'backup': str(backup)}
    (target_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-home', type=Path, default=Path('/root/.hermes/profiles/money'))
    parser.add_argument('--bundle', type=Path, default=Path(__file__).parent / 'marketingskills')
    args = parser.parse_args()
    print(json.dumps(install(args.profile_home, args.bundle), ensure_ascii=False, indent=2))
