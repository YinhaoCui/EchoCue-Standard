"""Long-question submission boundaries and lossless context regression tests."""
import threading
import unittest
from unittest.mock import Mock, patch
import test_sessions
from answer_jobs import AnswerJobs, build_prompt
from generation_context import ContextPrompt

class LongQuestionTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_long_mode_blocks_predictions_even_for_questions(self):
        self.ui.advanced['question_mode'].set('长问题')
        self.ui.advanced['speculate'].set('每段定稿')
        with patch.object(self.ui, 'request_inputs') as collect:
            AnswerJobs.maybe_speculate(self.ui, {'sequence': 1, 'body': 'Why?', 'ok': True})
        collect.assert_not_called()

    def test_mode_change_discards_prediction_but_keeps_explicit_job(self):
        spec = Mock()
        self.ui.speculation = spec
        cancel = threading.Event()
        self.ui.jobs[999] = {'cancel': cancel}
        self.ui.advanced['question_mode'].set('快速问答')
        spec.discard.assert_called_once()
        self.assertIsNone(self.ui.speculation)
        self.assertFalse(cancel.is_set())
        self.ui.jobs.clear()

    def test_full_long_input_survives_and_settings_snapshot_is_independent(self):
        self.ui.provider.set('Codex'); self.ui.update_provider()
        self.ui.advanced['question_mode'].set('长问题')
        inputs, error = self.ui.request_inputs()
        self.assertIsNone(error)
        text = 'Background and constraints. ' * 4000 + 'Final request: implement it.'
        prompt = ContextPrompt(inputs, text, "system")
        self.assertTrue(prompt.state["transcript"] == text, "Complete input must be retained")
        self.assertIn('Do not answer only the last transcript segment', inputs['instructions'])
        self.ui.advanced['question_mode'].set('快速问答')
        self.assertEqual(inputs['options']['question_mode'], '长问题')
        self.assertNotIn('Do not answer only the last transcript segment', self.ui.request_inputs()[0]['instructions'])

    def test_caption_and_analysis_do_not_inherit_answer_instructions(self):
        self.ui.provider.set('Codex'); self.ui.update_provider()
        self.ui.advanced['question_mode'].set('长问题')
        for flags in ({'caption': True}, {'analysis': True}):
            self.assertNotIn('complete long question', self.ui.request_inputs(**flags)[0]['instructions'])
