"""Regression coverage for live HUD geometry, wheel routing and caption isolation."""
import time
from unittest.mock import patch
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import test_sessions


class UIRegressions(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def settle(self):
        for _ in range(8):
            self.root.update()
            time.sleep(.025)

    def test_caption_translation_preserves_source_and_stale_results(self):
        self.ui.locale.set_language('en')
        self.ui.caption_language.set('English')
        record = dict(source='电脑', body='电脑回答模型设置', text='[12:00:00 电脑]\n电脑回答模型设置', sequence=1)
        self.ui.live.records.append(record)
        self.ui.live_text = record['text']
        with patch('caption_translation.translate', return_value='The computer answers model settings.') as translation:
            self.ui.render_live_transcript()
            for _ in range(20):
                self.ui.poll()
                self.root.update()
                if self.ui.captions.cache:break
                time.sleep(.01)
            self.ui.render_live_transcript()
            self.assertIn('The computer answers', self.ui.transcript_view)
            self.assertEqual(self.ui.live_text, record['text'])
            self.assertEqual(self.ui.live.records[0]['body'], '电脑回答模型设置')
            translation.assert_called_once()
        epoch = self.ui.captions.epoch
        self.ui.caption_language.set('中文')
        self.ui.change_content_language('caption')
        self.ui.captions.receive((epoch, ('en', record['body']), 'STALE', None))
        self.assertIn(record['body'], self.ui.transcript_view)
        self.assertNotIn('STALE', self.ui.transcript_view)

class CaptionTransportTests(unittest.TestCase):
    def test_transports_use_translation_prompt_without_answer_session(self):
        from caption_translation import translate
        options = dict(codex_model='fixture', antigravity_model='fixture', claude_model='fixture', kiro_model='fixture', lm_base='http://127.0.0.1:1234')
        app = SimpleNamespace(token_ledger=Mock(), events=Mock(), session_id='test')
        providers = [('Codex', 'codex_answer'), ('Antigravity（本机登录）', 'antigravity_answer'),
                     ('Claude Code（本机登录）', 'claude_answer'), ('Kiro（本机登录）', 'kiro_answer'), ('Gemini', 'gemini_answer'),
                     ('LM Studio', 'compatible_answer'), ('Kimi', 'compatible_answer')]
        for provider, helper in providers:
            inputs = dict(provider=provider, model='fixture', key='', options=options, effort='自动', display_model='fixture')
            def answer(*args, **kwargs):
                self.assertNotIn('session_key', kwargs)
                if helper == 'codex_answer':
                    self.assertIn('Translate', kwargs['prompt_override'])
                    emit=kwargs['on_text']
                elif helper in ('antigravity_answer', 'claude_answer', 'kiro_answer'):
                    self.assertIn('Translate', args[1])
                    emit=args[4]
                else:
                    self.assertIn('翻译' if provider=='Kimi' else 'Translate', kwargs['system_prompt'])
                    emit=args[5] if helper=='gemini_answer' else args[6]
                kwargs['on_usage']({'input_tokens':12, 'output_tokens':4})
                emit('翻译结果')
                return '翻译结果'
            with self.subTest(provider=provider), patch('audio_answer.'+helper, side_effect=answer):
                self.assertEqual(translate(inputs,'Hello','zh',threading.Event(),app),'翻译结果')
                self.assertEqual(app.token_ledger.record.call_args.args[3]['output_tokens'],4)


if __name__ == '__main__':
    unittest.main()
