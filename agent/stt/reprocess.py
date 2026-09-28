"""Offline second-pass ASR. Writes review candidates; never edits events or a DB."""
import argparse
from array import array
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
import time

RATE = 16000
CONTEXT_SECONDS = 2.0
MAX_GAP = 0.15
VERSION = 1
TOOL = 'ultron-offline-reprocess'
FILENAME = re.compile(r'^(\d+(?:\.\d+)?)_(mic|loopback)_.+\.flac$')


@dataclass(frozen=True)
class Chunk:
    path: Path
    start: float
    channel: str
    duration: float

    @property
    def end(self):
        return self.start + self.duration


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _atomic(path, text):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _safe_audio(directory, reference):
    if not isinstance(reference, str) or not reference:
        raise ValueError('audio_file must be a relative filename')
    windows = PureWindowsPath(reference)
    relative = Path(reference)
    if (windows.drive or windows.root or relative.is_absolute()
            or '..' in windows.parts or '..' in relative.parts):
        raise ValueError('unsafe audio_file reference')
    path = (directory / reference).resolve()
    if not path.is_relative_to(directory) or not FILENAME.fullmatch(path.name):
        raise ValueError('audio_file must refer to a captured FLAC inside audio-dir')
    return path


def load_events(path, audio_dir, selection):
    grouped, selected = {}, set()
    with path.open(encoding='utf-8-sig') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError(f'event on line {number} must be an object')
            if event.get('kind', 'transcript') != 'transcript':
                continue
            reference = event.get('audio_file')
            if not reference:
                continue
            audio = _safe_audio(audio_dir, reference)
            if not event.get('id'):
                raise ValueError(f'transcript on line {number} has no id')
            grouped.setdefault(audio, []).append(str(event['id']))
            if selection == 'all' or event.get('confidence') == 'low':
                selected.add(audio)
    return grouped, selected


def context_window(target, chunks):
    channel = sorted((chunk for chunk in chunks if chunk.channel == target.channel),
                     key=lambda chunk: (chunk.start, str(chunk.path)))
    index = channel.index(target)
    first = last = index
    while first > 0:
        previous, current = channel[first - 1], channel[first]
        gap = current.start - previous.end
        if not (-1e-6 <= gap <= MAX_GAP + 1e-6) or previous.end <= target.start - CONTEXT_SECONDS:
            break
        first -= 1
    while last + 1 < len(channel):
        current, following = channel[last], channel[last + 1]
        gap = following.start - current.end
        if not (-1e-6 <= gap <= MAX_GAP + 1e-6) or following.start >= target.end + CONTEXT_SECONDS:
            break
        last += 1
    start = max(channel[first].start, target.start - CONTEXT_SECONDS)
    end = min(channel[last].end, target.end + CONTEXT_SECONDS)
    pieces = [(chunk, max(start, chunk.start), min(end, chunk.end))
              for chunk in channel[first:last + 1]]
    return pieces, start, end


def _audio_info(path):
    import soundfile as sf
    info = sf.info(str(path))
    if info.samplerate != RATE:
        raise ValueError('captured audio must be 16000 Hz')
    return info.frames / RATE


def _audio_reader(path, start, duration):
    import soundfile as sf
    with sf.SoundFile(str(path)) as stream:
        if stream.samplerate != RATE:
            raise ValueError('captured audio must be 16000 Hz')
        stream.seek(round(start * RATE))
        return stream.read(round(duration * RATE), dtype='float32', always_2d=True).mean(axis=1)


def _assemble(pieces, start, end, reader):
    audio = array('f', [0.0]) * round((end - start) * RATE)
    for chunk, begin, finish in pieces:
        offset = round((begin - start) * RATE)
        count = round((finish - begin) * RATE)
        samples = array('f', reader(chunk.path, begin - chunk.start, finish - begin))
        if abs(len(samples) - count) > 1:
            raise ValueError('audio length changed or truncated while reading')
        available = min(count, len(samples), len(audio) - offset)
        audio[offset:offset + available] = samples[:available]
    return audio


