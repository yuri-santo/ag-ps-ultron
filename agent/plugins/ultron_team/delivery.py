"""Keep instructions in writing and derive short speech without inventing content."""
import re
import unicodedata


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn')


def explicit_mail_request(text):
    value = normalize(text).strip()
    if value.startswith('/reuniao'):
        return False
    if re.match(r'^/(?:gmail|easysapers)(?:\s|$)', value):
        return True
    if not re.search(r'\b(?:gmail|easysapers|workmail)\b', value):
        return False
    return bool(re.search(
        r'\b(?:veja|verifique|confira|confere|olhe|leia|liste|procure|busque|pesquise|'
        r'resuma|prepare|rascunhe|cheque|checa|mostre)\b.{0,80}'
        r'(?:\b(?:meu|minha|email|e-mail|caixa|mensagens|inbox)\b)', value))


def speech_plan(response, request='', *, voice_input=False):
    if not response or re.search(r'(?:MEDIA:|\[\[audio)', response, re.I):
        return None
    query = normalize(request)
    if any(term in query for term in ('somente texto', 'so texto', 'sem audio', 'nao mande audio')):
        return None
    wants_audio = voice_input or any(term in query for term in ('audio', 'voz', 'fale comigo'))
    numbered = bool(re.search(r'^\s*\d+[.)]\s', response, re.M))
    long = len(response) > 1100
    if not wants_audio and not long:
        return None
    prose = re.sub(r'```[\s\S]*?```', '', response)
    prose = re.sub(r'`[^`]*`', '', prose)
    prose = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', prose)
    prose = re.sub(r'https?://\S+', '', prose)
    prose = re.sub(r'^[ \t]*[#>*-]+[ \t]*', '', prose, flags=re.M)
    prose = re.sub(r'[*_~]', '', prose).strip()
    pointer = 'O passo a passo completo está no texto. Confira os comandos e siga a ordem por lá.'
    if not prose:
        return pointer
    if long or numbered or len(prose) > 650:
        introduction = re.split(r'\n\s*\d+[.)]\s', prose)[0]
        sentences = re.findall(r'[^.!?]+[.!?](?:\s|$)', introduction)
        prefix = ''
        for sentence in sentences:
            if len(prefix) + len(sentence) > 500:
                break
            prefix += sentence
        return (prefix.strip() + ' ' + pointer).strip()
    return prose


def attach_audio(response, path):
    if not path or any(char in str(path) for char in ('\r', '\n', '\x00')):
        return response
    return response + '\n\nMEDIA:' + str(path)
