"""Explicit local deployment, after operator backup. Uses Hermes native cron API."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        parser.error('Inspect and back up local installation, then pass --apply')
    sys.path.insert(0, '/opt/hermes-agent-20260924')
    from cron.jobs import list_jobs, update_job
    from cron_interests import TOPICS, updates
    source = Path(__file__).resolve().parent
    root = Path('/root/ultron-local/context')
    scripts = Path('/root/.hermes/scripts')
    plugin = Path('/root/.hermes/plugins/a_team_workflow/__init__.py')
    policy = (source / 'CONTEXT-POLICY.md').read_text(encoding='utf-8')
    if len(policy) > 4000:
        raise ValueError('Context policy exceeds native prompt budget')
    jobs = [j for j in list_jobs(include_disabled=True) if j['name'] in TOPICS]
    plans = [(j, updates(j)) for j in jobs]
    old = plugin.read_text()
    anchor = '    register_collaboration(ctx)'
    addition = "\n    ctx.register_system_prompt_section(id='contextual-tool-policy', content=pathlib.Path('/root/ultron-local/context/CONTEXT-POLICY.md').read_text(), max_chars=4000)"
    if addition not in old:
        if old.count(anchor) != 1:
            raise ValueError('Unexpected plugin version')
        changed = old.replace(anchor, anchor + addition)
    else:
        changed = old
    ast.parse(changed)
    root.mkdir(parents=True, exist_ok=True)
    for name in ['interests.py', 'interest_manage.py', 'CONTEXT-POLICY.md']:
        shutil.copy2(source / name, root / name)
    for topic in sorted(set(TOPICS.values())):
        code = ("import json, sys\n"
                "try:\n"
                "    sys.path.insert(0, '/root/ultron-local/context')\n"
                "    from interests import InterestStore, gate\n"
                f"    result = gate(InterestStore().list(), {topic!r})\n"
                "except Exception:\n"
                "    result = {'wakeAgent': False, 'reason': 'interest_gate_unavailable'}\n"
                "print(json.dumps(result, ensure_ascii=False, allow_nan=False))\n")
        ast.parse(code)
        (scripts / ('interest_' + topic + '.py')).write_text(code)
    plugin.write_text(changed)
    for job, plan in plans:
        result = update_job(job['id'], plan)
        if not result:
            raise RuntimeError('Native cron update failed')
        print(json.dumps({'name': job['name'], 'script': result['script'],
                          'enabled': result['enabled'], 'state': result['state']}))


if __name__ == '__main__':
    main()
