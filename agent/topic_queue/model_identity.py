"""Use observed response-body identity when the local proxy omits model headers."""
import sys


def aliases():
    sys.path.insert(0, '/root/ultron-local') if '/root/ultron-local' not in sys.path else None
    import model_review
    return set(model_review.live_aliases())


def observe(agent, response):
    try:
        from .specialist import capture_identity
    except ImportError:
        from specialist import capture_identity
    try:
        capture_identity(agent, response, aliases())
    except Exception:
        agent.last_served_model = None
