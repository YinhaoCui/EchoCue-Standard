import pathlib
import pathlib
import urllib.request
import base64
import io
import json
import threading
import time
import unittest
from unittest.mock import patch
import audio_answer as a
import screenshot_context as s
import test_product

PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='
def attachment():return dict(id='one',title='Test window',created='2026-10-12 10:00:00',data=PNG)


class ImageRequests(unittest.TestCase):
    def test_gemini_sends_png_with_text(self):
        event={'candidates':[{'content':{'parts':[{'text':'OK'}]},'finishReason':'STOP'}]}
        with patch.object(urllib.request,'urlopen',return_value=io.BytesIO(('data: '+json.dumps(event)+'\n\n').encode())) as post:
            a.gemini_answer(None,'key','gemini-test','context',threading.Event(),lambda _:None,transcript='question',images=[attachment()])
        parts=json.loads(post.call_args.args[0].data)['contents'][0]['parts']
        self.assertEqual(parts[-1]['inlineData'],{'mimeType':'image/png','data':PNG})

    def test_compatible_sends_png_with_text(self):
        event={'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}]}
        with patch.object(urllib.request,'urlopen',return_value=io.BytesIO(('data: '+json.dumps(event)+'\n\n').encode())) as post:
            a.compatible_answer('LM Studio','question','','vision-model','context',threading.Event(),lambda _:None,images=[attachment()])
        content=json.loads(post.call_args.args[0].data)['messages'][1]['content']
        self.assertEqual(content[-1]['image_url']['url'],'data:image/png;base64,'+PNG)

    def test_codex_attachment_exists_during_request_and_is_cleaned_on_failure(self):
        paths=[]
        with self.assertRaisesRegex(RuntimeError,'fixture'):
            with s.image_files([attachment()],a.WORK) as files:
                paths=files
                def run(*args,**kw):
                    self.assertEqual(pathlib.Path(kw['images'][0]).read_bytes(),base64.b64decode(PNG))
                    raise RuntimeError('fixture')
                with patch('api_clients.find_codex',return_value='codex'),patch('codex_service.CodexService.answer',side_effect=run):
                    a.codex_answer('question','context',threading.Event(),on_text=lambda _:None,image_paths=files)
        self.assertFalse(pathlib.Path(paths[0]).exists())


class ScreenshotUITests(unittest.TestCase):
    setUp=test_product.ProductUITests.setUp
    tearDown=test_product.ProductUITests.tearDown

    def test_capture_uses_last_external_window_then_adds_context(self):
        target={'handle':123,'process':456,'title':'Test window'}
        self.ui.capture_target=target
        with patch.object(s,'foreground_window',return_value=None),patch.object(s,'capture_window',return_value=attachment()) as capture:
            self.ui.capture_screenshot()
            deadline=time.monotonic()+2
            while self.ui.screenshot_busy and time.monotonic()<deadline:
                self.ui.poll();time.sleep(.01)
        capture.assert_called_once_with(target)
        self.assertEqual(self.ui.context_images,[attachment()])
        self.ui.session_writer.close()
        self.assertEqual(self.ui.session_store.load(self.ui.session_id)['images'],[attachment()])
        self.ui.session_writer=None
        self.ui.context_images.clear();self.ui.save_session();self.ui.session_writer.close()
        self.assertEqual(self.ui.session_store.load(self.ui.session_id)['images'],[])

    def test_restore_images_and_ignore_capture_after_context_clear(self):
        self.ui.restore_payload({'images':[attachment()]})
        self.assertEqual(self.ui.context_images,[attachment()])
        self.ui.receive_screenshot((self.ui.context_version-1,attachment(),''))
        self.assertEqual(len(self.ui.context_images),1)

    def test_preview_and_remove_last_image(self):
        import tkinter as tk
        photo=tk.PhotoImage(master=self.root,width=2,height=2)
        photo.put('white',to=(0,0,2,2))
        item=attachment();item['data']=base64.b64encode(photo.tk.call(str(photo),'data','-format','png')).decode('ascii')
        self.ui.context_images=[item]
        self.ui.screenshot_manager();self.root.update()
        window=self.ui.screenshot_manager_window
        canvas=next(w for w in window.winfo_children() if isinstance(w,tk.Canvas))
        self.assertEqual(canvas.picture.width(),2)
        button=next(w for w in window.winfo_children() if w.winfo_class()=='TButton')
        button.invoke()
        self.assertEqual(self.ui.context_images,[])
        window.destroy()

    def test_screenshot_only_answer_passes_images_without_waiting_for_audio(self):
        self.ui.context_images=[attachment()]
        self.ui.provider.set('Gemini');self.ui.key.set('fake');self.ui.model.set('gemini-test')
        def answer(*args,**kwargs):
            self.assertEqual(kwargs['images'],[attachment()]);args[5]('OK')
        with patch.object(a,'gemini_answer',side_effect=answer) as generate:
            self.ui.ask();self.ui.worker.join(2)
        self.assertEqual(generate.call_count,1)


    def test_text_only_provider_gets_screenshot_text_instead_of_an_error(self):
        self.ui.context_images=[attachment()]
        self.ui.provider.set('DeepSeek');self.ui.key.set('fake');self.ui.model.set('deepseek-chat')
        import image_text;image_text._cache.clear()
        with patch('image_text._read',return_value='CODE 4826'):
            inputs,error=self.ui.request_inputs()
        self.assertIsNone(error)
        self.assertEqual(inputs['images'],[])
        self.assertIn('CODE 4826',inputs['documents'])
        self.assertIn('Test window',inputs['documents'])


class ScreenshotTextTests(unittest.TestCase):
    def test_each_image_is_read_once(self):
        import image_text
        image_text._cache.clear();calls=[]
        def reader(data,work):calls.append(data);return 'hello'
        for _ in range(2):text=image_text.screenshot_text([attachment()],a.WORK,reader=reader)
        self.assertEqual(len(calls),1)
        self.assertIn('[Screenshot 1: 2026-10-12 10:00:00 · Test window]\nhello',text)


class KiroImageTests(unittest.TestCase):
    def test_screenshots_are_written_and_named_and_v3_is_used(self):
        import tempfile,kiro_support as k
        with tempfile.TemporaryDirectory() as tmp:
            shots,text=k.attach_images(pathlib.Path(tmp),[attachment()])
            self.assertEqual((shots/'shot-1.png').read_bytes(),base64.b64decode(PNG))
            self.assertIn('shots/'+shots.name+'/shot-1.png',text)
            self.assertEqual(k.attach_images(pathlib.Path(tmp),[]),(None,''))
        with patch.object(k,'find_kiro',return_value='kiro-cli'):
            self.assertIn('--v3',k.command(images=True))
            self.assertIn(k.IMAGE_AGENT['name'],k.command(images=True))
            self.assertNotIn('--v3',k.command())
        rule=k.IMAGE_AGENT['permissions']['rules'][0]
        self.assertEqual((rule['capability'],rule['effect'],rule['match']),('fs_read','allow',['shots/**']))


if __name__=='__main__':unittest.main()
