import pytest
from admission import Scope
from contract import QueueError
from profile_selection import Selection, parse_command

SCOPE = Scope('telegram', '1', '2', '2')


@pytest.fixture
def selection(tmp_path):
    for directory in (tmp_path, tmp_path / 'profiles/pink', tmp_path / 'profiles/cerebro'):
        directory.mkdir(parents=True, exist_ok=True)
        for name in ('SOUL.md', 'config.yaml'):
            (directory / name).write_text('test')
    return Selection(tmp_path, ['pink', 'cerebro'])


def test_initial_ultron_persistent_choice_restart_and_scoped_state(selection):
    assert selection.current(SCOPE) == 'ultron'
    selection.choose(SCOPE, 'pink', '10')
    restarted = Selection(selection.home, selection.profiles)
    assert restarted.current(SCOPE) == 'pink'
    assert restarted.current(Scope('telegram', 'other', '2', '2')) == 'ultron'
    assert restarted.current(Scope('telegram', '1', '2', '2', 'topic')) == 'ultron'
    restarted.choose(SCOPE, 'ultron', '11')
    assert restarted.current(SCOPE) == 'ultron'


def test_delayed_command_cannot_revert_choice_and_old_request_keeps_author(selection):
    selection.choose(SCOPE, 'pink', '10')
    assert selection.snapshot(SCOPE, '11') == 'pink'
    selection.choose(SCOPE, 'ultron', '20')
    selection.choose(SCOPE, 'cerebro', '12')
    assert selection.current(SCOPE) == 'ultron'
    assert selection.snapshot(SCOPE, '11') == 'pink'
    assert selection.snapshot(SCOPE, '21') == 'ultron'
    assert selection.snapshot(SCOPE, '19') == 'cerebro'
    assert selection.snapshot(SCOPE, '9') == 'ultron'


def test_missing_profile_never_changes_selection(selection):
    with pytest.raises(QueueError):
        selection.choose(SCOPE, '../outside', '10')
    assert selection.current(SCOPE) == 'ultron'


def test_explicit_commands_aliases_and_bot_address():
    assert parse_command('/celebro@MyBot explique isto', ['cerebro'], 'mybot') == ('cerebro', 'explique isto')
    assert parse_command('/pink@other pergunta', ['pink'], 'mybot') is None
    assert parse_command('texto /pink', ['pink']) is None
    assert parse_command('/stop', ['pink']) is None
    assert parse_command('/perfil', []) == ('perfil', '')
