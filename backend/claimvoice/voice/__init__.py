"""Voice runtime: Pipecat pipelines over SmallWebRTC (WebSocket fallback), speech adapters and their fakes.

Pipeline per call: transport.input -> VAD (Silero) -> speech-to-text -> dialogue engine -> text-to-speech ->
transport.output, with barge-in (caller speech during line speech cancels the line's audio). In the offline
`browser_speech` mode the browser recognises speech and speaks replies; text travels on the data channel."""
