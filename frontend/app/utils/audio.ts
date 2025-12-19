// A silent WAV of a given length (8-bit mono, 2 kHz): lets the recording band play on a real clock when a call's
// audio isn't stored (the caller declined, or the local mock is on). Tiny: 2 KB per second.
export function silentWav(seconds: number, sampleRate = 2000): Uint8Array<ArrayBuffer> {
  const samples = Math.max(1, Math.round(seconds * sampleRate))
  const buf = new Uint8Array(new ArrayBuffer(44 + samples))
  const view = new DataView(buf.buffer)
  const str = (o: number, s: string) => { for (let i = 0; i < s.length; i++) buf[o + i] = s.charCodeAt(i) }
  str(0, 'RIFF')
  view.setUint32(4, 36 + samples, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate, true) // byte rate
  view.setUint16(32, 1, true) // block align
  view.setUint16(34, 8, true) // bits
  str(36, 'data')
  view.setUint32(40, samples, true)
  buf.fill(128, 44) // 8-bit silence
  return buf
}

export function silentWavUrl(seconds: number): string {
  return URL.createObjectURL(new Blob([silentWav(seconds)], { type: 'audio/wav' }))
}
