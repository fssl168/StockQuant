/**
 * 分类告警音效管理器
 *
 * 按告警等级播放差异化提示音，支持静音/音量调节、浏览器自动播放权限申请、
 * 优先级 FIFO 队列（高优先级打断低优先级、同优先级按入队顺序播放）以及
 * Web Audio API 降级。
 *
 * 使用示例:
 *   soundManager.play('risk')
 *   soundManager.setMute(true)
 *   soundManager.setVolume(0.8)
 */

export type SoundLevel = 'risk' | 'opportunity' | 'info' | 'critical'

export interface SoundConfig {
  file: string
  priority: 'low' | 'medium' | 'high' | 'critical'
}

export const SOUND_REGISTRY: Record<SoundLevel, SoundConfig> = {
  risk: { file: '/sounds/risk-long.mp3', priority: 'high' },
  opportunity: { file: '/sounds/opportunity-short.mp3', priority: 'medium' },
  info: { file: '/sounds/info-double.mp3', priority: 'low' },
  critical: { file: '/sounds/critical-triple.mp3', priority: 'critical' },
}

const PRIORITY_RANK: Record<SoundConfig['priority'], number> = {
  low: 0,
  medium: 1,
  high: 2,
  critical: 3,
}

/** Web Audio API 降级方案的 beep 频率映射 */
const BEEP_FREQ_MAP: Record<SoundLevel, number> = {
  risk: 880,
  opportunity: 660,
  info: 440,
  critical: 1100,
}

/** 降级方案 beep 的持续时间（毫秒） */
const BEEP_DURATION_MS = 180

/** 队列最大长度，防止无限堆积 */
const MAX_QUEUE_SIZE = 5

interface QueueItem {
  level: SoundLevel
  priority: number
  enqueuedAt: number
}

export class SoundManager {
  private audioCache = new Map<string, HTMLAudioElement>()
  private _muted = false
  private _volume = 0.5
  private _permissionGranted = false

  /** 当前正在播放的 AudioElement（null = 空闲） */
  private _current: HTMLAudioElement | null = null
  private _currentPriority: number = -1
  private _currentLevel: SoundLevel | null = null

  /** FIFO 等待队列 */
  private queue: QueueItem[] = []

  /** 已创建的 Web Audio context（降级用） */
  private audioCtx: AudioContext | null = null

  // ---------- 同步访问器 ----------

  get muted(): boolean {
    return this._muted
  }

  get volume(): number {
    return this._volume
  }

  get permissionGranted(): boolean {
    return this._permissionGranted
  }

  /** 当前队列长度（调试用） */
  get queueSize(): number {
    return this.queue.length
  }

  // ---------- 设置 ----------

  setMute(muted: boolean): void {
    this._muted = muted
    if (muted) {
      this.stop()
    }
  }

  setVolume(vol: number): void {
    this._volume = Math.max(0, Math.min(1, vol))
    // 立即应用到已缓存的元素
    for (const audio of this.audioCache.values()) {
      audio.volume = this._volume
    }
  }

  // ---------- 播放 ----------

  /**
   * 播放指定等级的音效
   *
   * - 空闲：立即播放
   * - 当前正在播放更高/同等优先级：新音效入队（同优先级 FIFO）
   * - 新音效优先级更高：打断当前，被打断的音效重新入队头部
   */
  play(level: SoundLevel): void {
    if (this._muted) return

    const config = SOUND_REGISTRY[level]
    const priority = PRIORITY_RANK[config.priority]

    // 空闲：立即播放
    if (!this._current) {
      this._playNow(level, priority)
      return
    }

    // 当前正在播放更高或同等优先级：新音效入队（同优先级 FIFO）
    if (priority <= this._currentPriority) {
      if (this.queue.length < MAX_QUEUE_SIZE) {
        this.queue.push({ level, priority, enqueuedAt: Date.now() })
      }
      return
    }

    // 新优先级更高：打断当前，被中断的音效重新入队头部
    if (this._currentLevel) {
      // 队列头部插入，等待播放完后接着播
      this.queue.unshift({
        level: this._currentLevel,
        priority: this._currentPriority,
        enqueuedAt: Date.now(),
      })
      // 队列长度仍受 MAX_QUEUE_SIZE 限制
      if (this.queue.length > MAX_QUEUE_SIZE) {
        this.queue.length = MAX_QUEUE_SIZE
      }
    }
    this.stop()
    this._playNow(level, priority)
  }