class WhisperRecognizer:
    def __init__(self, model, threads, glossary, allow_download, model_factory=None):
        if model_factory is None:
            from faster_whisper import WhisperModel
            model_factory = WhisperModel
        self.model = model_factory(model, device='cpu', compute_type='int8', cpu_threads=threads,
                                   local_files_only=not allow_download)
        self.glossary = glossary

    def __call__(self, audio):
        import numpy as np
        segments, _ = self.model.transcribe(
            np.frombuffer(audio, dtype=np.float32), language='pt', beam_size=5,
            word_timestamps=True, vad_filter=True, condition_on_previous_text=False,
            initial_prompt=self.glossary or None)
        return segments


def _score(value):
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def _candidate(segments, target, window_start, source_ids, key, context_files):
    words, segment_scores = [], []
    for segment in segments:
        used = False
        for word in getattr(segment, 'words', None) or []:
            start, end = _score(word.start), _score(word.end)
            if start is None or end is None or end <= start:
                continue
            midpoint = window_start + (start + end) / 2
            if target.start <= midpoint < target.end:
                words.append({'text': word.word, 'start': max(target.start, window_start + start),
                              'end': min(target.end, window_start + end),
                              'probability': _score(getattr(word, 'probability', None))})
                used = True
        if used:
            segment_scores.append({name: _score(getattr(segment, name, None))
                                   for name in ('avg_logprob', 'no_speech_prob', 'compression_ratio')})
    probabilities = [word['probability'] for word in words if word['probability'] is not None]
    return {'id': 'reprocess:' + key, 'kind': 'transcript_candidate', 'review_required': True,
            'source_event_ids': source_ids, 'source_audio': target.path.name,
            'context_audio': context_files, 'channel': target.channel,
            'at': target.start, 'end': target.end, 'text': ''.join(word['text'] for word in words).strip(),
            'words': words, 'scores': {'segments': segment_scores,
                                     'mean_word_probability': sum(probabilities) / len(probabilities)
                                     if probabilities else None},
            'warnings': [] if words else ['no_timestamped_words_in_central_window']}


