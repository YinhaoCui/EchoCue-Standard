import urllib.request
import io
import json
import threading
import unittest
from unittest.mock import patch
import audio_answer as a
from model_catalog import select_models,thinking_options
from reasoning_support import choices,parameters
from test_screenshots import attachment


class MuseTests(unittest.TestCase):
    def test_official_request_carries_screenshot_effort_and_usage(self):
        events=[{'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}]},
                {'choices':[],'usage':{'prompt_tokens':8,'completion_tokens':3,'total_tokens':11}}]
        stream=''.join('data: '+json.dumps(event)+'\n\n' for event in events)
        usage=[]
        with patch.object(urllib.request,'urlopen',return_value=io.BytesIO(stream.encode())) as post:
            result=a.compatible_answer('Meta Muse','question','fake','muse-spark-1.3','context',threading.Event(),lambda _:None,
                                       images=[attachment()],effort='high',on_usage=usage.append,max_output=2048)
        request=post.call_args.args[0];body=json.loads(request.data)
        self.assertEqual(request.full_url,'https://api.meta.ai/v1/chat/completions')
        self.assertEqual(request.get_header('Authorization'),'Bearer fake')
        self.assertEqual(body['reasoning_effort'],'high')
        self.assertEqual(body['max_completion_tokens'],2048)
        self.assertNotIn('max_tokens',body)
        self.assertEqual(body['messages'][0]['role'],'developer')
        self.assertTrue(body['messages'][1]['content'][-1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertEqual(result,'OK');self.assertEqual(usage[0]['total_tokens'],11)

    def test_model_discovery_uses_official_endpoint_and_filters_non_chat_models(self):
        ids=['muse-spark-1.3','muse-image-1.0','muse-voice-transcribe-1.0','sam-3.1']
        with patch.object(urllib.request,'urlopen',return_value=io.BytesIO(json.dumps({'data':[{'id':m} for m in ids]}).encode())) as get:
            models=a.list_provider_models('Meta Muse','fake')
        self.assertEqual(get.call_args.args[0].full_url,'https://api.meta.ai/v1/models')
        selected=select_models('Meta Muse',models)
        self.assertEqual(selected,['muse-spark-1.3'])
        self.assertFalse(set(ids[1:]) & set(selected))

    def test_reasoning_levels_do_not_offer_unsupported_none_or_max(self):
        self.assertEqual(thinking_options('Meta Muse','muse-spark-1.3'),{'reasoning_effort':'minimal'})
        self.assertEqual(parameters('Meta Muse','muse-wonder-1.0','max'),{'reasoning_effort':'max'})
        for model in ('muse-spark-1.2','muse-spark-1.3-contributor'):
            self.assertNotIn('max',choices('Meta Muse',model))
            self.assertNotIn('none',choices('Meta Muse',model))


if __name__=='__main__':unittest.main()
