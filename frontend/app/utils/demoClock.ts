// The API is the source of truth for "now". Every response carries X-ClaimVoice-Now (ISO-8601); the app keeps the
// offset between that and the browser clock so countdowns and "2 minutes ago" read in demo time.
let offsetMs = 0

export function syncFromHeader(value: string | null | undefined, browserNow: number = Date.now()): void {
  if (!value) return
  const server = Date.parse(value)
  if (!Number.isNaN(server)) offsetMs = server - browserNow
}

export function demoNow(browserNow: number = Date.now()): Date {
  return new Date(browserNow + offsetMs)
}

export function resetDemoClock(): void {
  offsetMs = 0
}
