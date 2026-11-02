"""Question admission and generation-only prediction reuse regressions."""
import unittest
from unittest.mock import patch

import answer_jobs
import providers
from glass_bridge import GlassBridge
import test_latency
import test_sessions


class QuestionAdmissionTests(unittest.TestCase):
    def test_declarative_english_does_not_trigger_answers(self):
        for text in ('This is the current implementation.', 'We are reviewing the requirements.',
                     'I can describe the problem.', 'The difference is small.', 'We know how this works.'):
            with self.subTest(text=text):
                self.assertFalse(answer_jobs.looks_like_question(text))

    def test_questions_and_requests_without_asr_punctuation_still_work(self):
        for text in ('What is a closure', 'Is this correct', 'Could you explain the next step',
                     'Please describe the solution', 'Tell me the difference', 'How does it work',
                     '[10:00:00 电脑]\nAre these results correct', 'Okay, can we continue',
                     'The background is clear. What should we do next', '这个函数怎么优化', '这样可以吗', 'Why?'):
            with self.subTest(text=text):
                self.assertTrue(answer_jobs.looks_like_question(text))


class PredictionReuseTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown
    prepare = test_latency.SpeculationTests.prepare
    segment = test_latency.SpeculationTests.segment

    def test_caption_and_appearance_edits_keep_the_same_generated_answer(self):
        with self.prepare():
            record = self.segment()
            answer_jobs.AnswerJobs.maybe_speculate(self.ui, record)
            self.ui.speculation.worker.join(2)
            GlassBridge(self.ui).settings(dict(caption_provider='Microsoft Translator (built-in)', ui_theme='classic'))
            self.ui.ask(); self.ui.worker.join(2); self.ui.poll()
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.ui.jobs[self.ui.ask_revision]['timing'].get('speculative'))

    def test_generation_changes_still_invalidate_prediction(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider(); self.ui.model.set('test-model')
        before = self.ui.request_inputs()[0]
        original = answer_jobs.request_signature(before, 'What next?')
        for option, value in (('lm_base', 'http://localhost:4321/v1'),
                              ('thinking_policy', '关闭'), ('incremental_context', '关闭')):
            changed = dict(before, options={**before['options'], option: value})
            self.assertNotEqual(original, answer_jobs.request_signature(changed, 'What next?'))
        changed = dict(before, instructions=before['instructions'] + ' Additional requirement.')
        self.assertNotEqual(original, answer_jobs.request_signature(changed, 'What next?'))
        changed = dict(before, key='different-key')
        self.assertNotEqual(original, answer_jobs.request_signature(changed, 'What next?'))
        self.assertNotEqual(original, answer_jobs.request_signature(before, 'A different question?'))

    def test_selected_cli_model_invalidates_but_other_platform_model_does_not(self):
        self.ui.provider.set(providers.CODEX); self.ui.update_provider()
        before = self.ui.request_inputs()[0]
        original = answer_jobs.request_signature(before, 'Why?')
        changed = dict(before, options={**before['options'], 'codex_model': 'different-model'})
        self.assertNotEqual(original, answer_jobs.request_signature(changed, 'Why?'))
        changed = dict(before, options={**before['options'], 'claude_model': 'unrelated-model'})
        self.assertEqual(original, answer_jobs.request_signature(changed, 'Why?'))
