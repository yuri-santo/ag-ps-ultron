import copy
import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).with_name('publication_policy.py')


class PublicationPolicyTests(unittest.TestCase):
    def policy(self):
        self.assertTrue(MODULE.exists(), 'publication policy is not implemented')
        spec = importlib.util.spec_from_file_location('policy_under_test', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_symbols_in_caption_comment_narration_and_subtitles_are_rejected(self):
        for symbol in ('\U0001f4aa', '\U0001f525', '\U0001f449', '\u2764',
                       '\U0001f1e7\U0001f1f7', '1\ufe0f\u20e3', '\u2600',
                       '\U0001f468\u200d\U0001f4bb', '\u00a9\ufe0f'):
            for field in ('caption', 'comment', 'narration', 'subtitles'):
                with self.subTest(symbol=ascii(symbol), field=field):
                    with self.assertRaisesRegex(ValueError, 'emoji'):
                        self.policy().require_plain_text('Texto ' + symbol, field)

    def test_plain_portuguese_urls_units_and_punctuation_are_preserved(self):
        text = 'Publicidade. A\u00e7\u00e3o em 30\u00b0C; 1 kg, R$ 25,00. https://meli.la/AbC?x=Y#z'
        self.assertEqual(self.policy().require_plain_text(text, 'caption'), text)

    def test_unverified_promises_are_rejected_without_sanitizing(self):
        for promise in ('frete gr\u00e1tis', 'FRETE GRATIS', 'entrega gratuita',
                        'laudo aprovado', 'laudo laboratorial aprovado',
                        'desconto exclusivo', 'rende 200 doses',
                        'primeiro coment\u00e1rio fixado', 'resultado garantido'):
            with self.subTest(promise=promise):
                with self.assertRaisesRegex(ValueError, 'evidence'):
                    self.policy().require_publication_text(promise, 'caption')

    def test_brief_checks_all_new_delivery_text_without_mutation(self):
        brief = {'caption': 'Publicidade. Imagens geradas por IA.',
                 'comment_text': 'Link de afiliado: https://meli.la/ExactOriginal',
                 'scenes': [{'narration': 'Confira as condi\u00e7\u00f5es no an\u00fancio.'}]}
        before = copy.deepcopy(brief)
        self.policy().require_brief_text(brief)
        self.assertEqual(brief, before)
        for target, key in ((brief, 'caption'), (brief, 'comment_text'),
                            (brief['scenes'][0], 'narration')):
            original = target[key]
            target[key] = original + ' \U0001f4aa'
            with self.assertRaisesRegex(ValueError, 'emoji'):
                self.policy().require_brief_text(brief)
            target[key] = original

    def test_declarative_facts_do_not_override_unsupported_promises(self):
        brief = {'caption': 'Laudo aprovado', 'comment_text': 'Afiliado.',
                 'scenes': [], 'facts': {'verified': True, 'verified_features': ['Laudo aprovado']}}
        with self.assertRaisesRegex(ValueError, 'evidence'):
            self.policy().require_brief_text(brief)


if __name__ == '__main__':
    unittest.main()
