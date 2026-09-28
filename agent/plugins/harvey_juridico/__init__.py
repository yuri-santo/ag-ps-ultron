"""Ferramentas exclusivas do Harvey (perfil jurídico).

Fontes: Vade Mecum do Senado (local, exclusivo deste perfil), LexML, DataJud/CNJ, DJEN,
jurisprudência oficial (STF/STJ/TST/TJs) e o Frank para verificar alegações decisivas.
Tudo somente leitura. Não é registrado em nenhum outro perfil.
"""
import json
from pathlib import Path

from . import jurisprudencia, oficiais, planalto, prazos
from .frank_client import Frank
from .vademecum import VadeMecum

TOOLSET = 'harvey_juridico'
PERFIL = 'harvey'
PROMPT = """Harvey — fontes e método (obrigatório):
1. Lei: vademecum_consultar primeiro (compilado até jan/2026, com página). Confirme a redação vigente com planalto_artigo (notas "Redação dada pela Lei..., de...") e diga a data da consulta; norma fora do Vade Mecum: web_search site:planalto.gov.br ou lexml_buscar.
2. Jurisprudência: só fontes oficiais (STF, STJ, TST, TJs, CNJ). Use jurisprudencia_links e web_search/web_extract nos domínios oficiais; tj_jurisprudencia para TJs. Cite número, órgão, relator, data de julgamento e de publicação. Jusbrasil entra só como link para o Yuri conferir; não raspe nem leia por automação (termos de uso proíbem).
3. Datas: todo prazo passa por prazo_processual; processo por datajud_processo; intimações por djen_comunicacoes. Nunca estime prazo de cabeça; sinalize feriados locais não cobertos.
4. Frank: alegação decisiva (tese, precedente, mudança de lei) vai para frank_verificar com a URL oficial; use o retorno real e diga se ficou pendente.
5. Separe fato, norma, precedente e opinião; grau de risco; o que não verificou."""


def _tool(register, name, description, properties, required, operation):
    schema = {'name': name, 'description': description,
              'parameters': {'type': 'object', 'properties': properties, 'required': required}}

    def handler(args, **kwargs):
        try:
            # Modelos às vezes mandam campos extras (ex.: 'reason'); só os do schema chegam à função.
            clean = {k: v for k, v in (args or {}).items() if k in properties}
            return json.dumps(operation(**clean), ensure_ascii=False)
        except (ValueError, oficiais.FonteErro, FileNotFoundError) as exc:
            return json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({'status': 'error', 'error': type(exc).__name__}, ensure_ascii=False)
    register(name=name, toolset=TOOLSET, schema=schema, handler=handler, description=description)


