"""Opt-in, bounded real review probes. Prints no prompts, keys or responses."""
import json
from pathlib import Path
import sys


def main():
    sys.path.insert(0, '/root/ultron-local')
    import model_review
    policy = json.loads(Path('/root/ultron-local/review-policy.json').read_text())
    routes = policy['reviewers']
    if '--configured-fallbacks' in sys.argv:
        routes = [dict(model=model, tier=2) for model in model_review.live_aliases()['hermes-reasoning']
                  if model.startswith(('nvidia/', 'openrouter/'))]
    for route in routes:
        try:
            response = model_review.router_transport(route, dict(
                task='Responda a saudacao oi em portugues.', candidate='Oi!', evidence=[]), 512, 25)
            verdict = model_review.extract_verdict(response.get('content', ''))
            record = dict(route=route['model'], served=response.get('model'), verdict=verdict.get('verdict'))
        except Exception as exc:
            record = dict(route=route['model'], error=type(exc).__name__, code=getattr(exc, 'code', None))
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
