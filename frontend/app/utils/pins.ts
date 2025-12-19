// Moment pins above the recording lanes: centred on their moment, kept inside the band, and moved to a second row
// when they would overlap the pin before them.
export interface PinIn { x: number, label: string }
export interface PinOut { left: number, width: number, row: 0 | 1 }

/** Rough pill width for a label at 12 px (icon + padding included). */
export function pinWidth(label: string): number {
  return Math.round(label.length * 6.6 + 40)
}

export function layoutPins<T extends PinIn>(pins: T[], width: number, gap = 6): (T & PinOut)[] {
  const ends: [number, number] = [-Infinity, -Infinity]
  return pins.map((p) => {
    const w = pinWidth(p.label)
    const left = Math.max(0, Math.min(width - w, p.x * width - w / 2))
    let row: 0 | 1 = 0
    if (left < ends[0] + gap) row = left >= ends[1] + gap ? 1 : (ends[0] <= ends[1] ? 0 : 1)
    ends[row] = left + w
    return { ...p, left, width: w, row }
  })
}