def run(audio_dir, events, output_dir, model='small', selection='low-confidence', limit=None,
        threads=4, glossary=None, allow_download=False, recognizer=None,
        audio_info=None, audio_reader=None):
    if selection not in ('all', 'low-confidence') or threads < 1 or (limit is not None and limit < 1):
        raise ValueError('invalid selection, threads or limit')
    audio_dir, events, output_dir = Path(audio_dir).resolve(), Path(events).resolve(), Path(output_dir).resolve()
    if not audio_dir.is_dir() or output_dir == audio_dir:
        raise ValueError('audio-dir must exist and output-dir must be separate')
    terms = Path(glossary).read_text(encoding='utf-8-sig').strip() if glossary else ''
    if len(terms) > 1000:
        raise ValueError('glossary exceeds 1000 characters')
    grouped, selected = load_events(events, audio_dir, selection)
    manifest_path = output_dir / 'manifest.json'
    if output_dir.exists() and any(output_dir.iterdir()):
        if not manifest_path.exists() or json.loads(manifest_path.read_text(encoding='utf-8')).get('tool') != TOOL:
            raise ValueError('output-dir must be new or a previous reprocess output')
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints = output_dir / 'checkpoints'
    checkpoints.mkdir(exist_ok=True)
    if checkpoints.is_symlink() or manifest_path.is_symlink():
        raise ValueError('output paths must not be symbolic links')
    model_path = Path(model)
    fingerprint = None
    if model_path.is_dir():
        fingerprint = {str(path.relative_to(model_path)): _hash_file(path)
                       for path in sorted(model_path.rglob('*')) if path.is_file()}
        model = str(model_path.resolve())
    config = {'version': VERSION, 'model': model, 'model_files': fingerprint,
              'threads': threads, 'glossary': terms, 'language': 'pt', 'beam_size': 5,
              'compute_type': 'int8', 'vad_filter': True, 'word_timestamps': True,
              'condition_on_previous_text': False, 'context_seconds': CONTEXT_SECONDS, 'max_gap': MAX_GAP}
    started = time.perf_counter()
    metrics = {'elapsed_s': 0.0, 'inference_s': 0.0, 'model_load_s': 0.0,
               'central_audio_s_processed': 0.0, 'context_audio_s_processed': 0.0}
    manifest = {'tool': TOOL, 'version': VERSION, 'status': 'partial', 'selection': selection,
                'config': config, 'eligible_audio': len(selected), 'attempted': 0,
                'completed': 0, 'cache_hits': 0, 'deferred': 0, 'failures': [],
                'metrics': metrics, 'allow_download': allow_download, 'limit': limit}
    candidates = []

    def save():
        metrics['elapsed_s'] = round(time.perf_counter() - started, 6)
        _atomic(output_dir / 'candidates.jsonl', ''.join(_json(candidate) + '\n' for candidate in candidates))
        _atomic(manifest_path, _json(manifest) + '\n')

    # Establish provenance before expensive I/O so interruption remains resumable.
    _atomic(manifest_path, _json(manifest) + '\n')
    info, reader = audio_info or _audio_info, audio_reader or _audio_reader
    chunks, catalog_errors = [], {}
    for path in sorted(audio_dir.glob('*.flac')):
        match = FILENAME.fullmatch(path.name)
        if not match:
            continue
        try:
            path = _safe_audio(audio_dir, path.name)
            duration = info(path)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError('invalid audio duration')
            chunks.append(Chunk(path, float(match[1]), match[2], duration))
        except Exception as exc:
            catalog_errors[path] = type(exc).__name__ + ': ' + str(exc)
    catalog = {chunk.path: chunk for chunk in chunks}
    hashes = {}
    model_error = None
    for path in sorted(selected, key=lambda value: (float(FILENAME.fullmatch(value.name)[1]), value.name)):
        try:
            if path not in catalog:
                raise ValueError(catalog_errors.get(path, 'selected audio is missing'))
            target = catalog[path]
            pieces, start, end = context_window(target, chunks)
            audio_hashes = []
            for chunk, begin, finish in pieces:
                if chunk.path not in hashes:
                    hashes[chunk.path] = _hash_file(chunk.path)
                audio_hashes.append([chunk.path.name, hashes[chunk.path], begin, finish])
            source_ids = sorted(set(grouped[path]))
            key = hashlib.sha256(_json({'config': config, 'audio': audio_hashes,
                                       'source_ids': source_ids}).encode('utf-8')).hexdigest()
            checkpoint = checkpoints / (key + '.json')
            cached = None
            if checkpoint.is_file():
                try:
                    cached = json.loads(checkpoint.read_text(encoding='utf-8'))
                except (ValueError, OSError):
                    pass
            if cached and cached.get('key') == key and cached.get('candidate', {}).get('id') == 'reprocess:' + key:
                candidates.append(cached['candidate'])
                manifest['cache_hits'] += 1
                manifest['completed'] += 1
                continue
            if limit is not None and manifest['attempted'] >= limit:
                manifest['deferred'] += 1
                continue
            manifest['attempted'] += 1
            if model_error:
                raise RuntimeError(model_error)
            if recognizer is None:
                load_start = time.perf_counter()
                try:
                    recognizer = WhisperRecognizer(model, threads, terms, allow_download)
                except Exception as exc:
                    model_error = type(exc).__name__ + ': ' + str(exc)
                    raise
                finally:
                    metrics['model_load_s'] += time.perf_counter() - load_start
            samples = _assemble(pieces, start, end, reader)
            inference_start = time.perf_counter()
            try:
                candidate = _candidate(recognizer(samples), target, start, source_ids, key,
                                       [chunk.path.name for chunk, _, _ in pieces])
            finally:
                metrics['inference_s'] += time.perf_counter() - inference_start
            _atomic(checkpoint, _json({'key': key, 'candidate': candidate}) + '\n')
            candidates.append(candidate)
            manifest['completed'] += 1
            metrics['central_audio_s_processed'] += target.duration
            metrics['context_audio_s_processed'] += end - start
        except Exception as exc:
            manifest['failures'].append({'source_audio': path.name,
                                         'error': type(exc).__name__ + ': ' + str(exc)})
        save()
    if manifest['completed'] == len(selected):
        manifest['status'] = 'complete'
    elif manifest['failures'] and not manifest['completed'] and not manifest['deferred']:
        manifest['status'] = 'failed'
    save()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio-dir', required=True)
    parser.add_argument('--events', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--model', default='small')
    parser.add_argument('--selection', choices=['low-confidence', 'all'], default='low-confidence')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--glossary')
    parser.add_argument('--allow-download', action='store_true')
    args = parser.parse_args()
    try:
        result = run(**vars(args))
    except Exception as exc:
        parser.exit(1, type(exc).__name__ + ': ' + str(exc) + '\n')
    print(_json(result))
    return 1 if result['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
