"""Measure how long a worker event takes to reach a page reader, per timer setting.

python tools/benchmark_ui_latency.py

Runs the real controller and state feed (no window, no network providers).
A producer thread posts live-transcript drafts and answer text the way the
transcriber and answer workers do; a reader long-polls the feed the way the
page does. The delay between the two is what the user sees as display lag.
CPU is the controller thread's share of one core while idle.
"""

from pathlib import Path
import json
import statistics
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'app'), str(ROOT / 'tests')]
import app_paths  # noqa: E402,F401  (puts the bundled vendor packages on sys.path)
import audio_answer  # noqa: E402
import glass_bridge  # noqa: E402
import session_control  # noqa: E402
import test_sessions  # noqa: E402

# (label, controller poll ms, publish ms, live-draft redraw seconds)
VARIANTS = (
    ('60 / 100 / 0.12', 60, 100, 0.12),
    ('30 / 50 / 0.06', 30, 50, 0.06),
    ('20 / 33 / 0.03', 20, 33, 0.03),
    ('10 / 16 / 0.016', 10, 16, 0.016),
)
EVENTS = 60


def measure(poll_ms, tick_ms, redraw):
    audio_answer.POLL_MS, glass_bridge.TICK_MS, session_control.LIVE_RENDER_SECONDS = poll_ms, tick_ms, redraw
    case = test_sessions.UITests()
    case.setUp()
    ui = case.ui
    ui.token_ledger.lock, ui.token_ledger.rows = threading.Lock(), []
    bridge = glass_bridge.GlassBridge(ui)
    bridge.tick()
    sent, seen, stop = {}, {}, threading.Event()

    def reader():
        rev, boot, texts = -1, '', {'transcript': {'v': None, 'text': ''}, 'output': {'v': None, 'text': ''}}
        while not stop.is_set():
            reply = json.loads(
                bridge.feed.read(rev=rev, boot=boot, versions={k: v['v'] for k, v in texts.items()}, wait=0.5)
            )
            now = time.perf_counter()
            rev, boot = reply['rev'], reply['boot']
            for key, have in texts.items():
                entry = reply.get(key)
                if entry:
                    have['text'] = entry['text'] if 'text' in entry else have['text'][: entry['keep']] + entry['add']
                    have['v'] = entry['v']
            joined = texts['transcript']['text'] + texts['output']['text']
            for marker in sent:
                if marker not in seen and marker in joined:
                    seen[marker] = now

    def producer():
        time.sleep(0.5)
        for index in range(EVENTS):
            time.sleep(0.11 + (index * 37 % 90) / 1000)  # spread over the timer phases
            if index % 2:
                marker = f'<draft{index}>'
                event = ('live_partial', {'source': '电脑', 'generation': 1, 'text': '所以这个问题是 ' + marker})
            else:
                marker = f'<answer{index}>'
                event = ('text', ' ' + marker)
            sent[marker] = time.perf_counter()
            ui.events.put(event)
        time.sleep(0.6)
        stop.set()

    threads = [threading.Thread(target=reader, daemon=True), threading.Thread(target=producer, daemon=True)]
    for thread in threads:
        thread.start()
    while not stop.is_set():
        case.root.update()
        time.sleep(0.001)
    idle_cpu, idle_wall = time.thread_time(), time.perf_counter()
    while time.perf_counter() - idle_wall < 2:
        case.root.update()
        time.sleep(0.001)
    cpu = (time.thread_time() - idle_cpu) / (time.perf_counter() - idle_wall)
    bridge.close()
    case.tearDown()
    result = {}
    for kind in ('draft', 'answer'):
        delays = sorted((seen[m] - at) * 1000 for m, at in sent.items() if kind in m and m in seen)
        missing = sum(1 for m in sent if kind in m and m not in seen)
        result[kind] = (statistics.median(delays), delays[int(len(delays) * 0.95) - 1], delays[-1], missing)
    return result, cpu


if __name__ == '__main__':
    print(
        f'{"poll / publish / redraw":<24}{"draft ms p50":>13}{"p95":>7}{"max":>7}{"answer ms p50":>15}{"p95":>7}{"max":>7}{"idle CPU":>10}'
    )
    for label, *settings in VARIANTS:
        result, cpu = measure(*settings)
        d, a = result['draft'], result['answer']
        lost = d[3] + a[3]
        print(
            f'{label:<24}{d[0]:>13.0f}{d[1]:>7.0f}{d[2]:>7.0f}{a[0]:>15.0f}{a[1]:>7.0f}{a[2]:>7.0f}{cpu:>9.1%}'
            + (f'  ({lost} not shown)' if lost else '')
        )
