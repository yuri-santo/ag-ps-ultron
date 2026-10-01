"""Synthetic regression coverage; no microphones, private records or delivery."""
import ast
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import render_report
import patch_capture_stop


RUNTIME = '''import time
class Copilot:
    async def _launch(self, sid):
        self.store.update(sid,capture_stop_confirmed=False)
    async def ingest(self, sid, event):
        kind = event.get('kind')
        if kind=='stopped':
            if not event.get('replayed'):
                self.store.update(sid,pending_audio=event.get('pending',0),capture_stop_confirmed=True)
    async def finish(self, sid):
        await self._diarizar(sid)
        payload = {'ended_at':time.time()}
        return payload
'''

CAPTURE = '''import time
def run(args):
    acquisition_done = threading.Event()
    def capture(channel):
        blocks, started = [], None
        try:
            with context as recorder:
                recorder.read()
                blocks = [1]
                blocks, started = [], None
        except Exception as exc:
            raise
        finally:
            save(channel, blocks, started)
    capture('mic')
    capture('loopback')
    drain()
    notice('stopped', 'Captura encerrada e fila processada.',
           pending=len(list(spool.root.glob('*.wav'))))
'''


def transformed(kind, source):
    return getattr(patch_capture_stop, 'transform_' + kind)(source)


class CaptureStopTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = {}
        namespace = {}
        exec(transformed('runtime', RUNTIME), namespace)
        self.copilot = namespace['Copilot']()
        self.copilot.store = SimpleNamespace(
            get=lambda sid: {'state': dict(self.state)},
            update=lambda sid, **values: self.state.update(values))

        async def diarize(sid):
            return {}

        self.copilot._diarizar = diarize

    async def test_end_survives_slow_finalization(self):
        await self.copilot.ingest('s', {'kind': 'stopped', 'at': 200,
            'capture_ended_at': 100, 'capture_ended_at_source': 'capture_streams_closed'})
        payload = await self.copilot.finish('s')
        self.assertEqual(payload['ended_at'], 100)
        self.assertFalse(payload['ended_at_estimated'])
        self.assertEqual(payload['ended_at_source'], 'capture_streams_closed')

    async def test_legacy_stopped_is_only_an_estimate(self):
        await self.copilot.ingest('s', {'kind': 'stopped', 'at': 200})
        payload = await self.copilot.finish('s')
        self.assertEqual(payload['ended_at'], 200)
        self.assertTrue(payload['ended_at_estimated'])
        self.assertEqual(payload['ended_at_source'], 'stopped_after_queue_drain')

    async def test_no_timestamp_stays_unknown(self):
        await self.copilot.ingest('s', {'kind': 'stopped'})
        self.assertIsNone((await self.copilot.finish('s'))['ended_at'])

    async def test_replayed_stop_does_not_replace_current_end(self):
        await self.copilot.ingest('s', {'kind': 'stopped', 'at': 200})
        await self.copilot.ingest('s', {'kind': 'stopped', 'at': 50, 'replayed': True})
        self.assertEqual((await self.copilot.finish('s'))['ended_at'], 200)

    async def test_launch_clears_previous_capture_end(self):
        await self.copilot.ingest('s', {'kind': 'stopped', 'at': 200})
        await self.copilot._launch('s')
        self.assertIsNone((await self.copilot.finish('s'))['ended_at'])

    async def test_invalid_or_unproven_end_stays_unknown(self):
        for value, source in [(float('nan'), 'capture_streams_closed'),
                              (float('inf'), 'capture_streams_closed'),
                              (True, 'capture_streams_closed'),
                              (300, 'capture_streams_closed'), (100, 'unknown')]:
            with self.subTest(value=value, source=source):
                await self.copilot.ingest('s', {'kind': 'stopped', 'at': 200,
                    'capture_ended_at': value, 'capture_ended_at_source': source})
                payload = await self.copilot.finish('s')
                self.assertIsNone(payload['ended_at'])
                self.assertEqual(payload['ended_at_source'], 'unknown')


class CaptureSourceTests(unittest.TestCase):
    def test_stream_closure_is_recorded_before_save_and_asr_drain(self):
        now = [100]
        events = []

        class Recorder:
            def __enter__(self):
                return self

            def read(self):
                now[0] += 1

            def __exit__(self, *args):
                now[0] += 1

        def delay(*args):
            now[0] += 1000

        namespace = {'threading': SimpleNamespace(Event=lambda: None),
            'context': Recorder(), 'save': delay, 'drain': delay,
            'spool': SimpleNamespace(root=SimpleNamespace(glob=lambda _: [])),
            'notice': lambda *args, **kwargs: events.append(kwargs)}
        exec(transformed('capture', CAPTURE), namespace)
        namespace['time'] = SimpleNamespace(time=lambda: now[0])
        namespace['run'](None)
        self.assertEqual(events[0].get('capture_ended_at'), 1104)
        self.assertEqual(events[0].get('capture_ended_at_source'), 'capture_streams_closed')
        self.assertEqual(now[0], 3104)

    def test_transform_is_idempotent_and_rejects_unknown_layout(self):
        for kind, source in [('runtime', RUNTIME), ('capture', CAPTURE)]:
            first = transformed(kind, source)
            self.assertEqual(transformed(kind, first), first)
            ast.parse(first)
            with self.assertRaises(ValueError):
                transformed(kind, 'print("unknown")')

    def test_one_channel_cannot_confirm_capture_end(self):
        namespace = {'threading': SimpleNamespace(Event=lambda: None),
            'context': None, 'save': lambda *args: None, 'drain': lambda: None,
            'spool': SimpleNamespace(root=SimpleNamespace(glob=lambda _: []))}
        events = []
        namespace['notice'] = lambda *args, **kwargs: events.append(kwargs)
        source = CAPTURE.replace("    capture('mic')", '').replace("    capture('loopback')", '')
        exec(transformed('capture', source), namespace)
        namespace['run'](None)
        self.assertIsNone(events[0]['capture_ended_at'])

    def test_optional_installed_sources_are_parsed_read_only(self):
        for kind in ('runtime', 'capture'):
            path = os.environ.get('MEETING_' + kind.upper() + '_SOURCE')
            if not path:
                continue
            original = Path(path).read_bytes()
            first = transformed(kind, original.decode('utf-8'))
            self.assertEqual(transformed(kind, first), first)
            ast.parse(first)
            self.assertEqual(Path(path).read_bytes(), original)


class InstalledRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_installed_methods_preserve_end_through_report_payload(self):
        path = os.environ.get('MEETING_RUNTIME_SOURCE')
        if not path:
            self.skipTest('Set MEETING_RUNTIME_SOURCE for read-only installed-source coverage')
        tree = ast.parse(transformed('runtime', Path(path).read_text(encoding='utf-8')))
        copilot = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Copilot')
        copilot.body = [n for n in copilot.body if getattr(n, 'name', '') in ('ingest', 'finish')]
        finish = next(n for n in copilot.body if n.name == 'finish')
        # Exercise real ingestion/finalization up to payload construction; no subprocess or delivery.
        payload_index = next(i for i, n in enumerate(finish.body)
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'payload'
                                                 for t in n.targets))
        finish.body = finish.body[:payload_index + 1] + [ast.Return(value=ast.Name(id='payload', ctx=ast.Load()))]
        helper = next(n for n in tree.body if getattr(n, 'name', '') == '_capture_end_fields')
        module = ast.fix_missing_locations(ast.Module(body=[helper, copilot], type_ignores=[]))
        state = {}
        async def consolidate(sid):
            return {'summary': 'synthetic', 'records': [], 'rejected': 0}
        async def diarize(sid):
            return {}
        namespace = {'time': SimpleNamespace(time=lambda: 999999),
            'Consolidator': lambda *args: SimpleNamespace(run=consolidate),
            'resolve_scope': lambda *args: '', 'CLIENTS': {}}
        exec(compile(module, '<patched-installed-runtime>', 'exec'), namespace)
        instance = namespace['Copilot']()
        with tempfile.TemporaryDirectory() as directory:
            instance.store = SimpleNamespace(get=lambda _: {'state': dict(state)},
                update=lambda _, **values: state.update(values), add_event=lambda *args: True,
                transcript=lambda _: 'synthetic transcript', full_record=lambda _: 'synthetic full record',
                events=lambda _: [], session_dir=lambda _: Path(directory))
            instance.intelligence = SimpleNamespace(alerts=SimpleNamespace(list=lambda *args, **kwargs: []))
            instance.llm = None
            instance.settings = {}
            instance.event = lambda *args, **kwargs: None
            instance._diarizar = diarize
            await instance.ingest('synthetic', {'kind': 'stopped', 'at': 200,
                'capture_ended_at': 100, 'capture_ended_at_source': 'capture_streams_closed'})
            payload = await instance.finish('synthetic')
            self.assertEqual(payload['ended_at'], 100)
            self.assertEqual(payload['transcript'], 'synthetic transcript')
            self.assertEqual((Path(directory) / 'registro-integral.txt').read_text(), 'synthetic transcript')


class ReportEndTests(unittest.TestCase):
    def test_legacy_processing_timestamp_is_not_claimed_as_real_capture_end(self):
        minutes = render_report.build_minutes({'ended_at': 1789666354})
        self.assertIn('estimado', minutes['fim'])
        self.assertIn('origem', minutes['fim'])

    def test_queue_drain_is_labeled_as_estimated_notice(self):
        minutes = render_report.build_minutes({'ended_at': 1789666354,
            'ended_at_source': 'stopped_after_queue_drain', 'ended_at_estimated': True})
        self.assertIn('estimado', minutes['fim'])
        self.assertIn('fim real não confirmado', minutes['fim'])

    def test_verified_capture_end_remains_a_clock_time(self):
        minutes = render_report.build_minutes({'ended_at': 1789666354,
            'ended_at_source': 'capture_streams_closed', 'ended_at_estimated': False})
        self.assertRegex(minutes['fim'], r'^\d{2}:\d{2}$')

    def test_explicitly_unknown_end_does_not_fall_back_to_processing_time(self):
        minutes = render_report.build_minutes({'ended_at': None, 'ended_at_source': 'unknown',
            'session': {'state': {'ended': 1789666354}}})
        self.assertEqual(minutes['fim'], render_report.NAO_APURADO)


if __name__ == '__main__':
    unittest.main()
