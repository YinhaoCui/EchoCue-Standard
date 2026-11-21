"""AnswerRunner runs without the Tk application: every dependency is passed in."""

import queue
import threading
import unittest
from unittest.mock import MagicMock, patch

import app_log
import providers
from answer_runner import AnswerRunner


def inputs(**changes):
    values = dict(
        provider='Kimi',
        key='secret-key-123456',
        model='kimi-k2.6',
        display_model='kimi-k2.6',
        options={'lm_base': '', 'thinking_policy': '自动', 'incremental_context': 'on'},
        effort='自动',
        timeout=30,
        images=[],
        analysis=False,
        context_version=1,
        reasoning=False,
        fast=False,
        output_limit=None,
        profile='',
        documents='',
        summary='',
        history=[],
        context_records=[],
        terms='',
        instructions='',
    )
    values.update(changes)
    return values


class AnswerRunnerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = MagicMock()
        self.events = queue.Queue()
        self.runner = AnswerRunner(
            live=MagicMock(), generation_lanes=MagicMock(), token_ledger=self.ledger, events=self.events, session_id='s'
        )
        self.sent = []

    def run_with(self, answer, data=None):
        with patch.object(providers, 'answer', side_effect=answer):
            self.runner.run(
                data or inputs(),
                'What is a queue?',
                0,
                threading.Event(),
                lambda kind, value: self.sent.append((kind, value)),
                {'start': 0.0},
                lambda: 'job',
            )
        return dict((kind, value) for kind, value in self.sent if kind in ('state', 'completed', 'done'))

    def test_streams_text_completes_and_records_usage(self):
        def answer(request):
            request.emit('A queue is FIFO.')
            request.on_usage({'output_tokens': 5})

        result = self.run_with(answer)
        self.assertEqual(result['state'], '已完成')
        self.assertEqual(result['completed'][3], 'A queue is FIFO.')
        self.assertIn(('usage', {'output_tokens': 5}), self.sent)
        record = self.ledger.record.call_args.args
        self.assertEqual((record[0], record[1], record[4]), ('s:job', 'Kimi', '完成'))
        self.assertEqual(self.events.get_nowait(), ('usage_updated', ''))

    def test_failure_keeps_partial_text_and_hides_the_key(self):
        def answer(request):
            request.emit('partial')
            raise RuntimeError('bad key secret-key-123456')

        with self.assertLogs('ai_listener.answers', 'WARNING') as logs:
            result = self.run_with(answer)
        self.assertEqual(result['state'], '失败，可重试')
        texts = [value for kind, value in self.sent if kind == 'text']
        self.assertEqual(texts[0], 'partial')
        self.assertIn('[KEY]', texts[-1])
        # The log file's formatter redacts the whole record, traceback included.
        written = app_log.RedactingFormatter().format(logs.records[0])
        self.assertIn('Traceback', written)
        self.assertNotIn('secret-key-123456', texts[-1] + written)
        self.assertEqual(self.ledger.record.call_args.args[4], '失败/未完成')


if __name__ == '__main__':
    unittest.main()
