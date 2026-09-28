"""Clientes somente-leitura de fontes oficiais: LexML (SRU), DataJud (CNJ) e DJEN/Comunica PJe.

Endereços fixos (sem URL vinda do modelo), tempo limite, tamanho máximo de resposta e nenhum
envio de dado pessoal além do número de processo/OAB pedido na consulta.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = 'Harvey-Ultron/1.0 (pesquisa juridica pessoal; fontes oficiais)'
MAX_BYTES = 6 * 1024 * 1024
# Chave pública divulgada pelo CNJ (muda sem aviso; pode ser sobrescrita nas configurações).
DATAJUD_KEY_PUBLICA = 'cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=='
UF_POR_TR = {1: 'ac', 2: 'al', 3: 'ap', 4: 'am', 5: 'ba', 6: 'ce', 7: 'dft', 8: 'es', 9: 'go', 10: 'ma', 11: 'mt',
             12: 'ms', 13: 'mg', 14: 'pa', 15: 'pb', 16: 'pr', 17: 'pe', 18: 'pi', 19: 'rj', 20: 'rn', 21: 'rs',
             22: 'ro', 23: 'rr', 24: 'sc', 25: 'se', 26: 'sp', 27: 'to'}


class FonteErro(RuntimeError):
    pass


def _http(url, *, data=None, headers=None, timeout=40, opener=None):
    request = urllib.request.Request(url, data=data, headers={'User-Agent': UA, **(headers or {})},
                                     method='POST' if data is not None else 'GET')
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise FonteErro(f'http_{exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FonteErro('fonte_indisponivel:' + type(getattr(exc, 'reason', exc)).__name__) from None
    if len(body) > MAX_BYTES:
        raise FonteErro('resposta_grande_demais')
    return body


# ---------------- LexML ----------------
def _cql_termo(texto):
    limpo = re.sub(r'[^\w\s.\-/º°]', ' ', str(texto or ''), flags=re.U)
    limpo = re.sub(r'\s+', ' ', limpo).strip()[:200]
    if not limpo:
        raise ValueError('consulta_vazia')
    return limpo.replace('"', '')


def lexml_query(consulta, tipo='', ano=''):
    termo = _cql_termo(consulta)
    partes = [f'(dc.title any "{termo}" or dc.description any "{termo}")']
    if tipo:
        partes.append(f'tipoDocumento any "{_cql_termo(tipo)}"')
    if ano:
        if not re.fullmatch(r'\d{4}', str(ano)):
            raise ValueError('ano_invalido')
        partes.append(f'date any "{ano}"')
    return ' and '.join(partes)


def parse_lexml(xml_bytes, limite=10):
    text = xml_bytes.decode('utf-8', errors='replace')
    if '<html' in text[:500].lower():
        raise FonteErro('lexml_bloqueou_consulta_automatica')
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        raise FonteErro('lexml_resposta_invalida (use planalto_artigo)') from None
    total = None
    resultados = []
    for el in root.iter():
        tag = el.tag.rsplit('}', 1)[-1]
        if tag == 'numberOfRecords' and el.text:
            total = int(el.text)
        if tag == 'recordData':
            item = {}
            for field in el.iter():
                name = field.tag.rsplit('}', 1)[-1]
                if field.text and field.text.strip() and name in ('title', 'date', 'description', 'type', 'urn', 'identifier', 'subject', 'publisher'):
                    item.setdefault(name, field.text.strip()[:600])
            urn = item.get('urn') or (item.get('identifier') if str(item.get('identifier', '')).startswith('urn:') else '')
            if urn:
                item['url'] = 'https://www.lexml.gov.br/urn/' + urn
            resultados.append(item)
            if len(resultados) >= limite:
                break
    return {'total': total, 'resultados': resultados}


def lexml_buscar(consulta, tipo='', ano='', limite=10, opener=None):
    limite = max(1, min(int(limite or 10), 30))
    params = urllib.parse.urlencode({'operation': 'searchRetrieve', 'version': '1.1',
                                     'query': lexml_query(consulta, tipo, ano), 'startRecord': 1,
                                     'maximumRecords': limite, 'recordSchema': 'dc'})
    body = _http('https://www.lexml.gov.br/busca/SRU?' + params, timeout=25, opener=opener)
    data = parse_lexml(body, limite)
    data.update(status='ok', fonte='LexML Brasil (SRU oficial)',
                observacao='Confirme o texto e a data de vigência no link oficial; LexML indexa normas e proposições.')
    return data


# ---------------- DataJud ----------------
def normalizar_cnj(numero):
    digits = re.sub(r'\D', '', str(numero or ''))
    if len(digits) != 20:
        raise ValueError('numero_cnj_invalido')
    n, dd, ano, j, tr, orig = digits[:7], digits[7:9], digits[9:13], digits[13], digits[14:16], digits[16:]
    # Dígito verificador ISO 7064 mod 97-10 (Resolução CNJ 65/2008).
    esperado = 98 - (int(n + ano + j + tr + orig + '00') % 97)
    return {'digits': digits, 'formatado': f'{n}-{dd}.{ano}.{j}.{tr}.{orig}', 'segmento': int(j), 'tribunal': int(tr),
            'ano': int(ano), 'dv_ok': int(dd) == esperado}


def alias_tribunal(info):
    j, tr = info['segmento'], info['tribunal']
    if j == 8 and tr in UF_POR_TR:
        return 'tjdft' if tr == 7 else 'tj' + UF_POR_TR[tr]
    if j == 4 and 1 <= tr <= 6:
        return f'trf{tr}'
    if j == 5:
        return 'tst' if tr == 0 else f'trt{tr}'
    if j == 6:
        return 'tse' if tr == 0 else ('tre-dft' if tr == 7 else 'tre-' + UF_POR_TR.get(tr, ''))
    if j == 3:
        return 'stj'
    if j == 7:
        return 'stm'
    if j == 9 and tr in (13, 21, 26):
        return {13: 'tjmmg', 21: 'tjmrs', 26: 'tjmsp'}[tr]
    if j == 1:
        raise ValueError('stf_nao_esta_no_datajud')
    raise ValueError('tribunal_nao_mapeado')


def datajud_processo(numero, chave='', opener=None):
    info = normalizar_cnj(numero)
    if not info['dv_ok']:
        return {'status': 'error', 'error': 'digito_verificador_invalido', 'numero': info['formatado']}
    alias = alias_tribunal(info)
    body = json.dumps({'query': {'match': {'numeroProcesso': info['digits']}}, 'size': 3}).encode()
    raw = _http(f'https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search', data=body, timeout=60,
                headers={'Authorization': 'APIKey ' + (chave or DATAJUD_KEY_PUBLICA), 'Content-Type': 'application/json'},
                opener=opener)
    data = json.loads(raw)
    hits = (data.get('hits') or {}).get('hits') or []
    processos = []
    for hit in hits:
        s = hit.get('_source') or {}
        movimentos = sorted(s.get('movimentos') or [], key=lambda m: m.get('dataHora') or '', reverse=True)
        processos.append({
            'numero': info['formatado'], 'tribunal': s.get('tribunal'), 'grau': s.get('grau'),
            'classe': (s.get('classe') or {}).get('nome'), 'assuntos': [a.get('nome') for a in s.get('assuntos') or [] if isinstance(a, dict)][:10],
            'orgao_julgador': (s.get('orgaoJulgador') or {}).get('nome'), 'data_ajuizamento': s.get('dataAjuizamento'),
            'ultima_atualizacao': s.get('dataHoraUltimaAtualizacao'), 'sistema': (s.get('sistema') or {}).get('nome'),
            'movimentos_recentes': [{'data': m.get('dataHora'), 'movimento': m.get('nome'),
                                     'complemento': '; '.join(str(c.get('nome') or c.get('descricao') or '') for c in m.get('complementosTabelados') or [])[:300]}
                                    for m in movimentos[:25]]})
    return {'status': 'ok', 'fonte': f'DataJud/CNJ (api_publica_{alias})', 'encontrados': len(processos), 'processos': processos,
            'observacao': 'Metadados e movimentos oficiais; não traz o inteiro teor. Datas em UTC/ISO conforme o CNJ.'}


# ---------------- DJEN / Comunica PJe ----------------
def djen_comunicacoes(numero_processo='', oab='', uf='', data_inicio='', data_fim='', pagina=1, opener=None):
    params = {'pagina': max(1, min(int(pagina or 1), 50)), 'itensPorPagina': 50}
    if numero_processo:
        params['numeroProcesso'] = normalizar_cnj(numero_processo)['digits']
    if oab:
        if not re.fullmatch(r'\d{1,7}', re.sub(r'\D', '', str(oab))) or not re.fullmatch(r'[A-Za-z]{2}', str(uf or '')):
            raise ValueError('oab_ou_uf_invalida')
        params.update(numeroOab=re.sub(r'\D', '', str(oab)), ufOab=str(uf).upper())
    if not numero_processo and not oab:
        raise ValueError('informe_processo_ou_oab')
    for chave, valor in (('dataDisponibilizacaoInicio', data_inicio), ('dataDisponibilizacaoFim', data_fim)):
        if valor:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(valor)):
                raise ValueError('data_invalida')
            params[chave] = valor
    raw = _http('https://comunicaapi.pje.jus.br/api/v1/comunicacao?' + urllib.parse.urlencode(params), timeout=40, opener=opener)
    data = json.loads(raw)
    items = data.get('items') or data.get('content') or []
    def curto(v):
        return v[:3000] + ' …[truncado]' if isinstance(v, str) and len(v) > 3000 else v
    comunicacoes = [{k: curto(v) for k, v in item.items() if not isinstance(v, (dict, list)) or k in ('destinatarios', 'destinatarioadvogados')}
                    for item in items if isinstance(item, dict)]
    return {'status': 'ok', 'fonte': 'DJEN — Comunica PJe (CNJ)', 'total': data.get('count', len(comunicacoes)),
            'pagina': params['pagina'], 'comunicacoes': comunicacoes,
            'observacao': 'Data de disponibilização ≠ data de publicação: publica-se no 1º dia útil seguinte (CPC, art. 224, §§ 2º e 3º). Use prazo_processual.'}
