import { describe, it, expect, beforeEach } from 'vitest'
import { SoundManager, soundManager, type SoundLevel, SOUND_REGISTRY } from './soundManager'

// 每个测试使用新实例，避免互相干扰
function createInstance(): SoundManager {
  return new SoundManager()
}

describe('SoundManager', () => {
  let sm: SoundManager

  beforeEach(() => {
    sm = createInstance()
  })

  // ---- initial state ----

  it('should start muted = false', () => {
    expect(sm.muted).toBe(false)
  })

  it('should start with volume = 0.5', () => {
    expect(sm.volume).toBe(0.5)
  })

  it('should start with permissionGranted = false', () => {
    expect(sm.permissionGranted).toBe(false)
  })

  // ---- setMute / muted ----

  it('setMute(true) should set muted to true', () => {
    sm.setMute(true)
    expect(sm.muted).toBe(true)
  })

  it('setMute(false) should set muted to false', () => {
    sm.setMute(true)
    sm.setMute(false)
    expect(sm.muted).toBe(false)
  })

  it('play should be a no-op when muted', () => {
    sm.setMute(true)
    // Should not throw
    expect(() => sm.play('risk')).not.toThrow()
  })

  // ---- setVolume ----

  it('setVolume should clamp to [0, 1]', () => {
    sm.setVolume(-1)
    expect(sm.volume).toBe(0)

    sm.setVolume(2)
    expect(sm.volume).toBe(1)
  })

  it('setVolume(0.8) should update volume', () => {
    sm.setVolume(0.8)
    expect(sm.volume).toBe(0.8)
  })

  // ---- clearCache ----

  it('clearCache should not throw', () => {
    expect(() => sm.clearCache()).not.toThrow()
  })

  // ---- stop ----

  it('stop should not throw', () => {
    expect(() => sm.stop()).not.toThrow()
  })

  // ---- singleton ----

  it('soundManager singleton should be an instance of SoundManager', () => {
    expect(soundManager).toBeInstanceOf(SoundManager)
  })

  // ---- priority behaviour ----

  it('priority levels are correctly ordered', () => {
    expect(SOUND_REGISTRY.critical.priority).toBe('critical')
    expect(SOUND_REGISTRY.risk.priority).toBe('high')
    expect(SOUND_REGISTRY.opportunity.priority).toBe('medium')
    expect(SOUND_REGISTRY.info.priority).toBe('low')
  })
})

describe('SoundManager -- play by level', () => {
  let sm: SoundManager

  beforeEach(() => {
    sm = createInstance()
  })

  it('play should not throw for any sound level', () => {
    const levels: SoundLevel[] = ['risk', 'opportunity', 'info', 'critical']
    for (const level of levels) {
      expect(() => sm.play(level)).not.toThrow()
    }
  })

  it('play should not throw on empty list', () => {
    expect(() => sm.play('info')).not.toThrow()
  })
})
