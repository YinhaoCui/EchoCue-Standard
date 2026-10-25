"""Kiro CLI headless transport (stream-json over stdin), using the local Kiro login."""
import base64
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import uuid
from session_support import Cancelled
from generation_context import render

PROVIDER = 'Kiro（本机登录）'
EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']
# A tool-free workspace agent: answers must come from the supplied text only.
AGENT = {'name': 'audio-qa', 'description': 'Answer supplied transcript and context only.',
         'tools': [], 'allowedTools': [], 'mcpServers': {}, 'resources': [], 'includeMcpJson': False}
# With screenshots attached: the read tool only, and the V3 engine, which enforces
# that reads outside shots/ are refused (V2 accepts path rules but ignores them).
IMAGE_AGENT = {'name': 'audio-qa-images', 'description': 'Answer supplied transcript, context and screenshots only.',
               'tools': ['read'], 'mcpServers': {}, 'resources': [], 'includeMcpJson': False,
               'permissions': {'rules': [{'capability': 'fs_read', 'effect': 'allow', 'match': ['shots/**']}]}}


def find_kiro():
    for name in ('kiro-cli.exe', 'kiro-cli'):
        found = shutil.which(name)
        if found:
            return found
    candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'Kiro-Cli/kiro-cli.exe'
    if candidate.is_file():
        return str(candidate)
    raise RuntimeError('Kiro CLI was not found. Install kiro-cli and run kiro-cli login.')


def workspace(root):
    folder = Path(root) / 'work/kiro-qa'
    agents = folder / '.kiro/agents'
    agents.mkdir(parents=True, exist_ok=True)
    for agent in (AGENT, IMAGE_AGENT):
        path = agents / (agent['name'] + '.json')
        text = json.dumps(agent, indent=2)
        if not path.is_file() or path.read_text(encoding='utf-8') != text:
            path.write_text(text, encoding='utf-8')
    return folder


def attach_images(folder, images):
    """Write screenshots into a fresh shots/ subfolder; return (folder, prompt text naming them)."""
    if not images:
        return None, ''
    shots = folder / 'shots' / uuid.uuid4().hex
    shots.mkdir(parents=True)
    lines = []
    for number, item in enumerate(images, 1):
        name = f'shot-{number}.png'
        (shots / name).write_bytes(base64.b64decode(item['data'], validate=True))
        lines.append(f"- shots/{shots.name}/{name} ({item.get('created', '')} · {item.get('title', 'Screenshot')})")
    return shots, ('Attached screenshots. As the one exception to the no-files rule, read each one with the read tool '
                   '(Image mode) before answering, without mentioning that you read it; read no other file:\n' + '\n'.join(lines) + '\n\n')


def command(model='', effort='自动', images=False):
    agent = (IMAGE_AGENT if images else AGENT)['name']
    args = [find_kiro(), 'chat', *(['--v3'] if images else []), '--no-interactive', '--output-format', 'stream-json',
            '--trust-tools=', '--agent', agent, '--wrap', 'never']
    if model.strip():
        args += ['--model', model.strip()]
    if effort in EFFORTS:
        args += ['--effort', effort]
    elif effort not in ('自动', '服务默认'):
        raise ValueError('Unsupported Kiro reasoning effort')
    return args


def parse_catalog(raw):
    data = json.loads(raw)
    models = []
    for item in data.get('models', []):
        value = item.get('model_id') if isinstance(item, dict) else None
        if isinstance(value, str) and value.strip() and value not in models:
            models.append(value)
    return models


def read_model_catalog(root, timeout=30):
    result = subprocess.run([find_kiro(), 'chat', '--list-models', '--format', 'json'],
                            capture_output=True, timeout=timeout, cwd=workspace(root),
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError('Kiro CLI could not list models. Check kiro-cli login.')
    models = parse_catalog(result.stdout.decode('utf-8', errors='replace'))
    if not models:
        raise RuntimeError('Kiro CLI returned an empty model catalog. You can still enter a model ID.')
    return models


def _forget(folder, session, v3=False):
    """Answers are one-shot; do not leave a saved chat per answer."""
    try:
        subprocess.run([find_kiro(), 'chat', *(['--v3'] if v3 else []), '--delete-session', session], cwd=folder, capture_output=True,
                       timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        pass


def kiro_answer(root, prompt, model, cancel, on_text, on_usage=None, total_timeout=600, effort='自动',
                images=(), thinking_policy='自动', session_key=None):
    if cancel.is_set():
        raise Cancelled()
    folder = workspace(root)
    instructions = Path(__file__).with_name('cli_instructions.md').read_text(encoding='utf-8')
    shots, attached = attach_images(folder, images)
    message = instructions + '\n\n' + attached + render(prompt)
    process = subprocess.Popen(command(model, effort, images=bool(images)), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=folder, creationflags=subprocess.CREATE_NO_WINDOW)
    events, errors = queue.Queue(), []

    def write():
        try:
            process.stdin.write(message.encode('utf-8'))
            process.stdin.close()
        except (OSError, ValueError):
            events.put(None)

    def read():
        try:
            for line in process.stdout:
                try:
                    events.put(json.loads(line))
                except (ValueError, UnicodeError):
                    pass
        finally:
            events.put(None)

    def drain():
        for line in process.stderr:
            errors.append(line.decode('utf-8', errors='replace')[-500:])
            del errors[:-5]

    threads = [threading.Thread(target=fn, daemon=True) for fn in (write, read, drain)]
    for thread in threads:
        thread.start()
    started, pieces, session = time.monotonic(), [], None
    try:
        while True:
            if cancel.is_set():
                raise Cancelled()
            if time.monotonic() - started > total_timeout:
                raise RuntimeError('Kiro answer timed out.')
            try:
                event = events.get(timeout=.1)
            except queue.Empty:
                continue
            if event is None:
                raise RuntimeError('Kiro CLI stopped without finishing. Check kiro-cli login and credits.')
            kind, data = event.get('type'), event.get('data') or {}
            session = data.get('sessionId') or session
            if kind == 'sessionUpdate':
                update = data.get('update', {})
                content = update.get('content', {})
                if update.get('sessionUpdate') == 'agent_message_chunk' and content.get('type') == 'text':
                    text = content.get('text', '')
                    if text:
                        pieces.append(text)
                        on_text(text)
            elif kind == 'runError':
                raise RuntimeError('Kiro CLI error: ' + str(data.get('message', 'unknown'))[:400])
            elif kind == 'runFinished':
                if data.get('status') != 'success':
                    raise RuntimeError('Kiro CLI did not finish the answer: ' + str(data.get('stopReason', 'unknown')))
                final, streamed = data.get('finalText') or '', ''.join(pieces)
                if final.startswith(streamed) and len(final) > len(streamed):
                    pieces.append(final[len(streamed):])
                    on_text(pieces[-1])
                if not pieces:
                    raise RuntimeError('Kiro CLI returned no text.')
                return ''.join(pieces)
    finally:
        try:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for pipe in (process.stdout, process.stderr):
            try:
                pipe.close()
            except (OSError, ValueError):
                pass
        if shots:
            shutil.rmtree(shots, ignore_errors=True)
        if session:
            threading.Thread(target=_forget, args=(folder, session, bool(images)), daemon=True).start()
