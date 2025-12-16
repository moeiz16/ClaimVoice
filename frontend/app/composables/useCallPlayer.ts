// Plays the landing call: the real audio when its file loads, otherwise a silent clock over the same timings, so
// captions, the slip and the route reveal behave identically. Nothing auto-plays.
export function useCallPlayer(duration: Ref<number>, sources: Ref<{ src: string, type: string }[]>) {
  const t = ref(0)
  const playing = ref(false)
  const hasAudio = ref(false)
  const muted = ref(false)
  let audio: HTMLAudioElement | null = null
  let raf = 0
  let last = 0

  function setupAudio() {
    audio?.pause()
    audio = null
    hasAudio.value = false
    if (typeof Audio === 'undefined') return
    const a = new Audio()
    const pick = sources.value.find(s => a.canPlayType(s.type))
    if (!pick) return
    a.preload = 'auto'
    a.src = pick.src
    a.addEventListener('loadedmetadata', () => { hasAudio.value = true; audio = a; a.currentTime = t.value })
    a.addEventListener('error', () => { if (audio === a) audio = null; hasAudio.value = false })
    a.addEventListener('ended', () => { playing.value = false; t.value = duration.value })
  }

  const loop = (ts: number) => {
    if (!playing.value) return
    if (audio && hasAudio.value) t.value = Math.min(duration.value, audio.currentTime)
    else {
      const dt = last ? (ts - last) / 1000 : 0
      t.value = Math.min(duration.value, t.value + dt)
    }
    last = ts
    if (t.value >= duration.value) { playing.value = false; audio?.pause(); return }
    raf = requestAnimationFrame(loop)
  }

  function play() {
    if (t.value >= duration.value - 0.05) seek(0)
    playing.value = true
    last = 0
    if (audio && hasAudio.value) {
      audio.muted = muted.value
      void audio.play().catch(() => { /* blocked: the silent clock keeps the captions moving */ audio = null; hasAudio.value = false })
    }
    raf = requestAnimationFrame(loop)
  }

  function pause() {
    playing.value = false
    audio?.pause()
    cancelAnimationFrame(raf)
  }

  function toggle() { if (playing.value) pause(); else play() }

  function seek(to: number) {
    t.value = Math.max(0, Math.min(duration.value, to))
    if (audio && hasAudio.value) audio.currentTime = t.value
  }

  watch(sources, setupAudio)
  watch(muted, (m) => { if (audio) audio.muted = m })
  onMounted(setupAudio)
  onBeforeUnmount(() => { pause(); audio = null })

  return { t, playing, hasAudio, muted, play, pause, toggle, seek }
}
