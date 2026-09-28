"""Quem falou quando: diarização local (pyannote-segmentation-3.0 + embeddings 3D-Speaker, via sherpa-onnx).

Entrada (stdin JSON): {"audio_dir": ".../capture_state/<sessão>/audio", "events": [{"id","at","end","channel"}]}
Saída (stdout JSON): {"vozes": N, "rotulos": {"id_da_fala": "Participante 1"}, "duracao_s": ...}
Só o canal "loopback" (áudio recebido da reunião) é diarizado; o microfone local é sempre o Yuri.
Tudo roda em CPU, sem enviar áudio para fora.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

MODELS = Path(os.environ.get('ULTRON_STT_MODELS', '/root/tools/stt-models'))
RATE = 16000


def diarizador(threshold=0.55):
    import sherpa_onnx
    seg = sorted(glob.glob(str(MODELS / 'seg' / '**' / 'model*.onnx'), recursive=True))
    if not seg or not (MODELS / 'emb.onnx').exists():
        raise FileNotFoundError('modelos_de_diarizacao_ausentes')
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=seg[0]),
            num_threads=max(2, min(6, (os.cpu_count() or 4) - 1))),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(MODELS / 'emb.onnx'),
                                                              num_threads=max(2, min(6, (os.cpu_count() or 4) - 1))),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=threshold),
        min_duration_on=0.3, min_duration_off=0.5)
    if not config.validate():
        raise RuntimeError('configuracao_de_diarizacao_invalida')
    return sherpa_onnx.OfflineSpeakerDiarization(config)


def ler(path):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(path), dtype='float32', always_2d=True)
    data = data.mean(axis=1)
    if sr != RATE:
        idx = np.linspace(0, len(data) - 1, int(len(data) * RATE / sr))
        data = np.interp(idx, np.arange(len(data)), data).astype('float32')
    return data


def montar_linha_do_tempo(arquivos, gap=0.3):
    """Concatena os trechos do canal da reunião; devolve áudio e (offset, início_absoluto, duração)."""
    import numpy as np
    partes, mapa, pos = [], [], 0.0
    silencio = np.zeros(int(gap * RATE), dtype='float32')
    for inicio, path in arquivos:
        audio = ler(path)
        mapa.append((pos, inicio, len(audio) / RATE))
        partes += [audio, silencio]
        pos += len(audio) / RATE + gap
    return (np.concatenate(partes) if partes else np.zeros(0, dtype='float32')), mapa


def para_absoluto(t, mapa):
    for off, inicio, dur in mapa:
        if off <= t <= off + dur:
            return inicio + (t - off)
    return None


def atribuir(segmentos, events):
    """segmentos: [(ini_abs, fim_abs, falante)]. Cada fala recebe o falante com maior sobreposição."""
    rotulos, ordem = {}, []
    for ev in events:
        if ev.get('channel') != 'loopback':
            continue
        a = float(ev['at'])
        b = float(ev.get('end') or a + 3.0)
        melhor, maior = None, 0.0
        for s, e, spk in segmentos:
            sobre = min(b, e) - max(a, s)
            if sobre > maior:
                melhor, maior = spk, sobre
        if melhor is not None:
            if melhor not in ordem:
                ordem.append(melhor)
            rotulos[str(ev['id'])] = f'Participante {ordem.index(melhor) + 1}'
    return rotulos, len(ordem)


def diarizar_sessao(audio_dir, events):
    audio_dir = Path(audio_dir)
    arquivos = []
    for f in sorted(audio_dir.glob('*_loopback_*.flac')):
        try:
            arquivos.append((float(f.name.split('_', 1)[0]), f))
        except ValueError:
            continue
    if not arquivos:
        return {'vozes': 0, 'rotulos': {}, 'motivo': 'sem_audio_da_reuniao'}
    arquivos.sort()
    audio, mapa = montar_linha_do_tempo(arquivos)
    sd = diarizador()
    resultado = sd.process(audio).sort_by_start_time()
    segmentos = []
    for r in resultado:
        s, e = para_absoluto(r.start, mapa), para_absoluto(r.end, mapa)
        if s is not None and e is not None and e > s:
            segmentos.append((s, e, int(r.speaker)))
    rotulos, vozes = atribuir(segmentos, events)
    return {'vozes': vozes, 'rotulos': rotulos, 'duracao_s': round(len(audio) / RATE, 1), 'segmentos': len(segmentos)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--teste')
    args = ap.parse_args()
    if args.teste:
        sd = diarizador()
        res = sd.process(ler(args.teste)).sort_by_start_time()
        print(json.dumps({'falantes': len({r.speaker for r in res}),
                          'segmentos': [[round(r.start, 2), round(r.end, 2), int(r.speaker)] for r in res][:20]}))
        return 0
    req = json.loads(sys.stdin.read(20_000_000) or '{}')
    try:
        out = diarizar_sessao(req['audio_dir'], req.get('events') or [])
    except Exception as exc:
        out = {'vozes': 0, 'rotulos': {}, 'motivo': type(exc).__name__ + ': ' + str(exc)[:200]}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
