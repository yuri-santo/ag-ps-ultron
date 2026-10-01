import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'audit'))
sys.path.insert(0, str(Path(__file__).parents[1] / 'meeting'))
from integrations.tools_adapter import Captions, register_tools


def sample():
    return json.loads((Path(__file__).parents[1] / 'meeting/examples/transcriptonic.json').read_text())


def test_caption_import_keeps_provenance_and_deduplicates(tmp_path):
    captions = Captions(tmp_path / 'private')
    raw = json.dumps(sample())
    first = captions.import_json(raw)
    assert captions.import_json(raw) == first
    assert first['identity_verified'] is False and first['source'] == 'platform_captions'
    payload = json.loads(Path(first['artifact_path']).read_text())
    assert payload['records'] == [] and payload['source_payload'] == sample()
    assert Path(first['transcript_path']).is_file()
    assert Path(first['artifact_path']).stat().st_mode & 0o777 == 0o600


def test_modified_cached_artifact_is_not_reused(tmp_path):
    captions = Captions(tmp_path / 'private')
    raw = json.dumps(sample())
    first = captions.import_json(raw)
    Path(first['artifact_path']).write_text('{}')
    with pytest.raises(ValueError):
        captions.import_json(raw)


def test_rejects_invalid_input_and_linked_destination(tmp_path):
    captions = Captions(tmp_path / 'private')
    for raw in ('{}', '{bad json', 'x' * (2 * 1024 * 1024 + 1)):
        with pytest.raises(ValueError):
            captions.import_json(raw)
    (tmp_path / 'private').symlink_to(tmp_path / 'other', target_is_directory=True)
    with pytest.raises(ValueError):
        captions.import_json(json.dumps(sample()))


@pytest.mark.parametrize('profile,expected', [
    ('', {'adoption_status','adoption_skill_audit','adoption_caption_import'}),
    ('mrrobot', {'adoption_status','adoption_skill_audit'}),
    ('maquiavel', {'adoption_status','adoption_caption_import'}),
    ('dona', {'adoption_status','adoption_caption_import'}),
    ('money', {'adoption_status', 'adoption_marketing_guide'}), ('not_a_profile', set()),
])
def test_tools_are_scoped_by_actual_profile(tmp_path, profile, expected):
    registered = []
    base = tmp_path / 'hermes'
    home = base / 'profiles' / profile if profile else base
    register_tools(lambda **kw: registered.append(kw), profile, home, base,
                   settings={'image':'sha256:'+'a'*64, 'skills':{}})
    assert {tool['name'] for tool in registered} == expected
    for tool in registered:
        assert tool['schema']['parameters']['additionalProperties'] is False
    status = next((t for t in registered if t['name']=='adoption_status'), None)
    if status:
        result = json.loads(status['handler']({}))
        assert result['tiktok_shop'] == 'blocked_by_owner'
        assert result['skillspector']['automatic_approval'] is False


def test_profile_cannot_claim_another_home(tmp_path):
    calls = []
    with pytest.raises(ValueError):
        register_tools(lambda **kw: calls.append(kw), 'mrrobot', tmp_path, tmp_path/'base', settings={})
    assert calls == []


def test_money_uses_native_readonly_skill_view_and_validates_its_source(tmp_path, monkeypatch):
    from integrations.tools_adapter import MarketingGuides
    home = tmp_path / 'money'
    source = home / 'skills/marketing/copywriting'
    source.mkdir(parents=True)
    (source / 'SKILL.md').write_text('A trusted source, !`never execute`')
    calls = []
    def reader(**kw):
        calls.append(kw)
        return json.dumps({'success': True, 'content': 'Guide', 'name': 'copywriting',
                           '_source_path': str(source/'SKILL.md'), 'skill_dir': str(source),
                           'linked_files': {'references': ['ref.md']}})
    guides = MarketingGuides(home, {'marketing:copywriting': str(source)}, reader=reader)
    output = guides.view('marketing:copywriting')
    assert calls == [{'name': 'marketing/copywriting', 'preprocess': False}]
    assert output['content'] == 'Guide' and output['commands_executed'] is False
    assert output['publication_authorized'] is False and '_source_path' not in output
    with pytest.raises(ValueError):
        guides.view('../../secret')
    assert len(calls) == 1
    bad = MarketingGuides(home, {'marketing:copywriting': str(source)}, reader=lambda **kw:
                         json.dumps({'success': True,'content':'private','_source_path':'/other/SKILL.md'}))
    with pytest.raises(ValueError):
        bad.view('marketing:copywriting')


def test_money_rejects_linked_or_foreign_catalog_before_native_view(tmp_path):
    from integrations.tools_adapter import MarketingGuides
    home = tmp_path / 'money'
    source = home / 'skills/marketing/copywriting'
    source.mkdir(parents=True)
    calls=[]
    reader=lambda **kw: calls.append(kw)
    foreign = MarketingGuides(home, {'marketing:copywriting':'/other/skill'}, reader=reader)
    with pytest.raises(ValueError):
        foreign.view('marketing:copywriting')
    (source/'SKILL.md').symlink_to('/etc/passwd')
    linked = MarketingGuides(home, {'marketing:copywriting':str(source)}, reader=reader)
    with pytest.raises(ValueError):
        linked.view('marketing:copywriting')
    assert not calls
