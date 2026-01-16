import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import CvTag from '../app/components/ui/CvTag.vue'
import CvMark from '../app/components/CvMark.vue'
import PageHead from '../app/components/ui/PageHead.vue'
import RoundButton from '../app/components/ui/RoundButton.vue'
import HeardValue from '../app/components/claim/HeardValue.vue'
import AnswerSheet from '../app/components/notice/AnswerSheet.vue'
import Conversation from '../app/components/voice/Conversation.vue'
import TranscriptText from '../app/components/voice/TranscriptText.vue'
import { useHeardLinks } from '../app/composables/useHeardLinks'
import { useSheet } from '../app/composables/useSheet'
import type { Slot, Turn } from '../app/types/api'
import { buildNotice } from '../app/utils/notice'
import { PLACES, placeOf, placesFor, questionFor } from '../app/utils/places'

const g = globalThis as Record<string, unknown>
g.useHeardLinks = useHeardLinks
g.useSheet = useSheet
g.useDemoClock = () => ({ now: ref(new Date('2026-01-08T14:42:00Z')), since: () => 108, elapsed: () => '1:48' })
const global = { components: { CvTag, CvMark, HeardValue, TranscriptText } }

const slot = (key: string, display: string, over: Partial<Slot> = {}): Slot => ({
  key, label: key === 'policy' ? 'Policy' : 'What happened', value: display, display, confidence: 0.9, confidenceLabel: 'sure', source: 'heard',
  sourceLabel: '▸ 0:28', span: { turnId: 't1', start: 11, end: 23 }, heardAtSeconds: 28, changedAtSeconds: null, confirmed: true, required: true, history: [], ...over,
})
const turn = (id: string, speaker: Turn['speaker'], text: string, over: Partial<Turn> = {}): Turn => ({
  id, seq: Number(id.slice(1)), speaker, speakerLabel: speaker === 'line' ? 'ClaimVoice' : speaker === 'caller' ? 'Caller' : 'Whisper · Renée K.', text, language: 'en',
  atMs: 12_000, endMs: 15_000, stage: 'loss_details', confidence: null, interrupted: false, redactions: 0, flags: [], ...over,
})

describe('the places, as questions', () => {
  it('names every place by the question it answers, with a short name and a G shortcut', () => {
    expect(PLACES.map(p => p.key)).toEqual(['lines', 'claims', 'quality', 'routing', 'settings', 'activity'])
    expect(PLACES.every(p => p.question.endsWith('?') && p.name.length > 0)).toBe(true)
    expect(new Set(PLACES.map(p => p.key2)).size).toBe(PLACES.length)
    expect(questionFor('lines')).toBe('Who\'s on the line?')
  })

  it('shows only the places a person can open, and files a record under its list', () => {
    expect(placesFor(['claims:read', 'audit:read']).map(p => p.key)).toEqual(['claims', 'activity'])
    expect(placeOf('/claims/c-123')?.key).toBe('claims')
    expect(placeOf('/settings/consent')?.key).toBe('settings')
    expect(placeOf('/sign-in')).toBeNull()
  })
})

describe('the question heading', () => {
  it('is the navigation on a place\'s own page: the heading is a button that opens the Questions sheet', async () => {
    const sheet = useSheet()
    sheet.open.value = false
    const w = mount(PageHead, { props: { title: 'Who\'s on the line?', caption: '4 calls with ClaimVoice.' }, slots: { default: '<button>Alberta</button>' }, global })
    const btn = w.find('h1 button')
    expect(btn.attributes('aria-haspopup')).toBe('dialog')
    expect(btn.attributes('aria-expanded')).toBe('false')
    expect(w.find('h1 .qt').text()).toBe('Who\'s on the line?')
    expect(w.find('.answer').text()).toBe('4 calls with ClaimVoice.')
    expect(w.find('.ctl button').text()).toBe('Alberta')
    await btn.trigger('click')
    expect(sheet.open.value).toBe(true)
  })

  it('puts a crumb above a record\'s name, and the name is plain text', () => {
    const w = mount(PageHead, { props: { title: 'Gord Lindqvist', back: { to: '/lines', label: 'Lines' } }, global })
    expect(w.find('h1').text()).toBe('Gord Lindqvist')
    expect(w.find('h1 button').exists()).toBe(false)
    expect(w.find('.crumb a').attributes('href')).toBe('/lines')
    expect(w.find('.crumb button').attributes('aria-label')).toBe('Open the other questions')
  })
})