def register_legal_tools(register, home, base, settings=None):
    """Usado pelo worker do ultron_team e pelo plugin do perfil. Retorna o nome do toolset."""
    settings = settings or {}
    home, base = Path(home), Path(base)
    db = Path(settings.get('vademecum_db') or home / 'juridico' / 'vademecum.sqlite')
    frank = Frank(base)
    S = {'type': 'string'}
    data = {'type': 'string', 'description': 'AAAA-MM-DD'}

    def vade(consulta='', norma='', artigo='', limite=5):
        return VadeMecum(db).consultar(consulta, norma, artigo, limite)

    _tool(register, 'vademecum_consultar',
          'Consulta o Vade Mecum do Senado Federal (3ª ed., atualizado até jan/2026): artigo exato (norma + artigo) ou busca por termos. '
          'Normas: CF, ADCT, LINDB, CC, CPC, CP, LCP, CPP, CTN, CDC, Código Eleitoral, Código Florestal, CLT, ECA, Estatutos, Lei de Drogas, LDB, '
          'Lei 14.133, LRF, LC 150, Lei 8.112, Maria da Penha. Retorna texto e citação com página.',
          {'consulta': {**S, 'description': 'termos da busca'}, 'norma': {**S, 'description': 'sigla ou nome, ex.: CC, CPC, CLT'},
           'artigo': {**S, 'description': 'ex.: 50, 5º, 1.036, 4-A'}, 'limite': {'type': 'integer', 'minimum': 1, 'maximum': 15}},
          [], vade)
    _tool(register, 'lexml_buscar',
          'Busca normas no LexML (índice oficial de legislação). O LexML costuma ficar fora do ar; se falhar, use planalto_artigo ou web_search site:planalto.gov.br.',
          {'consulta': S, 'tipo': {**S, 'description': 'ex.: Lei, Decreto, Lei Complementar'}, 'ano': {**S, 'description': 'AAAA'},
           'limite': {'type': 'integer', 'minimum': 1, 'maximum': 30}}, ['consulta'], oficiais.lexml_buscar)
    _tool(register, 'planalto_artigo',
          'Texto VIGENTE de um artigo no Planalto (legislação compilada, sem o texto riscado), com as notas "Redação dada pela Lei ..., de ...". '
          'Use para conferir se o artigo mudou depois de jan/2026. Atalhos de norma: ' + ', '.join(sorted(planalto.ATALHOS)) + '; ou passe url do planalto.gov.br.',
          {'artigo': S, 'norma': S, 'url': S}, ['artigo'], planalto.planalto_artigo)
    _tool(register, 'datajud_processo',
          'Consulta um processo pelo número CNJ na API pública do DataJud (CNJ): classe, assuntos, órgão, datas e movimentos recentes. Não cobre STF.',
          {'numero': {**S, 'description': 'NNNNNNN-DD.AAAA.J.TR.OOOO'}},
          ['numero'], lambda numero: oficiais.datajud_processo(numero, settings.get('datajud_api_key', '')))
    _tool(register, 'djen_comunicacoes',
          'Intimações/comunicações oficiais do DJEN (Comunica PJe/CNJ) por número de processo ou OAB+UF, com filtro de datas.',
          {'numero_processo': S, 'oab': S, 'uf': S, 'data_inicio': data, 'data_fim': data,
           'pagina': {'type': 'integer', 'minimum': 1, 'maximum': 50}}, [], oficiais.djen_comunicacoes)
    _tool(register, 'prazo_processual',
          'Calcula vencimento de prazo (CPC arts. 219, 220 e 224; ou contagem corrida), com feriados nacionais, carnaval/Corpus Christi forenses e recesso de 20/12 a 20/01.',
          {'data_inicial': {**data, 'description': 'data da intimação/publicação (ou da disponibilização no DJEN)'},
           'dias': {'type': 'integer', 'minimum': 1, 'maximum': 3650},
           'contagem': {'type': 'string', 'enum': ['uteis', 'corridos']},
           'disponibilizacao_djen': {'type': 'boolean', 'description': 'true se a data é de disponibilização no DJEN/DJe'},
           'feriados_extras': {'type': 'array', 'items': data, 'description': 'feriados locais/suspensões do tribunal'},
           'considerar_recesso': {'type': 'boolean'}},
          ['data_inicial', 'dias'], prazos.calcular_prazo)
    _tool(register, 'jurisprudencia_links',
          'Gera links de pesquisa oficial (STF, STJ, TST, CNJ) e o link do Jusbrasil para conferência humana sobre um tema.',
          {'tema': S}, ['tema'], jurisprudencia.links_oficiais)
    _tool(register, 'tj_jurisprudencia',
          'Pesquisa jurisprudência de 2º grau nos TJs (tjsp, tjrs, tjpr, tjsc, tjdft, tjba, tjce, tjes, tjmt, tjpa, tjpb, tjpe, tjpi, tjrn, tjro, tjrr, tjto) pela página oficial do tribunal.',
          {'tribunal': S, 'termo': S, 'pagina': {'type': 'integer', 'minimum': 1, 'maximum': 5}},
          ['tribunal', 'termo'], lambda tribunal, termo, pagina=1: jurisprudencia.tj_jurisprudencia(
              tribunal, termo, pagina, python=settings.get('juscraper_python', '/root/tools/juridico-venv/bin/python')))
    _tool(register, 'frank_verificar',
          'Envia ao Frank Investigator a URL oficial de uma alegação decisiva (lei, acórdão, tema) com evidências, para checagem independente. Retorna slug.',
          {'url': S, 'evidencias': {'type': 'array', 'items': S}, 'noticias': {'type': 'array', 'items': S}},
          ['url'], frank.verificar)
    _tool(register, 'frank_relatorio', 'Lê o relatório do Frank pelo slug (pronto só com ready=true).',
          {'slug': S}, ['slug'], frank.relatorio)
    return TOOLSET


def register(ctx):
    """Plugin do perfil: só registra quando o HERMES_HOME é o do Harvey."""
    from hermes_constants import get_hermes_home
    home = Path(get_hermes_home()).resolve()
    if home.name != PERFIL or home.parent.name != 'profiles':
        return
    base = home.parent.parent
    settings = {k: ctx.get_config(k, None) for k in ('vademecum_db', 'datajud_api_key', 'juscraper_python')}
    register_legal_tools(ctx.register_tool, home, base, {k: v for k, v in settings.items() if v})
    ctx.register_system_prompt_section('harvey_juridico', PROMPT, max_chars=2000)
