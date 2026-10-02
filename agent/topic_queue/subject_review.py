"""Single final-answer review entry for native chat and cron deliveries."""
import hashlib
import json
import os
from pathlib import Path

try:
    from .review_policy import collect, pertinent_profiles, warning
except ImportError:
    from review_policy import collect, pertinent_profiles, warning


def review_answer(text, request, producer, evidence, task_id, home=None):
    home = Path(home or os.environ.get('ULTRON_BASE_HOME', '/root/.hermes'))
    config = json.loads((home / 'topic-queue/config.json').read_text())
    roster = config['roster']
    author = os.environ.get('ULTRON_PROFILE', 'ultron')
    profiles = pertinent_profiles(request, author, roster)
    prepared = dict(parts=[text], served_identity=producer.get('served_model') or producer['model'],
                    evidence=evidence)
    votes = collect(prepared, request, profiles, home=home, proof_id=task_id)
    record = dict(status='approved', completed=True, reason='subject_review',
                  output_sha256=hashlib.sha256(text.encode()).hexdigest(), profile_reviews=votes,
                  reviews=[dict(verdict=v, reviewer={'profile': p}) for p, v in votes.items()])
    rejected = [v for v in votes.values() if v.get('verdict') in ('revise', 'blocked')]
    if rejected:
        record.update(status='revision_required', completed=False, reason='independent_review_revise')
    elif any(v.get('verdict') == 'unavailable' for v in votes.values()):
        # completed refers to delivery, never to approval. Individual votes stay incomplete.
        record.update(status='unvalidated', completed=True, reason='review_transport_unavailable',
                      approval_completed=False, confidence='limited', delivery_notice=warning(votes))
    elif not all(v.get('completed') is True and v.get('verdict') == 'approved' for v in votes.values()):
        record.update(status='pending_review', completed=False, reason='invalid_review')
    return record
