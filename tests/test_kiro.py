import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import audio_answer as a
import kiro_support as k
from session_support import Cancelled

EVENTS = [
    {'type': 'runStarted', 'data': {'payloadSchema': 'acp'}},
    {'type': 'metadata', 'data': {'sessionId': 'fixture-session'}},
    {'type': 'sessionUpdate', 'data': {'sessionId': 'fixture-session', 'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Hel'}}}},
    {'type': 'sessionUpdate', 'data': {'sessionId': 'fixture-session', 'update': {'sessionUpdate': 'tool_call', 'content': {'type': 'text', 'text': 'IGNORED'}}}},
    {'type': 'sessionUpdate', 'data': {'sessionId': 'fixture-session', 'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'lo'}}}},
]


def fixture(tmp, events, check_stdin=None):
    """A stand-in CLI that records stdin and prints stream-json lines."""
    script = Path(tmp) / 'fake_kiro.py'
    stdin_file = Path(tmp) / 'stdin.txt'
    events_file = Path(tmp) / 'events.json'
    events_file.write_text(json.dumps(events), encoding='utf-8')
    script.write_text(
        'import sys,json\n'
        f'open({str(stdin_file)!r},"w",encoding="utf-8").write(sys.stdin.buffer.read().decode("utf-8"))\n'
        f'for e in json.load(open({str(events_file)!r},encoding="utf-8")):\n'
        '    print(json.dumps(e),flush=True)\n', encoding='utf-8')
    return [sys.executable, str(script)], stdin_file


class KiroTransportTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(k, '_forget')
        self.forget = patcher.start()
        self.addCleanup(patcher.stop)

    def run_events(self, events, **kwargs):
        args, stdin_file = fixture(self.tmp.name, events)
        pieces = []
        with patch.object(k, 'command', return_value=args):
            result = k.kiro_answer(self.tmp.name, 'Question?', 'fixture-model', threading.Event(), pieces.append, **kwargs)
        return result, pieces, stdin_file.read_text(encoding='utf-8')

    def test_streams_agent_text_and_sends_instructions_on_stdin(self):
        finished = {'type': 'runFinished', 'data': {'sessionId': 'fixture-session', 'status': 'success', 'finalText': 'Hello'}}
        result, pieces, stdin = self.run_events(EVENTS + [finished])
        self.assertEqual(result, 'Hello')
        self.assertEqual(pieces, ['Hel', 'lo'])
        self.assertIn('Do not use tools', stdin)
        self.assertTrue(stdin.rstrip().endswith('Question?'))

    def test_final_text_completes_partial_stream(self):
        finished = {'type': 'runFinished', 'data': {'status': 'success', 'finalText': 'Hello world'}}
        result, pieces, _ = self.run_events(EVENTS + [finished])
        self.assertEqual(result, 'Hello world')
        self.assertEqual(pieces[-1], ' world')

    def test_run_error_is_reported(self):
        error = {'type': 'runError', 'data': {'message': "The model 'x' is not available."}}
        with self.assertRaisesRegex(RuntimeError, 'not available'):
            self.run_events(EVENTS[:2] + [error])

    def test_exit_without_finish_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError, 'stopped without finishing'):
            self.run_events(EVENTS)

    def test_session_is_forgotten_after_answer(self):
        finished = {'type': 'runFinished', 'data': {'sessionId': 'fixture-session', 'status': 'success', 'finalText': 'Hello'}}
        self.run_events(EVENTS + [finished])
        self.forget.assert_called_once()
        self.assertEqual(self.forget.call_args.args[1], 'fixture-session')

    def test_cancel_before_start(self):
        cancel = threading.Event(); cancel.set()
        with self.assertRaises(Cancelled):
            k.kiro_answer(self.tmp.name, 'Q', '', cancel, lambda _: None)

    def test_command_disables_tools_and_validates_effort(self):
        with patch.object(k, 'find_kiro', return_value='kiro-cli'):
            args = k.command('claude-sonnet-5.5', 'high')
            self.assertIn('--trust-tools=', args)
            self.assertEqual(args[args.index('--agent') + 1], 'audio-qa')
            self.assertEqual(args[args.index('--model') + 1], 'claude-sonnet-5.5')
            self.assertEqual(args[args.index('--effort') + 1], 'high')
            self.assertNotIn('--model', k.command('', '自动'))
            self.assertNotIn('--effort', k.command('', '服务默认'))
            with self.assertRaises(ValueError):
                k.command('', '--trust-all-tools')

    def test_workspace_agent_has_no_tools(self):
        folder = k.workspace(self.tmp.name)
        agent = json.loads((folder / '.kiro/agents/audio-qa.json').read_text(encoding='utf-8'))
        self.assertEqual(agent['tools'], [])
        self.assertEqual(agent['mcpServers'], {})

    def test_catalog_parses_model_ids(self):
        raw = json.dumps({'models': [{'model_id': 'auto'}, {'model_id': 'claude-sonnet-5.5'}, {'model_id': 'auto'}, None, {}]})
        self.assertEqual(k.parse_catalog(raw), ['auto', 'claude-sonnet-5.5'])

    def test_provider_is_listed_with_reasoning_levels(self):
        from reasoning_support import choices
        self.assertIn(k.PROVIDER, a.SPECIAL_PROVIDERS)
        self.assertEqual(choices(k.PROVIDER, 'auto'), ['自动', '服务默认', 'low', 'medium', 'high', 'xhigh', 'max'])


class ResizeTests(unittest.TestCase):
    def test_resize_size_clamps_and_rejects_bad_values(self):
        from glass_desktop import resize_size, MIN_SIZE
        self.assertEqual(resize_size(1200.6, 900), (1200, 900))
        self.assertEqual(resize_size(10, 10), MIN_SIZE)
        self.assertEqual(resize_size(99999, 99999), (10000, 10000))
        for bad in (('x', 1), (float('nan'), 600), (None, 600), (float('inf'), 600)):
            self.assertIsNone(resize_size(*bad))


if __name__ == '__main__':
    unittest.main()
