"""Meeting policy boundaries, acoustic safeguards and application integration."""
import threading
import time
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import audio_answer as a
import numpy as np
from meeting_assistance import AutoAnswers, validate_scenes
from meeting_audio import EchoSuppressor, LocalSpeakers
from session_data import record_text


class PolicyTests(unittest.TestCase):
    def record(self, body, sequence=1):
        return dict(body=body, sequence=sequence, ok=True)

    def test_questions_wait_for_silence_and_idle_and_skip_repeats(self):
        policy = AutoAnswers()
        policy.offer(self.record('How does a hash table work?'), 'questions')
        self.assertIsNone(policy.ready(5, 4.5, False, False, 'balanced'))
        self.assertIsNone(policy.ready(5, 0, True, False, 'balanced'))
        self.assertIsNone(policy.ready(5, 0, False, True, 'balanced'))
        self.assertEqual(policy.ready(5, 0, False, False, 'balanced'), 1)
        policy.dispatched(5)
        policy.offer(self.record('How does a hash table work', 2), 'questions')
        self.assertIsNone(policy.ready(30, 0, False, False, 'balanced'))
        policy.offer(self.record('Explain database transactions', 3), 'questions')
        self.assertIsNone(policy.ready(6, 0, False, False, 'balanced'))
        self.assertEqual(policy.ready(30, 0, False, False, 'balanced'), 3)

    def test_filter_short_and_smalltalk_and_merge_pending(self):
        policy = AutoAnswers()
        for text in ('嗯', 'Okay.', 'Thank you very much', 'Sounds good'):
            policy.offer(self.record(text), 'pause')
            self.assertIsNone(policy.pending)
        policy.offer(self.record('请解释一下数据库事务', 2), 'questions')
        policy.offer(self.record('What is isolation?', 3), 'questions')
        self.assertEqual(policy.pending[0], 3)

    def test_source_and_speaker_grouping_preserved_in_snapshot(self):
        records = [dict(sequence=i, source='电脑', speaker=voice, body=text,
                        text=f'[12:00:00 电脑 · {voice}]\n{text}')
                   for i, voice, text in [(1, 'Speaker 1', 'hello'), (2, 'Speaker 1', 'again'), (3, 'Speaker 2', 'reply')]]
        self.assertEqual(record_text(records), '[12:00:00 电脑 · Speaker 1]\nhello again\n\n[12:00:00 电脑 · Speaker 2]\nreply')
        from caption_translation import HEADER
        self.assertEqual(len(HEADER.findall(record_text(records))), 2)

    def test_scene_validation_rejects_secrets_and_invalid_attachments(self):
        scene = dict(profile='notes', documents='ref', instructions='brief', images=[])
        result = validate_scenes({'meeting': scene})
        scene['profile'] = 'changed'
        self.assertEqual(result['meeting']['profile'], 'notes')
        with self.assertRaises(ValueError):
            validate_scenes({'meeting': dict(scene, api_key='secret')})
        with self.assertRaises(ValueError):
            validate_scenes({'meeting': dict(scene, images=[dict(data='%%%')])})


