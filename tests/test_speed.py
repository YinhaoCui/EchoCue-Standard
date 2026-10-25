import unittest
from unittest.mock import patch
from speed_test import measure
from session_support import Cancelled

class SpeedTests(unittest.TestCase):
    def test_first_text_total_time_and_average_character_speed(self):
        def generate(emit,usage):
            emit('abcd'); emit('efgh'); usage({'completion_tokens':3})
        with patch('speed_test.time.perf_counter',side_effect=[0,1,4]):
            result=measure(generate)
        self.assertEqual(result['first'],1)
        self.assertEqual(result['elapsed'],4)
        self.assertEqual(result['chars_per_second'],2)
        self.assertEqual(result['output_tokens'],3)

    def test_buffered_codex_does_not_invent_first_token_latency(self):
        result=measure(lambda emit,usage:emit('OK'),streaming=False)
        self.assertIsNone(result['first'])
        self.assertIsNone(result['output_tokens'])

    def test_failure_and_cancel_are_not_success(self):
        def fail(emit,usage): emit('partial'); raise RuntimeError('断流')
        result=measure(fail)
        self.assertEqual(result['status'],'失败')
        self.assertEqual(result['text'],'partial')
        def cancel(emit,usage): raise Cancelled()
        self.assertEqual(measure(cancel)['status'],'已取消')

if __name__=='__main__': unittest.main()
