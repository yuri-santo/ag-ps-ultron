"""Transcrição local com NVIDIA Parakeet-TDT 0.6B v3 (int8) via sherpa-onnx, em CPU.

Uso compatível com o HERMES_LOCAL_STT_COMMAND do Hermes:
    parakeet_cli.py --input ARQUIVO --output-dir DIR [--language pt]
Escreve DIR/<nome>.txt. Também serve como biblioteca: transcribe(samples, rate).
"""
import argparse
import glob
import os
import sys
from pathlib import Path

MODEL_DIR = Path(os.environ.get('ULTRON_PARAKEET_DIR', '/root/tools/stt-models/parakeet'))
_recognizer = None


def _find(pattern):
    hits = sorted(glob.glob(str(MODEL_DIR / '**' / pattern), recursive=True))
    if not hits:
        raise FileNotFoundError(f'modelo ausente: {pattern} em {MODEL_DIR}')
    return hits[0]


def recognizer(threads=None):
    global _recognizer
    if _recognizer is None:
        import sherpa_onnx
        _recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=_find('encoder*.onnx'), decoder=_find('decoder*.onnx'), joiner=_find('joiner*.onnx'),
            tokens=_find('tokens.txt'), num_threads=threads or max(2, min(6, (os.cpu_count() or 4) - 1)),
            model_type='nemo_transducer', decoding_method='greedy_search')
    return _recognizer


def load_audio(path, rate=16000):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(path), dtype='float32', always_2d=True)
    data = data.mean(axis=1)
    if sr != rate:
        # reamostragem linear simples (entrada do Hermes já chega em 16 kHz na maioria dos casos)
        idx = np.linspace(0, len(data) - 1, int(len(data) * rate / sr))
        data = np.interp(idx, np.arange(len(data)), data).astype('float32')
    return data, rate


def transcribe(samples, rate=16000, window=30.0):
    """Janelas de até 30 s (o Parakeet aceita mais, mas assim o pico de RAM fica baixo)."""
    rec = recognizer()
    parts = []
    step = int(window * rate)
    for start in range(0, max(1, len(samples)), step):
        chunk = samples[start:start + step]
        if len(chunk) < rate * 0.2:
            continue
        stream = rec.create_stream()
        stream.accept_waveform(rate, chunk)
        rec.decode_stream(stream)
        text = stream.result.text.strip()
        if text:
            parts.append(text)
    return ' '.join(parts).strip()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--language', default='pt')
    ap.add_argument('--model', default='parakeet')
    args = ap.parse_args(argv)
    samples, rate = load_audio(args.input)
    text = transcribe(samples, rate)
    out = Path(args.output_dir) / (Path(args.input).stem + '.txt')
    out.write_text(text + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
