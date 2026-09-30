"""Local technical evidence, never visual, factual or publication approval."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a measurement')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Measurement is not finite')
    return value


def run_preflight(path, expected_duration=None, duration_tolerance=0.5,
                  probe_timeout=30, decode_timeout=300, diagnostics_timeout=300):
    for timeout in (probe_timeout, decode_timeout, diagnostics_timeout):
        if not 0 < number(timeout) <= 3600:
            raise ValueError('Timeout must be within 0..3600 seconds')
    if number(duration_tolerance) < 0:
        raise ValueError('Tolerance must be nonnegative')
    if expected_duration is not None and number(expected_duration) <= 0:
        raise ValueError('Expected duration must be positive')
    source = Path(path).resolve()
    report = {'version': 1, 'path': str(source), 'sha256': None,
              'technical_pass': False, 'status': 'fail',
              'visual_approval': 'not_reviewed', 'errors': [], 'warnings': []}

    def run(args, timeout):
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                encoding='utf-8', errors='replace')
        if result.returncode:
            raise ValueError('Media command failed: ' + result.stderr[-1500:])
        return result

    try:
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError('Missing or empty source file')
        report['sha256'] = sha256(source)
        probe = json.loads(run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file',
                               '-show_streams', '-show_format', '-of', 'json', str(source)],
                              probe_timeout).stdout)
        streams = probe['streams']
        if not isinstance(streams, list) or not all(isinstance(s, dict) for s in streams):
            raise ValueError('Invalid stream metadata')
        video = next(s for s in streams if s.get('codec_type') == 'video'
                     and not s.get('disposition', {}).get('attached_pic'))
        audio = next(s for s in streams if s.get('codec_type') == 'audio')
        width, height = number(video['width']), number(video['height'])
        if min(width, height) <= 0:
            raise ValueError('Invalid dimensions')
        sar = video.get('sample_aspect_ratio', '1:1')
        numerator, denominator = map(number, sar.split(':'))
        if min(numerator, denominator) <= 0:
            raise ValueError('Invalid sample aspect ratio')
        ratio = width * numerator / denominator / height
        rotation = number(video.get('tags', {}).get('rotate', 0))
        for side in video.get('side_data_list', []):
            if 'rotation' in side:
                rotation = number(side['rotation'])
        if rotation % 180:
            ratio = 1 / ratio if abs(rotation) % 180 == 90 else 0
        if abs(ratio - 9 / 16) > 0.005:
            raise ValueError('Display aspect ratio must be portrait 9:16')
        duration = number(probe['format']['duration'])
        if duration <= 0:
            raise ValueError('Invalid media duration')
        if expected_duration is not None and abs(duration - expected_duration) > duration_tolerance:
            raise ValueError('Duration differs from edit plan')
        if not audio.get('codec_name') or number(audio['sample_rate']) <= 0:
            raise ValueError('Invalid audio metadata')
        report['metadata'] = {'width': width, 'height': height, 'duration': duration,
                              'audio_codec': audio['codec_name'], 'display_ratio': ratio}
        base = ['ffmpeg', '-nostdin', '-hide_banner', '-threads', '1',
                '-protocol_whitelist', 'file', '-i', str(source)]
        decoded = run(base + ['-v', 'error', '-xerror', '-progress', 'pipe:1',
                             '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'], decode_timeout)
        frames = re.findall(r'^frame=(\d+)', decoded.stdout, re.M)
        if 'progress=end' not in decoded.stdout or not frames or int(frames[-1]) <= 0:
            raise ValueError('Full decode did not finish with video frames')
        report['full_decode_passed'] = True
        diagnostic = run(base + ['-filter_threads', '1', '-vf',
                                'scale=180:320,blackdetect=d=0.3:pix_th=0.10,freezedetect=n=-50dB:d=2',
                                '-af', 'silencedetect=n=-45dB:d=0.5', '-f', 'null', '-'],
                         diagnostics_timeout)
        for code, marker in [('silence', 'silence_start:'), ('black', 'black_start:'),
                             ('freeze', 'freeze_start:')]:
            observations = [line.strip() for line in diagnostic.stderr.splitlines() if marker in line]
            if observations:
                report['warnings'].append({'code': code, 'requires_inspection': True,
                                           'observations': observations[:100]})
        if sha256(source) != report['sha256']:
            raise ValueError('Source changed during inspection')
        report.update(technical_pass=True, status='pass')
    except (OSError, ValueError, TypeError, KeyError, StopIteration,
            AttributeError, ZeroDivisionError, subprocess.SubprocessError) as exc:
        report['errors'].append(str(exc) or 'Required media stream is missing')
    return report


def write_report(report, path):
    target = Path(path).resolve()
    source = Path(report['path']).resolve()
    if target == source or (target.exists() and source.exists() and target.samefile(source)):
        raise ValueError('Report cannot overwrite source media')
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + '.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video')
    parser.add_argument('--output', required=True)
    parser.add_argument('--expected-duration', type=float)
    args = parser.parse_args()
    report = run_preflight(args.video, expected_duration=args.expected_duration)
    write_report(report, args.output)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['technical_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
