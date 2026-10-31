# Local Jarvis avatar

Installed in `/home/rob/Documents/Github/AVTR-1`, branch `local/jarvis-voice`, upstream `avaturn-live/avtr-1`. GitHub fork: https://github.com/robegamesios/AVTR-1 (`origin`); original repository is `upstream`. The integration changes are local on branch `local/jarvis-voice`.

## Current status

- Pixi installed; renderer and streamer environments installed.
- RTX 3090 24 GB detected.
- Chatterbox Turbo synthesized a 24 kHz voice clip using the existing Jarvis runtime and voice.
- Moonshine transcribed that clip successfully.
- Codex returned a response using the existing ChatGPT login.
- Hugging Face access granted; all model assets downloaded; all seven TensorRT engines built for the RTX 3090.
- Renderer and UI healthy on ports 8082 and 8081. App started with `start-local.sh`.
- Existing renderer API check produced `example/jarvis-avatar.mp4`: 85 frames (3.4 seconds) rendered in 2.7 seconds from Chatterbox audio.
- The conversation engine check returned a ChatGPT reply and 5.74 seconds of 24 kHz PCM through AVTR speech events.
- Browser WebRTC connected and reached transcription/synthesis. A separate aiortc verification client failed ICE negotiation during concurrent browser use; that client did not verify returned live video/audio.

To reproduce the setup from this directory (Hugging Face login and downloads are already complete):

```bash
export PATH="$HOME/.pixi/bin:$PATH"
pixi run -e renderer hf auth login
pixi run -e renderer python scripts/download_artifacts.py
pixi run -e renderer build-trt-engines
./start-local.sh
```

Open http://127.0.0.1:8081 and choose **Jarvis · ChatGPT + Chatterbox**, an avatar and background, then Start. Grant microphone permission. Headphones improve speech recognition by reducing speaker feedback.

Ports: avatar UI 8081, renderer 8082, local speech adapter 8083. Stop with Ctrl+C.

The speech adapter reuses `../JARVIS-AI/venv` and its Chatterbox implementation and voice references. Set `JARVIS_ROOT` or `CHATTERBOX_REFERENCE_AUDIO` to override those paths. Moonshine runs locally. Text is sent to Codex through the existing ChatGPT login; account usage limits apply. This adapter uses Codex app-server with an ephemeral per-session conversation thread, rather than Hermes tools and Jarvis memories.

The current integration waits for a pause, transcribes with Moonshine, streams GPT text over one persistent Codex app-server connection per conversation, and synthesizes complete sentence-sized phrases with Chatterbox while later text is still arriving. AVTR receives the generated PCM audio for synchronized rendering. GPU coexistence and rendered video were verified. Lip-sync quality and live conversational latency should be judged in the browser; subjective playback has not been verified. Speech endpointing currently uses an adjustable energy threshold (`JARVIS_VAD_RMS`, default 450) and 650 ms silence.

Speaker volume: use the slider below the microphone selector (0–1000%). Generated Chatterbox audio is normalized toward −16 dBFS RMS with peak headroom. LLM is explicitly `gpt-6.1-sol`; set `AVTR_LLM_MODEL` before launch to override.

Change voice: select **Jarvis · ChatGPT + Chatterbox**, then use **Chatterbox voice** before starting a conversation. The selector discovers local audio references in Jarvis’s `backend/assets/voices` (or `CHATTERBOX_VOICES_DIR`). The choice is remembered per browser and passed per session; the same Chatterbox model is reused.

Local video quality: VP8 and H.264 now start at 6 Mbps, with a 2 Mbps minimum and 12 Mbps maximum. Adjust `AVTR_VIDEO_BITRATE`, `AVTR_VIDEO_MIN_BITRATE`, and `AVTR_VIDEO_MAX_BITRATE` before launch. These are local-demo codec defaults; browser/network adaptation and model detail still limit perceived sharpness.

Response latency improvements: persistent Codex app-server session, sentence-sized TTS queue, concise spoken answers, explicit low reasoning effort (`AVTR_LLM_EFFORT`), and STT/TTS preloading at worker startup. STT and TTS use separate locks. Text is streamed using `item/agentMessage/delta`; protocol reference: https://learn.chatgpt.com/docs/app-server . The model remains GPT-6.1-Sol. Voice timings log STT, first text, TTS and first-audio delivery; first-audio delivery precedes AVTR rendering/browser playback.

Focused checks after the change: first audio delivered to AVTR speech events at 3.77 s for an initial simple text question and 1.73 s for a follow-up; short-answer TTS took 0.52/0.49 s. A separate 3.3-second speech clip transcribed in 0.67 s. These are samples, not guaranteed latency or measurements from the end of microphone speech.
