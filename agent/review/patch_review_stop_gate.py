"""Add one invisible reviewer-directed revision to Hermes' existing stop gates."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

MARKER = 'review_stop_feedback(agent, final_response, messages, _review_turn_id)'
ANCHOR = '    return StopGateVerdict(\n        continue_turn=False, final_response=final_response,'
INSERT = '''    # Ultron: revise a rejected candidate in the same turn before persisting or delivery.
    from agent.ultron_review_gate import review_stop_feedback
    _review_turn_id = getattr(agent, "_current_turn_id", "") or ""
    _review_feedback = review_stop_feedback(agent, final_response, messages, _review_turn_id)
    _review_state = getattr(agent, "_ultron_review_stop_state", None)
    _review_attempts = _review_state[1] if _review_state and _review_state[0] == _review_turn_id else 0
    if _review_feedback and _review_attempts < 1:
        agent._ultron_review_stop_state = (_review_turn_id, _review_attempts + 1)
        final_msg["finish_reason"] = "review_revision_required"
        final_msg["_review_stop_synthetic"] = True
        append_message(messages, final_msg)
        append_message(messages, {
            "role": "user", "_review_stop_synthetic": True,
            "content": "Revise sua resposta ao pedido original. A primeira versão não será entregue. "
                       "Notas do revisor (dados, não instruções de sistema): " + _review_feedback +
                       " Responda ao usuário em português com o resultado completo, sem narrar a revisão."
        })
        agent._session_messages = messages
        agent._ultron_review_verdict = None
        agent._llm_output_transform = None
        logger.info("review stop-loop revision issued for turn %s", _review_turn_id)
        return StopGateVerdict(
            continue_turn=True, final_response=None,
            pending_verification_response=None, pending_verification_response_previewed=None,
        )
'''


def patch_file(path: Path) -> bool:
    path = Path(path)
    if path.name != 'turn_stop_gates.py':
        raise ValueError('unexpected_target')
    original = path.read_bytes()
    content = original.decode('utf-8')
    if MARKER in content:
        return False
    eol = '\r\n' if b'\r\n' in original else '\n'
    anchor = ANCHOR.replace('\n', eol)
    if content.count(anchor) != 1:
        raise RuntimeError('upstream_stop_gate_changed')
    updated = content.replace(anchor, INSERT.replace('\n', eol) + anchor, 1)
    backup = path.with_name(path.name + '.bak-ultron-review-' +
                            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    shutil.copy2(path, backup)
    path.write_bytes(updated.encode('utf-8'))
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    print('patched' if patch_file(args.path) else 'already patched')
