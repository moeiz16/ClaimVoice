import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import CvTag from '../app/components/ui/CvTag.vue'
import Slate from '../app/components/ui/Slate.vue'
import HeardValue from '../app/components/claim/HeardValue.vue'
import LossNotice from '../app/components/notice/LossNotice.vue'
import LineKey from '../app/components/shell/LineKey.vue'
import { useHeardLinks } from '../app/composables/useHeardLinks'
import type { Slot } from '../app/types/api'
import { boardRows } from '../app/utils/board'
import { buildNotice } from '../app/utils/notice'

const g = globalThis as Record<string, unknown>
g.useHeardLinks = useHeardLinks
g.useDemoClock = () => ({ now: ref(new Date('2026-01-08T14:42:00Z')), since: () => 108, elapsed: () => '1:48' })
const global = { components: { CvTag, HeardValue } }

const slot = (key: string, display: string, over: Partial<Slot> = {}): Slot => ({
  key, label: key === 'policy' ? 'Policy' : 'What happened', value: display, display, confidence: 0.9, confidenceLabel: 'sure', source: 'heard',
  sourceLabel: '▸ 0:28', span: { turnId: 't1', start: 11, end: 23 }, heardAtSeconds: 28, changedAtSeconds: null, confirmed: true, required: true, history: [], ...over,
})

describe('the slate', () => {
  it('is a caption block: back link, title, caption and page controls, and no avatar', () => {
    const w = mount(Slate, { props: { title: 'Lines', caption: 'Larkspur Mutual · 3 on the line', back: { to: '/lines', label: 'Board' } }, slots: { default: '<button>Night line</button>' } })
    expect(w.find('h1').text()).toBe('Lines')
    expect(w.find('.sub').text()).toContain('3 on the line')
    expect(w.find('a').attributes('href')).toBe('/lines')
    expect(w.find('.ctl button').text()).toBe('Night line')
    expect(w.find('.acct').exists()).toBe(false)
  })
})

describe('status tags', () => {
  it('map each status to a semantic colour and always carry an icon', () => {
    const w = mount(CvTag, { props: { kind: 'urgent', icon: 'urgent' }, slots: { default: 'Urgent safety' } })
    expect(w.attributes('data-color')).toBe('error')
    expect(w.find('svg').attributes('data-icon')).toBe('i-lucide-triangle-alert')
    expect(w.text()).toBe('Urgent safety')
    const full = mount(CvTag, { props: { kind: 'fast', icon: 'i-lucide-check' }, slots: { default: 'Fast-track' } })
    expect(full.find('svg').attributes('data-icon')).toBe('i-lucide-check')
  })
})

describe('the loss notice component', () => {
  const sections = buildNotice({ callId: 'c', claimId: null, lossType: 'wind', lossTypeLabel: 'Wind', progress: 0.4, missing: [], sections: [
    { key: 'policy', label: 'Policy', slots: [slot('policy', 'LM-AB-204118')] },
    { key: 'loss', label: 'What happened', slots: [slot('what', '', { span: null, sourceLabel: '' })] },
  ] }, 4)
  const turns = [{ id: 't1', text: 'Sure, it\'s LM-AB-204118 on the card.' }]

  it('renders numbered sections of boxes with the value, its source and the caller\'s words', () => {
    const w = mount(LossNotice, { props: { sections, step: 4, turns, reference: 'Draft CV-26-01860' }, global })
    expect(w.findAll('fieldset')).toHaveLength(2)
    expect(w.findAll('.no').map(n => n.text())).toEqual(['2', '4'])
    expect(w.find('.ref').text()).toBe('Draft CV-26-01860')
    const box = w.find('.box')
    expect(box.find('.k').text()).toBe('Policy')
    expect(box.find('.heard .at').text()).toBe('0:28')
    expect(box.find('.margin-note').text()).toContain('LM-AB-204118')
    expect(w.find('.box.empty .pending').text()).toBe('Not heard yet')
    expect(w.findAll('.u-stepper li')).toHaveLength(7)
    expect(w.find('.u-stepper [data-active]').text()).toBe('What happened')
  })

  it('says each section\'s state in words, and can speak French on the caller\'s own screen', () => {
    const w = mount(LossNotice, { props: { sections, step: 4, turns }, global })
    expect(w.findAll('.shead .cv-tag').map(t => t.text())).toEqual(['Complete', 'Filling in'])
    const fr = mount(LossNotice, { props: { sections, step: 4, turns, words: 'fr' }, global })
    expect(fr.findAll('.shead .cv-tag').map(t => t.text())).toEqual(['Complet', 'En cours'])
    expect(fr.find('.u-stepper [data-active]').text()).toBe('Ce qui s\'est passé')
  })

  it('reports a clicked value so the page can play its words', async () => {
    const w = mount(LossNotice, { props: { sections, step: 4, turns }, global })
    await w.find('button.heard').trigger('click')
    expect(w.emitted('activate')?.[0]?.[0]).toMatchObject({ key: 'policy' })
  })
})

describe('line keys', () => {
  it('show the line number and lamp, and say the state and wait in words', () => {
    const [row] = boardRows([], [{ id: 'h', callId: 'c4', reason: 'urgent_safety', reasonLabel: 'Urgent safety', detail: '', priority: 'urgent', state: 'waiting', requestedAt: '2026-01-08T14:40:12Z', waitingSeconds: 108, acceptedBy: null, acceptedAt: null, callerLabel: 'Hal Petrenko', lineLabel: 'Line 4', place: 'Airdrie', lossTypeLabel: 'Wind', language: 'en', summary: '', actionsTaken: [], to: null, team: null }])
    const w = mount(LineKey, { props: { row: row! } })
    const key = w.find('.key')
    expect(key.classes()).toContain('lamp-urgent')
    expect(key.find('.n').text()).toBe('4')
    expect(key.attributes('aria-label')).toBe('Line 4 · Hal Petrenko · urgent safety · waiting 1:48')
    expect(key.find('.t').text()).toBe('1:48')
    const lit = mount(LineKey, { props: { row: row!, listening: true, plain: true } })
    expect(lit.find('.key').classes()).toContain('listening')
    expect(lit.find('a').exists()).toBe(false)
  })
})
