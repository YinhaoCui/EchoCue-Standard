import io
import json
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import app_paths
import dlx_translation as dlx
import test_sessions
from glass_bridge import GlassBridge
from caption_translation import translate as caption_translate


class DlxTests(unittest.TestCase):
    def test_request_and_optional_token(self):
        response = io.BytesIO(json.dumps(dict(code=200, data='你好')).encode())
        with patch.object(dlx, 'ensure_local') as start, patch('urllib.request.urlopen', return_value=response) as post:
            self.assertEqual(dlx.translate('Hello', 'zh', dlx.DEFAULT_URL, 'private-token', threading.Event()), '你好')
        start.assert_called_once()
        request = post.call_args.args[0]
        self.assertEqual(request.full_url, dlx.DEFAULT_URL)
        self.assertEqual(request.get_header('Authorization'), 'Bearer private-token')
        self.assertEqual(json.loads(request.data), dict(text='Hello', source_lang='auto', target_lang='ZH'))

    def test_chunks_preserve_all_text_and_utf16_limit(self):
        text = 'hello世界🙂 ' * 500
        pieces = list(dlx.chunks(text))
        self.assertEqual(''.join(pieces), text)
        self.assertTrue(all(len(p.encode('utf-16-le')) // 2 <= 1500 for p in pieces))

    def test_invalid_endpoint_rejects_credentials_and_remote_plaintext(self):
        for value in ('http://external.test', 'http://user:secret@localhost:1188',
                      'http://localhost:1188?token=secret', 'file:///x', 'http://localhost:bad', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                dlx.endpoint(value)
        self.assertEqual(dlx.endpoint('https://example.test/dlx'), 'https://example.test/dlx/translate')

    def test_bad_service_response_is_reported(self):
        for value in ({'code': 503, 'message': 'private-token'}, {'code': 200, 'data': []}, {}):
            with patch.object(dlx, 'ensure_local'), patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(value).encode())):
                with self.assertRaises(RuntimeError) as raised:
                    dlx.translate('Hello', 'zh', dlx.DEFAULT_URL, 'private-token', threading.Event())
                self.assertNotIn('private-token', str(raised.exception))

    def test_stop_only_terminates_application_owned_worker(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(dlx, '_process', process):
            dlx.stop()
            process.terminate.assert_called_once()
            dlx.stop()
            process.terminate.assert_called_once()

    def test_bundled_worker_starts_hidden_on_loopback_and_restarts_after_token_change(self):
        old, new = Mock(), Mock()
        old.poll.return_value = new.poll.return_value = None
        opener = Mock()
        opener.open.side_effect = [urllib.error.URLError('not listening'),
                                  io.BytesIO(b'{"message":"DLX Translation API"}')]
        with patch.object(dlx, '_process', old), patch.object(dlx, '_token', 'old-token'), \
                patch('pathlib.Path.is_file', return_value=True), \
                patch('urllib.request.build_opener', return_value=opener), \
                patch.object(dlx.subprocess, 'Popen', return_value=new) as launch:
            dlx.ensure_local(dlx.DEFAULT_URL, 'new-token', threading.Event())
            old.terminate.assert_called_once()
            self.assertEqual(dlx._process, new)
            self.assertEqual(launch.call_args.args[0][1:], ['-ip', '127.0.0.1', '-port', '1188'])
            self.assertEqual(launch.call_args.kwargs['env']['TOKEN'], 'new-token')
            self.assertEqual(launch.call_args.kwargs['creationflags'], getattr(dlx.subprocess, 'CREATE_NO_WINDOW', 0))

    def test_existing_local_service_is_reused_without_taking_ownership(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"message":"DeepL Free API"}')
        with patch.object(dlx, '_process', None), patch('urllib.request.build_opener', return_value=opener), \
                patch.object(dlx.subprocess, 'Popen') as launch:
            dlx.ensure_local(dlx.DEFAULT_URL, '', threading.Event())
            launch.assert_not_called()
            self.assertIsNone(dlx._process)

    def test_cancel_before_translation_does_not_start_worker(self):
        from session_support import Cancelled
        cancel = threading.Event(); cancel.set()
        with patch.object(dlx, 'ensure_local') as start, self.assertRaises(Cancelled):
            dlx.translate('Hello', 'zh', dlx.DEFAULT_URL, '', cancel)
        start.assert_not_called()


class DlxIntegrationTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_settings_key_privacy_and_independent_provider(self):
        self.ui.remember_keys.set(False)
        bridge = GlassBridge(self.ui)
        answer = self.ui.provider.get()
        bridge.settings(dict(caption_provider='DLX', dlx_url='http://localhost:1189', dlx_token='private-token'))
        inputs, error = self.ui.caption_models.inputs()
        self.assertIsNone(error)
        self.assertEqual(inputs['options']['dlx_url'], 'http://localhost:1189/translate')
        self.assertEqual(inputs['key'], 'private-token')
        self.assertNotIn('private-token', str(bridge.snapshot()))
        self.assertEqual(self.ui.provider.get(), answer)
        import audio_answer
        with patch.object(audio_answer, 'save_settings') as save:
            self.ui.remember_keys.set(True); self.ui.save_preferences()
            self.assertEqual(save.call_args.args[1]['dlx_token'], 'private-token')
            self.ui.remember_keys.set(False); self.ui.save_preferences()
            self.assertNotIn('dlx_token', save.call_args.args[1])

    def test_invalid_address_does_not_update_provider_or_token(self):
        before = self.ui.advanced['caption_provider'].get()
        with self.assertRaises(ValueError):
            GlassBridge(self.ui).settings(dict(caption_provider='DLX', dlx_url='http://external.test', dlx_token='secret'))
        self.assertEqual(self.ui.advanced['caption_provider'].get(), before)
        self.assertEqual(self.ui.dlx_token.get(), '')

    def test_caption_route_over_real_local_http_keeps_answer_provider_independent(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                requests.append((self.path, self.headers.get('Authorization'),
                                 json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                body = json.dumps(dict(code=200, data='你好')).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            GlassBridge(self.ui).settings(dict(caption_provider='DLX', dlx_token='fixture-token',
                                               dlx_url=f'http://127.0.0.1:{server.server_port}/translate'))
            inputs, error = self.ui.caption_models.inputs()
            self.assertIsNone(error)
            pieces = []
            import audio_answer
            with patch.object(audio_answer, 'compatible_answer') as llm:
                result = caption_translate(inputs, 'Hello', 'zh', threading.Event(), self.ui, pieces.append)
            llm.assert_not_called()
            self.assertEqual((result, pieces), ('你好', ['你好']))
            self.assertEqual(requests, [('/translate', 'Bearer fixture-token',
                                         dict(text='Hello', source_lang='auto', target_lang='ZH'))])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
