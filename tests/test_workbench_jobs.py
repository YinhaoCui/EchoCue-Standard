import unittest
from types import SimpleNamespace
from glass_bridge import presentation_jobs


class WorkbenchJobTests(unittest.TestCase):
    def test_spans_preserve_emoji_and_interrupted_output_without_exposing_inputs(self):
        app=SimpleNamespace(output_parts=['intro 😀', 'answer 一', '\n', 'partial 🧭'],
                            job_regions={1:1, 2:3}, locale=SimpleNamespace(t=lambda text:text),
                            jobs={1:dict(done=True,completed=True,provider='DeepSeek',model='old',key='secret'),
                                  2:dict(done=True,state='Interrupted')})
        jobs=presentation_jobs(app)
        text=''.join(app.output_parts).encode('utf-16-le')
        for job, expected in zip(jobs, ['answer 一', 'partial 🧭']):
            start,end=job['span']
            self.assertEqual(text[start*2:end*2].decode('utf-16-le'),expected)
            self.assertNotIn('key',job)
        self.assertFalse(jobs[1]['completed'])
        self.assertEqual(jobs[0]['model'],'old')

    def test_missing_log_region_falls_back_without_losing_task(self):
        app=SimpleNamespace(jobs={7:{}},locale=SimpleNamespace(t=lambda text:text))
        self.assertIsNone(presentation_jobs(app)[0]['span'])
