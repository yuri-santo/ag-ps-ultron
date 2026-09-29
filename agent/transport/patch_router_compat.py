"""Install the local router compatibility hook without replacing upstream files."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil


MARKER = 'api_messages = protect_router_tool_results('
ANCHOR = '    kwargs = _build_api_kwargs_for_mode(agent, api_messages, tools_for_api)\n'
INSERT = '''    from agent.ultron_router_compat import protect_router_tool_results
    api_messages = protect_router_tool_results(
        api_messages, base_url=getattr(agent, "base_url", None),
        api_mode=getattr(agent, "api_mode", "chat_completions"),
    )
'''


def patch_file(path):
    path = Path(path)
    if path.name != 'chat_completion_helpers.py':
        raise ValueError('unexpected_target')
    original = path.read_bytes()
    content = original.decode('utf-8')
    if MARKER in content:
        return False
    eol = '\r\n' if b'\r\n' in original else '\n'
    anchor = ANCHOR.replace('\n', eol)
    if content.count(anchor) != 1:
        raise RuntimeError('upstream_request_builder_changed')
    updated = content.replace(anchor, INSERT.replace('\n', eol) + anchor, 1)
    compile(updated, str(path), 'exec')
    backup = path.with_name(path.name + '.bak-ultron-router-' +
                            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    shutil.copy2(path, backup)
    path.write_bytes(updated.encode('utf-8'))
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    print('patched' if patch_file(args.path) else 'already patched')