describe('status tags', () => {
  it('map each status to a semantic colour and always carry an icon', () => {
    const w = mount(CvTag, { props: { kind: 'urgent', icon: 'urgent' }, slots: { default: 'Urgent safety' } })
    expect(w.attributes('data-color')).toBe('error')
    expect(w.find('svg').attributes('data-icon')).toBe('i-lucide-triangle-alert')
    expect(w.text()).toBe('Urgent safety')
    const full = mount(CvTag, { props: { kind: 'jade', icon: 'i-lucide-check' }, slots: { default: 'Filling in' } })
    expect(full.attributes('data-color')).toBe('primary')
  })
})

describe('round call buttons', () => {
  it('say their word under the circle and their pressed state to assistive technology', async () => {
    const w = mount(RoundButton, { props: { icon: 'i-lucide-headphones', label: 'Listening', pressed: true } })
    expect(w.find('button').attributes('aria-pressed')).toBe('true')
    expect(w.find('.w').text()).toBe('Listening')
    expect(w.classes()).toContain('on')
    await w.trigger('click')
    expect(w.emitted('click')).toHaveLength(1)
    const off = mount(RoundButton, { props: { icon: 'i-lucide-phone', label: 'Take over', disabled: true } })
    await off.trigger('click')
    expect(off.emitted('click')).toBeUndefined()
  })
})

describe('the answer sheet', () => {
  const sections = buildNotice({ callId: 'c', claimId: null, lossType: 'wind', lossTypeLabel: 'Wind', progress: 0.4, missing: [], sections: [
    { key: 'policy', label: 'Policy', slots: [slot('policy', 'LM-AB-204118')] },
    { key: 'loss', label: 'What happened', slots: [slot('what', '', { span: null, sourceLabel: '' })] },
  ] }, 4)

  it('writes each script step as ClaimVoice\'s question with the caller\'s answers and their sources', () => {
    const w = mount(AnswerSheet, { props: { sections, step: 4, reference: 'Draft CV-26-01860' }, global })
    expect(w.findAll('.pair')).toHaveLength(2)
    expect(w.findAll('.q h3').map(h => h.text())).toEqual(['Who\'s calling, and on which policy?', 'What happened?'])
    expect(w.find('.ref').text()).toBe('Draft CV-26-01860')
    const kv = w.find('.kv')
    expect(kv.find('dt').text()).toBe('Policy')
    expect(kv.find('.heard .at').text()).toBe('0:28')
    expect(w.find('.kv.empty .pending').text()).toBe('Not heard yet')
    expect(w.find('.st-current .typing').exists()).toBe(true)
  })

  it('says each step\'s state in words, and can ask in French on the caller\'s own screen', () => {
    const w = mount(AnswerSheet, { props: { sections, step: 4 }, global })
    expect(w.findAll('.qmeta .cv-tag').map(t => t.text())).toEqual(['Answered', 'Asking now'])
    const fr = mount(AnswerSheet, { props: { sections, step: 4, words: 'fr' }, global })
    expect(fr.findAll('.qmeta .cv-tag').map(t => t.text())).toEqual(['Répondu', 'En cours'])
    expect(fr.findAll('.q h3')[1]!.text()).toBe('Que s\'est-il passé ?')
  })

  it('reports a pressed answer so the page can play its words', async () => {
    const w = mount(AnswerSheet, { props: { sections, step: 4 }, global })
    await w.find('button.heard').trigger('click')
    expect(w.emitted('activate')?.[0]?.[0]).toMatchObject({ key: 'policy' })
  })
})

describe('the conversation as bubbles', () => {
  it('puts ClaimVoice on the left and the caller on the right, names whispers, and plays from a time', async () => {
    const turns = [turn('t1', 'line', 'Is everyone safe?'), turn('t2', 'caller', 'Yes, we\'re fine.'), turn('t3', 'whisper', 'Ask about the garage')]
    const w = mount(Conversation, { props: { turns, callerLabel: 'Gord Lindqvist', seekable: true, currentId: 't2' }, global })
    const li = w.findAll('li.turn')
    expect(li.map(l => l.classes().includes('right'))).toEqual([false, true, false])
    expect(li[1]!.find('.meta b').text()).toBe('Gord')
    expect(li[1]!.attributes('aria-current')).toBe('true')
    expect(li[2]!.find('.meta b').text()).toBe('Whisper, ClaimVoice only · Renée K.')
    await li[0]!.find('button.tm').trigger('click')
    expect(w.emitted('seek')?.[0]).toEqual([12])
  })

  it('shows words still being heard as a settling caller bubble', () => {
    const w = mount(Conversation, { props: { turns: [], callerLabel: 'Hal Petrenko', interim: 'the gas meter' }, global })
    expect(w.find('.interim-turn .hearing').text()).toBe('hearing now')
    expect(w.findAll('.interim-turn .interim')).toHaveLength(3)
  })
})
