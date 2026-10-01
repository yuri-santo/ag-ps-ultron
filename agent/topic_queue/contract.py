"""Closed proposal schema. Text offsets are Python Unicode code points, not bytes."""
import json


class QueueError(ValueError):
    """The requested metadata operation could not be committed."""


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':'))
    except (TypeError, ValueError, RecursionError) as exc:
        raise QueueError('Invalid JSON value') from exc


def require(condition, reason):
    if not condition:
        raise QueueError(reason)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def closed(value, fields):
    require(isinstance(value, dict) and set(value) == set(fields), 'Unexpected schema fields')


def intervals(spans, text):
    require(isinstance(spans, (list, tuple)) and bool(spans), 'Request spans are required')
    result = []
    for pair in spans:
        require(isinstance(pair, (tuple, list)) and len(pair) == 2, 'Invalid request span')
        start, end = pair
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(text),
                'Request span is outside text')
        result.append((start, end))
    result.sort()
    require(all(a[1] <= b[0] for a, b in zip(result, result[1:])), 'Overlapping request spans')
    return result


def acyclic(graph):
    """Iterative Kahn validation avoids a recursion-dependent topic count limit."""
    incoming = {key: len(deps) for key, deps in graph.items()}
    children = {key: [] for key in graph}
    for key, deps in graph.items():
        for dep in deps:
            require(dep in graph, 'Unknown dependency')
            children[dep].append(key)
    ready = [key for key, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for child in children[key]:
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    require(visited == len(graph), 'Dependency cycle')


def validate_plan(value, text, request_spans, allowed_profiles):
    closed(value, {'schema_version', 'topics', 'ignored'})
    require(type(value['schema_version']) is int and value['schema_version'] == 1,
            'Unsupported plan schema')
    topics = value['topics']
    require(isinstance(topics, list) and bool(topics), 'Plan needs topics')
    require(isinstance(value['ignored'], list), 'Ignored spans must be a list')
    coverage = bytearray(len(text))
    requests = bytearray(len(text))
    authorized = bytearray(len(text))
    for start, end in request_spans:
        authorized[start:end] = b'\1' * (end - start)

    def span(item, *, ignored=False):
        closed(item, {'start', 'end', 'text', 'reason' if ignored else 'kind'})
        start, end = item['start'], item['end']
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(text),
                'Span is outside text')
        require(item['text'] == text[start:end], 'Span quote differs from source')
        require(not any(coverage[start:end]), 'Overlapping coverage')
        coverage[start:end] = b'\1' * (end - start)
        if ignored:
            require(item['reason'] in ('non_actionable', 'untrusted'), 'Invalid ignored reason')
        else:
            require(item['kind'] in ('request', 'context'), 'Invalid span kind')
            if item['kind'] == 'request':
                require(all(authorized[start:end]), 'Request cites untrusted text')
                require(bool(text[start:end].strip()), 'Empty request')
                requests[start:end] = b'\1' * (end - start)

    graph = {}
    existing = set()
    for topic in topics:
        closed(topic, {'key', 'title', 'profile', 'topic_id', 'expected_version', 'depends_on', 'spans'})
        key = topic['key']
        require(nonempty(key) and key not in graph, 'Duplicate or empty topic key')
        require(nonempty(topic['title']), 'Topic title is required')
        require(isinstance(topic['profile'], str) and topic['profile'] in allowed_profiles,
                'Profile is not permitted')
        target = topic['topic_id']
        if target is None:
            require(topic['expected_version'] is None, 'New topic cannot have prior version')
        else:
            require(nonempty(target) and target not in existing, 'Repeated or invalid target')
            require(type(topic['expected_version']) is int and topic['expected_version'] > 0,
                    'Existing topic needs exact expected version')
            existing.add(target)
        deps = topic['depends_on']
        require(isinstance(deps, list) and all(nonempty(x) for x in deps), 'Invalid dependencies')
        require(len(set(deps)) == len(deps), 'Repeated dependency')
        graph[key] = deps
        require(isinstance(topic['spans'], list) and bool(topic['spans']), 'Topic needs source spans')
        for item in topic['spans']:
            span(item)
        require(any(item['kind'] == 'request' for item in topic['spans']), 'Topic needs a real request')
    for item in value['ignored']:
        span(item, ignored=True)
    require(all(coverage[i] for i, char in enumerate(text) if not char.isspace()),
            'Plan does not cover complete message')
    require(all(requests[i] for i, char in enumerate(text) if authorized[i] and not char.isspace()),
            'Authorized request was discarded')
    acyclic(graph)
