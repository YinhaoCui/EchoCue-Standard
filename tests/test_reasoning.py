import json
import threading
import unittest
from unittest.mock import patch
import audio_answer as a
from reasoning_support import choices, parameters

class ReasoningTests(unittest.TestCase):
    def test_model_specific_choices_and_no_fabricated_controls(self):
        self.assertEqual(choices('Codex','model',{'model':['low','high']}),['自动','服务默认','low','high'])
        self.assertNotIn('关闭',choices('Kimi','kimi-k3'))
        self.assertNotIn('关闭',choices('Gemini','gemini-2.5-pro'))
        self.assertEqual(choices('Antigravity（本机登录）','gemini-any'),['自动','服务默认','low','medium','high'])
        self.assertEqual(choices('LM Studio','local'),['自动','服务默认'])
        self.assertEqual(parameters('Kimi','kimi-k3','max'),{'reasoning_effort':'max'})
        self.assertEqual(parameters('通义千问（北京）','qwen3.8-flash','预算 4096'),{'enable_thinking':True,'thinking_budget':4096})
        with self.assertRaises(ValueError): parameters('Kimi','kimi-k2.7-code','关闭')

    def test_codex_explicit_effort_is_forwarded_to_service(self):
        with patch('api_clients.find_codex',return_value='codex.exe'),patch('codex_service.get_service') as service:
            a.codex_answer('q','',threading.Event(),model='model',effort='xhigh')
        self.assertEqual(service.return_value.answer.call_args.args[2],'xhigh')

    def test_explicit_effort_overrides_quick_or_reasoning_mode_in_payload(self):
        event={'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}]}
        for provider,model,effort,expected in [
            ('DeepSeek','deepseek-flash','max',{'thinking':{'type':'enabled'},'reasoning_effort':'max'}),
            ('DeepSeek','deepseek-flash','关闭',{'thinking':{'type':'disabled'}}),
            ('Kimi','kimi-k3','high',{'reasoning_effort':'high'}),
            ('通义千问（北京）','qwen3.8-flash','预算 8192',{'enable_thinking':True,'thinking_budget':8192})]:
            with patch('api_clients.streaming_events',return_value=iter([event])) as request:
                a.compatible_answer(provider,'q','fake',model,'',threading.Event(),lambda _:None,reasoning=True,effort=effort)
            payload=json.loads(request.call_args.args[0].data)
            for key,value in expected.items(): self.assertEqual(payload[key],value)
            if effort=='关闭': self.assertNotIn('reasoning_effort',payload)

    def test_gemini_explicit_selection_overrides_fast_mode(self):
        event={'candidates':[{'content':{'parts':[{'text':'OK'}]},'finishReason':'STOP'}]}
        for effort,expected in [('high',{'thinkingLevel':'high'}),('服务默认',None)]:
            with patch('api_clients.streaming_events',return_value=iter([event])) as request:
                a.gemini_answer(None,'fake','gemini-3.8-flash','',threading.Event(),lambda _:None,fast=True,transcript='q',effort=effort)
            self.assertEqual(json.loads(request.call_args.args[0].data)['generationConfig'].get('thinkingConfig'),expected)

    def test_web_paste_provider_is_removed(self):
        self.assertNotIn('DeepSeek 网页（手动粘贴）',a.SPECIAL_PROVIDERS)
        self.assertIn('DeepSeek',a.API_PROVIDERS)

if __name__=='__main__': unittest.main()
