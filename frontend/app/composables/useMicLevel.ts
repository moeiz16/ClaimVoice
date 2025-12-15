// The microphone's level for the demo-line orb and live waveform: getUserMedia → AudioContext →
// MediaStreamAudioSourceNode → AnalyserNode (fftSize 1024, smoothing 0.6), RMS per frame. The stream is also handed to
// the WebRTC leg so the line can hear the caller.
import { rmsLevel } from '~/utils/waveform'

export function useMicLevel() {
  const level = ref(0)
  const stream = shallowRef<MediaStream | null>(null)
  const error = ref<'blocked' | 'missing' | null>(null)
  let ctx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let frame: Float32Array<ArrayBuffer> | null = null
  let raf = 0

  async function start(): Promise<MediaStream | null> {
    if (stream.value) return stream.value
    if (!navigator.mediaDevices?.getUserMedia) { error.value = 'missing'; return null }
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      stream.value = s
      ctx = new AudioContext()
      const src = ctx.createMediaStreamSource(s)
      analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      analyser.smoothingTimeConstant = 0.6
      src.connect(analyser)
      frame = new Float32Array(new ArrayBuffer(analyser.fftSize * 4))
      const tick = () => {
        raf = requestAnimationFrame(tick)
        if (!analyser || !frame) return
        analyser.getFloatTimeDomainData(frame)
        level.value = rmsLevel(frame)
      }
      tick()
      error.value = null
      return s
    }
    catch (e) {
      error.value = (e as DOMException).name === 'NotFoundError' ? 'missing' : 'blocked'
      return null
    }
  }

  function stop() {
    cancelAnimationFrame(raf)
    stream.value?.getTracks().forEach(t => t.stop())
    stream.value = null
    void ctx?.close()
    ctx = null
    analyser = null
    level.value = 0
  }

  onBeforeUnmount(stop)
  return { level, stream, error, start, stop }
}
