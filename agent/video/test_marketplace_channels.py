import unittest
from marketplace_channels import classify, annotate_pool, require_channel


class ChannelsTests(unittest.TestCase):
    def test_owner_url_preserved_byte_for_byte(self):
        url = 'https://meli.la/AbCd?matt_tool=owner&x=1'
        original = {'source':'owner','links':[{'url':url,'label':'Item','priority':20}]}
        out = annotate_pool(original)
        self.assertEqual(out['links'][0]['url'], url)
        self.assertNotIn('commerce', original['links'][0])
        self.assertEqual(out['links'][0]['commerce']['program'],'mercado_livre')
        self.assertFalse(out['links'][0]['commerce']['shop_eligible'])
        self.assertFalse(out['links'][0]['commerce']['commission_verified'])

    def test_unknown_or_spoofed_domain_never_promoted(self):
        for url in ['https://meli.la.evil.test/a','https://tiktok.com.evil.test/a',
                    'http://meli.la/a','https://user:pass@meli.la/a','https://meli.la:123/a',
                    'javascript:alert(1)','https://example.com/tiktok.com']:
            self.assertEqual(classify(url)['program'],'unverified')

    def test_reannotation_does_not_duplicate_or_change_business_fields(self):
        value={'links':[{'url':'https://meli.la/1','label':'A'},
                        {'url':'https://meli.la/1','label':'B'}]}
        out=annotate_pool(value)
        self.assertEqual(len(out['links']),2)
        self.assertEqual(out,annotate_pool(out))

    def test_ml_cannot_be_shop_product(self):
        p={'affiliate_url':'https://meli.la/1','publication_channel':'tiktok_shop',
           'shop_product_id':'123','identity_verified':True,'shop_eligible':True}
        with self.assertRaises(ValueError):require_channel(p)

    def test_unresolved_tiktok_short_link_not_shop_evidence(self):
        with self.assertRaises(ValueError):
            require_channel({'affiliate_url':'https://vt.tiktok.com/abc',
                             'publication_channel':'tiktok_shop','shop_product_id':'123'})

    def test_shop_requires_native_identity_not_just_booleans(self):
        p={'affiliate_url':'https://www.tiktok.com/view/product/123456',
           'publication_channel':'tiktok_shop','shop_product_id':'123456',
           'identity_verified':True,'shop_eligible':True}
        with self.assertRaises(ValueError):require_channel(p)

    def test_existing_ml_external_research_remains_available(self):
        self.assertEqual(require_channel({'url':'https://meli.la/1'}),'external_affiliate')


if __name__=='__main__':unittest.main()
