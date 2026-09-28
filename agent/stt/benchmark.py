"""Compara faster-whisper (base, int8) e Parakeet v3 (sherpa-onnx) em PT-BR sintetizado. Imprime JSON."""
import asyncio, json, re, subprocess, sys, time, unicodedata
from pathlib import Path

FRASES = [
    'Bom dia a todos, vamos começar a reunião de alinhamento do projeto de aprovação no SAP.',
    'O prazo para entrega do relatório financeiro é sexta-feira, dia três de outubro, às dezoito horas.',
    'Precisamos validar o commit do método customizado antes de subir a transporte para produção.',
    'O Harvey vai revisar o contrato e o Bigode confere o impacto no orçamento do mês.',
]
WORK = Path(sys.argv[1])
HP = sys.argv[2]


def norm(t):
    t = ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')
    return re.findall(r'[a-z0-9]+', t)


def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(1, len(r))


async def synth():
    import edge_tts
    files = []
    for i, frase in enumerate(FRASES):
        mp3 = WORK / f'frase{i}.mp3'
        if not mp3.exists():
            await edge_tts.Communicate(frase, 'pt-BR-AntonioNeural').save(str(mp3))
        wav = WORK / f'frase{i}.wav'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(mp3), '-ar', '16000', '-ac', '1', str(wav)], check=True)
        files.append(wav)
    return files


files = asyncio.run(synth())
sys.path.insert(0, str(Path(__file__).parent))
import parakeet_cli
t0 = time.time(); parakeet_cli.recognizer(); load_p = time.time() - t0
res = {'parakeet': {'carga_s': round(load_p, 2), 'textos': [], 'tempo_s': 0, 'wer': 0}}
for f, ref in zip(files, FRASES):
    s, r = parakeet_cli.load_audio(f)
    t = time.time(); txt = parakeet_cli.transcribe(s, r); res['parakeet']['tempo_s'] += time.time() - t
    res['parakeet']['textos'].append(txt); res['parakeet']['wer'] += wer(ref, txt) / len(FRASES)
code = r'''
import json, sys, time
from faster_whisper import WhisperModel
t=time.time(); m=WhisperModel("base", device="cpu", compute_type="int8"); load=time.time()-t
out={"carga_s":round(load,2),"textos":[],"tempo_s":0}
for f in sys.argv[1:]:
    t=time.time(); segs,_=m.transcribe(f, language="pt", vad_filter=True); txt="".join(s.text for s in segs).strip(); out["tempo_s"]+=time.time()-t; out["textos"].append(txt)
print(json.dumps(out, ensure_ascii=False))
'''
w = json.loads(subprocess.run([HP, '-c', code, *map(str, files)], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
w['wer'] = sum(wer(ref, t) for ref, t in zip(FRASES, w['textos'])) / len(FRASES)
res['whisper_base'] = w
audio_s = sum(len(parakeet_cli.load_audio(f)[0]) / 16000 for f in files)
for k in ('parakeet', 'whisper_base'):
    res[k]['tempo_s'] = round(res[k]['tempo_s'], 2); res[k]['wer'] = round(res[k]['wer'], 3)
    res[k]['x_tempo_real'] = round(audio_s / max(0.01, res[k]['tempo_s']), 1)
res['audio_total_s'] = round(audio_s, 1)
print(json.dumps(res, ensure_ascii=False, indent=1))
