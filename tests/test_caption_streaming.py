"""Completed caption display and bounded concurrency under a stalled translation."""
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from caption_translation import CaptionPresenter, translate


class CaptionStreamingTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(
            content_language=lambda _: 'bilingual', locale=SimpleNamespace(language='zh'),
            closing=False, follow_live=True, live_dirty=False, events=queue.Queue(),
            caption_models=SimpleNamespace(inputs=lambda: ({'key': ''}, None)), status=Mock())
        self.presenter = CaptionPresenter(self.app)
        self.release = threading.Event()
        self.addCleanup(self.release.set)
        self.addCleanup(self.presenter.close)

    def receive(self, expected):
        kind, payload = self.app.events.get(timeout=3)
        while kind == 'usage_updated':
            kind, payload = self.app.events.get(timeout=3)
        self.assertEqual(kind, expected)
        self.presenter.receive(payload)
        return payload

    def test_chinese_only_appears_after_entire_translation_finishes(self):
        started = threading.Event()
        inputs = dict(provider='Kimi', model='fixture', key='', options={'lm_base': ''},
                      effort='自动', display_model='fixture')
        self.app.caption_models.inputs = lambda: (inputs, None)
        self.app.token_ledger = Mock()
        self.app.session_id = 'fixture'
        def slow(*args, **kwargs):
            emit = args[6]
            emit('你好')
            started.set()
            self.release.wait(3)
            emit('世界')
        with patch('audio_answer.compatible_answer', side_effect=slow):
            self.presenter.body('Hello world')
            self.assertTrue(started.wait(3))
            self.assertEqual(self.presenter.body('Hello world'), 'Hello world\n正在翻译…')
            self.assertFalse(self.app.live_dirty)
            self.assertTrue(self.app.events.empty())
            self.assertNotIn(('bilingual', 'Hello world'), self.presenter.cache)
            self.release.set()
            self.receive('caption_result')
            self.assertEqual(self.presenter.body('Hello world'), 'Hello world\n中文：你好世界')
            self.assertTrue(self.app.live_dirty)

    def test_stalled_first_segment_does_not_block_later_segments(self):
        started = queue.Queue()
        def slow(inputs, text, language, cancel, app):
            started.put(text)
            if text == 'First':
                self.release.wait(3)
            return '译文' + text
        with patch('caption_translation.translate', side_effect=slow):
            for text in ('First', 'Second', 'Third', 'Fourth'):
                self.presenter.body(text)
            self.assertEqual({started.get(timeout=3) for _ in range(3)}, {'First', 'Second', 'Third'})
            self.assertEqual(len(self.presenter.workers), 3)
            self.assertEqual(len(self.presenter.queue), 1)
            self.receive('caption_result')
            self.assertEqual(started.get(timeout=3), 'Fourth')
            self.assertIn(('bilingual', 'First'), self.presenter.workers)
            self.release.set()
            for _ in range(3):
                self.receive('caption_result')
            self.assertFalse(self.presenter.pending)
            self.assertFalse(self.presenter.queue)
            self.assertEqual(len(self.presenter.cache), 4)

    def test_close_cancels_every_worker_and_ignores_late_updates(self):
        key = ('bilingual', 'Hello')
        cancels = [threading.Event() for _ in range(3)]
        self.presenter.workers = {(key[0], str(i)): event for i, event in enumerate(cancels)}
        epoch = self.presenter.epoch
        self.presenter.close()
        self.assertTrue(all(event.is_set() for event in cancels))
        self.presenter.receive((epoch, key, '过时', None))
        self.assertFalse(self.presenter.cache)

    def test_language_switch_keeps_all_inflight_requests_deduplicated(self):
        keys = [('bilingual', text) for text in ('One', 'Two', 'Three')]
        self.presenter.workers = {key: threading.Event() for key in keys}
        self.presenter.pending = set(keys)
        self.presenter.reset()
        with patch.object(self.presenter, 'start_next') as start:
            for _, text in keys:
                self.presenter.body(text)
            start.assert_not_called()
        self.assertEqual(self.presenter.pending, set(keys))

    def test_backlog_gives_new_speech_a_slot_without_dropping_old_speech(self):
        started = queue.Queue()
        def slow(inputs, text, language, cancel, app):
            started.put(text)
            self.release.wait(3)
            return '译文' + text
        with patch('caption_translation.translate', side_effect=slow):
            for text in ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven'):
                self.presenter.body(text)
            self.assertEqual({started.get(timeout=3) for _ in range(3)}, {'One', 'Two', 'Three'})
            # Free slots deterministically while the workers are held at the provider.
            for text, expected in [('One', 'Four'), ('Two', 'Five'), ('Three', 'Seven')]:
                self.presenter.receive((self.presenter.epoch, ('bilingual', text), '译文', None))
                self.assertEqual(started.get(timeout=3), expected)
            self.assertEqual(list(self.presenter.queue), [('bilingual', 'Six')])
            self.presenter.close()
            self.release.set()

    def test_out_of_order_results_remain_in_transcript_order(self):
        records = [dict(source='电脑', body=text, text='[12:00:00 电脑]\n' + text)
                   for text in ('First.', 'Second.')]
        self.app.live = SimpleNamespace(lock=threading.Lock(), records=records)
        from live_transcription import append_transcript
        original, source = '', None
        for record in records:
            original, source = append_transcript(original, source, record)
        self.app.locale.t = lambda text: text
        self.presenter.workers = {('bilingual', text): threading.Event() for text in ('First.', 'Second.')}
        self.presenter.receive((0, ('bilingual', 'Second.'), 'Second.\n中文：第二', None))
        self.presenter.receive((0, ('bilingual', 'First.'), 'First.\n中文：第一', None))
        result = self.presenter.transcript(original)
        self.assertLess(result.index('第一'), result.index('第二'))
        self.assertEqual([record['body'] for record in records], ['First.', 'Second.'])

    def test_transport_buffers_chunks_and_returns_complete_translation(self):
        app = SimpleNamespace(token_ledger=Mock(), session_id='fixture', events=queue.Queue())
        inputs = dict(provider='Kimi', model='fixture', key='', options={'lm_base': ''},
                      effort='自动', display_model='fixture')
        def answer(*args, **kwargs):
            emit = args[6]
            emit('你')
            self.assertTrue(app.events.empty())
            emit('好')
            self.assertTrue(app.events.empty())
        with patch('audio_answer.compatible_answer', side_effect=answer):
            self.assertEqual(translate(inputs, 'Hello', 'zh', threading.Event(), app), '你好')

    def test_completed_caption_event_reaches_the_controller(self):
        from audio_answer import App
        controller = SimpleNamespace(captions=self.presenter)
        key = ('bilingual', 'Hello')
        self.presenter.workers[key] = threading.Event()
        App.handle_event(controller, 'caption_result', (0, key, 'Hello\n中文：你好！', None))
        self.assertEqual(self.presenter.body('Hello'), 'Hello\n中文：你好！')

    def test_failure_preserves_original_and_frees_slot(self):
        key = ('bilingual', 'Hello')
        self.presenter.workers[key] = threading.Event()
        self.presenter.receive((0, key, '', 'Network error'))
        self.assertIn('Hello', self.presenter.body('Hello'))
        self.assertIn('翻译失败', self.presenter.body('Hello'))
        self.assertFalse(self.presenter.workers)


if __name__ == '__main__':
    unittest.main()
