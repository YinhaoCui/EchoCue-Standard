"""Short ASR endpoints must be translated with their surrounding speech."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app_paths
from caption_translation import CaptionPresenter
from live_transcription import append_transcript
import test_sessions


class CaptionBatchingTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(
            content_language=lambda _: 'bilingual', locale=SimpleNamespace(language='zh', t=lambda text: text),
            closing=False, follow_live=True, live_dirty=False, live_drafts={},
            root=Mock(), capture=SimpleNamespace(active=lambda: True), mic=SimpleNamespace(active=lambda: False),
            live=SimpleNamespace(lock=threading.RLock(), records=[], sources={}, submitted=0, completed=0))
        self.presenter = CaptionPresenter(self.app)
        dispatch = patch.object(self.presenter, 'start_next')
        self.start = dispatch.start()
        self.addCleanup(dispatch.stop)
        self.addCleanup(self.presenter.close)

    def add(self, text, source='电脑', speaker=None):
        record = dict(source=source, body=text, text='[16:21:58 ' + source + ']\n' + text,
                      sequence=len(self.app.live.records) + 1)
        if speaker:
            record['speaker'] = speaker
        self.app.live.records.append(record)

    def render(self):
        text, source = '', None
        for record in self.app.live.records:
            text, source = append_transcript(text, source, record)
        return self.presenter.transcript(text)

    def test_single_word_endpoints_wait_and_become_one_translation(self):
        for fragment in ('THE OLD WOMAN', 'MISSUS', 'REPLIED THE INQUIRY', 'ANSWER'):
            self.add(fragment)
            view = self.render()
            self.assertIn(fragment, view)
            self.assertFalse(self.presenter.pending, 'Incomplete fragments must not be translated separately')
        self.add('WITH CLEAR CRITERIA FOR EACH ITEM.')
        self.render()
        combined = 'THE OLD WOMAN MISSUS REPLIED THE INQUIRY ANSWER WITH CLEAR CRITERIA FOR EACH ITEM.'
        self.assertEqual(list(self.presenter.queue), [('bilingual', combined)])
        self.assertEqual(len(self.app.live.records), 5)

    def test_pause_flushes_a_short_utterance_without_losing_it(self):
        self.add('THANK YOU')
        self.render()
        self.assertFalse(self.presenter.pending)
        self.app.capture.active = lambda: False
        self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'THANK YOU')])

    def test_active_draft_prevents_idle_flush_of_previous_fragment(self):
        self.add('EVIDENCE')
        with patch('caption_translation.time.monotonic', return_value=10):
            self.render()
        self.app.live_drafts['电脑'] = {'text': 'REPLIED THE INQUIRY'}
        with patch('caption_translation.time.monotonic', return_value=20):
            self.render()
        self.assertFalse(self.presenter.pending)
        self.app.live_drafts.clear()
        with patch('caption_translation.time.monotonic', return_value=22):
            self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'EVIDENCE')])

    def test_complete_sentence_is_not_retranslated_when_speech_extends(self):
        self.add('This is a complete sentence.')
        self.render()
        self.add('NEXT')
        self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'This is a complete sentence.')])
        self.add('QUESTION?')
        self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'This is a complete sentence.'),
                                                      ('bilingual', 'NEXT QUESTION?')])

    def test_sources_and_speakers_are_never_mixed(self):
        self.add('Computer sentence.', speaker='Speaker 1')
        self.add('MICROPHONE FRAGMENT', source='麦克风')
        self.add('Different speaker.', speaker='Speaker 2')
        self.app.capture.active = lambda: False
        self.render()
        bodies = [key[1] for key in self.presenter.queue]
        self.assertEqual(bodies, ['Computer sentence.', 'MICROPHONE FRAGMENT', 'Different speaker.'])

    def test_interleaved_sources_accumulate_separately(self):
        self.add('COMPUTER FIRST')
        self.render()
        self.add('MICROPHONE FIRST', source='麦克风')
        self.render()
        self.add('COMPUTER SECOND.')
        self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'COMPUTER FIRST COMPUTER SECOND.')])
        self.app.capture.active = lambda: False
        self.render()
        self.assertEqual(list(self.presenter.queue)[1], ('bilingual', 'MICROPHONE FIRST'))

    def test_idle_timer_requests_a_refresh_then_flushes_remaining_text(self):
        self.add('THANK YOU')
        with patch('caption_translation.time.monotonic', return_value=10):
            self.render()
        delay, callback = self.app.root.after.call_args.args
        self.assertEqual(delay, 1200)
        callback()
        self.assertTrue(self.app.live_dirty)
        with patch('caption_translation.time.monotonic', return_value=12):
            self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'THANK YOU')])

    def test_queued_recognition_prevents_premature_idle_flush(self):
        self.add('EVIDENCE')
        self.app.live.submitted = 2
        self.app.live.completed = 1
        with patch('caption_translation.time.monotonic', return_value=10):
            self.render()
        with patch('caption_translation.time.monotonic', return_value=15):
            self.render()
        self.assertFalse(self.presenter.pending)
        self.add('IS IMPORTANT.')
        self.app.live.completed = 2
        self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'EVIDENCE IS IMPORTANT.')])

    def test_editing_source_records_rebuilds_batches_without_mutating_them(self):
        self.add('WRONG')
        self.render()
        self.app.live.records[0].update(body='Correct sentence.', text='[16:21:58 电脑]\nCorrect sentence.')
        self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'Correct sentence.')])
        self.assertEqual(self.app.live.records[0]['body'], 'Correct sentence.')

    def test_final_events_waiting_for_ui_do_not_bypass_short_fragment_grouping(self):
        self.add('THE OLD WOMAN')
        self.add('REPLIED WITH CLEAR EVIDENCE.')
        # Recognition can append the next record before the UI handles its event.
        with patch('caption_translation.time.monotonic', return_value=10):
            self.presenter.transcript(self.app.live.records[0]['text'])
        with patch('caption_translation.time.monotonic', return_value=20):
            self.presenter.transcript(self.app.live.records[0]['text'])
        self.assertFalse(self.presenter.pending)
        self.render()
        self.assertEqual(list(self.presenter.queue), [('bilingual', 'THE OLD WOMAN REPLIED WITH CLEAR EVIDENCE.')])


class CaptionBatchingIntegrationTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_controller_sends_combined_sentence_once_and_keeps_source_segments(self):
        self.ui.caption_language.set('中英双语')
        self.ui.capture.active.return_value = True
        fragments = ['THE OLD WOMAN', 'REPLIED', 'WITH CLEAR EVIDENCE.']
        translation = self.patches[0].target.translate
        for sequence, body in enumerate(fragments, 1):
            record = dict(source='电脑', sequence=sequence, generation=sequence,
                          body=body, text='[16:21:58 电脑]\n' + body)
            self.ui.live.records.append(record)
            self.ui.handle_event('live_segment', record)
            self.ui.render_live_transcript()
            if sequence < len(fragments):
                translation.assert_not_called()
        kind, result = self.ui.events.get(timeout=3)
        self.assertEqual(kind, 'caption_result')
        self.ui.handle_event(kind, result)
        self.ui.render_live_transcript()
        translation.assert_called_once()
        self.assertEqual(translation.call_args.args[1], ' '.join(fragments))
        self.assertIn(' '.join(fragments) + '\n中文：Translated fixture', self.ui.transcript_view)
        self.assertEqual([record['body'] for record in self.ui.live.records], fragments)


if __name__ == '__main__':
    unittest.main()
