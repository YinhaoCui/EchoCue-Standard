import io
import json
import unittest
from unittest.mock import patch
import usage_ui as m

class MonitorTests(unittest.TestCase):
    def test_deepseek_balance_uses_only_official_endpoint_and_no_inference(self):
        response={'balance_infos':[{'currency':'CNY','total_balance':'12.5','topped_up_balance':'10','granted_balance':'2.5'}]}
        with patch.object(m.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            self.assertIn('可用 12.5',m.deepseek_balance('fake'))
        request=call.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.deepseek.com/user/balance')
        self.assertIsNone(request.data)

    def test_kimi_balance_and_invalid_payload(self):
        response={'code':0,'data':{'available_balance':5,'cash_balance':2,'voucher_balance':3}}
        with patch.object(m.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            self.assertIn('CNY 可用 5',m.deepseek_balance('fake','Kimi'))
        self.assertEqual(call.call_args.args[0].full_url,'https://api.moonshot.cn/v1/users/me/balance')
        with patch.object(m.urllib.request,'urlopen',return_value=io.BytesIO(b'{"code":1}')):
            with self.assertRaises(RuntimeError): m.deepseek_balance('fake','Kimi')

    def test_provider_totals_session_and_missing_usage(self):
        rows=[{'request':'s:1','provider':'Kimi','usage':{'input':4,'output':2,'total':6}},
              {'request':'old:2','provider':'Kimi','usage':{}},
              {'request':'s:3','provider':'通义千问（北京）','usage':{'input':9,'output':1,'total':10}}]
        text=m.usage_lines(rows,'s')
        self.assertIn('Kimi：本次 1 / 累计 2',text)
        self.assertIn('1 次总量未知',text)
        self.assertIn('输入 9 / 输出 1 / 总 Token 10',text)

if __name__=='__main__': unittest.main()
