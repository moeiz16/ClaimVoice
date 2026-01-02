// Photo preparation on the caller's phone: HEIC/HEIF (and very large photos) are redrawn as JPEG in the browser, so
// the upload is a format the line accepts and location details never leave the phone in the file.
export const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp']
export const MAX_BYTES = 10 * 1024 * 1024

export function needsConversion(file: Pick<File, 'type' | 'name' | 'size'>): boolean {
  const heic = /image\/hei[cf]/i.test(file.type) || /\.hei[cf]$/i.test(file.name)
  return heic || !ACCEPTED.includes(file.type) || file.size > 4 * 1024 * 1024
}

/** What the first bytes of a file say it is: a photo format the line takes, or not a photo at all. */
export function sniffImage(head: Uint8Array): 'jpeg' | 'png' | 'webp' | 'heic' | null {
  const at = (i: number, ...b: number[]) => b.every((x, k) => head[i + k] === x)
  const ascii = (i: number, s: string) => [...s].every((c, k) => head[i + k] === c.charCodeAt(0))
  if (at(0, 0xFF, 0xD8, 0xFF)) return 'jpeg'
  if (at(0, 0x89, 0x50, 0x4E, 0x47)) return 'png'
  if (ascii(0, 'RIFF') && ascii(8, 'WEBP')) return 'webp'
  if (ascii(4, 'ftyp')) return 'heic'
  return null
}

/** True when the file starts like a photo (checked on the phone, before anything is sent). */
export async function looksLikePhoto(file: Blob): Promise<boolean> {
  const head = new Uint8Array(await file.slice(0, 16).arrayBuffer())
  return sniffImage(head) !== null
}

/** Fit (w, h) inside a max edge, keeping the aspect ratio. */
export function fitWithin(w: number, h: number, max = 2400): { w: number, h: number } {
  const s = Math.min(1, max / Math.max(w, h))
  return { w: Math.round(w * s), h: Math.round(h * s) }
}

export async function toJpeg(file: File, quality = 0.85): Promise<File> {
  const bitmap = await createImageBitmap(file)
  const { w, h } = fitWithin(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, w, h)
  bitmap.close?.()
  const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/jpeg', quality))
  if (!blob) throw new Error('convert')
  return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' })
}
