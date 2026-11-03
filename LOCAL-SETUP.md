# Running AVTR-1 mod-1 locally

The Moonshine + Chatterbox integration is on `develop` and `main`. Use `develop` for ongoing work; the former `local/jarvis-voice` branch was merged and deleted. Full installation, configuration, and architecture details are in [README.md](README.md).

## Existing Ubuntu installation

From the mod-1 checkout:

```bash
git switch develop
git pull --ff-only origin develop
export JARVIS_ROOT=/path/to/JARVIS-AI
./start-local.sh
```

Use your existing JARVIS-AI path. The launcher’s fallback is `/home/rob/Documents/Github/JARVIS-AI`. It reuses that checkout’s `venv/bin/python` and Chatterbox implementation. The current Codex client expects `~/.local/bin/codex` with an existing signed-in account.

Open **http://127.0.0.1:8081** and select **Jarvis · ChatGPT + Chatterbox**. Choose the Chatterbox voice, avatar, and background before starting. Allow the microphone and use headphones to reduce feedback. Stop with **Ctrl+C**.

| Service | Port |
| --- | --- |
| Browser interface / streamer | 8081 |
| Renderer | 8082 |
| Moonshine + Chatterbox adapter | 8083 |

## First-time preparation

Install Pixi and prepare the external JARVIS-AI speech environment as described in the README, then run:

```bash
pixi install
pixi run -e renderer download
pixi run -e renderer build-trt-engines
```

Downloads require Hugging Face access. Engines must be built for the target NVIDIA GPU. The recorded Ubuntu setup used an RTX 3090 with 24 GB VRAM.

## Voice and endpoint settings

Export speech settings before launch. Voice references are discovered from `$JARVIS_ROOT/backend/assets/voices`, or `CHATTERBOX_VOICES_DIR`. The browser selection determines the reference used for each synthesis request.

`JARVIS_VAD_RMS` defaults to 450. Recognition can start after 300 ms of silence, but the utterance is confirmed only after the 650 ms endpoint pause. Resumed speech invalidates the speculative transcript. Replies use complete-sentence TTS chunks with punctuation lookahead; the earlier eight-word chunk experiment is not active.

GPT replies use a persistent Codex connection per conversation with default model `gpt-6.1-sol` and effort `low`. Override through `AVTR_LLM_MODEL` and `AVTR_LLM_EFFORT`. This is an ephemeral text conversation with tools unavailable, not a connection to Hermes tools or JARVIS memories.

## Session logs

```bash
./start-local.sh 2>&1 | tee mod-1-session.log
```

The `voice timing:` lines measure transcription, first text, and synthesis. `first_audio=True` records publication to AVTR speech events, before renderer and browser playback. Use a recording with audio to assess actual answer onset and lip synchronization; do not treat the first-audio timer as end-to-end audible latency.
