"""Validate visual-review evidence bindings, never infer visual truth or authorize posting."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


CHECKS = ('item', 'packaging', 'labels', 'colors', 'shape', 'accessories', 'scale')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')


class ProductIdentityError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise ProductIdentityError(message)


def _object(value, label):
    _require(isinstance(value, dict), label + ' must be an object')
    return value


def _text(value, label, notes=False):
    _require(isinstance(value, str) and bool(value.strip()), label + ' is required')
    _require(not re.search(r'preencher|placeholder|\btodo\b|\btbd\b', value, re.I),
             label + ' contains a placeholder')
    if notes:
        _require(len(value.strip()) >= 24 and len(re.findall(r'\w+', value)) >= 5,
                 label + ' must describe observed distinguishing details')
    return value


def _number(value, label):
    _require(type(value) in (int, float) and math.isfinite(value), label + ' must be finite')
    return value


def _url(value):
    _text(value, 'source URL')
    parsed = urlsplit(value)
    _require(parsed.scheme == 'https' and bool(parsed.hostname)
             and parsed.username is None and parsed.password is None
             and not any(c.isspace() for c in value), 'source URL must be HTTPS without credentials')


def _fresh(value, now, label):
    _text(value, label)
    checked = dt.datetime.fromisoformat(value)
    _require(checked.tzinfo is not None and 0 <= (now - checked).total_seconds() <= 86400,
             label + ' must be timezone-aware and within the last 24 hours')


def _path(value, root=None):
    _require(isinstance(value, (str, Path)), 'artifact path must be a local absolute path')
    path = Path(value)
    _require(path.is_absolute() and '..' not in path.parts, 'relative/traversal artifact path refused')
    _require(not any(part.is_symlink() for part in (path, *path.parents)), 'symlink artifact path refused')
    resolved = path.resolve(strict=True)
    _require(resolved.is_file() and resolved.stat().st_size > 0, 'artifact must be a nonempty regular file')
    if root is not None:
        _require(resolved.is_relative_to(root), 'artifact outside campaign directory')
    return resolved


def _digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def _json(path):
    return _object(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_pairs), str(path))


class _Evidence:
    def __init__(self, root):
        self.root = root
        self.artifacts = {}

    def file(self, binding, expected=None):
        binding = _object(binding, 'artifact binding')
        digest = binding.get('sha256')
        _require(isinstance(digest, str) and SHA256.fullmatch(digest), 'invalid SHA-256 binding')
        path = _path(binding.get('path'), self.root)
        if expected is not None:
            _require(path == _path(expected, self.root), 'artifact path differs from current input')
        _require(_digest(path) == digest, 'artifact missing or changed: ' + str(path))
        self.artifacts[str(path)] = {'path': str(path), 'sha256': digest}
        return path


def require_product_identity(brief, quality, video_path, manifest_path=None, *, now=None):
    """Return verified artifact bindings or raise ValueError; broker review remains mandatory.

    ``brief`` is its current path or parsed object (compared to the bound brief file).
    ``quality.product_identity`` must hash-bind the manifest, even with an explicit path.
    All evidence is local to the campaign directory containing the brief.
    """
    try:
        return _validate(brief, quality, video_path, manifest_path, now)
    except ProductIdentityError:
        raise
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise ProductIdentityError('Invalid or unavailable product identity evidence: ' + str(exc)) from exc


def _validate(brief, quality, video_path, manifest_path, now):
    now = now or dt.datetime.now(dt.timezone.utc)
    _object(quality, 'quality')
    binding = _object(quality.get('product_identity'), 'quality.product_identity')
    manifest_file = _path(binding.get('path'))
    manifest = _json(manifest_file)
    brief_binding = _object(manifest.get('brief'), 'manifest.brief')
    brief_file = _path(brief_binding.get('path'))
    evidence = _Evidence(brief_file.parent)
    evidence.file(binding, manifest_path or manifest_file)
    evidence.file(brief_binding, brief_file if isinstance(brief, dict) else brief)
    current = _json(brief_file)
    if isinstance(brief, dict):
        _require(current == brief, 'brief object differs from current brief file')
    product = _object(current.get('product'), 'brief.product')
    _require(type(product.get('packaging_required')) is bool, 'explicit packaging_required policy missing')
    _require(type(manifest.get('version')) is int and manifest['version'] == 1, 'unsupported identity version')
    for key, value in (('campaign_id', current.get('campaign_id')),
                       ('canonical_product_id', product.get('canonical_product_id')),
                       ('variant', product.get('variant'))):
        _text(value, key)
        _require(manifest.get(key) == value, key + ' differs from brief')
    _text(manifest.get('reviewer'), 'reviewer')
    _require(manifest.get('method') == 'visual_comparison', 'real visual comparison record required')
    _fresh(manifest.get('checked_at'), now, 'visual review date')
    video_file = evidence.file(manifest.get('video'), video_path)
    _require(quality.get('video_sha256') == manifest['video']['sha256'], 'quality/video mismatch')

    references = _object(current.get('facts'), 'facts').get('identity_references')
    _require(isinstance(references, list) and len(references) > 0, 'official reference images required')
    _require(manifest.get('references') == references, 'references differ from pinned brief references')
    seen_references = set()
    for reference in references:
        reference_file = evidence.file(reference)
        _require(reference_file.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'), 'reference must be an image file')
        _require(reference_file not in seen_references, 'duplicate official reference')
        seen_references.add(reference_file)
        _url(reference.get('source_url'))
        source = _json(evidence.file(reference.get('source_receipt')))
        for key in ('canonical_product_id', 'variant'):
            _require(source.get(key) == product[key], 'official source receipt identity mismatch')
        _require(source.get('source_url') == reference['source_url']
                 and source.get('image_sha256') == reference['sha256'], 'official source/image binding mismatch')
        _require(source.get('authority') in ('manufacturer', 'official_store'), 'official source authority required')
        _fresh(source.get('checked_at'), now, 'official reference date')
        _text(source.get('observation'), 'official source observation', notes=True)

    render_file = evidence.file(manifest.get('render_receipt'), video_file.parent / 'render-receipt.json')
    render = _json(render_file)
    _require(render.get('brief_sha256') == brief_binding['sha256']
             and render.get('video_sha256') == manifest['video']['sha256'], 'render brief/video binding mismatch')
    _require(_path(render.get('path'), evidence.root) == video_file, 'render points to different video')
    duration = _number(render.get('duration'), 'render duration')
    scenes, reviews, segments = current.get('scenes'), manifest.get('scenes'), render.get('segments')
    _require(isinstance(scenes, list) and len(scenes) > 0 and isinstance(reviews, list)
             and isinstance(segments, list) and len(scenes) == len(reviews) == len(segments),
             'every rendered scene needs identity evidence')
    previous_start = -1
    previous_end = 0
    used_frames = set()
    for index, (scene, review, segment) in enumerate(zip(scenes, reviews, segments), 1):
        _object(scene, 'scene')
        _object(review, 'scene review')
        _object(segment, 'render segment')
        _require(type(review.get('scene_id')) is int and review['scene_id'] == index, 'scene review order mismatch')
        _require(segment.get('scene') == scene, 'render segment differs from brief scene')
        scene_file = evidence.file(review.get('source'), scene.get('path'))
        _require(review['source']['sha256'] == scene.get('sha256'), 'source scene differs from brief hash')
        _require(bool(scene.get('generation_receipt')), 'brief must pin generation receipt path')
        receipt_file = evidence.file(review.get('generation_receipt'), scene.get('generation_receipt'))
        receipt = _json(receipt_file)
        _require(_path(receipt.get('path'), evidence.root) == scene_file
                 and receipt.get('sha256') == scene['sha256'], 'generation receipt source mismatch')
        _url(receipt.get('project_url'))
        _text(receipt.get('job_id'), 'generation job')
        _require(receipt.get('reference_attached') is True, 'generation reference attachment missing')
        start = _number(segment.get('start'), 'segment start')
        length = _number(segment.get('duration'), 'segment duration')
        end = start + length
        _require(length > 0 and 0 <= start < end <= duration + 0.05 and start > previous_start,
                 'invalid render timeline')
        _require(start <= previous_end + 0.05, 'unreviewed gap in render timeline')
        previous_start, previous_end = start, end
        frames = review.get('frames')
        _require(isinstance(frames, list) and len(frames) >= 3, 'inspect beginning, middle and end of each scene')
        times = []
        for frame in frames:
            frame_file = evidence.file(frame)
            _require(frame_file not in seen_references, 'official reference cannot substitute a video frame')
            _require(frame_file.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'), 'evidence frame must be an image')
            _require(frame_file not in used_frames, 'each inspected timestamp needs a distinct frame file')
            used_frames.add(frame_file)
            timestamp = _number(frame.get('timestamp'), 'frame timestamp')
            _require(start <= timestamp <= end, 'frame timestamp outside final-video scene')
            times.append(timestamp)
        _require(times == sorted(set(times)), 'frame timestamps must be unique and increasing')
        edge = min(0.5, length / 4)
        _require(times[0] <= start + edge and times[-1] >= end - edge
                 and any(start + length / 3 <= t <= start + 2 * length / 3 for t in times),
                 'scene beginning, middle or end not inspected')
        checks = _object(review.get('checks'), 'scene checks')
        for key in CHECKS:
            check = _object(checks.get(key), key + ' check')
            allowed = ('match', 'not_visible') if key == 'packaging' and not product['packaging_required'] else ('match',)
            _require(check.get('status') in allowed, key + ' is unknown, mismatched or not visible')
            _text(check.get('notes'), key + ' observations', notes=True)
    _require(abs(previous_end - duration) <= 0.05, 'final rendered interval is not reviewed')
    return {'status': 'evidence_validated', 'visual_truth_verified': False, 'manifest': manifest,
            'artifacts': list(evidence.artifacts.values())}
