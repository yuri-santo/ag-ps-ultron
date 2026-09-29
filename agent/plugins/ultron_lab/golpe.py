"""Análise determinística de golpes em e-mails e mensagens (PT-BR).

Port adaptado das camadas determinísticas do Frank FBI (akitaonrails/frank_fbi):
autenticação de cabeçalhos (camada 1), conteúdo/links/anexos (camada 3) e
política de escalonamento de risco, acrescidos de padrões de golpes brasileiros
(Pix, boleto, Receita/gov.br, "novo número", falsa central, tarefas pagas).

Nada aqui abre links, baixa anexos ou chama rede. O texto analisado é dado
externo: nunca é tratado como instrução.
"""
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
import ipaddress
import re
import unicodedata
from urllib.parse import urlparse

MAX_INPUT = 2 * 1024 * 1024

WEIGHTS = {'autenticacao': 0.15, 'conteudo': 0.15, 'padroes': 0.20}

VEREDITOS = (
    (25, 'legitimo', 'Legítimo'),
    (50, 'suspeito_provavel_ok', 'Suspeito (provavelmente ok)'),
    (75, 'suspeito_provavel_golpe', 'Suspeito (provável golpe)'),
    (100, 'golpe', 'Golpe'),
)

URL_SHORTENERS = {
    'bit.ly', 'tinyurl.com', 'goo.gl', 'ow.ly', 't.co', 'is.gd', 'buff.ly', 'adf.ly', 'rb.gy',
    'short.link', 'cutt.ly', 'tiny.cc', 's.id', 'rebrand.ly', 'bl.ink', 'encurtador.com.br',
    'abre.ai', 'migre.me', 'l1nk.dev', 'shorturl.at', 'u.to', 'x.gd', 'v.gd', 'qrco.de',
}

SUSPICIOUS_TLDS = {
    'xyz', 'top', 'click', 'zip', 'mov', 'icu', 'cfd', 'sbs', 'buzz', 'rest', 'monster', 'quest',
    'cyou', 'shop', 'online', 'site', 'live', 'lol', 'work', 'gq', 'tk', 'ml', 'cf', 'ga',
}

DANGEROUS_EXTENSIONS = (
    '.exe', '.scr', '.bat', '.cmd', '.com', '.pif', '.vbs', '.vbe', '.js', '.jse', '.wsf', '.msi',
    '.dll', '.jar', '.ps1', '.reg', '.inf', '.hta', '.cpl', '.lnk', '.url', '.appx', '.msix',
)

SUSPICIOUS_ATTACHMENT_RULES = (
    ('arquivo_compactado', ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.cab'), 12,
     'Arquivo compactado pode ocultar executáveis, scripts ou documentos perigosos'),
    ('imagem_de_disco', ('.iso', '.img', '.vhd', '.vhdx'), 18,
     'Imagem de disco pode carregar instaladores e atalhos maliciosos'),
    ('documento_com_macro', ('.docm', '.xlsm', '.pptm', '.xlam', '.dotm'), 18,
     'Documento com macro pode executar código ao ser aberto'),
    ('onenote', ('.one',), 18, 'Arquivo do OneNote é vetor comum de malware e phishing'),
    ('pacote_mobile', ('.apk', '.xapk'), 18, 'Pacote de aplicativo instala software fora das lojas oficiais'),
    ('documento_web', ('.html', '.htm', '.svg', '.shtml'), 10,
     'Arquivo web anexado pode abrir página falsa de login localmente'),
)

SUSPICIOUS_MAILERS = ('phpmailer', 'swiftmailer', 'sendblaster', 'massmail', 'bulkmail', 'atompark')

FREEMAIL = {'gmail.com', 'yahoo.com', 'yahoo.com.br', 'outlook.com', 'hotmail.com', 'live.com',
            'bol.com.br', 'uol.com.br', 'terra.com.br', 'ig.com.br', 'icloud.com', 'proton.me',
            'protonmail.com', 'gmx.com', 'aol.com', 'mail.com'}

