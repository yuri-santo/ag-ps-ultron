import json
from types import SimpleNamespace


def test_capture_uses_observed_body_not_requested_alias():
    from specialist import capture_identity
    agent = SimpleNamespace(model='combo', last_served_model=None)
    capture_identity(agent, SimpleNamespace(model='gemini-3.8-flash'), {'combo'})
    assert agent.last_served_model == 'gemini-3.8-flash'
    capture_identity(agent, SimpleNamespace(model='combo'), {'combo'})
    assert agent.last_served_model is None
    capture_identity(agent, SimpleNamespace(model=''), {'combo'})
    assert agent.last_served_model is None


def test_capture_does_not_accept_non_string_or_url_as_identity():
    from specialist import capture_identity
    for value in ({'model': 'forged'}, 'https://endpoint', 'bad\nidentity'):
        agent = SimpleNamespace(model='combo', last_served_model=None)
        capture_identity(agent, SimpleNamespace(model=value), {'combo'})
        assert agent.last_served_model is None
