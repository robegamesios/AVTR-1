"""Moonshine -> signed-in Codex -> Chatterbox -> AVTR speech scheduler."""

import asyncio
import base64
import contextlib
import logging
import os
import time
import uuid

import httpx
import numpy as np

from avaturn_live_streamer.events import (
    DiscardAvatarSpeechBuffer,
    InputTranscript,
    ResponseTranscript,
    SegmentChunkGenerated,
    SegmentGenerationCompleted,
    SegmentGenerationStarted,
    Shutdown,
    TextEchoEnqueueText,
    UserSpeechReceived,
)
from avaturn_live_streamer.speech.speech_buffer import SpeechBuffer

from .codex_voice import CodexVoice
from .speech_phrases import phrase_boundary

_LOGGER = logging.getLogger(__name__)


class JarvisClient:
    def __init__(self, voice: str = "jarvis"):
        self.voice = voice

    async def run(self, bus, clocks):
        pending = asyncio.Queue(maxsize=2)
        response_task = None
        voice_url = os.environ.get("JARVIS_VOICE_URL", "http://127.0.0.1:8083")
        async with (
            httpx.AsyncClient(base_url=voice_url, timeout=180) as http,
            CodexVoice() as llm,
        ):
            (await http.get("/health")).raise_for_status()

            async def respond(text):
                started = time.monotonic()
                await bus.publish(InputTranscript(transcript=text, timestamp=time.time()))
                phrases = asyncio.Queue()
                reply = []
                first_audio = True

                async def speak():
                    nonlocal first_audio
                    while True:
                        phrase = await phrases.get()
                        if phrase is None:
                            return
                        tts_started = time.monotonic()
                        result = await http.post(
                            "/synthesize", json={"text": phrase, "voice": self.voice}
                        )
                        result.raise_for_status()
                        data = result.json()
                        audio = SpeechBuffer.from_bytes(
                            base64.b64decode(data["audio"]), data["sample_rate"]
                        ).resample(24000)
                        sid = uuid.uuid4().hex
                        await bus.publish(SegmentGenerationStarted(segment_id=sid))
                        await bus.publish(SegmentChunkGenerated(segment_id=sid, buffer=audio))
                        await bus.publish(SegmentGenerationCompleted(segment_id=sid))
                        elapsed = time.monotonic() - started
                        _LOGGER.info(
                            "voice timing: tts_ms=%.0f audio_seconds=%.2f first_audio=%s elapsed_ms=%.0f",
                            (time.monotonic() - tts_started) * 1000,
                            float(audio.duration),
                            first_audio,
                            elapsed * 1000,
                        )
                        first_audio = False

                async with asyncio.TaskGroup() as tasks:
                    tasks.create_task(speak())
                    buffer = ""
                    first_text = True
                    async for delta in llm.stream(text):
                        if first_text:
                            _LOGGER.info(
                                "voice timing: first_text_ms=%.0f",
                                (time.monotonic() - started) * 1000,
                            )
                            first_text = False
                        reply.append(delta)
                        buffer += delta
                        while True:
                            split = phrase_boundary(buffer)
                            if split is None:
                                break
                            await phrases.put(buffer[:split].strip())
                            buffer = buffer[split:].lstrip()
                    if buffer.strip():
                        await phrases.put(buffer.strip())
                    await phrases.put(None)
                    await bus.publish(
                        ResponseTranscript(transcript="".join(reply).strip(), timestamp=time.time())
                    )

            async def transcribe(audio):
                started = time.monotonic()
                result = await http.post(
                    "/transcribe", json={"audio": base64.b64encode(audio).decode()}
                )
                result.raise_for_status()
                _LOGGER.info("voice timing: stt_ms=%.0f", (time.monotonic() - started) * 1000)
                return result.json()["text"]

            async def responses():
                while True:
                    kind, value = await pending.get()
                    if kind == "audio":
                        value = await transcribe(value)
                    elif kind == "transcript_task":
                        waited = time.monotonic()
                        value = await value
                        _LOGGER.info(
                            "voice timing: stt_wait_after_pause_ms=%.0f",
                            (time.monotonic() - waited) * 1000,
                        )
                    if value.strip():
                        await respond(value)

            async with bus.subscribe(UserSpeechReceived, TextEchoEnqueueText, Shutdown) as sub:
                bus.ready()
                response_task = asyncio.create_task(responses())
                chunks = []
                silence = 0.0
                duration = 0.0
                prefetch = None
                speculative = set()

                def transcription_done(task):
                    speculative.discard(task)
                    if not task.cancelled() and task.exception() is not None:
                        _LOGGER.warning("speculative transcription failed: %s", task.exception())

                try:
                    async for event in sub:
                        if response_task.done():
                            await response_task
                        if isinstance(event, Shutdown):
                            return
                        if isinstance(event, TextEchoEnqueueText):
                            if not pending.full():
                                pending.put_nowait(("text", event.text))
                        elif isinstance(event, UserSpeechReceived):
                            buf = event.buffer.resample(16000)
                            raw = buf.to_bytes()
                            samples = np.frombuffer(raw, dtype="<i2").astype(np.float32)
                            loud = samples.size and float(np.sqrt(np.mean(samples**2))) > float(
                                os.environ.get("JARVIS_VAD_RMS", "450")
                            )
                            seconds = len(samples) / 16000
                            if loud:
                                # A resumed utterance invalidates the earlier snapshot.
                                # Let native transcription finish; never run it concurrently.
                                prefetch = None
                            if loud or chunks:
                                if loud and not chunks:
                                    await bus.publish(DiscardAvatarSpeechBuffer())
                                chunks.append(raw)
                                duration += seconds
                                silence = 0 if loud else silence + seconds
                                # Overlap STT with the existing 650 ms endpoint pause.
                                # Only confirmed turns reach the LLM; resumed speech
                                # discards the speculative result and keeps capturing.
                                if (
                                    silence >= 0.30
                                    and duration - silence >= 0.2
                                    and prefetch is None
                                    and not speculative
                                ):
                                    prefetch = asyncio.create_task(transcribe(b"".join(chunks)))
                                    speculative.add(prefetch)
                                    prefetch.add_done_callback(transcription_done)
                                if silence >= 0.65 or duration >= 25:
                                    if duration - silence >= 0.2 and not pending.full():
                                        if prefetch is not None:
                                            pending.put_nowait(("transcript_task", prefetch))
                                        else:
                                            pending.put_nowait(("audio", b"".join(chunks)))
                                    prefetch = None
                                    chunks, silence, duration = [], 0, 0
                finally:
                    response_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await response_task
                    if speculative:
                        await asyncio.gather(*speculative, return_exceptions=True)