# Marcas/órgãos imitados com frequência no Brasil -> domínios oficiais registráveis.
BRANDS = {
    'receita federal': ('gov.br',), 'gov.br': ('gov.br',), 'detran': ('gov.br',),
    'correios': ('correios.com.br',), 'inss': ('gov.br',), 'serasa': ('serasa.com.br',),
    'caixa economica': ('caixa.gov.br',), 'banco do brasil': ('bb.com.br',), 'itau': ('itau.com.br',),
    'bradesco': ('bradesco.com.br',), 'santander': ('santander.com.br',), 'nubank': ('nubank.com.br',),
    'mercado livre': ('mercadolivre.com.br', 'mercadolivre.com'),
    'mercado pago': ('mercadopago.com.br', 'mercadopago.com'), 'banco central': ('bcb.gov.br',),
    'microsoft': ('microsoft.com', 'office.com', 'outlook.com', 'live.com', 'microsoftonline.com'),
    'google': ('google.com', 'gmail.com', 'youtube.com', 'googleapis.com', 'gstatic.com'),
    'apple': ('apple.com', 'icloud.com'),
    'netflix': ('netflix.com',), 'amazon': ('amazon.com', 'amazon.com.br'), 'shopee': ('shopee.com.br',),
    'linkedin': ('linkedin.com',), 'whatsapp': ('whatsapp.com', 'wa.me'),
}

