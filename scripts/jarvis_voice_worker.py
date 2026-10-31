"""Local speech adapter, run with JARVIS-AI/venv/bin/python."""

import asyncio
import base64
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from moonshine_voice import Transcriber, get_model_for_language

JARVIS = Path(os.environ.get("JARVIS_ROOT", "/home/rob/Documents/Github/JARVIS-AI"))
sys.path.insert(0, str(JARVIS))
from backend.modules.chatterbox_client import ChatterboxTurboTTS  # noqa: E402

stt_lock = asyncio.Lock()
tts_lock = asyncio.Lock()
stt = None
tts = None


def get_stt():
    global stt
    if stt is None:
        path, arch = get_model_for_language("en")
        stt = Transcriber(model_path=path, model_arch=arch)
    return stt


def get_tts():
    global tts
    if tts is None:
        tts = ChatterboxTurboTTS(
            reference_audio=os.environ.get(
                "CHATTERBOX_REFERENCE_AUDIO", str(JARVIS / "backend/assets/voices/jarvis.wav")
            )
        )
    return tts


@asynccontextmanager
async def lifespan(app):
    # Pay cold model initialization at launch, before accepting a conversation.
    await asyncio.to_thread(get_stt)
    await get_tts().warmup()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "stt": "moonshine", "tts": "chatterbox-turbo"}


def voice_catalog():
    root = Path(os.environ.get("CHATTERBOX_VOICES_DIR", str(JARVIS / "backend/assets/voices")))
    return {
        p.stem: p
        for p in sorted(root.glob("*"))
        if p.is_file() and p.suffix.lower() in {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
    }


@app.get("/voices")
async def voices():
    return {
        "voices": [{"id": key, "name": key.replace("_", " ").title()} for key in voice_catalog()]
    }


@app.post("/transcribe")
async def transcribe(request: Request):
    global stt
    data = await request.json()
    audio = np.frombuffer(base64.b64decode(data["audio"]), dtype="<i2").astype(np.float32) / 32768

    def run():
        result = get_stt().transcribe_without_streaming(audio.tolist(), sample_rate=16000)
        return " ".join(line.text for line in result.lines).strip()

    async with stt_lock:
        text = await asyncio.to_thread(run)
    return {"text": text}


@app.post("/synthesize")
async def synthesize(request: Request):
    global tts
    data = await request.json()
    voice = str(data.get("voice") or "jarvis")
    reference = voice_catalog().get(voice)
    if reference is None:
        raise HTTPException(status_code=400, detail="Unknown Chatterbox voice")
    async with tts_lock:
        audio = await get_tts().synthesize_for(
            data["text"], reference_audio=str(reference), playback_rate=1.0
        )
    # Raise quiet synthesis without clipping peaks; keep silence unchanged.
    pcm = np.frombuffer(audio.audio, dtype="<i2").astype(np.float32) / 32768.0
    if pcm.size:
        peak = float(np.max(np.abs(pcm)))
        rms = float(np.sqrt(np.mean(pcm**2)))
        if peak > 0.001 and rms > 0.0001:
            target_rms = 10 ** (-16 / 20)
            gain = max(1.0, min(6.0, target_rms / rms, 0.95 / peak))
            pcm = np.clip(pcm * gain, -0.99, 0.99)
    output = (pcm * 32767).astype("<i2").tobytes()
    return {"audio": base64.b64encode(output).decode(), "sample_rate": audio.sample_rate}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("JARVIS_VOICE_PORT", "8083")))
