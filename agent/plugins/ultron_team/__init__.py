"""Ultron's persistent specialist team and optional ElevenLabs delivery."""
import json
import logging
import os
from pathlib import Path
import threading
import time
import uuid
from .bridge import Bridge, PROFILES
from .delivery import attach_audio, speech_plan
from .domain_tools import register_domain_tools

LOG = logging.getLogger(__name__)


def register(ctx):
    from hermes_constants import get_hermes_home
    home = Path(get_hermes_home()).resolve()
    base = Path(ctx.get_config('base_home', '/root/.hermes')).resolve()
    profile = home.name if home.parent == base / 'profiles' else ''
    if profile in PROFILES:
        register_domain_tools(ctx.register_tool, profile, home, base)
        return
    if home != base:
        return
    bridge = Bridge(base, timeout=180)
    schema = {'name': 'ultron_specialist',
              'description': 'Consulta um perfil persistente real: Gmail pessoal, Easysapers profissional ou Reuniões. '
                             'Retorna resposta e evidência da execução. Não envia e-mails nem inicia gravação.',
              'parameters': {'type': 'object', 'properties': {
                  'profile': {'type': 'string', 'enum': list(PROFILES)},
                  'task': {'type': 'string', 'description': 'Pedido completo e claro para o especialista'},
                  'context': {'type': 'string', 'description': 'Somente os dados relevantes; sem segredos'}},
                  'required': ['profile', 'task'], 'additionalProperties': False}}
    def dispatch(args, **kwargs):
        from gateway.session_context import get_session_env
        result = bridge.dispatch(args.get('profile'), args.get('task'),
            context=args.get('context', ''), parent_session_id=get_session_env('HERMES_SESSION_ID', ''))
        return json.dumps(result, ensure_ascii=False)
    ctx.register_tool(name='ultron_specialist', toolset='ultron_team', schema=schema,
                      handler=dispatch, description=schema['description'])
    personality = Path(__file__).with_name('personality.md')
    if personality.is_file():
        ctx.register_system_prompt_section('ultron_team', personality.read_text(encoding='utf-8-sig'), max_chars=4000)

    pending = {}
    inbound_voice = {}
    lock = threading.Lock()

    def prune_voice(now):
        for key in list(inbound_voice):
            if now - inbound_voice[key] > 600:
                inbound_voice.pop(key, None)

    def observe_inbound(**kwargs):
        # Metadata only: this hook runs before gateway authorization and STT.
        if not ctx.get_config('voice_enabled', False):
            return None
        event = kwargs.get('event')
        source = getattr(event, 'source', None)
        profile = getattr(source, 'profile', None) or ''
        if profile not in ('', 'default'):
            return None
        kind = getattr(event, 'message_type', None)
        if getattr(kind, 'value', kind) != 'voice':
            return None
        platform = getattr(source, 'platform', None)
        platform = getattr(platform, 'value', platform)
        message_id = getattr(event, 'message_id', None) or getattr(source, 'message_id', None)
        chat_id = getattr(source, 'chat_id', None)
        if platform not in ('telegram', 'api_server', 'web', 'cli') or not message_id or not chat_id:
            return None
        key = tuple(str(value or '') for value in (
            platform, chat_id, getattr(source, 'user_id', None),
            getattr(source, 'thread_id', None), message_id))
        with lock:
            now = time.monotonic()
            prune_voice(now)
            if len(inbound_voice) >= 128:
                inbound_voice.pop(next(iter(inbound_voice)))
            inbound_voice[key] = now
        return None

    def consume_voice():
        if not ctx.get_config('voice_enabled', False):
            return False
        try:
            from gateway.session_context import get_session_env
        except ImportError:
            return False
        if get_session_env('HERMES_SESSION_PROFILE', '') not in ('', 'default'):
            return False
        key = tuple(str(get_session_env('HERMES_SESSION_' + name, '') or '')
                    for name in ('PLATFORM', 'CHAT_ID', 'USER_ID', 'THREAD_ID', 'MESSAGE_ID'))
        with lock:
            prune_voice(time.monotonic())
            return inbound_voice.pop(key, None) is not None

    def before(**kwargs):
        session = kwargs.get('session_id', '')
        message = kwargs.get('user_message', '')
        if not isinstance(message, str):
            message = ''
        voice_input = consume_voice()
        with lock:
            now = time.monotonic()
            for key in list(pending):
                if now - pending[key][0] > 600:
                    pending.pop(key, None)
            if len(pending) >= 128:
                pending.pop(next(iter(pending)))
            pending[session] = (now, message[-12000:], voice_input)
        return ('Conversa privada com Yuri: tom casual, sarcasmo natural quando couber, sem cerimônia '
                'ou bajulação. Palavrões são permitidos quando úteis. Discorde com fundamento; admita desconhecimento; nunca invente fatos '
                'ou resultados. Gmail/Easysapers/Reuniões são perfis reais: use ultron_specialist. '
                'Instruções longas ficam completas em texto; áudio é apoio. A voz Jarvis/ElevenLabs '
                + ('está habilitada; confirme geração e entrega antes de afirmar sucesso.' if ctx.get_config('voice_enabled', False) else
                   'ainda depende de acesso e voz verificados. Não use outra voz como substituta.'))

    def transform(**kwargs):
        response = kwargs.get('response_text', '')
        if kwargs.get('platform') not in ('telegram', 'api_server', 'web', 'cli'):
            return None
        if not ctx.get_config('voice_enabled', False):
            return None
        with lock:
            _, request, voice_input = pending.pop(kwargs.get('session_id', ''), (0, '', False))
        spoken = speech_plan(response, request, voice_input=voice_input or '[voice' in request.casefold())
        if not spoken:
            return None
        unavailable = response + '\n\nNão consegui gerar o áudio agora; o conteúdo completo está no texto.'
        try:
            from hermes_cli.config import load_config_readonly
            from tools.tts_tool import _resolve_provider_key
            import requests
            voice = ((load_config_readonly().get('tts') or {}).get('elevenlabs') or {})
            voice_id = voice.get('voice_id')
            key = _resolve_provider_key('ELEVENLABS_API_KEY', 'elevenlabs')
            if not key or not voice_id:
                return unavailable
            cache = base / 'audio_cache'
            cache.mkdir(exist_ok=True, mode=0o700)
            output = cache / ('ultron_' + uuid.uuid4().hex + '.mp3')
            with requests.post('https://api.elevenlabs.io/v1/text-to-speech/' + voice_id,
                headers={'xi-api-key': key, 'Content-Type': 'application/json'},
                json={'text': spoken, 'model_id': voice.get('model_id', 'eleven_flash_v2_5')},
                timeout=(5, 18), stream=True) as result:
                result.raise_for_status()
                if not result.headers.get('Content-Type', '').startswith('audio/'):
                    return unavailable
                data = bytearray()
                for chunk in result.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 4000000:
                        return unavailable
                if len(data) < 200:
                    return unavailable
            descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
            return attach_audio(response, output)
        except Exception as exc:
            LOG.warning('Ultron supplementary audio unavailable: %s', type(exc).__name__)
            return unavailable
    ctx.register_hook('pre_gateway_dispatch', observe_inbound)
    ctx.register_hook('pre_llm_call', before)
    ctx.register_hook('transform_llm_output', transform)
