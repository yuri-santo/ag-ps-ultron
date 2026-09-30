"""Evidence binding and cut audio envelopes for the existing affiliate renderer."""
import json
import math
from pathlib import Path

from media_preflight import run_preflight, sha256, write_report


def voice_filter(duration):
    duration = float(duration)
    if not math.isfinite(duration) or duration <= 0.06:
        raise ValueError('Invalid voice duration')
    return ('aresample=48000,afade=t=in:st=0:d=0.03,'
            f'afade=t=out:st={duration - 0.03:.6f}:d=0.03')


def check_render(video, expected_duration):
    video = Path(video)
    report = run_preflight(video, expected_duration=expected_duration)
    target = video.parent / 'media-preflight.json'
    write_report(report, target)
    if report.get('technical_pass') is not True:
        raise ValueError('Technical preflight failed; inspect media-preflight.json')
    return {'sha256': sha256(target), 'video_sha256': report['sha256'],
            'warnings': report['warnings'], 'visual_approval': 'not_reviewed'}


def require_preflight(video, receipt):
    binding = receipt.get('preflight')
    if not isinstance(binding, dict):
        raise ValueError('Render requires technical preflight; preserve old version and re-render')
    video = Path(video)
    target = video.parent / 'media-preflight.json'
    if not target.is_file() or sha256(target) != binding.get('sha256'):
        raise ValueError('Preflight evidence missing or changed')
    report = json.loads(target.read_text())
    digest = sha256(video)
    if (report.get('technical_pass') is not True or report.get('full_decode_passed') is not True
            or report.get('sha256') != digest or binding.get('video_sha256') != digest):
        raise ValueError('Preflight does not approve the current media bytes')
    return report
