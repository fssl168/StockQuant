import { describe, it, expect } from 'vitest'
import { getRuleSoundLevel, type AlertRule } from '@/stores/alertStore'
import type { SoundLevel } from '@/utils/soundManager'

function makeRule(overrides: Partial<AlertRule> = {}): AlertRule {
  return {
    id: 'rule-1',
    name: 'test rule',
    type: 'price',
    enabled: true,
    notifyVia: ['sound'],
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('getRuleSoundLevel', () => {
  describe('per-rule override (rule.soundLevel)', () => {
    it('returns rule.soundLevel when set, regardless of type', () => {
      const rule = makeRule({ type: 'price', soundLevel: 'critical' })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('critical')
    })

    it('returns rule.soundLevel even for types with a different default', () => {
      // index_correlation defaults to 'info', but override wins
      const rule = makeRule({ type: 'index_correlation', soundLevel: 'risk' })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('risk')
    })

    const allLevels: SoundLevel[] = ['risk', 'opportunity', 'info', 'critical']
    for (const level of allLevels) {
      it(`returns '${level}' when rule.soundLevel = '${level}'`, () => {
        const rule = makeRule({ soundLevel: level })
        expect(getRuleSoundLevel(rule)).toBe(level)
      })
    }
  })

  describe('type-based default fallback', () => {
    it('price → opportunity (default)', () => {
      const rule = makeRule({ type: 'price' })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('opportunity')
    })

    it('depth_change → opportunity (default)', () => {
      const rule = makeRule({ type: 'depth_change' })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('opportunity')
    })

    it('index_correlation → info (default)', () => {
      const rule = makeRule({ type: 'index_correlation' })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('info')
    })

    it('sector_correlation → info (default)', () => {
      const rule = makeRule({ type: 'sector_correlation' })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('info')
    })
  })

  describe('undefined soundLevel falls back to type default', () => {
    it('explicit undefined soundLevel uses type default', () => {
      const rule = makeRule({ type: 'price', soundLevel: undefined })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('opportunity')
    })
  })

  describe('rule not requesting sound channel is still resolvable', () => {
    // The helper is pure — it does not check notifyVia. The store is
    // responsible for gating on notifyVia before calling soundManager.play.
    it('returns a level even when notifyVia does not include sound', () => {
      const rule = makeRule({
        type: 'price',
        notifyVia: ['email'],
      })
      expect(getRuleSoundLevel(rule)).toBe<SoundLevel>('opportunity')
    })
  })
})
