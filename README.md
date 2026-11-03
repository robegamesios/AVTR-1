# AVTR-1 mod-1 — JARVIS voice avatar

This is [robegamesios’s modified Linux version of AVTR-1](https://github.com/robegamesios/AVTR-1), called **mod-1**. It connects local Moonshine speech recognition, streamed GPT replies through a signed-in Codex session, and local Chatterbox Turbo speech synthesis to the AVTR-1 avatar renderer and browser interface.

The original [avaturn-live/avtr-1](https://github.com/avaturn-live/avtr-1) project is referred to as **origin** when comparing implementations. This fork retains its motion model, TensorRT renderer, speech scheduler, and WebRTC foundations, with a modified conversation pipeline and local launch workflow.

**`develop` is the default development branch. `main` also contains the Moonshine + Chatterbox integration.** The former `local/jarvis-voice` branch has been merged and deleted. This repository targets Linux with NVIDIA CUDA/TensorRT; Apple Silicon work is maintained separately in [AVTR-1-Mac](https://github.com/robegamesios/AVTR-1-Mac).

## What mod-1 adds

- Local English transcription with Moonshine, using the existing JARVIS-AI Python environment.
- A persistent Codex app-server connection per conversation, using the signed-in account for streamed text replies. The configured defaults are `gpt-6.1-sol` and low reasoning effort.
- Local Chatterbox Turbo synthesis through JARVIS-AI, with a selectable reference voice and output loudness normalization.
- Complete-sentence speech generation while later reply text is still arriving, including punctuation lookahead for abbreviations and decimals.
- Speculative transcription after 300 ms of silence, overlapping recognition with the 650 ms endpoint pause. Resumed speech invalidates the earlier snapshot; only a confirmed turn reaches the language model.
- Speech-model warmup at launch, voice selection in the browser, adjustable playback volume, and timing logs for recognition, first text, and synthesis.

## Conversation flow

```text
Browser microphone → Moonshine → Codex streamed reply → sentence queue
                                                        ↓
Browser audio + avatar ← WebRTC ← AVTR renderer ← Chatterbox Turbo PCM
```

Speech recognition and synthesis run locally. Reply text is processed through the signed-in Codex service, so this conversation mode requires an internet connection and account access. It uses an ephemeral conversation thread, with tools unavailable; it does not connect to Hermes tools or JARVIS memories.

## Requirements

- Linux x86-64 and an NVIDIA GPU compatible with the renderer’s TensorRT engines.
- A CUDA 12.8-compatible driver/runtime setup and the dependencies defined in `pixi.toml` and `pixi.lock`.
- [Pixi](https://pixi.sh/) for separate renderer and streamer environments.
- A working JARVIS-AI checkout with `venv/bin/python`, `moonshine_voice`, and `backend.modules.chatterbox_client.ChatterboxTurboTTS`, plus that module’s speech dependencies and model assets. This fork imports that implementation rather than bundling JARVIS-AI.
- A signed-in Codex executable at `~/.local/bin/codex`, as used by the current client.
- At least one Chatterbox reference recording, normally `JARVIS-AI/backend/assets/voices/jarvis.wav`.

The existing Ubuntu setup was prepared with an RTX 3090 with 24 GB VRAM. That is a tested setup, not a minimum hardware specification.

## Install and launch

```bash
git clone --branch develop https://github.com/robegamesios/AVTR-1.git
cd AVTR-1
pixi install
```

Optionally set the model storage directory before downloading and building. Its default is this checkout’s `artifacts/` directory.

```bash
export AVTR1_LOCAL_STORAGE=/path/to/avtr1_storage
```

Download model assets and build the engines for this GPU:

```bash
pixi run -e renderer download
pixi run -e renderer build-trt-engines
```

The download task invokes Hugging Face login. It retrieves AVTR-1 assets from [avaturn-live/avtr-1](https://huggingface.co/avaturn-live/avtr-1) and renderer dependencies from [digital-avatar/ditto-talkinghead](https://huggingface.co/digital-avatar/ditto-talkinghead). TensorRT engines are built locally for the target GPU.

Set the actual JARVIS-AI location and start mod-1:

```bash
export JARVIS_ROOT=/path/to/JARVIS-AI
./start-local.sh
```

The launcher starts the speech adapter and the renderer/streamer orchestrator. It waits for service readiness before starting the browser server. Open **http://127.0.0.1:8081**, select **Jarvis · ChatGPT + Chatterbox**, choose a voice, avatar, and background, and start the conversation. Allow microphone access. Headphones reduce speaker feedback. Stop the launcher with **Ctrl+C**.

| Service | Default address |
| --- | --- |
| Browser / WebRTC streamer | `http://127.0.0.1:8081` |
| Renderer | `http://localhost:8082` |
| Local speech adapter | `http://127.0.0.1:8083` |

The renderer currently binds to `0.0.0.0`; the browser server defaults to loopback. These addresses describe the local launcher, not a public deployment configuration.

## Configuration

Export these variables in the shell before `./start-local.sh`. This is especially important for speech-worker settings: the launcher starts that worker before the orchestrator loads `.env`.

| Variable | Default / purpose |
| --- | --- |
| `JARVIS_ROOT` | `/home/rob/Documents/Github/JARVIS-AI`; set this to your checkout |
| `CHATTERBOX_VOICES_DIR` | `$JARVIS_ROOT/backend/assets/voices`; browser voice catalog |
| `CHATTERBOX_REFERENCE_AUDIO` | `$JARVIS_ROOT/backend/assets/voices/jarvis.wav`; initial model reference |
| `JARVIS_VOICE_PORT` | `8083`; speech-worker port |
| `JARVIS_VOICE_URL` | `http://127.0.0.1:8083`; streamer’s speech endpoint; update when changing the worker port |
| `AVTR_LLM_MODEL` | `gpt-6.1-sol` |
| `AVTR_LLM_EFFORT` | `low` |
| `JARVIS_VAD_RMS` | `450`; microphone energy threshold for speech detection |
| `STREAMER_PORT` | `8081` through `start-local.sh` |
| `RENDERER_PORT` | `8082` through `start-local.sh` |
| `AVTR_VIDEO_BITRATE` | `6000000` bits/s |
| `AVTR_VIDEO_MIN_BITRATE` | `2000000` bits/s |
| `AVTR_VIDEO_MAX_BITRATE` | `12000000` bits/s |

Voice references can be WAV, FLAC, MP3, OGG, or M4A files. The browser remembers the selected voice for the next conversation. Per-request synthesis uses the selected catalog file; setting the initial reference alone does not replace the catalog.

The inherited OpenAI Realtime and Cartesia conversation options remain available with their own configuration. They are alternatives to the mod-1 JARVIS pipeline. Optional STUN/TURN settings are listed in [.env.example](.env.example); direct local/LAN connections usually do not require a TURN relay.

## Performance and timing

The renderer targets 25 fps and generates five frames per motion chunk, corresponding to 200 ms of playback. Actual conversational latency also includes endpoint detection, recognition, first reply text, sentence completion, synthesis, rendering, and browser delivery.

The Ubuntu recording and session logs supplied on November 3, 2026 are the mod-1 comparison reference for the Mac port. They demonstrate the desired natural idle animation and smooth conversational playback in that session. They do not establish a universal latency or hardware guarantee. The upstream GPU benchmark table has been removed because it did not measure this modified conversation pipeline.

Capture a session log:

```bash
./start-local.sh 2>&1 | tee mod-1-session.log
```

Look for `voice timing:` entries:

- `stt_ms`: transcription request duration.
- `stt_wait_after_pause_ms`: remaining transcription wait after the endpoint gate.
- `first_text_ms`: time to the first text delta after reply processing starts.
- `tts_ms` and `audio_seconds`: synthesis duration and generated audio length.
- `first_audio=True` with `elapsed_ms`: time until the first generated audio is published to AVTR’s speech events.

**First audio published is earlier than rendered, audible browser playback.** These timers do not independently measure microphone-question-end to audible-answer latency. The old `turn-latency-measurement` experiment was not merged, so its `latency_table.py` tool is not part of this version.

## Troubleshooting

- **Speech worker fails to import:** check `JARVIS_ROOT`, its `venv/bin/python`, Moonshine, and the JARVIS Chatterbox module. Pixi does not install that external environment.
- **No voices:** check the reference files in `CHATTERBOX_VOICES_DIR` and the speech adapter’s `/voices` endpoint.
- **No GPT reply:** check the Codex executable path and account sign-in on the same Linux user account that runs the launcher.
- **Speech is missed or background noise triggers turns:** adjust `JARVIS_VAD_RMS`, check the microphone, and use headphones.
- **Renderer startup fails:** verify model downloads, compatible CUDA/TensorRT dependencies, and locally built engines for this GPU.
- **WebRTC cannot connect remotely:** use the browser connectivity probe and configure STUN/TURN as needed through `.env.example`. Remote microphone access also depends on the browser’s secure-context requirements.

See [LOCAL-SETUP.md](LOCAL-SETUP.md) for a short operational checklist.

## Offline rendering

The inherited renderer can still generate an avatar video from recorded speech or silence:

```bash
pixi run -e renderer generate_offline --speech example/speaker_1.ogg
pixi run -e renderer generate_offline --speech example/speaker_1.ogg --avatar maria --bg minimal_office
pixi run -e renderer generate_offline --duration 10
```

## Attribution and licenses

Mod-1 builds on [AVTR-1 by Avaturn / Goodsize Inc.](https://github.com/avaturn-live/avtr-1). The original model, renderer, streamer, and their notices retain their respective licenses. The local integration also depends on Moonshine, Chatterbox Turbo, Codex, and the external JARVIS-AI implementation; their applicable terms remain separate.

Preserved repository notices:

- [License and component map](LICENSE.md)
- [Model and tooling license](LICENSE-MODEL.md)
- [Renderer license and required notice](LICENSE-RENDERER.md)
- [Streamer license and required notice](LICENSE-STREAMER.md)
- [Patent notice](PATENTS.md)
- [Third-party notices](THIRD-PARTY-NOTICES.md)

The fork does not replace or relicense the upstream components. Consult those files for the terms that apply to each component.
