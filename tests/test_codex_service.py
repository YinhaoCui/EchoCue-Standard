import pathlib
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from codex_service import CodexService
from session_support import Cancelled


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.service=CodexService('',pathlib.Path(__file__).parent,
            command=[sys.executable,'-u',str(pathlib.Path(__file__).with_name('fake_codex_server.py'))])
        self.addCleanup(self.service.close)

    def answer(self,text,cancel=None,emit=None,usage=None):
        return self.service.answer(text,'gpt-6-astra','low',cancel or threading.Event(),emit or (lambda _:None),usage,timeout=5)

    def test_sequential_streams_reuse_process_and_report_usage(self):
        chunks=[];usage=[]
        self.assertEqual(self.answer('one',emit=chunks.append,usage=usage.append),'first:one:last')
        pid=self.service.process.pid
        self.assertEqual(self.answer('two'),'first:two:last')
        self.assertEqual(pid,self.service.process.pid)
        self.assertEqual(self.service.launches,1)
        self.assertEqual(''.join(chunks),'first:one:last')
        self.assertEqual(usage[-1]['total_tokens'],12)

    def test_cancel_one_parallel_answer_keeps_other_alive(self):
        cancel=threading.Event();first=threading.Event()
        with ThreadPoolExecutor(2) as pool:
            slow=pool.submit(self.answer,'slow',cancel,lambda _:first.set())
            self.assertTrue(first.wait(3))
            other=pool.submit(self.answer,'other')
            cancel.set()
            with self.assertRaises(Cancelled):slow.result(timeout=4)
            self.assertEqual(other.result(timeout=4),'first:other:last')
        self.assertEqual(self.service.launches,1)

    def test_failure_does_not_restart_and_crash_recovers_on_next_request(self):
        with self.assertRaises(RuntimeError):self.answer('fail')
        self.assertEqual(self.answer('next'),'first:next:last')
        self.assertEqual(self.service.launches,1)
        with self.assertRaises(RuntimeError):self.answer('crash')
        self.service.process.wait(timeout=2)
        self.assertEqual(self.answer('recovered'),'first:recovered:last')
        self.assertEqual(self.service.launches,2)
