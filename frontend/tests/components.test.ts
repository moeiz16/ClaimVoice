import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CvIcon from '../app/components/CvIcon'
import CvTag from '../app/components/ui/CvTag.vue'
import RouteTag from '../app/components/ui/RouteTag.vue'
import RubricBeads from '../app/components/quality/RubricBeads.vue'
import ScriptProgress from '../app/components/lines/ScriptProgress.vue'
import HeardValue from '../app/components/claim/HeardValue.vue'
import type { Slot } from '../app/types/api'

const global = { components: { CvIcon, CvTag } }

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

describe('script progress', () => {
  it('fills done steps, half-fills the current one and labels itself', () => {
    const w = mount(ScriptProgress, { props: { stage: { key: 'loss_details', label: 'Details', step: 4, stepLabel: 'What happened', steps: 7, nextLabel: 'Photos next' } } })
    const segs = w.findAll('i')
    expect(segs).toHaveLength(7)
    expect(segs.filter(s => s.classes().includes('done'))).toHaveLength(3)
    expect(segs[3]!.classes()).toContain('cur')
    expect(w.attributes('aria-label')).toBe('Step 4 of 7: What happened')
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
    expect(w.find('.tag').classes()).toContain('siu')
    const custom = mount(RouteTag, { props: { route: 'fast_track', label: 'Traitement rapide' }, global })
    expect(custom.text()).toBe('Traitement rapide')
  })
})