# (categoria, pontos por ocorrência, teto, regex aplicadas ao texto normalizado sem acento/minúsculo)
TEXT_PATTERNS = (
    ('urgencia', 8, 30, [
        r'\burgente\b', r'\bimediatamente\b', r'\bultimo aviso\b', r'\bultimas? horas\b',
        r'\bexpira(m|ra)? (hoje|amanha|em \d+)', r'\bprazo (final|encerra)', r'\bem ate \d+ ?(h|horas|minutos)\b',
        r'\b(sera|serao|foi|esta) (bloquead|suspens|cancelad|desativad|encerrad)',
        r'\bevite (o |a )?(bloqueio|cancelamento|suspensao|multa|protesto)', r'\bregularize\b',
        r'\bact now\b', r'\bexpires? today\b', r'\bwithin 24 hours\b', r'\baccount (will be )?suspended\b',
    ]),
    ('pagamento', 12, 30, [
        r'\bchave pix\b', r'\b(faz|faca|fazer|manda|mande|envia|envie) (um |o )?pix\b',
        r'\b(pagamento|pago|pagos|receba|recebe|saque|deposito) (imediato |diario |na hora )?(via |por |no |em )?pix\b',
        r'\bpix\b.{0,40}\b(taxa|valor|pagamento|agora)\b', r'\bqr ?code\b.{0,30}\b(pagar|pagamento|pix)\b',
        r'\bboleto\b', r'\blinha digitavel\b',
        r'\btaxa (de )?(liberacao|desbloqueio|alfandega|alfandegaria|importacao|entrega|adesao|saque|cadastro)\b',
        r'\b(valores|dinheiro|saldo) a receber\b', r'\brestituicao\b', r'\breembolso (pendente|disponivel)\b',
        r'\b(voce )?(ganhou|foi sorteado|premiad)', r'\bemprestimo (pre-?)?aprovado\b', r'\blucro garantido\b',
        r'\brenda extra\b', r'\bretorno garantido\b', r'\bdeposito (antecipado|inicial)\b',
        r'\bwire transfer\b', r'\bgift ?cards?\b', r'\bguaranteed returns?\b', r'\bunclaimed funds\b',
    ]),
    ('dados_pessoais', 15, 30, [
        r'\b(informe|envie|confirme|atualize|digite|valide) (o |a |seu |sua |os |seus |suas )?'
        r'(cpf|senha|dados|token|cartao|conta|codigo)',
        r'\bcodigo (de )?(verificacao|seguranca|confirmacao|sms)\b', r'\bcvv\b', r'\bnumero do cartao\b',
        r'\bdata de nascimento\b', r'\bselfie\b', r'\bfoto (do |de |da )?(documento|rg|cnh)\b', r'\bdados bancarios\b',
        r'\bsenha (do|da|de) (banco|app|aplicativo|cartao|conta)\b', r'\bverify your (identity|account)\b',
        r'\bsocial security\b', r'\bcredit card number\b',
    ]),
    ('autoridade', 6, 24, [
        r'\breceita federal\b', r'\bgov\.br\b', r'\bdetran\b', r'\bpolicia federal\b', r'\bministerio\b',
        r'\binss\b', r'\bbanco central\b', r'\bsefaz\b', r'\btribunal\b', r'\boficial de justica\b',
        r'\bintimacao\b', r'\bmandado\b', r'\bprocesso judicial\b', r'\bmulta\b', r'\bipva\b',
        r'\bcpf (irregular|suspenso|cancelado|pendente)\b', r'\bcentral de (seguranca|atendimento)\b',
        r'\binterpol\b', r'\bfbi\b',
    ]),
    ('phishing', 10, 30, [
        r'\bclique (aqui|no link|no botao|abaixo)\b', r'\bacesse (o link|agora|o site)\b',
        r'\bverifique sua conta\b', r'\batividade (suspeita|incomum)\b', r'\bacesso nao reconhecido\b',
        r'\blogin (incomum|suspeito)\b', r'\bcompra nao reconhecida\b',
        r'\b(encomenda|pacote|objeto) (esta )?(retid|taxad|pendente|aguardando)',
        r'\btarifa de importacao\b', r'\bcaixa de (entrada|e-?mail) (cheia|lotada)\b', r'\bsua senha expira\b',
        r'\bclick here to verify\b', r'\bunusual activity\b', r'\baccount has been compromised\b',
    ]),
    ('golpe_relacional', 15, 30, [
        r'\b(mudei|troquei) (de |o )?(numero|celular|telefone|chip)\b', r'\besse (e|eh) (o )?meu (novo )?numero\b',
        r'\bsalva (esse|este|meu) (novo )?numero\b', r'\bme empresta\b', r'\bpreciso de um favor\b',
        r'\bnao (posso|consigo) (falar|atender) agora\b', r'\bconsegue (me )?(fazer|mandar|transferir)\b',
        r'\bdepois (eu )?te (devolvo|pago)\b', r'\bestou sem (acesso|limite)\b',
    ]),
    ('tarefas_pagas', 12, 30, [
        r'\b(curtir|avaliar|assistir) (videos|produtos|posts|anuncios)\b', r'\btarefas? simples\b',
        r'\bganhe (ate )?(r\$ ?)?\d+.{0,20}(por dia|diari|por hora)', r'\btrabalho (em casa|remoto).{0,60}\bpix\b',
        r'\bcomissao (diaria|garantida)\b', r'\brecrutadora?\b.{0,80}\bwhatsapp\b',
    ]),
    ('injecao_ia', 15, 30, [
        r'\bignore (todas |as |todas as )?(instrucoes|ordens|regras)', r'\bignore (all |any )?(previous|prior) instructions\b',
        r'\b(diga|responda|classifique|informe) que (isto|isso|esta mensagem|este e-?mail) (e|eh) (legitim|segur|confiavel)',
        r'\bvoce (agora )?(e|eh) um (assistente|modelo)\b', r'\byou are now\b', r'\bsystem prompt\b',
    ]),
)

PATTERN_LABELS = {'urgencia': 'Urgência', 'pagamento': 'Pagamento/dinheiro', 'dados_pessoais': 'Pede dados pessoais',
                  'autoridade': 'Cita órgão/autoridade', 'phishing': 'Frases de phishing',
                  'golpe_relacional': 'Golpe do número novo/favor', 'tarefas_pagas': 'Tarefas pagas',
                  'injecao_ia': 'Tenta dar ordens a assistentes de IA'}

WHATSAPP_PATTERNS = (r'https?://wa\.me/', r'https?://wa\.link/', r'https?://chat\.whatsapp\.com/',
                     r'https?://api\.whatsapp\.com/')
BROKEN_TEMPLATE_PATTERNS = (r'%%unsubscribelink%%', r'%25%25unsubscribe', r'\{\{\s*unsubscribe\s*\}\}',
                            r'\{unsubscribe_url\}', r'%%email%%', r'\{\{\s*(nome|name|first_?name)\s*\}\}')
