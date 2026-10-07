"""Run with the installed Hermes runtime on PYTHONPATH."""
import json
import pytest
tt = pytest.importorskip('tools.terminal_tool', reason='Requires installed Hermes runtime')


@pytest.mark.parametrize('heartbeat', [60, 120])
def test_explicit_notifications_off_accepts_spurious_heartbeat(monkeypatch, heartbeat):
    calls = []
    monkeypatch.setattr(tt, 'terminal_tool', lambda **kw: calls.append(kw) or '{}')
    result = json.loads(tt._handle_terminal({
        'command': 'printf ok', 'background': False, 'notify': False,
        'heartbeat': heartbeat, 'pty': False,
    }))
    assert not result.get('error'), result
    assert len(calls) == 1
    assert calls[0]['heartbeat'] == 0
    assert calls[0]['notify_on_complete'] is False
    assert calls[0]['background'] is False


@pytest.mark.parametrize('extra', [{'notify': True}, {'heartbeat': 60},
                                 {'notify': False, 'heartbeat': 60, 'pty': True}])
def test_foreground_does_not_silently_enable_background(monkeypatch, extra):
    calls = []
    monkeypatch.setattr(tt, 'terminal_tool', lambda **kw: calls.append(kw) or '{}')
    result = json.loads(tt._handle_terminal({'command': 'printf ok', **extra}))
    assert result.get('error')
    assert not calls
