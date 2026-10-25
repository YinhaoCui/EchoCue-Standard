import unittest
import threading
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from localization import Locale
import audio_answer as a
import test_sessions


class LocaleTests(unittest.TestCase):
    def setUp(self):self.root=tk.Tk();self.root.withdraw();self.locale=Locale(self.root)
    def tearDown(self):self.root.destroy()

    def test_combobox_translates_display_but_keeps_internal_values(self):
        source=tk.StringVar(self.root,value='电脑')
        box=ttk.Combobox(self.root,textvariable=source,values=['电脑','麦克风'],state='readonly')
        self.assertEqual(source.get(),'电脑');self.assertEqual(box.get(),'电脑')
        self.assertEqual(box.tk.call(box._w,'get'),'System audio')
        box.current(1)
        self.assertEqual(source.get(),'麦克风');self.assertEqual(box.get(),'麦克风')
        self.assertEqual(box.tk.call(box._w,'get'),'Microphone')
        self.locale.set_language('zh');self.assertEqual(box.tk.call(box._w,'get'),'麦克风')
        box.set('电脑');self.locale.set_language('en')
        self.assertEqual(box.tk.call(box._w,'get'),'System audio')

    def test_entry_and_text_are_never_translated(self):
        source=tk.StringVar(self.root,value='电脑回答模型')
        entry=ttk.Entry(self.root,textvariable=source);text=tk.Text(self.root);text.insert('end','回答与资料')
        self.locale.set_language('zh');self.locale.set_language('en')
        self.assertEqual(entry.get(),'电脑回答模型');self.assertEqual(text.get('1.0','end-1c'),'回答与资料')

    def test_short_buttons_expand_for_english_and_restore_for_chinese(self):
        button=ttk.Button(self.root,text='继续',width=5)
        self.assertEqual(button.cget('text'),'Continue');self.assertGreaterEqual(button.cget('width'),8)
        self.locale.set_language('zh');self.assertEqual(button.cget('width'),5)

    def test_dynamic_labels_menu_tabs_and_dialog_titles_switch(self):
        value=tk.StringVar(self.root,value='准备');label=ttk.Label(self.root,textvariable=value)
        menu=tk.Menu(self.root);menu.add_command(label='回答')
        tabs=ttk.Notebook(self.root);pane=ttk.Frame(tabs);tabs.add(pane,text='资料与上下文')
        win=tk.Toplevel(self.root);win.title('快捷键设置')
        self.assertEqual(win.title(),'Keyboard shortcuts')
        value.set('停止监听')
        self.assertEqual(label.tk.globalgetvar(str(label.cget('textvariable'))),'Stop listening')
        self.assertEqual(value.get(),'停止监听')
        self.locale.set_language('zh')
        self.assertEqual(menu.entrycget(0,'label'),'回答');self.assertEqual(tabs.tab(pane,'text'),'资料与上下文')
        self.assertEqual(win.title(),'快捷键设置')


class EnglishAppTests(unittest.TestCase):
    initial_settings={}
    setUp=test_sessions.UITests.setUp
    tearDown=test_sessions.UITests.tearDown

    def test_default_english_switch_preserves_content_and_settings(self):
        self.assertEqual(self.ui.locale.language,'en');self.assertEqual(self.ui.locale.t('准备'),'Prepare')
        original=self.ui.advanced['asr_engine'].get()
        self.ui.put_text('模型输出：电脑回答',replace=True)
        self.ui.put_text('用户转录：资料',replace=True,target='transcript')
        self.ui.profile='个人资料：回答';self.ui.history=[{'回答':'既有回复'}]
        self.ui.change_ui_language('zh');self.assertEqual(self.ui.locale.language,'zh')
        self.ui.change_ui_language('en')
        self.assertEqual(self.ui.output_text,'模型输出：电脑回答')
        self.assertEqual(self.ui.transcript_view,'用户转录：资料')
        self.assertEqual(self.ui.profile,'个人资料：回答');self.assertEqual(self.ui.history,[{'回答':'既有回复'}])
        self.assertEqual(self.ui.advanced['asr_engine'].get(),original)

    def test_language_saved_even_without_api_key_storage(self):
        self.ui.remember_keys.set(False);self.ui.change_ui_language('zh');self.ui.save_preferences()
        self.assertEqual(a.save_settings.call_args.args[1]['ui_language'],'zh')
        self.assertNotIn('apis',a.save_settings.call_args.args[1])

    def test_lazy_panels_use_selected_language(self):
        self.ui.mic.audio.get_device_count.return_value=0
        self.ui.show_speed_test()
        self.assertEqual(self.ui.speed_window.title(),'Coding speed test')
        self.ui.change_ui_language('zh')
        self.assertEqual(self.ui.speed_window.title(),'Coding 回答测速')

    def test_language_switch_during_streaming_keeps_answer_and_request(self):
        self.ui.provider.set('LM Studio');self.ui.update_provider();self.ui.model.set('fixture')
        arrived=threading.Event();finish=threading.Event()
        def answer(*args,**kwargs):
            args[6]('回答正文');arrived.set();finish.wait(3);args[6](' remains unchanged')
        try:
            with patch.object(a,'compatible_answer',side_effect=answer):
                self.ui.ask(transcript_override='问题');self.assertTrue(arrived.wait(1));self.ui.poll()
                self.ui.change_ui_language('zh');self.ui.change_ui_language('en')
                job=self.ui.jobs[self.ui.ask_revision]
                self.assertFalse(job['cancel'].is_set());self.assertFalse(job['done'])
                self.assertIn('回答正文',self.ui.output_text)
                finish.set();self.ui.worker.join(2)
                for _ in range(5):self.ui.poll()
                self.assertEqual(job['answer'],'回答正文 remains unchanged')
        finally:finish.set()
