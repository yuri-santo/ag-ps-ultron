"""Aquece o Whisper local no processo do gateway, para a voz do Hermes desktop não estourar o tempo.

O Hermes desktop espera no máximo 20 s pela transcrição. Carregar o faster-whisper do zero no
WSL leva ~28 s (visto no agent.log em 28/09/2026), então a primeira fala depois de reiniciar o
gateway, ou depois do descarregamento por ociosidade, sempre falhava com TimeoutError.
Aqui o modelo é carregado em segundo plano logo após o gateway subir, com 1 s de silêncio.
Só roda no serviço do gateway (systemd) e só uma vez por processo; qualquer erro é ignorado.
"""
import logging
import os
import sys
import tempfile
import threading
import wave

LOG = logging.getLogger(__name__)
_started = False
_lock = threading.Lock()


def is_gateway_process(argv=None, environ=None):
    argv = ' '.join(argv if argv is not None else sys.argv)
    environ = os.environ if environ is None else environ
    return bool(environ.get('INVOCATION_ID')) and 'gateway' in argv and 'dashboard' not in argv


def _silence(path, seconds=1.0, rate=16000):
    with wave.open(path, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b'\x00\x00' * int(rate * seconds))


def warm(transcribe=None, delay=15.0, sleep=None):
    import time
    (sleep or time.sleep)(delay)
    try:
        if transcribe is None:
            from tools.transcription_tools import _load_stt_config, transcribe_audio
            config = _load_stt_config() or {}
            if str(config.get('provider', 'local')) != 'local' or config.get('enabled') is False:
                return 'ignorado'
            transcribe = transcribe_audio
        with tempfile.TemporaryDirectory(prefix='stt-warmup-') as tmp:
            path = os.path.join(tmp, 'aquecimento.wav')
            _silence(path)
            transcribe(path)
        LOG.info('ultron_lab: modelo local de transcrição aquecido')
        return 'ok'
    except Exception as exc:  # nunca derruba o gateway
        LOG.warning('ultron_lab: aquecimento da transcrição falhou: %s', type(exc).__name__)
        return 'falhou'


def start(argv=None, environ=None, delay=15.0):
    global _started
    if not is_gateway_process(argv, environ):
        return False
    with _lock:
        if _started:
            return False
        _started = True
    threading.Thread(target=warm, kwargs={'delay': delay}, name='ultron-stt-warmup', daemon=True).start()
    return True
