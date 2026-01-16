import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CvTag from '../app/components/ui/CvTag.vue'
import RouteTag from '../app/components/ui/RouteTag.vue'
import RubricBeads from '../app/components/quality/RubricBeads.vue'
import StepRing from '../app/components/lines/StepRing.vue'
import HeardValue from '../app/components/claim/HeardValue.vue'
import type { Slot } from '../app/types/api'

const global = { components: { CvTag } }

const slot = (over: Partial<Slot>): Slot => ({
  key: 'policy_number', label: 'Policy', value: 'LM-AB-204118', display: 'LM-AB-204118', confidence: 0.95, confidenceLabel: 'sure', source: 'heard',
  sourceLabel: '▸ 0:31', span: { turnId: 't1', start: 0, end: 5 }, heardAtSeconds: 31, changedAtSeconds: null, confirmed: true, required: true, history: [], ...over,
})

describe('rubric beads', () => {
  it('says met, missed or not applicable in words, not colour alone', () => {
    const w = mount(RubricBeads, {
      props: { beads: [
        { key: 'consent_first', label: 'Consent first', passed: true, detail: null },
        { key: 'required_fields', label: 'Required details', passed: false, detail: '9/10' },
        { key: 'handoff_correct', label: 'Right hand-off', passed: null, detail: null },
      ] },
      global,
    })
    const items = w.findAll('li')
    expect(items).toHaveLength(3)
    expect(items[0]!.classes()).toContain('ok')
    expect(items[0]!.text()).toContain('met')
    expect(items[1]!.text()).toContain('Required details (9/10)')
    expect(items[1]!.text()).toContain('missed')
    expect(items[2]!.text()).toContain('not applicable')
  })
})

describe('step and wait rings', () => {
  it('draws the seven steps as arcs, done ones full, the current one half, and says it in words', () => {
    const w = mount(StepRing, { props: { label: 'Gord Lindqvist', initials: 'GL', stage: { key: 'loss_details', label: 'Details', step: 4, stepLabel: 'What happened', steps: 7, nextLabel: 'Photos next' } } })
    expect(w.findAll('circle.track')).toHaveLength(7)
    expect(w.findAll('circle.arc')).toHaveLength(4)
    expect(w.find('.ini').text()).toBe('GL')
    expect(w.attributes('role')).toBe('img')
    expect(w.attributes('aria-label')).toBe('Gord Lindqvist: step 4 of 7, What happened')
  })

  it('fills a wait ring as the wait grows, never empty and never past full', () => {
    const arc = (s: number) => Number(mount(StepRing, { props: { label: 'Hal', initials: 'HP', waitSeconds: s, of: 180 } }).find('circle.arc').attributes('stroke-dasharray')!.split(' ')[0])
    expect(arc(0)).toBeGreaterThan(0)
    expect(arc(90)).toBeLessThan(arc(180))
    expect(arc(900)).toBeCloseTo(arc(180))
  })
})

describe('claim-file values', () => {
  it('shows a heard value with its moment chip and tells you where it came from', async () => {
    const w = mount(HeardValue, { props: { field: slot({}) }, global })
    const b = w.find('button.heard')
    expect(b.text()).toContain('LM-AB-204118')
    expect(b.find('.at').text()).toBe('0:31')
    expect(b.attributes('aria-label')).toContain('Heard at 0:31')
    await b.trigger('click')
    expect(w.emitted('activate')).toHaveLength(1)
  })

  it('says "from the policy" for values that weren\'t heard', () => {
    const w = mount(HeardValue, { props: { field: slot({ source: 'policy_record', sourceLabel: 'from the policy', span: null, display: '27 Sandarac Way NW' }) }, global })
    expect(w.find('button').exists()).toBe(false)
    expect(w.text()).toContain('27 Sandarac Way NW')
    expect(w.text()).toContain('from the policy')
  })

  it('shows a dashed pending pill when nothing has been heard yet', () => {
    const w = mount(HeardValue, { props: { field: slot({ display: '', sourceLabel: '', span: null }) }, global })
    expect(w.find('.pending').text()).toBe('Not heard yet')
  })

  it('flags a value that is not sure yet and one the caller changed', () => {
    const w = mount(HeardValue, { props: { field: slot({ confidenceLabel: 'check', changedAtSeconds: 192 }) }, global })
    expect(w.find('button.heard').classes()).toContain('settling')
    expect(w.text()).toContain('not sure yet')
    expect(w.text()).toContain('Changed at 3:12')
  })
})

describe('route tags', () => {
  it('always pair the route with an icon and a word', () => {
    const w = mount(RouteTag, { props: { route: 'special_investigation' }, global })
    expect(w.text()).toBe('Closer look')
    expect(w.find('svg').exists()).toBe(true)
    expect(w.find('.cv-tag').classes()).toContain('k-siu')
    expect(w.find('.cv-tag').attributes('data-color')).toBe('warning')
    const custom = mount(RouteTag, { props: { route: 'fast_track', label: 'Traitement rapide' }, global })
    expect(custom.text()).toBe('Traitement rapide')
  })
})
