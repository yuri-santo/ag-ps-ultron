"""Pure source migrations: capture closure time must precede report processing.

These functions return source text; they never write or deploy installed files.
"""
import ast


END_HELPER = '''def _capture_end_fields(event):
    import math

    def valid(value):
        return type(value) in (int, float) and math.isfinite(value) and value > 0

    ended = event.get('capture_ended_at')
    stopped = event.get('at')
    source = event.get('capture_ended_at_source')
    if (source == 'capture_streams_closed' and valid(ended)
            and valid(stopped) and ended <= stopped):
        return dict(capture_ended_at=ended, capture_ended_at_estimated=False,
                    capture_ended_at_source=source)
    # Old agents timestamp their stop notice after ASR, not device closure.
    if 'capture_ended_at' not in event and valid(stopped):
        return dict(capture_ended_at=stopped, capture_ended_at_estimated=True,
                    capture_ended_at_source='stopped_after_queue_drain')
    return dict(capture_ended_at=None, capture_ended_at_estimated=None,
                capture_ended_at_source='unknown')


'''


def _replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Unknown source layout: ' + old[:80])
    return source.replace(old, new, 1)


def _method_replace(source, name, old, new):
    tree = ast.parse(source)
    methods = [node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if len(methods) != 1:
        raise ValueError('Unknown method layout: ' + name)
    node = methods[0]
    lines = source.splitlines(keepends=True)
    body = ''.join(lines[node.lineno - 1:node.end_lineno])
    replacement = _replace(body, old, new)
    return ''.join(lines[:node.lineno - 1]) + replacement + ''.join(lines[node.end_lineno:])


def transform_runtime(source):
    """Retain event provenance; do not substitute finalization time on retry."""
    if 'def _capture_end_fields(event):' in source:
        required = ("**_capture_end_fields(event)", "'ended_at_estimated':",
                    "'ended_at_source':", 'capture_ended_at_source=None')
        if not all(part in source for part in required):
            raise ValueError('Incomplete capture end migration')
        ast.parse(source)
        return source
    source = _method_replace(source, '_launch',
        'self.store.update(sid,capture_stop_confirmed=False)',
        'self.store.update(sid,capture_stop_confirmed=False, capture_ended_at=None, '
        'capture_ended_at_estimated=None, capture_ended_at_source=None)')
    source = _method_replace(source, 'ingest',
        "self.store.update(sid,pending_audio=event.get('pending',0),capture_stop_confirmed=True)",
        "self.store.update(sid,pending_audio=event.get('pending',0),capture_stop_confirmed=True, "
        '**_capture_end_fields(event))')
    source = _method_replace(source, 'finish', "'ended_at':time.time()",
        "'ended_at':self.store.get(sid)['state'].get('capture_ended_at'),"
        "'ended_at_estimated':self.store.get(sid)['state'].get('capture_ended_at_estimated'),"
        "'ended_at_source':self.store.get(sid)['state'].get('capture_ended_at_source') or 'unknown'")
    source = _replace(source, 'class Copilot:', END_HELPER + 'class Copilot:')
    ast.parse(source)
    return source


def transform_capture(source):
    """Measure closure in acquisition workers, before saving and ASR drain."""
    if 'acquisition_ends = {}' in source:
        if ('acquisition_ends[channel] = time.time()' not in source
                or "capture_ended_at_source=" not in source):
            raise ValueError('Incomplete capture acquisition migration')
        ast.parse(source)
        return source
    source = _replace(source, '    acquisition_done = threading.Event()',
        '    acquisition_ends = {}\n    acquisition_done = threading.Event()')
    source = _method_replace(source, 'capture', '\n        except Exception as exc:',
        '\n            acquisition_ends[channel] = time.time()\n        except Exception as exc:')
    source = _replace(source, "notice('stopped', 'Captura encerrada e fila processada.',",
        "notice('stopped', 'Captura encerrada e fila processada.',\n"
        "               capture_ended_at=(max(acquisition_ends.values()) if "
        "{'mic', 'loopback'}.issubset(acquisition_ends) else None),\n"
        "               capture_ended_at_source='capture_streams_closed',")
    ast.parse(source)
    return source