  /**
   * 立即播放（内部使用，不经过队列）
   */
  private _playNow(level: SoundLevel, priority: number): void {
    const config = SOUND_REGISTRY[level]
    this._currentLevel = level

    const cached = this.audioCache.get(config.file)
    if (cached) {
      cached.volume = this._volume
      cached.currentTime = 0
      cached.onended = () => this._onPlayEnd()
      const playPromise = cached.play()
      if (playPromise) {
        playPromise.catch(() => this.fallbackBeep(level))
      } else {
        this.fallbackBeep(level)
      }
      this._current = cached
      this._currentPriority = priority
    } else {
      this.loadAndPlay(config)
    }
  }

  /**
   * 当前音效播放结束：清空当前指针，播放下一条
   */
  private _onPlayEnd(): void {
    this._current = null
    this._currentPriority = -1
    this._currentLevel = null

    // 播放下一条（FIFO）
    const next = this.queue.shift()
    if (next) {
      this._playNow(next.level, next.priority)
    }
  }

  /**
   * 停止当前播放并清空队列
   */
  stop(): void {
    if (this._current) {
      try {
        this._current.pause()
        this._current.currentTime = 0
        this._current.onended = null
      } catch {
        // ignore
      }
      this._current = null
      this._currentPriority = -1
      this._currentLevel = null
    }
    this.queue = []
  }

  // ---------- 浏览器权限 ----------

  async requestPermission(): Promise<boolean> {
    // 检查浏览器是否支持权限 API
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this._permissionGranted = true // 不支持则默认放行
      return this._permissionGranted
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      // 立即关闭，仅用于获取权限
      stream.getTracks().forEach((t) => t.stop())
      this._permissionGranted = true
      return true
    } catch {
      this._permissionGranted = false
      return false
    }
  }

  // ---------- 缓存管理 ----------

  /**
   * 预加载所有音效（调用一次即可缓存在内存中）
   */
  preloadAll(): void {
    for (const config of Object.values(SOUND_REGISTRY)) {
      this.loadAndCache(config)
    }
  }

  /**
   * 清空音频缓存，释放内存（同时停止播放）
   */
  clearCache(): void {
    for (const audio of this.audioCache.values()) {
      try {
        audio.pause()
      } catch {
        // ignore
      }
    }
    this.audioCache.clear()
    this._current = null
    this._currentPriority = -1
    this._currentLevel = null
    this.queue = []
  }

  // ---------- 私有方法 ----------

  private loadAndCache(config: SoundConfig): void {
    if (this.audioCache.has(config.file)) return

    const audio = new Audio(config.file)
    audio.preload = 'auto'
    audio.volume = this._volume
    audio.addEventListener('error', () => {
      // 加载失败，移除缓存条目，后续会走降级
      this.audioCache.delete(config.file)
    })
    this.audioCache.set(config.file, audio)
  }

  private loadAndPlay(config: SoundConfig): void {
    this.loadAndCache(config)
    const cached = this.audioCache.get(config.file)
    if (!cached) {
      // 加载失败（文件不存在），立即降级
      this.fallbackBeep(levelFromConfig(config))
      return
    }
    // 直接调用 _playNow（复用 onended 绑定）
    const level = levelFromConfig(config)
    this._playNow(level, PRIORITY_RANK[config.priority])
  }

  private fallbackBeep(level: SoundLevel): void {
    // 尝试 Web Audio API beep
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
      }
      const ctx = this.audioCtx
      if (ctx.state === 'suspended') ctx.resume()

      const oscillator = ctx.createOscillator()
      const gain = ctx.createGain()
      oscillator.type = 'sine'
      oscillator.frequency.setValueAtTime(BEEP_FREQ_MAP[level], ctx.currentTime)
      gain.gain.setValueAtTime(this._volume, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + BEEP_DURATION_MS / 1000)
      oscillator.connect(gain)
      gain.connect(ctx.destination)
      oscillator.start(ctx.currentTime)
      oscillator.stop(ctx.currentTime + BEEP_DURATION_MS / 1000)
      // beep 结束后也触发 _onPlayEnd 以推进队列
      oscillator.onended = () => this._onPlayEnd()
    } catch {
      // 最终降级：无声。但仍需推进队列。
      this._onPlayEnd()
    }
  }
}

/** 从文件路径反查 SoundLevel（用于降级 beep） */
const FILE_TO_LEVEL = new Map<string, SoundLevel>()
for (const [level, config] of Object.entries(SOUND_REGISTRY)) {
  FILE_TO_LEVEL.set(config.file, level as SoundLevel)
}

function levelFromConfig(config: SoundConfig): SoundLevel {
  return FILE_TO_LEVEL.get(config.file) ?? 'info'
}

/** 单例 */
export const soundManager = new SoundManager()
