"""Realtime captions must stay current without losing finalized source speech."""
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app_paths
from caption_translation import CaptionPresenter


class RealtimeCaptionTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(
            content_language=lambda _: 'bilingual', locale=SimpleNamespace(language='zh', t=lambda x: x),
            closing=False, follow_live=True, live_dirty=False, events=queue.Queue(), root=Mock(),
            live_drafts={}, capture=SimpleNamespace(active=lambda: True), mic=SimpleNamespace(active=lambda: True),
            live=SimpleNamespace(lock=threading.RLock(), records=[], sources={}, submitted=0, completed=0),
            caption_models=SimpleNamespace(inputs=lambda: ({'key': ''}, None)), status=Mock())
        self.presenter = CaptionPresenter(self.app)
        self.addCleanup(self.presenter.close)

    def record(self, text, source='电脑'):
        record = dict(source=source, body=text, text='[12:00:00 ' + source + ']\n' + text,
                      sequence=len(self.app.live.records) + 1)
        self.app.live.records.append(record)
        return record

    def test_hard_deadline_flushes_while_other_recognition_is_pending(self):
        self.record('THANK YOU')
        self.app.live.submitted, self.app.live.completed = 2, 1
        with patch.object(self.presenter, 'start_next'), patch('caption_translation.time.monotonic', return_value=10):
            self.presenter.transcript(self.app.live.records[0]['text'])
        with patch.object(self.presenter, 'start_next'), patch('caption_translation.time.monotonic', return_value=11.6):
            self.presenter.transcript(self.app.live.records[0]['text'])
        self.assertIn(('bilingual', 'THANK YOU'), self.presenter.queue)
        self.assertEqual(self.app.live.records[0]['body'], 'THANK YOU')

    def test_deadline_is_not_extended_by_new_fragments(self):
        with patch('caption_translation.time.monotonic', return_value=10):
            self.presenter.record_batches([self.record('THE SERVER')])
        with patch('caption_translation.time.monotonic', return_value=11):
            self.record('IS READY')
            self.presenter.record_batches(self.app.live.records)
        with patch('caption_translation.time.monotonic', return_value=11.6):
            batches = self.presenter.record_batches(self.app.live.records)
        self.assertTrue(batches[0]['caption_ready'])

    def draft(self, text, now, source='电脑', generation=1):
        with patch('caption_translation.time.monotonic', return_value=now):
            return self.presenter.body(text, draft=True, source=source, generation=generation)

    def test_stable_draft_is_translated_before_asr_finalization(self):
        with patch.object(self.presenter, 'start_next'):
            self.draft('Please explain how this works', 10)
            self.draft('Please explain how this works in practice', 10.3)
            view = self.draft('Please explain how this works in practice', 10.6)
        key = ('bilingual', 'Please explain how this works')
        self.assertIn(key, self.presenter.pending)
        self.assertEqual(self.app.live.records, [])
        self.assertIn('Please explain how this works in practice', view)

    def test_new_drafts_replace_queued_preview_instead_of_growing_backlog(self):
        with patch.object(self.presenter, 'start_next'):
            self.draft('Please explain how this works', 10)
            self.draft('Please explain how this works', 10.6)
            self.draft('Please explain how this works in production', 11)
            self.draft('Please explain how this works in production', 11.7)
            self.draft('Please explain how this works in production today', 12)
            self.draft('Please explain how this works in production today', 12.8)
        self.assertLessEqual(len(self.presenter.preview_queue), 1)
        self.assertLessEqual(len(self.presenter.pending), 1)

    def test_final_request_promotes_identical_preview_and_keeps_partial(self):
        text = 'Please explain how this works'
        with patch.object(self.presenter, 'start_next'):
            self.draft(text, 10)
            self.draft(text, 10.6)
            self.presenter.body(text)
        key = ('bilingual', text)
        self.assertEqual(list(self.presenter.queue), [key])
        self.assertFalse(self.presenter.preview_queue)
        self.assertNotIn(key, self.presenter.preview_keys)

    def test_stale_preview_does_not_replace_new_generation(self):
        old = 'Please explain how this works'
        new = 'Tell me about the new system'
        with patch.object(self.presenter, 'start_next'):
            self.draft(old, 10)
            self.draft(old, 10.6)
            key = ('bilingual', old)
            self.presenter.workers[key] = threading.Event()
            self.draft(new, 11, generation=2)
            self.presenter.receive_partial((self.presenter.epoch, key, old + '\n中文：旧译文'))
            view = self.draft(new, 11.1, generation=2)
        self.assertIn(new, view)
        self.assertNotIn('旧译文', view)

    def test_slow_preview_still_shows_while_newer_text_waits(self):
        text = 'Please explain how this works'
        with patch.object(self.presenter, 'start_next'):
            self.draft(text, 10)
            self.draft(text, 10.6)
            key = ('bilingual', text)
            self.presenter.preview_queue.clear()
            self.presenter.workers[key] = threading.Event()
            self.draft(text + ' in production', 11)
            self.draft(text + ' in production', 11.7)
            self.presenter.receive_partial((self.presenter.epoch, key, text + '\n中文：请解释其工作方式'))
            view = self.draft(text + ' in production', 11.8)
        self.assertIn(text + ' in production', view)
        self.assertIn('暂译：请解释其工作方式', view)

    def test_newer_preview_is_not_overwritten_by_late_old_result(self):
        text = 'Please explain how this works'
        with patch.object(self.presenter, 'start_next'):
            self.draft(text, 10)
            self.draft(text, 10.6)
            old = ('bilingual', text)
            self.presenter.preview_queue.clear()
            self.presenter.workers[old] = threading.Event()
            self.draft(text + ' in production', 11)
            self.draft(text + ' in production', 11.7)
            new = ('bilingual', text + ' in production')
            self.presenter.preview_queue.clear()
            self.presenter.workers[new] = threading.Event()
            self.presenter.receive_partial((self.presenter.epoch, new, new[1] + '\n中文：新译文'))
            self.presenter.receive_partial((self.presenter.epoch, old, old[1] + '\n中文：旧译文'))
            view = self.draft(new[1], 11.8)
        self.assertIn('新译文', view)
        self.assertNotIn('旧译文', view)

    def test_at_most_two_previews_leave_capacity_for_finalized_speech(self):
        release, started = threading.Event(), queue.Queue()
        self.addCleanup(release.set)
        def translate(inputs, text, language, cancel, app, **kwargs):
            started.put(text)
            release.wait(2)
            return '译文'
        with patch('caption_translation.translate', side_effect=translate):
            for source in ('电脑', '麦克风', '第三来源'):
                self.draft('Please explain how this works ' + source, 10, source=source)
                self.draft('Please explain how this works ' + source, 10.6, source=source)
            first = [started.get(timeout=2) for _ in range(2)]
            self.assertTrue(started.empty())
            self.assertEqual(len(self.presenter.workers), 2)
            self.presenter.body('A final sentence.')
            self.assertEqual(started.get(timeout=2), 'A final sentence.')
            self.assertEqual(len(self.presenter.workers), 3)
            self.assertEqual(len(first), 2)
            self.presenter.close()
            release.set()

    def test_partial_failure_preserves_received_text_as_incomplete(self):
        key = ('bilingual', 'Hello')
        self.presenter.pending.add(key)
        self.presenter.workers[key] = threading.Event()
        self.presenter.receive_partial((self.presenter.epoch, key, 'Hello\n中文：你好'))
        self.presenter.receive((self.presenter.epoch, key, '', 'Connection lost'))
        view = self.presenter.body('Hello')
        self.assertIn('你好', view)
        self.assertIn('未完成', view)
        self.assertFalse(self.presenter.workers)

    def test_preview_window_is_bounded_but_final_translation_keeps_entire_source(self):
        text = 'This is a long continuous conversation. ' * 20
        text = text.strip()
        with patch.object(self.presenter, 'start_next'):
            self.draft(text, 10)
            self.draft(text, 10.6)
            self.assertLessEqual(len(self.presenter.preview_queue['电脑'][1]), 400)
            self.presenter.sync_previews({})
            self.presenter.body(text)
        self.assertEqual(list(self.presenter.queue), [('bilingual', text)])
        self.assertFalse(self.presenter.preview_queue)

    def test_partial_arriving_after_final_cannot_replace_completed_translation(self):
        key = ('bilingual', 'Hello')
        self.presenter.workers[key] = threading.Event()
        self.presenter.receive((self.presenter.epoch, key, 'Hello\n中文：完整译文', None))
        self.presenter.receive_partial((self.presenter.epoch, key, 'Hello\n中文：过时部分'))
        self.assertEqual(self.presenter.body('Hello'), 'Hello\n中文：完整译文')

    def test_live_controller_displays_preview_without_adding_it_to_final_records(self):
        from audio_answer import App
        self.app.captions = self.presenter
        self.app.live_text = ''
        text = 'Please explain how this works'
        self.app.live_drafts = {'电脑': dict(text=text, generation=1)}
        with patch.object(self.presenter, 'start_next'):
            with patch('caption_translation.time.monotonic', return_value=10):
                App.render_live_transcript(self.app)
            with patch('caption_translation.time.monotonic', return_value=10.6):
                App.render_live_transcript(self.app)
            key = ('bilingual', text)
            self.presenter.workers[key] = threading.Event()
            App.handle_event(self.app, 'caption_partial', (self.presenter.epoch, key, text + '\n中文：临时译文'))
            App.render_live_transcript(self.app)
        self.assertIn('暂译：临时译文', self.app.transcript_view)
        self.assertEqual(self.app.live_text, '')
        self.assertEqual(self.app.live.records, [])

    def test_corrected_recognition_restarts_stability_wait(self):
        with patch.object(self.presenter, 'start_next'):
            self.draft('Please explain how this works', 10)
            self.draft('Could you describe another system', 10.4)
            self.draft('Could you describe another system', 10.6)
            self.assertFalse(self.presenter.pending)
            self.draft('Could you describe another system', 11)
        self.assertEqual(list(self.presenter.preview_queue.values()),
                         [('bilingual', 'Could you describe another system')])

    def test_cached_translation_of_live_draft_is_still_marked_provisional(self):
        text = 'Please explain how this works'
        self.presenter.cache[('bilingual', text)] = text + '\n中文：解释一下'
        view = self.draft(text, 10)
        self.assertIn(text, view)
        self.assertIn('暂译：解释一下', view)
        self.assertFalse(self.presenter.pending)


if __name__ == '__main__':
    unittest.main()
