"""Independent answer jobs with stable text regions and full transcript snapshots."""

import subprocess
import re
import hashlib
import threading
import time
import uuid
from session_support import local_base
import option_values
import providers
from answer_runner import AnswerRunner, build_prompt  # noqa: F401 - build_prompt is re-exported
from prompt_language import (
    choose,
    for_inputs,
    language,
    output_rule,
    preparation,
)

QUESTION_HINT = re.compile(
    r'[?？]|吗|呢|什么|怎么|怎样|为什么|为何|如何|哪|多少|是否|能不能|可不可以|有没有|是不是|'
    r'请问|解释|介绍|说说|讲讲|区别'
)
ENGLISH_QUESTION = re.compile(
    r'(?:^|[.!]\s+|\n)\s*(?:(?:please|okay|ok|well|so|hey|hi)[,\s]+)*'
    r'(?:what|why|how|when|where|which|who|whose|whom|can|could|would|should|do|does|did|is|are|am|'
    r'was|were|will|shall|have|has|had|may|might|must|tell\s+me|explain|describe|help\s+me)\b',
    re.I,
)


def looks_like_question(text):
    text = re.sub(r'(?m)^\[\d{2}:\d{2}(?::\d{2})?[^\]\n]*\]\s*', '', text or '')
    return bool(QUESTION_HINT.search(text) or ENGLISH_QUESTION.search(text))


def request_signature(inputs, transcript):
    """Everything that changes the request; a speculation is only reused when this is identical."""
    # Appearance, capture and caption settings do not change an already transcribed answer.
    selected = {'lm_base', 'thinking_policy', 'incremental_context'}
    if providers.is_cli(inputs['provider']):
        selected.add(providers.model_option(inputs['provider']))
    options = tuple(sorted((k, v) for k, v in inputs['options'].items() if k in selected))
    images = tuple(
        (i.get('created'), i.get('title'), hashlib.sha256(i.get('data', '').encode()).hexdigest())
        for i in inputs['images']
    )
    return (
        inputs['provider'],
        inputs['key'],
        inputs['model'],
        options,
        inputs['effort'],
        inputs['reasoning'],
        inputs['fast'],
        inputs['timeout'],
        inputs['output_limit'],
        images,
        inputs['context_version'],
        build_prompt(inputs, transcript),
        transcript,
    )


class Speculation:
    """An answer started when a segment is finalized; its events are buffered until a hotkey adopts it."""

    def __init__(self, events, signature, target, transcript):
        self.events, self.signature, self.target, self.transcript = events, signature, target, transcript
        self.cancel = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.buffer = []
        self.request_id = None
        self.release_callback = None
        self.clock = {'start': time.monotonic()}
        self.worker = None
        self.ledger_id = 'spec-' + uuid.uuid4().hex[:8]

    def send(self, kind, value):
        with self.lock:
            if self.request_id is None:
                self.buffer.append((kind, value))
                return
            request_id = self.request_id
        self.events.put(('job', (request_id, kind, value)))

    def ledger(self):
        return self.ledger_id if self.request_id is None else str(self.request_id)

    def discard(self):
        self.cancel.set()
        self.wake.set()
        with self.lock:
            callback, self.release_callback = self.release_callback, None
        if callback:
            callback(False)

    def release_when_decided(self, callback):
        with self.lock:
            if self.request_id is None and not self.cancel.is_set():
                self.release_callback = callback
                return
        callback(not self.cancel.is_set())

    def adopt(self, request_id, pressed):
        with self.lock:
            self.request_id = request_id
            self.clock['start'] = pressed
            self.events.put(('job', (request_id, 'timing', {'speculative': True})))
            for kind, value in self.buffer:
                if kind == 'timing':
                    # Work done before the key press costs the user nothing.
                    value = {
                        k: (0.0 if k in ('asr_wait', 'model_start', 'first_total') else v) for k, v in value.items()
                    }
                self.events.put(('job', (request_id, kind, value)))
            self.buffer.clear()
            callback, self.release_callback = self.release_callback, None
        self.wake.set()
        if callback:
            callback(True)

    def wait_to_generate(self):
        self.wake.wait(0.35)
        return not self.cancel.is_set()


