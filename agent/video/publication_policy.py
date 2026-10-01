"""Reject unsupported new delivery text without changing approved text or URLs."""
import re
import unicodedata


EMOJI = re.compile(
    '[\U0001f000-\U0001faff\u2600-\u27bf\u2300-\u23ff'
    '\u200d\u20e3\ufe0e\ufe0f\U000e0020-\U000e007f'
    '\u2194-\u2199\u21a9-\u21aa\u2934-\u2935\u2b05-\u2b07'
    '\u2b1b-\u2b1c\u2b50\u2b55\u3030\u303d\u3297\u3299]')
# These promises have no validated SKU/source/reviewer evidence contract yet.
UNSUPPORTED_PROMISE = re.compile(
    r'\b(?:frete\s+gratis|entrega\s+gratuita|'
    r'laudo(?:\s+laboratorial)?\s+aprovado|desconto\s+exclusivo|'
    r'rende\s+\d+(?:[.,]\d+)?\s+doses|comentario\s+fixado|'
    r'resultados?\s+garantidos?)\b')


def require_plain_text(text, label):
    if not isinstance(text, str):
        raise ValueError(label + ' must be text')
    if EMOJI.search(text):
        raise ValueError(label + ' contains an emoji; revise the source and obtain a new review')
    return text


def require_publication_text(text, label):
    require_plain_text(text, label)
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                         if not unicodedata.combining(c))
    if UNSUPPORTED_PROMISE.search(normalized):
        raise ValueError(label + ' contains a promise without validated evidence; '
                         'revise the claim and obtain a new review. Generic facts or '
                         'approval flags cannot verify an offer, attestation or pinned comment')
    return text


def require_brief_text(brief):
    require_publication_text(brief.get('caption', ''), 'caption')
    require_publication_text(brief.get('comment_text', ''), 'comment_text')
    for index, scene in enumerate(brief.get('scenes', []), 1):
        require_publication_text(scene.get('narration', ''), f'scene {index} narration')