URL_RE = re.compile(r'(?i)\b(?:https?://|www\.)[^\s<>"\'\)\]]+')
EMAIL_HEADER_RE = re.compile(r'(?im)^(received|from|to|subject|date|message-id|mime-version|return-path|'
                             r'authentication-results|delivered-to|dkim-signature|reply-to|content-type):')


class GolpeError(ValueError):
    pass


def normalize(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', text.casefold())


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self._hidden, self._href, self._anchor = [], [], 0, None, []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._hidden += 1
        if tag == 'a':
            self._href = dict(attrs).get('href') or ''
            self._anchor = []
        if tag in ('p', 'br', 'div', 'li', 'tr') and not self._hidden:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._hidden = max(0, self._hidden - 1)
        if tag == 'a' and self._href is not None:
            self.links.append((self._href.strip(), ''.join(self._anchor).strip()))
            self._href = None

    def handle_data(self, data):
        if self._hidden:
            return
        self.parts.append(data)
        if self._href is not None:
            self._anchor.append(data)


def html_to_text(html):
    parser = _HTMLText()
    try:
        parser.feed(html or '')
        parser.close()
    except Exception:
        return re.sub(r'<[^>]+>', ' ', html or ''), []
    return ''.join(parser.parts), parser.links


def _decode(part):
    raw = part.get_payload(decode=True) or b''
    try:
        return raw.decode(part.get_content_charset() or 'utf-8', errors='replace')
    except LookupError:
        return raw.decode('utf-8', errors='replace')


def _address(value):
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', value or '')
    return match.group(0).casefold() if match else ''


def _display_name(value):
    value = (value or '').strip()
    if '<' in value:
        return value.split('<', 1)[0].strip().strip('"').strip()
    return ''


def looks_like_email(data):
    head = data[:4096]
    if isinstance(head, bytes):
        head = head.decode('utf-8', errors='replace')
    first = head.lstrip().split('\n', 1)[0]
    if not re.match(r'^[A-Za-z][A-Za-z0-9-]*:', first):
        return False
    return len({k.casefold() for k in EMAIL_HEADER_RE.findall(head)}) >= 2


def parse_input(data):
    """Normaliza um e-mail RFC822 ou uma mensagem de texto simples (WhatsApp, SMS, colada)."""
    if isinstance(data, str):
        raw_bytes = data.encode('utf-8', errors='replace')
    elif isinstance(data, (bytes, bytearray)):
        raw_bytes = bytes(data)
    else:
        raise GolpeError('entrada_invalida')
    if not raw_bytes.strip():
        raise GolpeError('entrada_vazia')
    if len(raw_bytes) > MAX_INPUT:
        raise GolpeError('entrada_grande_demais')
    if not looks_like_email(raw_bytes):
        text = raw_bytes.decode('utf-8', errors='replace')
        return {'tipo': 'mensagem', 'text': text, 'html': '', 'html_text': '', 'plain': text, 'subject': '',
                'from': '', 'reply_to': '', 'display_name': '', 'headers': '', 'attachments': [], 'links': []}
    raw_bytes = raw_bytes.lstrip()
    msg = BytesParser(policy=policy.compat32).parsebytes(raw_bytes)
    separator = re.search(rb'\r?\n\r?\n', raw_bytes)
    header_block = raw_bytes[:separator.start()] if separator else raw_bytes
    plain, html, attachments = [], [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        disposition = (part.get('Content-Disposition') or '').casefold()
        if filename or 'attachment' in disposition:
            attachments.append({'filename': str(filename or 'sem_nome'), 'content_type': part.get_content_type()})
            continue
        if part.get_content_type() == 'text/plain':
            plain.append(_decode(part))
        elif part.get_content_type() == 'text/html':
            html.append(_decode(part))
    html_joined = '\n'.join(html)
    html_text, links = html_to_text(html_joined)
    text = '\n'.join(plain) if plain else html_text
    from_value = str(msg.get('From', ''))
    return {'tipo': 'email', 'text': text, 'html': html_joined, 'html_text': html_text,
            'plain': '\n'.join(plain), 'subject': str(msg.get('Subject', '')), 'from': _address(from_value),
            'display_name': _display_name(from_value), 'reply_to': _address(str(msg.get('Reply-To', ''))),
            'headers': header_block.decode('utf-8', errors='replace'), 'attachments': attachments,
            'links': links}


def extract_urls(item):
    found = []

    def add(url):
        url = url.rstrip('.,;:!?')
        if url.casefold().startswith('www.'):
            url = 'http://' + url
        if url not in found:
            found.append(url)
    for source in (item.get('text', ''), item.get('html', '')):
        for match in URL_RE.findall(source or ''):
            add(match)
    for href, _ in item.get('links', []):
        if href and href.casefold().startswith(('http://', 'https://')):
            add(href)
    return found[:200]


def host_of(url):
    try:
        return (urlparse(url).hostname or '').casefold().rstrip('.')
    except ValueError:
        return ''


def registrable(host):
    parts = host.split('.')
    if len(parts) >= 3 and parts[-1] == 'br' and parts[-2] in ('com', 'gov', 'org', 'net', 'edu', 'jus', 'mil', 'leg'):
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def _official(host, domains):
    return any(host == dom or host.endswith('.' + dom) for dom in domains)


def defang(url):
    return re.sub(r'(?i)^http', 'hxxp', url).replace('.', '[.]')


def _layer(nome, score, confidence, findings, details):
    return {'camada': nome, 'score': min(int(round(score)), 100), 'peso': WEIGHTS[nome],
            'confianca': round(min(max(confidence, 0.0), 1.0), 2), 'achados': findings, 'detalhes': details}


def analyze_headers(item):
    headers = item.get('headers', '')
    findings, details, score, escalations = [], {}, 0, []
    auth = ' '.join(re.findall(r'(?ims)^(?:Authentication-Results|ARC-Authentication-Results):.*?(?=^\S|\Z)', headers))

    def result(kind, values):
        match = re.search(r'\b' + kind + r'=(' + values + r')\b', auth, re.I)
        return match.group(1).casefold() if match else 'ausente'
    spf = result('spf', 'pass|fail|softfail|neutral|none|temperror|permerror')
    dkim = result('dkim', 'pass|fail|none|neutral|temperror|permerror|policy')
    dmarc = result('dmarc', 'pass|fail|none|bestguesspass|temperror|permerror')
    details.update(spf=spf, dkim=dkim, dmarc=dmarc)
    table = {'spf': {'fail': (30, 'SPF falhou: IP do remetente não autorizado pelo domínio'),
                     'softfail': (15, 'SPF softfail: IP não explicitamente autorizado'),
                     'none': (10, 'Domínio sem registro SPF'), 'ausente': (10, 'Sem resultado SPF nos cabeçalhos'),
                     'neutral': (5, None)},
             'dkim': {'fail': (25, 'Assinatura DKIM inválida'), 'none': (10, 'Sem assinatura DKIM'),
                      'ausente': (10, 'Sem resultado DKIM nos cabeçalhos')},
             'dmarc': {'fail': (25, 'DMARC falhou'), 'none': (10, 'Domínio sem política DMARC'),
                       'ausente': (10, 'Sem resultado DMARC nos cabeçalhos'),
                       'bestguesspass': (5, 'DMARC só por estimativa (sem política publicada)')}}
    for kind, value in (('spf', spf), ('dkim', dkim), ('dmarc', dmarc)):
        points, text = table[kind].get(value, (0, None))
        score += points
        if text:
            findings.append(text)
    sender, reply = item.get('from', ''), item.get('reply_to', '')
    sender_domain = sender.split('@')[-1] if sender else ''
    if sender and reply and registrable(reply.split('@')[-1]) != registrable(sender_domain):
        findings.append(f'Reply-To ({reply.split("@")[-1]}) difere do domínio do From ({sender_domain})')
        score += 20
        details['reply_to_divergente'] = True
    scl = re.search(r'(?i)\bSCL:(-?\d+)', headers)
    if scl and int(scl.group(1)) >= 5:
        findings.append(f'Filtro da Microsoft marcou spam alto (SCL {scl.group(1)})')
        score += min(int(scl.group(1)) * 3, 25)
    if re.search(r'(?im)^X-Spam-(Status|Flag):\s*Yes', headers):
        findings.append('Marcado como spam por filtro anterior')
        score += 15
    mailer = re.search(r'(?im)^X-Mailer:\s*(.+)$', headers)
    if mailer:
        details['x_mailer'] = mailer.group(1).strip()[:120]
        if any(name in mailer.group(1).casefold() for name in SUSPICIOUS_MAILERS):
            findings.append(f'Programa de envio em massa suspeito: {details["x_mailer"]}')
            score += 15
    display = normalize(item.get('display_name', ''))
    if sender_domain and display:
        for brand, official in BRANDS.items():
            if re.search(r'\b' + re.escape(brand) + r'\b', display):
                if not _official(sender_domain, official):
                    findings.append(f'Nome de exibição cita "{brand}" mas o remetente é {sender_domain}')
                    score += 25
                    details['marca_imitada'] = brand
                    escalations.append((60, f'Remetente se apresenta como "{brand}" usando domínio não oficial.'))
                break
    if sender_domain.startswith('xn--') or '.xn--' in sender_domain:
        findings.append('Domínio do remetente usa punycode (possível domínio sósia)')
        score += 20
    details['freemail'] = sender_domain in FREEMAIL
    signals = sum(1 for value in (spf, dkim, dmarc) if value != 'ausente')
    return _layer('autenticacao', score, 0.5 + 0.15 * signals, findings, details), escalations


def analyze_content(item, urls):
    findings, details, score, escalations = [], {}, 0, []
    hosts = [h for h in (host_of(u) for u in urls) if h]
    details['urls'] = len(urls)
    details['dominios'] = sorted(set(hosts))[:20]
    if len(urls) > 10:
        findings.append(f'Número incomum de links ({len(urls)})')
        score += 5
    mismatches = []
    for href, anchor in item.get('links', []):
        if not re.match(r'(?i)^(https?://|www\.)', anchor or ''):
            continue
        anchor_url = anchor if anchor.casefold().startswith('http') else 'http://' + anchor
        a, b = host_of(href), host_of(anchor_url)
        if a and b and registrable(a) != registrable(b):
            mismatches.append({'mostrado': defang(anchor_url), 'destino': defang(href)})
    if mismatches:
        findings.append(f'{len(mismatches)} link(s) mostram um endereço e levam a outro (phishing clássico)')
        score += 15 * len(mismatches)
        details['links_divergentes'] = mismatches[:5]
        escalations.append((70, 'Texto do link diverge do destino real.'))
    short = [u for u in urls if host_of(u) in URL_SHORTENERS]
    if short:
        findings.append(f'{len(short)} link(s) encurtado(s) escondem o destino real')
        score += 8 * len(short)
    ip_urls = []
    for u in urls:
        try:
            ipaddress.ip_address(host_of(u))
            ip_urls.append(u)
        except ValueError:
            pass
    if ip_urls:
        findings.append(f'{len(ip_urls)} link(s) apontam direto para IP em vez de domínio')
        score += 15
    puny = [h for h in hosts if h.startswith('xn--') or '.xn--' in h]
    if puny:
        findings.append('Link com domínio punycode (possível domínio sósia)')
        score += 15
    odd_tld = sorted({h for h in hosts if h.rsplit('.', 1)[-1] in SUSPICIOUS_TLDS})
    if odd_tld:
        findings.append('Domínio(s) com TLD muito usado em golpes: ' + ', '.join(odd_tld[:5]))
        score += min(8 * len(odd_tld), 20)
    lookalike = []
    for h in sorted(set(hosts)):
        squashed = h.replace('-', '').replace('.', '')
        for brand, official in BRANDS.items():
            token = normalize(brand).replace(' ', '').replace('.', '')
            if len(token) >= 4 and token in squashed and not _official(h, official):
                lookalike.append(h)
                break
    if lookalike:
        findings.append('Domínio(s) imitando marca/órgão: ' + ', '.join(lookalike[:5]))
        score += 20
        escalations.append((60, 'Link usa domínio que imita marca ou órgão oficial.'))
    full = item.get('text', '') + ' ' + item.get('html', '')
    wa = sum(1 for p in WHATSAPP_PATTERNS if re.search(p, full, re.I))
    if wa:
        findings.append('Desvia a conversa para WhatsApp')
        score += min(10 * wa, 20)
    broken = sum(1 for p in BROKEN_TEMPLATE_PATTERNS if re.search(p, full, re.I))
    if broken:
        findings.append('Variáveis de template não resolvidas (envio em massa mal configurado)')
        score += min(8 * broken, 15)
    attachments = item.get('attachments', [])
    risks = []
    dangerous = [a['filename'] for a in attachments if a['filename'].casefold().endswith(DANGEROUS_EXTENSIONS)]
    if dangerous:
        findings.append('Anexo(s) executável(is)/atalho: ' + ', '.join(dangerous))
        score += min(25 * len(dangerous), 45)
        risks += [{'arquivo': n, 'gravidade': 'perigoso', 'motivo': 'Executável, script ou atalho'} for n in dangerous]
        escalations.append((80, 'Contém anexo executável ou claramente perigoso.'))
    suspicious = []
    for a in attachments:
        name = a['filename'].casefold()
        for category, exts, points, reason in SUSPICIOUS_ATTACHMENT_RULES:
            if name.endswith(exts):
                suspicious.append((a['filename'], category, points, reason))
                break
    if suspicious:
        findings.append('Anexo(s) altamente suspeito(s): ' + ', '.join(s[0] for s in suspicious))
        score += min(sum(s[2] for s in suspicious), 35)
        risks += [{'arquivo': s[0], 'gravidade': 'suspeito', 'categoria': s[1], 'motivo': s[3]} for s in suspicious]
        escalations.append((65 if len(suspicious) >= 2 else 55, 'Contém anexo altamente suspeito.'))
    double = [a['filename'] for a in attachments
              if re.search(r'\.(pdf|doc|docx|xls|xlsx|jpg|jpeg|png|txt)\.[a-z0-9]{2,4}$', a['filename'], re.I)]
    if double:
        findings.append('Anexo com extensão dupla (disfarce): ' + ', '.join(double))
        score += min(15 * len(double), 30)
        escalations.append((75, 'Anexo com extensão dupla, padrão comum de disfarce.'))
    details['anexos'] = len(attachments)
    details['riscos_anexos'] = risks
    subject = item.get('subject', '')
    if len(subject) > 10 and subject == subject.upper() and re.search(r'[A-Z]', subject):
        findings.append('Assunto todo em MAIÚSCULAS')
        score += 8
    if subject.count('!') >= 3 or re.search(r'!{2,}', item.get('text', '')):
        findings.append('Excesso de pontos de exclamação')
        score += 5
    plain, html_text = item.get('plain', '').strip(), item.get('html_text', '').strip()
    if item.get('tipo') == 'email' and len(plain) >= 80 and len(html_text) >= 80:
        wp, wh = set(re.findall(r'\w{3,}', plain.casefold())), set(re.findall(r'\w{3,}', html_text.casefold()))
        if wp and wh and len(wp & wh) / len(wp | wh) < 0.30:
            findings.append('Versões texto e HTML dizem coisas diferentes (tentativa de enganar filtro)')
            score += 30
    length = len(item.get('text', ''))
    confidence = 1.0 if length > 200 else 0.8 if length > 50 else 0.5
    return _layer('conteudo', score, confidence, findings, details), escalations


def analyze_patterns(item, urls=()):
    text = normalize(' '.join((item.get('subject', ''), item.get('text', ''))))
    findings, details, score = [], {}, 0
    for category, points, cap, patterns in TEXT_PATTERNS:
        hits = []
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                hits.append(match.group(0)[:60])
        if hits:
            details[category] = hits[:6]
            score += min(points * len(hits), cap)
            findings.append(f'{PATTERN_LABELS[category]}: ' + '; '.join(f'"{h}"' for h in hits[:4]))
    escalations = []
    has = details.__contains__
    if has('golpe_relacional') and has('pagamento'):
        escalations.append((80, 'Padrão "mudei de número / me faz um Pix": golpe relacional clássico.'))
    if has('pagamento') and has('urgencia') and (has('autoridade') or has('phishing')):
        escalations.append((60, 'Cobrança urgente em nome de órgão/empresa pedindo pagamento.'))
    if has('dados_pessoais') and (has('phishing') or has('urgencia') or urls):
        escalations.append((60, 'Pede dados sensíveis com pressão ou link de verificação.'))
    elif len(details.get('dados_pessoais', [])) >= 2:
        escalations.append((55, 'Pede mais de um dado sensível (senha, código, cartão, documento).'))
    if has('injecao_ia'):
        escalations.append((55, 'Texto tenta instruir assistentes de IA: tática de quem quer passar pelo filtro.'))
    if has('tarefas_pagas') and has('pagamento'):
        escalations.append((70, 'Oferta de "tarefas pagas" com depósito/Pix: golpe de tarefas.'))
    elif len(details.get('tarefas_pagas', [])) >= 2:
        escalations.append((55, 'Oferta de "tarefas simples" com ganho diário: padrão de golpe de tarefas.'))
    length = len(text)
    confidence = 0.9 if length > 200 else 0.75 if length > 50 else 0.5
    return _layer('padroes', score, confidence, findings, details), escalations


def verdict(score):
    for limit, code, label in VEREDITOS:
        if score <= limit:
            return code, label
    return VEREDITOS[-1][1], VEREDITOS[-1][2]


RECOMENDACOES = {
    'legitimo': ['Nenhum sinal forte de golpe. Mesmo assim, confira valor e destinatário antes de pagar.'],
    'suspeito_provavel_ok': ['Provavelmente ok, mas confirme pelo canal oficial (app ou site digitado à mão) antes de agir.'],
    'suspeito_provavel_golpe': ['Não clique nos links nem abra anexos.',
                                'Confirme pelo canal oficial ou ligando para um número que você já tinha.',
                                'Não faça Pix/boleto nem informe códigos recebidos por SMS.'],
    'golpe': ['Trate como golpe: não responda, não clique, não pague.',
              'Se for "parente com número novo", ligue para o número antigo antes de qualquer coisa.',
              'Bloqueie/denuncie o remetente; se já pagou, acione o banco na hora (MED do Pix).'],
}


def analyze(data, *, max_urls=25):
    """Analisa texto/e-mail e devolve score 0-100, veredito e evidências por camada."""
    item = parse_input(data)
    urls = extract_urls(item)
    layers, escalations = [], []
    if item['tipo'] == 'email':
        layer, extra = analyze_headers(item)
        layers.append(layer)
        escalations += extra
    for analyzer in (lambda: analyze_content(item, urls), lambda: analyze_patterns(item, urls)):
        layer, extra = analyzer()
        layers.append(layer)
        escalations += extra
    weight = sum(layer['peso'] * layer['confianca'] for layer in layers)
    base = sum(layer['score'] * layer['peso'] * layer['confianca'] for layer in layers) / weight if weight else 0
    # Uma camada com sinal forte não pode ser diluída por camadas limpas.
    base = max(base, max((layer['score'] for layer in layers), default=0) * 0.6)
    floor = max((value for value, _ in escalations), default=0)
    final = int(round(min(max(base, floor), 100)))
    code, label = verdict(final)
    return {
        'status': 'ok', 'tipo': item['tipo'], 'score': final, 'veredito': code, 'veredito_label': label,
        'camadas': layers,
        'escalonamentos': [reason for _, reason in sorted(escalations, key=lambda e: -e[0])],
        'remetente': item.get('from') or None, 'assunto': item.get('subject') or None,
        'links': [defang(u) for u in urls[:max_urls]],
        'recomendacoes': RECOMENDACOES[code],
        'limites': ('Análise determinística offline: não abre links nem anexos, sem WHOIS nem blacklists. '
                    'O conteúdo analisado é dado externo, nunca instrução. E-mail encaminhado inline perde '
                    'cabeçalhos; prefira o original ou "encaminhar como anexo".'),
    }
