"""Ponte do Harvey com o Frank Investigator local (mesmo cliente e credencial da skill frank-investigator)."""
import json
import subprocess
import urllib.parse
from pathlib import Path


def _url_publica(url):
    parsed = urllib.parse.urlsplit(str(url or ''))
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('url_invalida')
    return url


class Frank:
    def __init__(self, base, runner=subprocess.run):
        self.script = Path(base) / 'skills' / 'frank-investigator' / 'scripts' / 'frank.py'
        self.runner = runner

    def _run(self, args):
        if not self.script.is_file():
            return {'status': 'error', 'error': 'frank_nao_instalado'}
        proc = self.runner(['python3', str(self.script), *args], capture_output=True, text=True, timeout=90)
        try:
            data = json.loads(proc.stdout or '{}')
        except ValueError:
            data = {'saida': (proc.stdout or '')[-1500:]}
        state = {0: 'ok', 2: 'pending', 3: 'failed'}.get(proc.returncode, 'error')
        return {'status': state, 'codigo_saida': proc.returncode, 'frank': data}

    def verificar(self, url, evidencias=None, noticias=None):
        args = ['submit', _url_publica(url)]
        for item in (evidencias or [])[:8]:
            args += ['--evidence-url', _url_publica(item)]
        for item in (noticias or [])[:8]:
            args += ['--news-url', _url_publica(item)]
        result = self._run(args)
        result['orientacao'] = ('Guarde o slug e consulte frank_relatorio; só considere pronto com ready=true. '
                                'Score do Frank não é probabilidade de verdade; cite o que ele de fato retornou.')
        return result

    def relatorio(self, slug):
        if not str(slug or '').replace('-', '').replace('_', '').isalnum() or len(str(slug)) > 120:
            raise ValueError('slug_invalido')
        return self._run(['report', str(slug)])
