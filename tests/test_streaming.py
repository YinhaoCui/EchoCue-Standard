import threading
import unittest
from unittest.mock import Mock
import audio_answer as a
from streaming_asr import StreamingLiveTranscriber, ASR_MODELS


class FakeStream:
    def __init__(self):
        self.samples = 0
        self.ready = False
    def accept_waveform(self, rate, data):
        self.samples += int((data != 0).sum())
        self.ready = True
    def input_finished(self):
        pass


class FakeRecognizer:
    def __init__(self, label='转录'):
        self.label = label
        self.streams = []
    def create_stream(self):
        stream = FakeStream()
        self.streams.append(stream)
        return stream
    def is_ready(self, stream):
        return stream.ready
    def decode_stream(self, stream):
        stream.ready = False
    def get_result(self, stream):
        return f'{self.label}:{stream.samples}'


class StreamingTests(unittest.TestCase):
    def test_preload_initializes_once_without_audio_or_records(self):
        loaded=threading.Event()
        def factory(name):
            loaded.set();return FakeRecognizer(name)
        factory=Mock(side_effect=factory)
        live=self.make_live(factory)
        live.preload('中文 · Zipformer')
        self.assertTrue(loaded.wait(2))
        self.assertEqual(live.submitted,0)
        self.assertEqual(live.records,[])
        live.configure('中文 · Zipformer')
        live.feed('电脑',b'\x00\x10'*100)
        self.snapshot(live,live.flush())
        self.assertEqual(factory.call_count,1)

    def make_live(self, factory=None):
        self.events = []
        self.partial = threading.Event()
        def emit(kind, value):
            self.events.append((kind,value))
            if kind == 'live_partial': self.partial.set()
        live = StreamingLiveTranscriber(a.ROOT, emit, factory=factory or (lambda name: FakeRecognizer(name)), rate=1000)
        self.addCleanup(live.close)
        return live

    def snapshot(self, live, target):
        cancel = threading.Event()
        timer = threading.Timer(3, cancel.set)
        timer.start()
        try: return live.snapshot(target,cancel)
        finally: timer.cancel()

    def test_partial_before_pause_and_two_sources_do_not_mix(self):
        recognizer=FakeRecognizer()
        factory=Mock(return_value=recognizer)
        live=self.make_live(factory)
        live.configure('中文 · Zipformer')
        live.feed('电脑',b'\x00\x10'*100)
        self.assertTrue(self.partial.wait(2))
        self.assertEqual(live.submitted,0)
        live.feed('麦克风',b'\x00\x10'*200)
        live.feed('电脑',b'\x00\x10'*150)
        text=self.snapshot(live,live.flush())
        self.assertIn('转录:250',text)
        self.assertIn('转录:200',text)
        self.assertEqual(len(recognizer.streams),2)
        factory.assert_called_once_with('中文 · Zipformer')

    def test_switch_finalizes_old_audio_and_snapshot_does_not_include_future_audio(self):
        live=self.make_live()
        live.configure('英文 · Zipformer')
        live.feed('电脑',b'\x00\x10'*100)
        live.configure('中文 · Zipformer')
        target=live.submitted
        live.feed('电脑',b'\x00\x10'*200)
        later=live.flush()
        first=self.snapshot(live,target)
        full=self.snapshot(live,later)
        self.assertIn('英文 · Zipformer:100',first)
        self.assertNotIn('中文 · Zipformer',first)
        self.assertIn('中文 · Zipformer:200',full)
        self.assertEqual(len(live.records),2)

    def test_pause_and_multiple_chunks_keep_all_audio(self):
        live=self.make_live()
        for i in range(20): live.feed('电脑',b'\x00\x10'*100)
        live.feed('电脑',b'\x00\x00'*650)
        self.assertEqual(live.submitted,1)
        text=self.snapshot(live,1)
        self.assertIn(':2000',text)
        self.assertEqual(len(live.records),1)

    def test_model_failure_finishes_snapshot_and_next_model_can_recover(self):
        def factory(name):
            if name=='英文 · Zipformer': raise RuntimeError('模型损坏')
            return FakeRecognizer()
        live=self.make_live(factory)
        live.configure('英文 · Zipformer')
        live.feed('电脑',b'\x00\x10'*100)
        self.assertIn('模型损坏',self.snapshot(live,live.flush()))
        self.assertFalse(live.records[0]['ok'])
        live.configure('中文 · Zipformer')
        live.feed('电脑',b'\x00\x10'*100)
        self.assertIn('转录:100',self.snapshot(live,live.flush()))
        self.assertTrue(live.records[-1]['ok'])

    def test_close_unblocks_waiting_snapshot(self):
        from session_support import Cancelled
        live=self.make_live()
        live.close()
        with self.assertRaises(Cancelled): live.snapshot(1,threading.Event())


if __name__=='__main__': unittest.main()
