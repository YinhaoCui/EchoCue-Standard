"""Run the real diagnostic bridge without opening native auxiliary windows."""
import threading
import time
import unittest
from unittest.mock import patch
import audio_answer as a
import test_sessions
from glass_bridge import GlassBridge


class InlineDiagnosticsTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def bridge(self):
        bridge=GlassBridge.__new__(GlassBridge)
        bridge.app=self.ui
        return bridge

    def test_benchmark_uses_existing_worker_and_ledger_without_a_window(self):
        self.ui.provider.set('LM Studio');self.ui.update_provider();self.ui.model.set('main-local')
        self.ui.api_settings['Kimi']={'key':'fake-key','model':'kimi-k3'}
        bridge=self.bridge()
        def answer(provider,prompt,key,model,instructions,cancel,emit,**kw):
            self.assertEqual((provider,key,model),('Kimi','fake-key','kimi-k3'))
            self.assertIn('unique_in_order',prompt)
            emit('example code');kw['on_usage']({'completion_tokens':5})
        with patch('tkinter.Toplevel',side_effect=AssertionError('Unexpected window')),patch.object(a,'compatible_answer',side_effect=answer):
            bridge.command({'action':'speed'})
            bridge.command({'action':'speed_select','provider':'Kimi'})
            bridge.command({'action':'speed_start','model':'kimi-k3','effort':'max','mode':'Coding','fast':False})
            self.ui.speed_worker.join(2);self.ui.poll()
        state=self.ui.inline_speed_state()
        self.assertFalse(state['busy'])
        self.assertEqual(state['results'][0]['text'],'example code')
        self.assertEqual(state['results'][0]['output_tokens'],5)
        self.assertEqual(self.ui.model.get(),'main-local')
        self.assertEqual(self.ui.provider.get(),'LM Studio')
        self.assertEqual(self.ui.token_ledger.record.call_count,1)
        self.assertIsNone(self.ui.speed_window)

    def test_cancel_and_invalid_selection_do_not_start_a_request(self):
        bridge=self.bridge();bridge.command({'action':'speed'})
        with patch.object(self.ui,'start_speed_test') as start:
            with self.assertRaises(ValueError):bridge.command({'action':'speed_start','provider':'unknown'})
            with self.assertRaises(ValueError):bridge.command({'action':'speed_start','model':'bad\nmodel'})
            start.assert_not_called()
        self.ui.speed_cancel=threading.Event();self.ui.speed_busy=True
        bridge.command({'action':'speed_cancel'})
        self.assertTrue(self.ui.speed_cancel.is_set())

    def test_api_report_stays_inline_and_redacts_key(self):
        self.ui.provider.set('DeepSeek');self.ui.update_provider();self.ui.key.set('secret-fixture');self.ui.model.set('deepseek-chat')
        def catalog(provider,key,**kwargs):
            if key: raise RuntimeError('bad '+key)
            return []
        with patch('tkinter.Toplevel',side_effect=AssertionError('Unexpected window')),patch.object(a.messagebox,'showinfo',side_effect=AssertionError('Unexpected report window')),patch.object(a,'list_provider_models',side_effect=catalog):
            self.bridge().command({'action':'check_apis'})
            deadline=time.monotonic()+3
            while self.ui.check_busy and time.monotonic()<deadline:
                self.ui.poll();time.sleep(.01)
            self.ui.poll()
        self.assertFalse(self.ui.check_busy)
        self.assertIn('DeepSeek',self.ui.inline_api_report)
        self.assertNotIn('secret-fixture',self.ui.inline_api_report)
        self.assertIn('[KEY]',self.ui.inline_api_report)

    def test_usage_actions_reuse_background_refresh_without_dialog(self):
        with patch.object(self.ui,'refresh_codex_quota') as quota,patch.object(self.ui,'refresh_deepseek_balance') as balance,patch.object(self.ui,'show_usage',side_effect=AssertionError('Unexpected window')):
            self.bridge().command({'action':'usage'})
            self.bridge().command({'action':'refresh_balance','provider':'Kimi'})
            quota.assert_called_once();balance.assert_called_once_with('Kimi')