class AudioTests(unittest.TestCase):
    def test_echo_delay_doubletalk_no_match_and_disabled(self):
        rng = np.random.default_rng(4)
        reference = rng.integers(-8000, 8000, 6000, dtype=np.int16)
        echo = (reference[1200:1520].astype(np.float32) * .5).astype(np.int16).tobytes()
        processor = EchoSuppressor()
        processor.process('电脑', reference.tobytes(), True, now=1)
        self.assertEqual(processor.process('麦克风', echo, True, now=1.1), bytes(len(echo)))
        independent = rng.integers(-2500, 2500, 320, dtype=np.int16)
        mixed = (np.frombuffer(echo, np.int16) + independent).tobytes()
        self.assertEqual(processor.process('麦克风', mixed, True, now=1.1), mixed)
        self.assertEqual(processor.process('麦克风', independent.tobytes(), True, now=1.1), independent.tobytes())
        self.assertEqual(processor.process('麦克风', echo, False, now=1.1), echo)
        self.assertEqual(processor.process('麦克风', echo, True, now=2), echo)

    def test_speaker_embeddings_match_only_within_source_and_short_is_unknown(self):
        extractor = Mock()
        extractor.is_ready.return_value = True
        extractor.compute.side_effect = [[1., 0., 0.], [1., .01, 0.], [0., 1., 0.], [1., 0., 0.]]
        speakers = LocalSpeakers('.', extractor=extractor)
        pcm = np.full(16000, 2000, dtype=np.int16).tobytes()
        self.assertIsNone(speakers.identify('电脑', pcm[:100], 16000))
        self.assertEqual(speakers.identify('电脑', pcm, 16000), 'Speaker 1')
        self.assertEqual(speakers.identify('电脑', pcm, 16000), 'Speaker 1')
        self.assertEqual(speakers.identify('电脑', pcm, 16000), 'Speaker 2')
        self.assertEqual(speakers.identify('麦克风', pcm, 16000), 'Speaker 3')

    def test_stream_records_keep_source_and_speaker_and_model_failure_keeps_transcription(self):
        from test_streaming import FakeRecognizer
        from streaming_asr import StreamingLiveTranscriber
        live = StreamingLiveTranscriber(a.ROOT, lambda *_: None, factory=lambda _: FakeRecognizer(), rate=1000)
        self.addCleanup(live.close)
        with patch('meeting_audio.LocalSpeakers') as factory:
            factory.return_value.identify.return_value = 'Speaker 7'
            live.configure_speakers(True)
            live.feed('电脑', b'\x00\x10' * 1200)
            target = live.flush()
            cancel = threading.Event()
            timer = threading.Timer(3, cancel.set)
            timer.start()
            try:
                transcript = live.snapshot(target, cancel)
            finally:
                timer.cancel()
            self.assertEqual(live.records[0]['source'], '电脑')
            self.assertEqual(live.records[0]['speaker'], 'Speaker 7')
            self.assertIn('Speaker 7', transcript)
            factory.assert_called_once()

    def test_missing_speaker_model_does_not_break_transcription(self):
        from test_streaming import FakeRecognizer
        from streaming_asr import StreamingLiveTranscriber
        live = StreamingLiveTranscriber(a.ROOT, lambda *_: None, factory=lambda _: FakeRecognizer(), rate=1000)
        self.addCleanup(live.close)
        with patch('meeting_audio.LocalSpeakers', side_effect=RuntimeError('missing model')):
            live.configure_speakers(True)
            live.feed('电脑', b'\x00\x10' * 1200)
            target = live.flush()
            cancel = threading.Event()
            timer = threading.Timer(3, cancel.set)
            timer.start()
            try:
                text = live.snapshot(target, cancel)
            finally:
                timer.cancel()
        self.assertTrue(live.records[0]['ok'])
        self.assertNotIn('speaker', live.records[0])
        self.assertIn('missing model', live.speaker_note)
        self.assertIn('转录:', text)


import test_sessions


class MeetingIntegrationTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def request(self, action, **values):
        data = dict(action=action, id=action, version=self.ui.scene_version, context_version=self.ui.context_version, **values)
        self.ui.meeting_command(data)
        return self.ui.meeting_result

    def test_scene_write_failure_stale_version_and_load_are_safe(self):
        self.ui.scenes = {}
        self.ui.scenes_error = ''
        self.ui.profile = 'my profile'
        self.ui.documents = 'my reference'
        with patch('account_support.save_settings', side_effect=OSError('disk full')):
            self.assertFalse(self.request('save_scene', name='work')['ok'])
        self.assertEqual(self.ui.scenes, {})
        with patch('account_support.save_settings') as save:
            self.assertTrue(self.request('save_scene', name='work')['ok'])
            self.assertNotIn('key', repr(save.call_args.args[1]))
        self.ui.profile = 'different'
        self.assertTrue(self.request('load_scene', name='work')['ok'])
        self.assertEqual(self.ui.profile, 'my profile')
        with patch('account_support.save_settings') as save:
            self.ui.meeting_command(dict(action='delete_scene', id='bad', version=-1, context_version=self.ui.context_version, name='work'))
            self.assertFalse(self.ui.meeting_result['ok'])
            save.assert_not_called()

    def test_quick_action_uses_selected_job_snapshot_without_changing_instructions(self):
        self.ui.jobs[12] = dict(done=True, completed=True, answer='original answer', transcript='original question', label='test')
        before = self.ui.instructions.get()
        with patch.object(self.ui, 'ask') as ask:
            self.assertTrue(self.request('quick_answer', job=12, kind='example')['ok'])
            values = ask.call_args.kwargs
            self.assertIn('original question', values['transcript_override'])
            self.assertIn('original answer', values['transcript_override'])
            self.assertIn('example', values['instruction_override'])
        self.assertEqual(before, self.ui.instructions.get())
        self.ui.jobs[12]['completed'] = False
        with patch.object(self.ui, 'ask') as ask:
            self.assertFalse(self.request('quick_answer', job=12, kind='shorten')['ok'])
            ask.assert_not_called()

    def test_recap_waits_for_last_segment_and_deduplicates(self):
        from test_streaming import FakeRecognizer
        self.ui.live.factory = lambda _: FakeRecognizer()
        self.ui.live.feed('电脑', b'\x00\x10' * 1200)
        self.ui.finish_recap()
        target = self.ui.recap_pending
        self.assertTrue(target)
        cancel = threading.Event()
        timer = threading.Timer(3, cancel.set)
        timer.start()
        try:
            self.ui.live.snapshot(target, cancel)
        finally:
            timer.cancel()
        with patch.object(self.ui, 'ask', return_value=1) as ask:
            self.ui.meeting_tick()
            self.assertEqual(ask.call_args.kwargs['target_override'], target)
            self.assertEqual(ask.call_args.kwargs['purpose'], 'recap')
            self.ui.jobs[1] = dict(done=True, completed=True, purpose='recap', target=target)
            self.ui.finish_recap()
            self.ui.meeting_tick()
            self.assertEqual(ask.call_count, 1)

    def test_automatic_waits_during_new_speech_and_includes_continuation(self):
        ui = self.ui
        ui.advanced['question_mode'].set('快速问答')
        ui.advanced['auto_answers'].set('questions')
        ui.live.last_voice = time.monotonic() - 5
        ui.live.completed = ui.live.submitted = 2
        ui.live.sources = {'电脑': dict(data=10)}
        ui.auto_answers.offer(dict(sequence=1, body='How does a transaction work?', ok=True), 'questions')
        def dispatched(**kwargs):
            ui.ask_revision += 1
            return ui.ask_revision
        with patch.object(ui, 'ask', side_effect=dispatched) as ask:
            ui.meeting_tick()
            ask.assert_not_called()
            ui.live.sources['电脑']['data'] = 0
            ui.meeting_tick()
            self.assertEqual(ask.call_args.kwargs['target_override'], 2)
            ui.meeting_tick()
            self.assertEqual(ask.call_count, 1)

    def test_restore_resets_paid_triggers_and_preserves_existing_labels(self):
        ui = self.ui
        ui.advanced['speaker_labels'].set('1')
        ui.auto_answers.offer(dict(sequence=1, body='How does hashing work?', ok=True), 'questions')
        payload = {'segment:1': dict(sequence=1, source='电脑', generation=1, speaker='Speaker 5',
                                    text='[12:00:00 电脑 · Speaker 5]\nquestion', body='question', ok=True)}
        with patch('meeting_audio.LocalSpeakers') as factory:
            ui.restore_payload(payload)
            ui.live.feed('电脑', b'\x00\x10' * 1200)
            target = ui.live.flush()
            cancel = threading.Event()
            timer = threading.Timer(3, cancel.set)
            timer.start()
            factory.return_value.identify.return_value = None
            try:
                ui.live.snapshot(target, cancel)
            finally:
                timer.cancel()
            factory.assert_called_once_with(ui.live.root, 6)
        self.assertIsNone(ui.auto_answers.pending)
        self.assertEqual(ui.live.records[0]['speaker'], 'Speaker 5')

    def test_request_specific_instruction_is_snapshotted_without_global_mutation(self):
        ui = self.ui
        before = ui.instructions.get()
        with patch.object(ui, 'run_request') as run:
            identity = ui.ask(transcript_override='Question', instruction_override='Use a concrete example', purpose='followup')
            ui.worker.join(2)
            inputs = run.call_args.args[0]
            self.assertIn('Use a concrete example', inputs['instructions'])
            from answer_jobs import build_prompt
            self.assertIn('Use a concrete example', build_prompt(inputs, 'Question'))
            self.assertEqual(ui.jobs[identity]['purpose'], 'followup')
        self.assertEqual(before, ui.instructions.get())

    def test_recap_does_not_send_unrelated_personal_material(self):
        self.ui.profile = 'private profile'
        self.ui.documents = 'unrelated document'
        self.ui.context_images = [dict(data='invalid image deliberately excluded from recap')]
        with patch.object(self.ui, 'run_request') as run, patch('providers.accepts_images', return_value=False), patch('image_text.screenshot_text', side_effect=AssertionError('Recap must not OCR screenshots')):
            self.ui.ask(transcript_override='meeting transcript', instruction_override='Summarize', purpose='recap')
            self.ui.worker.join(2)
            inputs = run.call_args.args[0]
        self.assertEqual(inputs['profile'], '')
        self.assertEqual(inputs['documents'], '')
        self.assertEqual(inputs['history'], [])
        self.assertEqual(inputs['images'], [])
        self.assertIsNone(inputs['session_key'])

    def test_scene_is_actually_encrypted_and_reloadable(self):
        import account_support
        self.ui.scenes_error = ''
        self.ui.scenes = {}
        self.ui.profile = 'private scene fixture'
        with tempfile.TemporaryDirectory(dir=a.WORK) as folder, patch.object(a, 'ROOT', Path(folder)):
            self.assertTrue(self.request('save_scene', name='private')['ok'])
            path = Path(folder) / 'data/scenes.dpapi'
            self.assertNotIn(b'private scene fixture', path.read_bytes())
            stored = account_support.load_settings(path)
            self.assertEqual(stored['private']['profile'], 'private scene fixture')
