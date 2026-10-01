"""Scoped migration of the existing external-affiliate catalog and executor."""
import ast


def transform(source):
    pairs = [
        ('def catalog(reg):', 'from marketplace_channels import annotate_pool, require_channel\n\ndef catalog(reg):'),
        ("pool=json.loads(POOL.read_text()).get('links',[]);available=[];excluded=[]",
         "pool=annotate_pool(json.loads(POOL.read_text())).get('links',[]);available=[];excluded=[]"),
        ("    validate_brief(brief);owned_link(brief['product']);validate_trends(brief.get('trend_evidence',{}))",
         "    require_channel(brief['product'])\n    validate_brief(brief);owned_link(brief['product']);validate_trends(brief.get('trend_evidence',{}))"),
    ]
    for old, new in pairs:
        if new in source:
            continue
        if source.count(old) != 1:
            raise ValueError('Unknown affiliate runtime anchor')
        source = source.replace(old, new, 1)
    ast.parse(source)
    return source


def transform_guard(source):
    pairs = [
        ('from affiliate_quality import require_preflight',
         'from affiliate_quality import require_preflight\nfrom marketplace_channels import require_channel'),
        ("    brief=json.loads(brief_path.read_text());validate_brief(brief)",
         "    brief=json.loads(brief_path.read_text());validate_brief(brief)\n    require_channel(brief['product'])"),
    ]
    for old, new in pairs:
        if new in source:
            continue
        if source.count(old) != 1:
            raise ValueError('Unknown affiliate guard anchor')
        source = source.replace(old, new, 1)
    ast.parse(source)
    return source
