"""Device labels are hidden only in the reading view, never in source records."""
import unittest
import threading
from types import SimpleNamespace

from audio_answer import App
from caption_translation import CaptionPresenter, display_transcript
from live_transcription import append_transcript


class CaptionPresentationTests(unittest.TestCase):
    def test_bilingual_segments_do_not_append_next_english_to_previous_chinese(self):
        records = [dict(source='电脑', body=text, text='[16:13:33 电脑]\n' + text)
                   for text in ('SO YOU TAKE THIS SERVER.', 'ALL THE COMPONENTS.')]
        original, source = '', None
        for record in records:
            original, source = append_transcript(original, source, record)
        app = SimpleNamespace(content_language=lambda _: 'bilingual',
            locale=SimpleNamespace(language='zh', t=lambda text: text),
            live=SimpleNamespace(lock=threading.Lock(), records=records))
        presenter = CaptionPresenter(app)
        presenter.cache[('bilingual', records[0]['body'])] = records[0]['body'] + '\n中文：所以你用这台服务器'
        presenter.cache[('bilingual', records[1]['body'])] = records[1]['body'] + '\n中文：所有组件'
        visible = presenter.transcript(original)
        self.assertIn('中文：所以你用这台服务器\n\nALL THE COMPONENTS.\n中文：所有组件', visible)
        self.assertEqual(original, '[16:13:33 电脑]\nSO YOU TAKE THIS SERVER. ALL THE COMPONENTS.')

    def test_device_labels_removed_but_timestamps_speakers_and_content_retained(self):
        for device in ('电脑', '麦克风', 'System audio', 'Microphone'):
            with self.subTest(device=device):
                text = f'[12:34:56 {device} · Speaker 2]\n电脑和麦克风 are in the transcript.'
                self.assertEqual(display_transcript(text),
                                 '[12:34:56 · Speaker 2]\n电脑和麦克风 are in the transcript.')
                self.assertIn(device, text)

    def test_live_drafts_show_text_without_recognition_notice(self):
        original = '[12:34:56 麦克风]\nHello'
        app = SimpleNamespace(live_text=original,
            live_drafts={'电脑': {'text': 'Draft one'}, '麦克风': {'text': 'Draft two'}},
            captions=SimpleNamespace(transcript=lambda text: text, body=lambda text, **_: text))
        App.render_live_transcript(app)
        self.assertEqual(app.transcript_view, '[12:34:56]\nHello\n\nDraft one\n\nDraft two')
        self.assertEqual(app.live_text, original)

    def test_selected_record_also_hides_labels_without_changing_record(self):
        original = '[12:34:56 System audio]\nHello'
        values = []
        app = SimpleNamespace(selected_transcript=0, transcript_records=[{'text': original}],
            captions=SimpleNamespace(transcript=lambda text: text),
            put_text=lambda text, **_: values.append(text))
        App.select_transcript(app)
        self.assertEqual(values, ['[12:34:56]\nHello'])
        self.assertEqual(app.transcript_records[0]['text'], original)


if __name__ == '__main__':
    unittest.main()
