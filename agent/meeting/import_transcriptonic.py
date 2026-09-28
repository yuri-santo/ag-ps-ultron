'''Offline adapter for Transcriptonic advanced webhook JSON (Python 3.10+).

Usage: python agent/meeting/import_transcriptonic.py webhook.json --output meeting.json
Reads a saved webhook body, not the extension's human-readable TXT download.
The result is input for render_report.build_minutes. It does not transcribe audio,
summarize, identify people, confirm decisions, execute content, or send data.

Contract reference: vivek-nexus/transcriptonic, extension/background-script/exporters.js
and extension/content-scripts/common-utils.js. Independently implemented adapter;
no upstream source code is bundled. Captions are platform labels, not diarization.
Capture timestamps denote observed caption blocks, not precise audio alignment.
'''

import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


ISO_TIMESTAMP = re.compile(
    r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)'
)


def _timestamp(value, field):
    if not isinstance(value, str) or not ISO_TIMESTAMP.fullmatch(value):
        raise ValueError(f'{field}: expected ISO timestamp with explicit timezone (Z or +/-HH:MM)')
    if value.endswith('-00:00'):
        raise ValueError(f'{field}: timestamp timezone -00:00 is unknown; provide a verified offset')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError(f'{field}: invalid ISO timestamp') from error
    return parsed


def _text(value, field):
    if not isinstance(value, str):
        raise ValueError(f'{field}: expected a string')
    return value


def _digest(value):
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def convert(payload):
    '''Convert structured caption data without promoting captured text to evidence of identity.'''
    if not isinstance(payload, dict) or payload.get('webhookBodyType') != 'advanced':
        raise ValueError('Use the Transcriptonic advanced webhook JSON; simple/TXT exports are ambiguous')
    start_raw = payload.get('meetingStartTimestamp')
    end_raw = payload.get('meetingEndTimestamp')
    start = _timestamp(start_raw, 'meetingStartTimestamp')
    end = _timestamp(end_raw, 'meetingEndTimestamp')
    if end < start:
        raise ValueError('meetingEndTimestamp: earlier than meetingStartTimestamp')
    title = _text(payload.get('meetingTitle'), 'meetingTitle')
    software = _text(payload.get('meetingSoftware'), 'meetingSoftware')
    transcript = payload.get('transcript')
    chat = payload.get('chatMessages', [])
    if not isinstance(transcript, list) or not isinstance(chat, list):
        raise ValueError('transcript and chatMessages must be arrays in the advanced webhook')

    session_id = 'transcriptonic-' + _digest([software, title, start_raw, end_raw])
    events, labels, rotulos, occurrences = [], [], {}, {}
    for collection, rows, content_field in [('transcript', transcript, 'transcriptText'),
                                             ('chatMessages', chat, 'chatMessageText')]:
        for index, row in enumerate(rows):
            field = f'{collection}[{index}]'
            if not isinstance(row, dict):
                raise ValueError(f'{field}: expected an object')
            name = _text(row.get('personName'), field + '.personName')
            content = _text(row.get(content_field), field + '.' + content_field)
            when = _timestamp(row.get('timestamp'), field + '.timestamp')
            if not start <= when <= end:
                raise ValueError(f'{field}.timestamp: outside the meeting interval; verify the source')
            if collection == 'chatMessages':
                continue
            label = name if name.strip() else 'Participante nao identificado'
            fingerprint = _digest([session_id, row['timestamp'], name, content])
            occurrences[fingerprint] = occurrences.get(fingerprint, 0) + 1
            event_id = f'tc-{fingerprint}-{occurrences[fingerprint]}'
            if label not in labels:
                labels.append(label)
            rotulos[event_id] = label + ' (rotulo da plataforma; identidade nao verificada)'
            events.append({
                'id': event_id, 'at': row['timestamp'], 'channel': 'captions', 'text': content,
                'speaker_label': label, 'identity_verified': False, 'capture_source': 'transcriptonic',
            })

    return {
        'session': {'id': session_id, 'title': title, 'created': start_raw, 'ended': end_raw,
                    'state': {'meeting': {'subject': title, 'start': start_raw, 'location': software}}},
        'ended_at': end_raw,
        'transcript_events': events,
        'speakers': {'source': 'platform_captions', 'identity_verified': False,
                     'vozes': 0, 'labels': labels, 'rotulos': rotulos},
        'records': [],
        'chat_messages': copy.deepcopy(chat),
        'source_payload': copy.deepcopy(payload),
        'provenance': {
            'source': 'transcriptonic', 'format': 'advanced_webhook',
            'timestamp_basis': 'caption_capture_time', 'identity_verified': False,
            'audio_available': False, 'chat_in_transcript': False,
            'warnings': [
                'Nomes sao rotulos da plataforma, nao identificacao pessoal verificada.',
                'Legendas podem conter erros; nao substituem a verificacao do audio.',
                'Chat preservado separadamente em chat_messages e source_payload.',
            ],
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Saved advanced webhook JSON (UTF-8)')
    parser.add_argument('--output', required=True, type=Path, help='New output JSON; existing files are refused')
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding='utf-8-sig'))
        output = json.dumps(convert(payload), ensure_ascii=False, indent=2) + '\n'
        with args.output.open('x', encoding='utf-8') as destination:
            destination.write(output)
    except FileExistsError:
        parser.exit(2, 'error: output exists; choose a new output path\n')
    except (OSError, ValueError) as error:
        parser.exit(2, f'error: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
