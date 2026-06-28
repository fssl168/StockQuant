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
  createdAt: string
  updatedAt: string
}

/**
 * 预警类型到音效等级的映射
 * - price / depth_change → opportunity（机会提示）
 * - index_correlation / sector_correlation → info（信息提示）
 */
const ALERT_TYPE_TO_SOUND: Record<AlertRule['type'], SoundLevel> = {
  price: 'opportunity',
  depth_change: 'opportunity',
  index_correlation: 'info',
  sector_correlation: 'info',
}

interface AlertRuleState {
  rules: AlertRule[]
  loading: boolean
  fetchRules: () => Promise<void>
  createRule: (data: Omit<AlertRule, 'id' | 'createdAt' | 'updatedAt'>) => Promise<void>
  updateRule: (id: string, data: Partial<Omit<AlertRule, 'id' | 'createdAt' | 'updatedAt'>>) => Promise<void>
  toggleRule: (id: string) => Promise<void>
  deleteRule: (id: string) => Promise<void>
}

export const useAlertStore = create<AlertRuleState>()(
  persist(
    (set, get) => ({
      rules: [],
      loading: false,

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
      },

      toggleRule: async (id) => {
        const rule = get().rules.find((r) => r.id === id)
        if (!rule) return
        await client.put(`/api/alerts/rules/${id}`, { enabled: !rule.enabled })
        await get().fetchRules()
        // 启用规则时（且配置了声音通道）播放对应音效
        if (!rule.enabled && rule.notifyVia.includes('sound')) {
          const soundLevel = ALERT_TYPE_TO_SOUND[rule.type] ?? 'info'
          soundManager.play(soundLevel)
        }
      },

      deleteRule: async (id) => {
        await client.delete(`/api/alerts/rules/${id}`)
        await get().fetchRules()
      },
    }),
    {
      name: 'stockquant-alerts',
      version: 1,
    }
  )
)
