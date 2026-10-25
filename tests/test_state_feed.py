import json
import random
import threading
import time
import unittest

from state_feed import StateFeed, common_prefix
from glass_bridge import state_query


class Reader:
    """Applies feed replies the way app/web/app.js does."""
    def __init__(self, feed):
        self.feed, self.boot, self.rev, self.base = feed, '', -1, None
        self.texts = {'transcript': [None, ''], 'output': [None, '']}

    def read(self, wait=0.0):
        data = json.loads(self.feed.read(self.rev, self.boot, {k: v[0] for k, v in self.texts.items()}, wait))
        if data['boot'] != self.boot:
            self.boot = data['boot']
            self.texts = {k: [None, ''] for k in self.texts}
        self.rev = data['rev']
        if 'state' in data:
            self.base = data['state']
        for key, entry in data.items():
            if key in self.texts:
                old = self.texts[key][1]
                text = entry['text'] if 'text' in entry else old[:entry['keep']] + entry['add']
                self.texts[key] = [entry['v'], text]
        return data


class CommonPrefixTests(unittest.TestCase):
    def test_matches_naive(self):
        rng = random.Random(7)
        for _ in range(500):
            a = ''.join(rng.choice('ab') for _ in range(rng.randint(0, 30)))
            b = ''.join(rng.choice('ab') for _ in range(rng.randint(0, 30)))
            naive = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            self.assertEqual(common_prefix(a, b), naive, (a, b))


class StateFeedTests(unittest.TestCase):
    def test_first_read_is_full_then_only_changes(self):
        feed, reader = StateFeed(), Reader(StateFeed())
        reader.feed = feed
        feed.publish({'status': 'Ready', 'transcript': 'Hello', 'output': ''})
        first = reader.read()
        self.assertEqual(first['state'], {'status': 'Ready'})
        self.assertEqual(first['transcript'], {'v': 1, 'text': 'Hello'})
        feed.publish({'status': 'Ready', 'transcript': 'Hello world', 'output': ''})
        second = reader.read()
        self.assertNotIn('state', second)
        self.assertEqual(second['transcript'], {'v': 2, 'keep': 5, 'add': ' world'})
        self.assertEqual(reader.read(), {'boot': feed.boot, 'rev': second['rev']})

    def test_reader_text_always_matches_after_random_edits(self):
        rng, feed = random.Random(3), StateFeed(window=8)
        reader, text = Reader(feed), ''
        for step in range(400):
            cut = rng.randint(0, len(text))
            text = text[:cut] + ''.join(rng.choice('xyz ') for _ in range(rng.randint(0, 6)))
            feed.publish({'transcript': text, 'output': text[::-1], 'n': step // 10})
            if rng.random() < 0.3:  # readers fall behind, sometimes past the window
                reader.read()
                self.assertEqual(reader.texts['transcript'][1], text)
                self.assertEqual(reader.texts['output'][1], text[::-1])
                self.assertEqual(reader.base, {'n': step // 10})

    def test_restart_or_unknown_version_sends_full_text(self):
        feed = StateFeed()
        feed.publish({'transcript': 'abc'})
        data = json.loads(feed.read(rev=5, boot='old-run', versions={'transcript': 1}))
        self.assertEqual(data['transcript'], {'v': 1, 'text': 'abc'})
        self.assertIn('state', data)

    def test_waiting_read_wakes_on_change(self):
        feed, reader = StateFeed(), None
        feed.publish({'status': 'a'})
        reader = Reader(feed)
        reader.read()
        threading.Timer(0.1, lambda: feed.publish({'status': 'b'})).start()
        start = time.monotonic()
        reader.read(wait=2)
        self.assertLess(time.monotonic() - start, 1.0)
        self.assertEqual(reader.base, {'status': 'b'})

    def test_idle_read_times_out(self):
        feed = StateFeed()
        feed.publish({'status': 'a'})
        reader = Reader(feed)
        reader.read()
        start = time.monotonic()
        self.assertNotIn('state', reader.read(wait=0.2))
        self.assertGreaterEqual(time.monotonic() - start, 0.15)


class StateQueryTests(unittest.TestCase):
    def test_parses_and_clamps(self):
        self.assertEqual(state_query('/state?rev=4&boot=ab12&tv=9&ov=&wait=30'),
                         dict(rev=4, boot='ab12', versions={'transcript': 9, 'output': None}, wait=1.0))
        self.assertEqual(state_query('/state'),
                         dict(rev=-1, boot='', versions={'transcript': None, 'output': None}, wait=0.0))
        for bad in ('wait=nan', 'wait=-3', 'wait=x', 'rev=x&tv=1.5'):
            with self.subTest(bad=bad):
                query = state_query('/state?' + bad)
                self.assertEqual(query['wait'], 0.0 if 'wait' in bad else 0.0)
                self.assertGreaterEqual(query['rev'], -1)


if __name__ == '__main__':
    unittest.main()
