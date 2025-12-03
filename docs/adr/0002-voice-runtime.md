# ADR 0002: Voice runtime: Pipecat over SmallWebRTC, inside the API process, with browser speech offline

**Status:** accepted

## Context
The line has to hold a natural phone-style conversation from a browser: stream audio both ways, notice when the
caller starts talking over it (barge-in), and reply in under 800 ms at the 95th percentile. It must run offline with
no keys, on a laptop, and it must not run speech or language models locally.

## Options considered
- **LiveKit Agents or Daily rooms:** strong, but need a media server or a hosted room service and an account.
- **Raw WebSocket audio only:** simple, but no echo cancellation or jitter handling, and poor on lossy networks.
- **Pipecat with SmallWebRTC:** peer-to-peer WebRTC between the browser and our Python process (aiortc), no media
  server, Pipecat's frame pipeline for VAD, speech services, interruptions and audio resampling.

## Decision
- **Pipecat 1.16 + SmallWebRTC** for the browser call, with Pipecat's WebSocket transport pattern as the fallback
  (same JSON messages plus 20 ms PCM frames) when WebRTC cannot connect in 8 s.
- **The voice runtime lives in the API process** (one asyncio task per call, `LineManager`). One process keeps memory
  low (one Python heap, one copy of the routing models), avoids a cross-process bus for live call facts, and lets
  supervisor actions reach a call directly. Ports 8041–8044 stay reserved should the runtime ever be split out.
- **Signalling over our own HTTP routes** (`POST …/webrtc/offer`, `PATCH …/webrtc/ice`) with a per-call bearer token,
  calling `SmallWebRTCConnection` directly (Pipecat's request handler depends on FastAPI).
- **Three modes:** `browser_speech` (default and offline: the browser's `SpeechRecognition` sends text on the data
  channel and `speechSynthesis` speaks the replies with local system voices; the microphone track still reaches the
  server for the recording and VAD), `voice` (cloud STT/TTS through Pipecat services, selected by environment
  variables), and `typed` (accessibility and no-microphone fallback).
- **Barge-in on both sides:** Silero VAD on the server cancels TTS output in `voice` mode; in `browser_speech` mode
  the browser cancels `speechSynthesis` when recognition hears speech and tells the server (`caller.barge_in`).
- **Speech adapters are Protocols with fakes** (`voice/adapters.py`): the fake STT plays scripted lines (tests, eval,
  response-time runs); the fake TTS produces a quiet tone with real duration so recordings and first-audio timing
  are realistic.

## Consequences
- Offline recognition quality is the browser's; the dialogue eval therefore runs on text (scripted callers), and the
  response-time report separates server time (measured) from recognition time (browser-side, not measurable on the
  server).
- In `browser_speech` mode the line's speech is produced in the browser, so the server recording has the caller's
  audio and silence where the line spoke; the transcript and captions carry the line's words, and the recording
  band draws both lanes from turn timings.
- WebRTC across networks needs STUN/TURN (`VOICE_ICE_SERVERS`); the local demo uses host candidates only.
- Scaling past one API process needs sticky routing of a call to its process and a shared SSE bus (future work).
