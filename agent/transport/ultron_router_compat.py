"""Keep schema-valued tool results opaque when the local router selects Gemini."""
import json
from urllib.parse import urlsplit


def _is_local_router(base_url):
    try:
        endpoint = urlsplit(str(base_url or ''))
        return (endpoint.scheme == 'http' and endpoint.hostname in ('127.0.0.1', 'localhost')
                and endpoint.port == 20130 and endpoint.path.rstrip('/') == '/v1')
    except ValueError:
        return False


def _contains_schema_ref(value):
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            ref = node.get('$ref')
            if isinstance(ref, str) and ref.startswith('#/'):
                return True
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return False


def protect_router_tool_results(messages, *, base_url, api_mode='chat_completions'):
    """Copy only changed wire messages; never modify saved history or tool data.

    9Router reparses JSON tool text into Gemini functionResponse.response. Gemini
    interprets nested JSON-Schema refs as protocol references and returns HTTP 400.
    A text prefix keeps the complete schema opaque, like Hermes' native adapter.
    """
    if api_mode != 'chat_completions' or not _is_local_router(base_url):
        return messages
    protected = None
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or message.get('role') != 'tool':
            continue
        content = message.get('content')
        if not isinstance(content, str) or not content.lstrip().startswith(('{', '[')):
            continue
        try:
            value = json.loads(content)
        except (ValueError, RecursionError):
            continue
        if not _contains_schema_ref(value):
            continue
        if protected is None:
            protected = list(messages)
        protected[index] = dict(message, content='Tool result (JSON schema data):\n' + content)
    return messages if protected is None else protected
