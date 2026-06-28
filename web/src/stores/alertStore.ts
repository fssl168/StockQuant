import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import client from '@/api/client'
import { soundManager, type SoundLevel } from '@/utils/soundManager'

export interface AlertRule {
  id: string
  name: string
  type: 'price' | 'depth_change' | 'index_correlation' | 'sector_correlation'
  symbol?: string
  indexSymbol?: string
  sector?: string
  enabled: boolean
  conditions?: Record<string, unknown>
  notifyVia: ('dingtalk' | 'email' | 'telegram' | 'sound' | 'browser')[]
  /**
   * Per-rule sound override. If set, this sound level is used instead of
   * the default mapping from `type` (see ALERT_TYPE_TO_SOUND).
   * If undefined, the rule falls back to the type-based default.
   */
  soundLevel?: SoundLevel
  createdAt: string
  updatedAt: string
}

/**
 * 预警类型到音效等级的映射（默认值，可被 rule.soundLevel 覆盖）
 * - price / depth_change → opportunity（机会提示）
 * - index_correlation / sector_correlation → info（信息提示）
 */
const ALERT_TYPE_TO_SOUND: Record<AlertRule['type'], SoundLevel> = {
  price: 'opportunity',
  depth_change: 'opportunity',
  index_correlation: 'info',
  sector_correlation: 'info',
}

/**
 * Resolve the sound level for a given alert rule.
 *
 * Priority:
 * 1. rule.soundLevel (per-rule override) — if defined
 * 2. ALERT_TYPE_TO_SOUND[rule.type]      — type-based default
 * 3. 'info'                                — final fallback
 *
 * Exported so UI components (e.g. AlertRuleForm) can preview the
 * resolved level for display.
 */
export function getRuleSoundLevel(rule: AlertRule): SoundLevel {
  return rule.soundLevel ?? ALERT_TYPE_TO_SOUND[rule.type] ?? 'info'
}

interface AlertRuleState {
  rules: AlertRule[]
  loading: boolean
  /** 已触发规则的上次触发时间戳（ruleId → ms epoch），用于冷却期去重 */
  triggeredAt: Record<string, number>
  fetchRules: () => Promise<void>
  createRule: (data: Omit<AlertRule, 'id' | 'createdAt' | 'updatedAt'>) => Promise<void>
  updateRule: (id: string, data: Partial<Omit<AlertRule, 'id' | 'createdAt' | 'updatedAt'>>) => Promise<void>
  toggleRule: (id: string) => Promise<void>
  deleteRule: (id: string) => Promise<void>
  /**
   * 检查实时行情并触发预警（真实触发管线）
   * - 遍历启用的规则，根据类型检查条件
   * - 触发时播放声音（若 notifyVia 含 'sound'）+ 浏览器通知（若含 'browser'）
   * - 同一规则在 COOLDOWN_MS 内不重复触发
   * @returns 触发的规则列表
   */
  checkAndTriggerAlerts: (prices: Record<string, { price: number; change: number }>) => AlertRule[]
  /** 重置已触发记录（规则修改后清除冷却） */
  resetTriggered: (ruleId?: string) => void
}

/** 触发冷却期：同一规则 60 秒内不重复触发 */
const ALERT_COOLDOWN_MS = 60_000

export const useAlertStore = create<AlertRuleState>()(
  persist(
    (set, get) => ({
      rules: [],
      loading: false,
      triggeredAt: {},

      fetchRules: async () => {
        set({ loading: true })
        try {
          const res = await client.get('/api/alerts/rules') as any
          set({ rules: Array.isArray(res) ? res : [], loading: false })
        } catch {
          set({ loading: false })
        }
      },

      createRule: async (data) => {
        await client.post('/api/alerts/rules', data)
        await get().fetchRules()
      },

      updateRule: async (id, data) => {
        await client.put(`/api/alerts/rules/${id}`, data)
        await get().fetchRules()
        // 规则修改后清除该规则的冷却记录
        get().resetTriggered(id)
      },

      toggleRule: async (id) => {
        const rule = get().rules.find((r) => r.id === id)
        if (!rule) return
        await client.put(`/api/alerts/rules/${id}`, { enabled: !rule.enabled })
        await get().fetchRules()
        // 启用规则时（且配置了声音通道）播放对应音效
        if (!rule.enabled && rule.notifyVia.includes('sound')) {
          soundManager.play(getRuleSoundLevel(rule))
        }
      },

      deleteRule: async (id) => {
        await client.delete(`/api/alerts/rules/${id}`)
        await get().fetchRules()
        // 删除规则后清除其触发记录
        get().resetTriggered(id)
      },

      checkAndTriggerAlerts: (prices) => {
        const state = get()
        const { rules, triggeredAt } = state
        const now = Date.now()
        const triggered: AlertRule[] = []
        const newTriggeredAt = { ...triggeredAt }

        for (const rule of rules) {
          if (!rule.enabled) continue

          // 冷却期检查
          const lastTriggered = triggeredAt[rule.id] ?? 0
          if (now - lastTriggered < ALERT_COOLDOWN_MS) continue

          // 根据规则类型检查条件
          let isTriggered = false
          if (rule.type === 'price' && rule.symbol) {
            const quote = prices[rule.symbol]
            if (!quote) continue
            const cond = rule.conditions as {
              condition?: 'above' | 'below' | 'cross'
              threshold?: number
            } | undefined
            const threshold = cond?.threshold
            const condition = cond?.condition
            if (threshold == null || !condition) continue

            if (condition === 'above' && quote.price > threshold) isTriggered = true
            else if (condition === 'below' && quote.price < threshold) isTriggered = true
            else if (condition === 'cross') {
              // cross: 价格接近阈值 ±0.5% 视为穿越
              const deviation = Math.abs(quote.price - threshold) / threshold
              if (deviation < 0.005) isTriggered = true
            }
          }
          // depth_change / index_correlation / sector_correlation 需要额外数据源，暂跳过
          // TODO: 接入盘口深度/指数/板块数据后补充

          if (!isTriggered) continue

          // 记录触发时间
          newTriggeredAt[rule.id] = now
          triggered.push(rule)

          // 播放声音
          if (rule.notifyVia.includes('sound')) {
            soundManager.play(getRuleSoundLevel(rule))
          }

          // 浏览器通知
          if (rule.notifyVia.includes('browser') && typeof Notification !== 'undefined') {
            try {
              if (Notification.permission === 'granted') {
                new Notification(`预警: ${rule.name}`, {
                  body: `${rule.symbol ?? ''} 价格触发 ${rule.type} 条件`,
                })
              } else if (Notification.permission !== 'denied') {
                Notification.requestPermission()
              }
            } catch {
              // 通知权限失败静默处理
            }
          }
        }

        // 更新触发记录
        if (triggered.length > 0) {
          set({ triggeredAt: newTriggeredAt })
        }

        return triggered
      },

      resetTriggered: (ruleId) => {
        if (ruleId) {
          set((s) => {
            const next = { ...s.triggeredAt }
            delete next[ruleId]
            return { triggeredAt: next }
          })
        } else {
          set({ triggeredAt: {} })
        }
      },
    }),
    {
      name: 'stockquant-alerts',
      version: 1,
      partialize: (state) => ({ rules: state.rules }),
    }
  )
)
