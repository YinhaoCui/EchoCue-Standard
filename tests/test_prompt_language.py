"""Verify transport prompts and lossless context independently of UI language."""
import copy
import json
import re
import threading
import unittest
from unittest.mock import patch
import audio_answer as a
from prompt_language import language, system_prompt, translation_prompt
from answer_jobs import build_prompt
from generation_context import ContextPrompt
from speed_test import benchmark_prompt

class PromptLanguageTests(unittest.TestCase):
    def test_provider_precedence_and_local_model_families(self):
        for provider in ('Codex','ChatGPT','OpenAI','Claude Code（本机登录）','Gemini','Antigravity（本机登录）'):
            self.assertEqual(language(provider,'qwen3-32b'),'en')
        for provider in ('DeepSeek','Kimi','通义千问（北京）'):
            self.assertEqual(language(provider,'default'),'zh')
        for model in ('qwen3.5-9b','org/DeepSeek-R1','zai-org/glm-4.7','moonshot/kimi-k2'):
            self.assertEqual(language('LM Studio',model),'zh')
        for model in ('llama-3.3','unknown','notqwen-1'):
            self.assertEqual(language('LM Studio',model),'en')

    def test_output_language_is_independent(self):
        english=system_prompt('Codex',target='zh')
        self.assertIn('Simplified Chinese',english)
        self.assertIsNone(re.search(r'[\u3400-\u9fff]',english))
        self.assertIn('回答语言：英文',system_prompt('Kimi',target='en'))
        self.assertIn('翻译成英文',translation_prompt('zh','en'))

    def test_context_preserves_user_text_and_references(self):
        raw='用户原文: Keep code x = "中文" unchanged.'
        data=dict(provider='Codex',model='',profile=raw,documents=raw,summary='',history=[{'转录':raw,'回答':raw}],
                  context_records=[],terms=raw,images=[],instructions=raw)
        before=copy.deepcopy(data)
        prompt=build_prompt(data,raw)
        parsed=json.loads(prompt.splitlines()[1])
        self.assertEqual(parsed['profile'],raw)
        self.assertEqual(parsed['history'][0]['回答'],raw)
        self.assertEqual(parsed['history'][0]['transcript_ref']['range'],[0,len(raw)])
        self.assertIn('User requirements:',prompt)
        self.assertEqual(data,before)
        first=ContextPrompt(data,raw,system_prompt('Codex'))
        data['documents']=raw+' extra'
        second=ContextPrompt(data,raw,system_prompt('Codex'))
        delta=json.loads(second.render(first.state).splitlines()[-1])
        self.assertEqual(delta['set']['documents'],raw+' extra')
        self.assertNotIn('以下 JSON',str(second))
        data['provider']='Kimi'
        self.assertIn('以下 JSON',str(ContextPrompt(data,raw,system_prompt('Kimi'))))

    def test_api_payloads_keep_original_and_select_template(self):
        for provider,model in [('DeepSeek','deepseek-chat'),('LM Studio','llama-3'),('LM Studio','qwen3-8b')]:
            captured=[]
            def events(request,*args,**kwargs):
                captured.append(json.loads(request.data))
                yield {'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}]}
            with patch('api_clients.streaming_events',events):
                a.compatible_answer(provider,'原文', '',model,'原要求',threading.Event(),lambda _:None,effort='服务默认')
            payload=captured[0]
            user=payload['messages'][1]['content']
            self.assertIn('原文',user);self.assertIn('原要求',user)
            expected='补充要求' if language(provider,model)=='zh' else 'Requirements'
            self.assertIn(expected,user)

    def test_gemini_wrapper_is_english_without_translating_data(self):
        captured=[]
        def events(request,*args,**kwargs):
            captured.append(json.loads(request.data))
            yield {'candidates':[{'content':{'parts':[{'text':'OK'}]},'finishReason':'STOP'}]}
        with patch('api_clients.streaming_events',events):
            a.gemini_answer(None,'fake','gemini-test','原要求',threading.Event(),lambda _:None,transcript='原文',fast=True)
        payload=captured[0]
        self.assertIsNone(re.search(r'[\u3400-\u9fff]',payload['systemInstruction']['parts'][0]['text']))
        user=payload['contents'][0]['parts'][0]['text']
        self.assertIn('原要求',user);self.assertIn('原文',user);self.assertIn('Requirements',user)

    def test_benchmark_has_matching_constraints_in_both_languages(self):
        for provider in ('Kimi','Gemini'):
            prompt=benchmark_prompt(provider,'default')
            for literal in ('unique_in_order(items)','O(n)','assert'):
                self.assertIn(literal,prompt)
        self.assertIsNone(re.search(r'[\u3400-\u9fff]',benchmark_prompt('Codex','default')))
