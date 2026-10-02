import json
import subject_review


def test_native_and_cron_return_candidate_with_limited_confidence(tmp_path, monkeypatch):
    (tmp_path / 'topic-queue').mkdir()
    (tmp_path / 'topic-queue/config.json').write_text(json.dumps({'roster': {'ultron': '', 'thor': ''}}))
    monkeypatch.setattr(subject_review, 'collect', lambda *a, **kw: {
        'thor': dict(verdict='unavailable', completed=False, technical_error='APITimeoutError')})
    result = subject_review.review_answer('Analise pronta.', 'nota SAP',
        {'model': 'actual'}, [], 'task', home=tmp_path)
    assert result['completed'] is True
    assert result['status'] == 'unvalidated' and result['approval_completed'] is False
    assert result['confidence'] == 'limited'
    assert 'Nao validado por Thor' in result['delivery_notice']


def test_native_substantive_issue_keeps_revision(tmp_path, monkeypatch):
    (tmp_path / 'topic-queue').mkdir()
    (tmp_path / 'topic-queue/config.json').write_text(json.dumps({'roster': {'ultron': '', 'thor': ''}}))
    monkeypatch.setattr(subject_review, 'collect', lambda *a, **kw: {
        'thor': dict(verdict='revise', completed=True, issues=['Nota incorreta'])})
    result = subject_review.review_answer('Texto.', 'nota SAP', {'model': 'actual'}, [], 'task', home=tmp_path)
    assert result['status'] == 'revision_required' and result['completed'] is False