class AnswerJobs:
    def job_transcript(self, job):
        if job.get('target') is not None:
            from session_data import record_text

            with self.live.lock:
                return record_text(self.live.records, job['target'])
        return job.get('transcript', '')

    def add_answer_region(self, request_id, text=''):
        """Reserve the place in the answer log where this job's text streams in."""
        self.job_regions[request_id] = len(self.output_parts)
        self.output_parts.extend((text, '\n'))

    def job_text(self, request_id, text):
        if request_id not in self.jobs:
            return
        if request_id not in self.job_regions:
            self.add_answer_region(request_id)
        self.output_parts[self.job_regions[request_id]] += text

    def cancel_job(self, request_id, message='已取消此回答。'):
        job = self.jobs.get(request_id)
        if job and not job['done']:
            job['cancel'].set()
            job['done'] = True
            job['state'] = '已取消'
            job['elapsed'] = time.monotonic() - job['started']
            self.job_text(request_id, '\n[' + self.locale.t(message) + ']\n')
        self.busy = any(not j['done'] for j in self.jobs.values())

    def cancel_answer(self, message='已取消全部回答；实时转录继续。'):
        self.cancel_context_preparation()
        spec = getattr(self, 'speculation', None)
        if spec:
            spec.discard()
            self.speculation = None
        for request_id in self.jobs:
            self.cancel_job(request_id, message)
        self.busy = False
        self.status.set(message)

    def cancel_context_preparation(self):
        cancel = getattr(self, 'context_warm_cancel', None)
        if cancel:
            cancel.set()
        self.context_warm_ticket = None
        if hasattr(self, 'context_warm_note'):
            self.context_warm_note.set('上下文准备已停止；下次回答仍会携带完整资料。')

    def prepare_model_context(self, spare_only=False):
        if self.advanced['warm_context'].get() != option_values.ON:
            return
        worker = getattr(self, 'context_warm_worker', None)
        if worker and worker.is_alive():
            return
        inputs, error = self.request_inputs()
        if error:
            self.context_warm_note.set('上下文未发送：' + error)
            return
        group = inputs.get('session_key')
        if group and self.generation_lanes.contains(group):
            return
        signature = request_signature(inputs, preparation(for_inputs(inputs)))
        if not group and getattr(self, 'prepared_context_signature', None) == signature:
            return
        self.cancel_context_preparation()
        inputs['timeout'] = min(inputs['timeout'], 90)
        inputs['_preparing'] = True
        inputs['_fresh_lane'] = True
        ticket = uuid.uuid4().hex
        self.context_warm_ticket = ticket
        cancel = self.context_warm_cancel = threading.Event()
        self.context_warm_note.set('正在发送上下文；监听与回答可继续。')
        prepared_ok = [False]
        prepared_stateful = [True]

        def send(kind, value):
            if cancel.is_set():
                return
            if kind == 'transport_mode':
                prepared_stateful[0] = value == 'stateful'
            if kind == 'completed':
                prepared_ok[0] = True
                self.prepared_context_signature = signature
                note = (
                    '上下文准备请求已完成；可续接通道将复用空闲会话。'
                    if inputs['provider'] in STATEFUL
                    else '上下文已发送；后续携带完整资料，缓存命中由服务决定。'
                )
                self.events.put(('context_warm', (ticket, note)))
            elif kind == 'text' and '[处理失败' in value:
                self.events.put(('context_warm', (ticket, '上下文准备失败：' + value)))

        text = preparation(for_inputs(inputs))
        from generation_context import STATEFUL

        count = 1
        initial_available = self.generation_lanes.available(inputs.get('session_key'))

        def prepare():
            for number in range(count):
                if cancel.is_set():
                    break
                prepared_ok[0] = False
                inputs['_fresh_lane'] = number >= initial_available
                self.run_request(
                    inputs,
                    text,
                    None,
                    cancel,
                    send,
                    {'start': time.monotonic()},
                    lambda n=number: 'context-warm-' + ticket + '-' + str(n),
                )
                if not prepared_ok[0] or not prepared_stateful[0]:
                    break

        self.context_warm_worker = threading.Thread(target=prepare, daemon=True)
        self.context_warm_worker.start()

    def ensure_spare_context(self):
        # No paid replenishment; active requests create a lane only when needed.
        return

    def request_inputs(self, analysis=False, continuation=None, caption=False):
        """Collect everything an answer depends on. Returns (inputs, error message)."""
        import audio_answer as a
        import copy

        provider = self.provider.get()
        documents = self.documents
        image_input = providers.accepts_images(provider)
        if not caption and self.context_images and not image_input:
            # No image input on this provider: send what Windows OCR reads in each screenshot.
            from image_text import screenshot_text

            try:
                text = screenshot_text(self.context_images, a.WORK)
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
                return None, '当前通道不支持图片，且无法识别截图文字。请选择支持截图的模型，或在“查看截图”中移除图片。'
            documents = (documents + '\n\n' if documents.strip() else '') + '截图文字（OCR）：\n' + text
        key, model = self.key.get().strip(), self.model.get().strip()
        if provider in a.API_PROVIDERS and provider != 'LM Studio' and not key:
            return None, '请填写当前平台的 Key。'
        if provider == 'LM Studio' and (not model or model == '选择或刷新本地模型'):
            return None, '请刷新本地模型目录并选择模型。'
        options = {k: v.get() for k, v in self.advanced.items()}
        if provider == 'LM Studio':
            try:
                local_base(options['lm_base'])
            except ValueError as exc:
                return None, str(exc)
        images = [] if caption or not image_input else copy.deepcopy(self.context_images)
        history = copy.deepcopy(self.history) if self.use_history.get() and not caption else []
        with self.live.lock:
            context_records = [] if caption else copy.deepcopy(self.live.records)
        answer_language = self.content_language('answer')
        lang = language(provider, model)
        instructions = self.instructions.get()
        if not caption:
            instructions += '\n' + output_rule(lang, answer_language)
        if not caption and not analysis and options.get('question_mode') == '长问题':
            instructions += choose(
                lang,
                '\n这是已确认提交的完整长问题。结合全部原文，区分背景、示例、限制条件和最终请求；同一要求的后续明确修正优先。不要只回答最后一个转录片段。先给核心结论或方案，再解释并提供必要的完整代码；只有缺失关键条件时才追问。',
                '\nThis is a complete long question explicitly submitted by the user. Use the full original input: distinguish background, examples, constraints and the final request; honor explicit later corrections to the same requirement. Do not answer only the last transcript segment. Lead with the conclusion or approach, then explain and include complete code when needed. Ask a clarification only when a critical requirement is missing.',
            )
        if continuation is not None:
            instructions += (
                choose(
                    lang,
                    '\n接着未完成回答继续，不重复，补齐未答部分：\n',
                    '\nContinue this unfinished answer without repeating completed sections:\n',
                )
                + self.jobs[continuation]['answer']
            )
        effort = self.reasoning_selection.get()
        reasoning = self.answer_mode.get() in ('推理', 'Coding')
        from reasoning_support import thinking_policy

        cli = providers.is_cli(provider)
        identity_model = options[providers.model_option(provider)] if cli else model
        effort, reasoning, thinking_instruction = thinking_policy(
            provider,
            identity_model,
            effort,
            options.get('thinking_policy', '自动'),
            reasoning,
            getattr(self, 'codex_capabilities', {}),
        )
        if effort == '自动' and not reasoning and options.get('thinking_policy', '自动') == '自动':
            from reasoning_support import choices

            available = choices(provider, identity_model, getattr(self, 'codex_capabilities', {}))[2:]
            effort = next((level for level in ('关闭', 'none', 'minimal', 'low') if level in available), '自动')
        if provider == providers.ANTIGRAVITY:
            from antigravity_support import quick_effort, resolve_model

            if effort == '自动' and not reasoning:
                effort = quick_effort(identity_model)
            try:
                options['antigravity_model'] = resolve_model(identity_model, effort)
            except ValueError as exc:
                return None, str(exc)
        if thinking_instruction:
            instructions += '\n' + thinking_instruction
        if self.answer_mode.get() == 'Coding':
            instructions += choose(
                lang,
                '\n给出完整代码与必要步骤，不用省略号代替实现。',
                '\nProvide complete code and necessary steps; do not replace implementation with ellipses.',
            )
        display_model = (
            (options[providers.model_option(provider)] or providers.get(provider).default_model) if cli else model
        )
        return dict(
            provider=provider,
            key=key,
            model=model,
            options=options,
            effort=effort,
            reasoning=reasoning,
            answer_language=answer_language,
            fast=self.fast_mode.get() and not reasoning,
            timeout=option_values.seconds(options['deadline']),
            output_limit=option_values.tokens(options['max_output']),
            instructions=instructions,
            terms=getattr(self, 'terms', ''),
            profile=self.profile,
            documents=documents,
            summary=self.context_summary,
            images=images,
            history=history,
            context_records=context_records,
            analysis=analysis,
            context_version=self.context_version,
            history_epoch=getattr(self, 'history_epoch', 0),
            session_key=(
                self.session_id,
                getattr(self, 'history_epoch', 0),
                self.context_version,
                provider,
                display_model,
                effort,
                options.get('thinking_policy', '自动'),
            )
            if self.use_history.get()
            else None,
            display_model=display_model,
        ), None

    def change_question_mode(self, *_):
        """Discard only unclaimed predictions; explicit jobs keep their input snapshot."""
        spec = getattr(self, 'speculation', None)
        if spec:
            spec.discard()
            self.speculation = None

    def claim_speculation(self, inputs, target):
        spec, self.speculation = getattr(self, 'speculation', None), None
        if spec is None:
            return None
        if spec.target == target and not spec.cancel.is_set():
            from session_data import record_text

            with self.live.lock:
                transcript = record_text(self.live.records, target)
            if spec.signature == request_signature(inputs, transcript):
                return spec
        spec.discard()
        return None

    def maybe_speculate(self, record):
        """Start answering a just-finalized segment in the background; the hotkey may adopt it."""
        if getattr(self, 'closing', False):
            return
        if getattr(self, 'transcription_paused', False):
            return
        old = getattr(self, 'speculation', None)
        if old:
            old.discard()
            self.speculation = None
        if self.advanced.get('question_mode') and self.advanced['question_mode'].get() == '长问题':
            return
        mode = self.advanced['speculate'].get() if 'speculate' in self.advanced else option_values.OFF
        body = record.get('body', '')
        if mode == option_values.OFF or not record.get('ok', True) or not body.strip():
            return
        if mode == option_values.QUESTIONS and not looks_like_question(body):
            return
        target = record['sequence']
        if self.live.submitted != target:
            return  # more speech queued; its own segment will speculate
        inputs, error = self.request_inputs()
        if error:
            return
        from session_data import record_text

        with self.live.lock:
            transcript = record_text(self.live.records, target)
        if not transcript.strip():
            return
        spec = Speculation(self.events, request_signature(inputs, transcript), target, transcript)
        inputs['_speculation'] = spec

        def generate():
            if spec.wait_to_generate():
                self.run_request(inputs, transcript, target, spec.cancel, spec.send, spec.clock, spec.ledger)

        spec.worker = threading.Thread(target=generate, daemon=True)
        self.speculation = spec
        spec.worker.start()

    def ask(
        self,
        analysis=False,
        reuse=False,
        continuation=None,
        transcript_override=None,
        pressed_at=None,
        target_override=None,
        instruction_override=None,
        purpose=None,
    ):
        pressed = time.monotonic() if pressed_at is None else pressed_at
        if getattr(self, 'closing', False):
            return
        transcript, target, live_request = None, None, False
        if target_override is not None:
            target, live_request = target_override, True
        elif transcript_override is not None:
            transcript = transcript_override
            if not transcript.strip():
                self.status.set('该任务尚无转录，请等待转录完成后重试。')
                return
        elif continuation is not None:
            transcript = self.job_transcript(self.jobs[continuation])
        elif reuse:
            index = self.selected_transcript
            if not 0 <= index < len(self.transcript_records):
                self.status.set('请先选择一段转录。')
                return
            transcript = self.transcript_records[index]['text']
        elif not analysis:
            target = self.live.flush()
            live_request = bool(target)
            if not target:
                if self.context_images:
                    transcript = '请结合上下文截图与补充要求回答；未指定问题时先分析截图。'
                    target = None
                else:
                    self.status.set('请开始监听；说完一句后即可看到转录。')
                    return
        inputs, error = (
            self.request_inputs(analysis, continuation, caption=True)
            if purpose == 'recap'
            else self.request_inputs(analysis, continuation)
        )
        if error:
            self.status.set(error)
            return
        if purpose == 'recap':
            inputs.update(
                profile='',
                documents='',
                summary='',
                images=[],
                history=[],
                session_key=None,
                instructions=output_rule(for_inputs(inputs), inputs.get('answer_language', 'en')),
            )
        if instruction_override:
            inputs['instructions'] += '\n\nCurrent request / 本次请求：\n' + instruction_override
        speculation = self.claim_speculation(inputs, target) if live_request and not instruction_override else None
        if hasattr(self, 'auto_answers') and target is not None and purpose != 'recap':
            pending = self.auto_answers.pending
            if pending and target >= pending[0]:
                self.auto_answers.dispatched(time.monotonic())
        provider, effort, display_model = inputs['provider'], inputs['effort'], inputs['display_model']
        self.schedule_save()
        self.ask_revision += 1
        request_id = self.ask_revision
        cancel = speculation.cancel if speculation else threading.Event()
        self.cancel = cancel
        label = (
            f'#{request_id} '
            + time.strftime('%H:%M:%S')
            + ' · '
            + provider
            + ' / '
            + display_model
            + ' · 思考：'
            + effort
        )
        action = '资料分析' if analysis else ('继续回答' if continuation is not None else '文字回答')
        if purpose:
            en, zh = {
                'recap': ('Meeting recap', '会议整理'),
                'automatic': ('Automatic answer', '自动回答'),
                'followup': ('Follow-up answer', '追问回答'),
            }.get(purpose, ('Answer', '回答'))
            action = en if self.locale.language == 'en' else zh
            label += ' · ' + action
        self.jobs[request_id] = {
            'cancel': cancel,
            'done': False,
            'started': pressed,
            'timeout': inputs['timeout'],
            'answer': '',
            'transcript': transcript or (speculation.transcript if speculation else ''),
            'label': label,
            'history_epoch': inputs['history_epoch'],
            'target': target,
            'state': '等待转录',
            'provider': provider,
            'model': display_model,
            'effort': effort,
            'prediction_eligible': live_request,
            'timing': {'dispatch': time.monotonic() - pressed, 'speculative': bool(speculation)},
        }
        self.jobs[request_id]['purpose'] = purpose
        self.busy = True
        if speculation:
            speculation.adopt(request_id, self.jobs[request_id]['started'])
            self.worker = speculation.worker
            self.status.set(f'任务 #{request_id} 使用说完时已开始的预生成回答。')
        else:
            self.status.set(f'已创建独立任务 #{request_id}，此前任务继续运行。')

            def send(kind, value):
                self.events.put(('job', (request_id, kind, value)))

            clock = {'start': pressed}
            self.worker = threading.Thread(
                target=self.run_request,
                daemon=True,
                args=(inputs, transcript, target, cancel, send, clock, lambda: str(request_id)),
            )
            self.worker.start()
        # Worker events are queued; the poll loop applies them after this returns.
        self.put_text(
            '\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' + self.locale.t(label) + ' · ' + self.locale.t(action) + '\n'
        )
        self.add_answer_region(request_id)
        self.job_labels[request_id] = label
        return request_id

    def run_request(self, inputs, transcript, target, cancel, send, clock, ledger_id):
        AnswerRunner(
            live=self.live,
            generation_lanes=self.generation_lanes,
            token_ledger=self.token_ledger,
            events=self.events,
            session_id=self.session_id,
        ).run(inputs, transcript, target, cancel, send, clock, ledger_id)
