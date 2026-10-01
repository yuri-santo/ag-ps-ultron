"""Separate affiliate programs; classification is not product or commission proof."""
from copy import deepcopy
from urllib.parse import urlsplit


def classify(url):
    program = 'unverified'
    try:
        p = urlsplit(url)
        valid = (p.scheme == 'https' and p.hostname and p.port in (None, 443)
                 and not p.username and not p.password and not any(c.isspace() for c in url))
        host = p.hostname or ''
        if valid:
            if host == 'meli.la' or host == 'mercadolivre.com.br' or host.endswith('.mercadolivre.com.br'):
                program = 'mercado_livre'
            elif host in ('tiktok.com', 'www.tiktok.com', 'vt.tiktok.com', 'vm.tiktok.com', 'shop.tiktok.com'):
                program = 'tiktok_unresolved'
    except (ValueError, TypeError, AttributeError):
        pass
    return {'program': program, 'shop_eligible': False,
            'commission_verified': False, 'identity_status': 'research_required',
            'channel': 'external_affiliate' if program == 'mercado_livre' else 'unverified'}


def annotate_pool(pool):
    if not isinstance(pool, dict) or not isinstance(pool.get('links'), list):
        raise ValueError('Expected existing owner link pool schema')
    result = deepcopy(pool)
    for item in result['links']:
        if not isinstance(item, dict) or not isinstance(item.get('url'), str):
            raise ValueError('Malformed pool item')
        item['commerce'] = classify(item['url'])
    return result


def require_channel(product):
    channel = product.get('publication_channel', 'external_affiliate')
    url = product.get('affiliate_url') or product.get('url')
    info = classify(url)
    if channel == 'tiktok_shop' or product.get('shop_product_id'):
        if info['program'] == 'mercado_livre':
            raise ValueError('Mercado Livre affiliate links cannot become TikTok Shop showcase items')
        # No Shop mutator has been implemented or verified in the existing external-link executor.
        raise ValueError('Native Shop executor and verified creator eligibility required; use separate flow')
    if channel != 'external_affiliate' or info['program'] != 'mercado_livre':
        raise ValueError('Unknown program/channel; verify it before using this executor')
    return channel
