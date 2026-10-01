"""Explicit local integration tools; imported text is data, never authority."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

try:
    from .import_transcriptonic import convert
    from .skill_audit import SkillAudit
except ImportError:
    from import_transcriptonic import convert
    from skill_audit import SkillAudit


def digest(data):
    return hashlib.sha256(data).hexdigest()


class MarketingGuides:
    def __init__(self, home, catalog, *, reader=None):
        self.home, self.catalog, self.reader = Path(home), dict(catalog), reader

    def view(self, skill):
        if not isinstance(skill, str) or not re.fullmatch(r'marketing:[a-z][a-z-]*', skill):
            raise ValueError('Expected an installed marketing skill ID')
        name = skill.split(':', 1)[1]
        directory = self.home / 'skills/marketing' / name
        source = directory / 'SKILL.md'
        if (self.catalog.get(skill) != str(directory) or not source.is_file()
                or any(p.is_symlink() for p in (source, *source.parents))
                or source.stat().st_size > 128 * 1024):
            raise ValueError('Skill is outside the installed Money catalog')
        reader = self.reader
        if reader is None:
            from tools.skills_tool import skill_view
            reader = skill_view
        # Native parsing/readiness, but never inline shell/template execution.
        result = json.loads(reader(name='marketing/' + name, preprocess=False))
        if (not isinstance(result, dict) or result.get('success') is not True
                or result.get('_source_path') != str(source)
                or not isinstance(result.get('content'), str)):
            raise ValueError('Native skill lookup did not resolve the expected installed source')
        return {'status': 'loaded', 'skill_id': skill, 'content': result['content'],
                'linked_files': result.get('linked_files'), 'commands_executed': False,
                'publication_authorized': False,
                'limitation': 'Guide only. References not loaded. No account access or authorization granted.'}


class Captions:
    def __init__(self, root):
        self.root = Path(root)

    def import_json(self, payload_json):
        if not isinstance(payload_json, str) or len(payload_json.encode()) > 2 * 1024 * 1024:
            raise ValueError('Expected an advanced webhook JSON up to 2 MiB')
        payload = convert(json.loads(payload_json))
        content = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
        transcript = '\n'.join(f"{e['at']} | {e['speaker_label']}: {e['text']}"
                               for e in payload['transcript_events']).encode()
        source_hash = digest(content)
        if any(p.is_symlink() for p in (self.root, *self.root.parents)):
            raise ValueError('Private caption directory cannot be a link')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        fd = os.open(self.root / '.import.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            output = self.root / source_hash
            if output.is_symlink():
                raise ValueError('Artifact directory cannot be a link')
            contents = {'report-input.json': content, 'transcript.txt': transcript}
            if output.exists():
                for name, data in contents.items():
                    file = output / name
                    if file.is_symlink() or not file.is_file() or file.read_bytes() != data:
                        raise ValueError('Existing import was modified; inspect privately')
            else:
                with tempfile.TemporaryDirectory(prefix='.caption-', dir=self.root) as temp:
                    stage = Path(temp) / 'artifact'
                    stage.mkdir(mode=0o700)
                    for name, data in contents.items():
                        fd = os.open(stage / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                        with os.fdopen(fd, 'wb') as stream:
                            stream.write(data)
                            stream.flush()
                            os.fsync(stream.fileno())
                    os.replace(stage, output)
                dfd = os.open(self.root, os.O_DIRECTORY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
        return {'status': 'imported', 'source': 'platform_captions', 'source_sha256': source_hash,
                'identity_verified': False, 'audio_transcribed': False,
                'confirmed_actions': 0, 'transcript_events': len(payload['transcript_events']),
                'artifact_path': str(output / 'report-input.json'),
                'transcript_path': str(output / 'transcript.txt')}


def register_tools(register, profile, home, base, *, settings):
    home, base = Path(home), Path(base)
    expected = base / 'profiles' / profile if profile else base
    if home != expected or home.resolve() != expected or any(p.is_symlink() for p in (home, *home.parents)):
        raise ValueError('Invalid profile boundary')
    if profile not in ('', 'mrrobot', 'maquiavel', 'dona', 'money'):
        return None

    def add(name, description, properties, required, operation):
        def handler(args, **kwargs):
            try:
                return json.dumps(operation(**args), ensure_ascii=False)
            except Exception as exc:
                # Source text, subprocess errors and local account data never enter diagnostics.
                return json.dumps({'status': 'error', 'error_type': type(exc).__name__,
                                   'completed': False, 'approved': False})
        schema = {'name': name, 'description': description, 'parameters': {
            'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}
        register(name=name, toolset='ultron_adoption', schema=schema, handler=handler, description=description)

    def status():
        return {'tiktok_shop': 'blocked_by_owner', 'external_affiliates': 'existing_guarded_flow',
                'skillspector': {'configured': bool(settings.get('image')), 'coverage': 'offline_static_only',
                                 'automatic_approval': False, 'skill_ids': sorted(settings.get('skills', {}))},
                'captions': 'advanced_webhook_import_only', 'phoneharness': 'offline_preparation_only',
                'marketing_guide_access': profile == 'money'}
    add('adoption_status', 'Consulta integracoes locais e IDs de skills auditaveis. Vitrine TikTok bloqueada pelo titular.',
        {}, [], status)
    if profile in ('', 'mrrobot'):
        auditor = SkillAudit(settings.get('skills', {}), home / 'integrations' / 'skill-audits', settings.get('image', ''))
        add('adoption_skill_audit', 'Audita uma skill cadastrada antes de instalar/atualizar. SkillSpector isolado sem rede/LLM; nao aprova nem instala.',
            {'skill': {'type': 'string', 'description': 'ID retornado por adoption_status'}}, ['skill'], auditor.scan)
    if profile in ('', 'maquiavel', 'dona'):
        captions = Captions(home / 'integrations' / 'captions')
        add('adoption_caption_import', 'Importa JSON advanced Transcriptonic fornecido pelo titular. Preserva transcricao e chat; nao confirma nomes/decisoes nem envia relatorio.',
            {'payload_json': {'type': 'string', 'description': 'Corpo JSON advanced completo; nao TXT nem URL'}},
            ['payload_json'], captions.import_json)
    if profile == 'money':
        guides = MarketingGuides(home, settings.get('skills', {}))
        parameter = {'type': 'string', 'description': 'ID marketing:nome informado por adoption_status'}
        if guides.catalog:
            parameter['enum'] = sorted(guides.catalog)
        add('adoption_marketing_guide', 'Le uma das dez skills de marketing instaladas no Money, antes de redigir roteiro/copy ou analisar campanhas. Sem executar comandos, editar skills ou autorizar publicacao.',
            {'skill': parameter}, ['skill'], guides.view)
    return 'ultron_adoption'
