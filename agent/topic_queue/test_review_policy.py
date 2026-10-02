import pytest

from review_policy import pertinent_profiles, technical_failure, warning, collect


def test_domain_is_not_author_or_numbers():
    roster = {'ultron': '', 'thor': '', 'greg': '', 'tanos': '', 'bigode': ''}
    assert pertinent_profiles('Analise o erro da nota SAP final 14', 'ultron', roster) == ['thor']
    assert pertinent_profiles('onde estao esses emails 1729 2026?', 'ultron', roster) == ['greg']
    assert pertinent_profiles('revise meu orcamento', 'ultron', roster) == ['bigode']
    assert 'tanos' not in pertinent_profiles('Analise a nota SAP', 'ultron', roster)


def test_only_transport_errors_can_degrade():
    assert technical_failure(TimeoutError())
    assert technical_failure(type('HTTPError', (Exception,), {'status_code': 404})())
    assert not technical_failure(ValueError('invalid binding'))
    assert not technical_failure(RuntimeError('something unknown'))


def test_timeout_returns_explicit_unavailable_without_approval():
    votes = collect({}, 'SAP', ['thor'], home='/unused', proof_id='test',
                    call=lambda *a, **kw: (_ for _ in ()).throw(TimeoutError()))
    assert votes['thor']['verdict'] == 'unavailable'
    assert votes['thor']['completed'] is False
    assert 'Thor' in warning(votes)


def test_substantive_rejection_is_not_degraded():
    vote = dict(verdict='blocked', completed=True, issues=['wrong product'])
    assert collect({}, 'SAP', ['thor'], home='/unused', proof_id='test',
                   call=lambda *a, **kw: vote)['thor'] == vote
    with pytest.raises(ValueError):
        collect({}, 'SAP', ['thor'], home='/unused', proof_id='test',
                call=lambda *a, **kw: (_ for _ in ()).throw(ValueError('invalid hash')))
