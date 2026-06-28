import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ScreenZone = 'primary' | 'secondary' | 'tertiary'

export interface ZoneDef {
  key: ScreenZone
  label: string
  components: ScreenComponent[]
  minWidth: number
  order: number
}

export type ScreenComponent =
  | 'watchlist'
  | 'kline'
  | 'depth'
  | 'tick'
  | 'volume_ratio'
  | 'indices'
  | 'heatmap'
  | 'order_panel'
  | 'position_panel'
  | 'alerts'
  | 'sentiment'

export type LayoutMode = 'single' | 'multi-screen'

export interface ScreenConfig {
  zones: Record<ScreenZone, ZoneDef>
  mode: LayoutMode
  // 区域大小比例 (0-1)
  zoneRatios: Record<ScreenZone, number>
}

export interface InfoFilterConfig {
  enabled: boolean
  coreOnly: ScreenComponent[]
  hidePanels: ScreenComponent[]
  collapseOnLowActivity: boolean
  lowActivityHours: { start: number; end: number }
}

interface LayoutState {
  mode: LayoutMode
  setMode: (mode: LayoutMode) => void

  zoneRatios: Record<ScreenZone, number>
  setZoneRatio: (zone: ScreenZone, ratio: number) => void
  resetZoneRatios: () => void

  // 信息过滤
  infoFilter: InfoFilterConfig
  toggleInfoFilter: () => void
  setHidePanel: (panel: ScreenComponent, hide: boolean) => void
  isPanelHidden: (panel: ScreenComponent) => boolean
  shouldShow: (panel: ScreenComponent) => boolean

  // 多屏坐标 (用于 window.open 多窗口模式)
  multiScreenWindows: {
    primary?: string
    secondary?: string
    tertiary?: string
  }
  setMultiScreenWindow: (zone: ScreenZone, url: string) => void
  clearMultiScreenWindow: (zone: ScreenZone) => void

  // 广播频道实例 (用于跨窗口通信)
  broadcastChannel: BroadcastChannel | null
  setBroadcastChannel: (channel: BroadcastChannel | null) => void

  // 同步事件
  syncEvents: {
    selectedSymbol: string | null
    onSymbolChange: (symbol: string | null) => void
  }

  // 机构模式开关 (VIEWER 不可见)
  institutionalEnabled: boolean
  toggleInstitutional: () => void
}

const defaultZoneRatios: Record<ScreenZone, number> = {
  primary: 0.45,
  secondary: 0.25,
  tertiary: 0.3,
}

const defaultInfoFilter: InfoFilterConfig = {
  enabled: false,
  coreOnly: ['depth', 'tick', 'volume_ratio'],
  hidePanels: [],
  collapseOnLowActivity: false,
  lowActivityHours: { start: 12, end: 14 },
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set, get) => ({
      mode: 'single',
      setMode: (mode) => set({ mode }),

      zoneRatios: defaultZoneRatios,
      setZoneRatio: (zone, ratio) =>
        set((state) => ({
          zoneRatios: { ...state.zoneRatios, [zone]: Math.max(0.1, Math.min(0.9, ratio)) },
        })),
      resetZoneRatios: () => set({ zoneRatios: defaultZoneRatios }),

      infoFilter: defaultInfoFilter,
      toggleInfoFilter: () =>
        set((state) => ({
          infoFilter: { ...state.infoFilter, enabled: !state.infoFilter.enabled },
        })),
      setHidePanel: (panel, hide) =>
        set((state) => ({
          infoFilter: {
            ...state.infoFilter,
            hidePanels: hide
              ? [...new Set([...state.infoFilter.hidePanels, panel])]
              : state.infoFilter.hidePanels.filter((p) => p !== panel),
          },
        })),
      isPanelHidden: (panel) => get().infoFilter.hidePanels.includes(panel),
      shouldShow: (panel) => {
        const { enabled, hidePanels, coreOnly, collapseOnLowActivity, lowActivityHours } = get().infoFilter
        if (!enabled) return true
        if (collapseOnLowActivity) {
          const hour = new Date().getHours()
          const { start, end } = lowActivityHours
          const inLowActivity = start < end
            ? (hour >= start && hour < end)
            : (hour >= start || hour < end)
          if (inLowActivity && !coreOnly.includes(panel)) return false
        }
        if (coreOnly.length > 0 && !coreOnly.includes(panel)) return false
        if (hidePanels.includes(panel)) return false
        return true
      },

      multiScreenWindows: {},
      setMultiScreenWindow: (zone, url) =>
        set((state) => ({
          multiScreenWindows: { ...state.multiScreenWindows, [zone]: url },
        })),
      clearMultiScreenWindow: (zone) =>
        set((state) => {
          const copy = { ...state.multiScreenWindows }
          delete copy[zone]
          return { multiScreenWindows: copy }
        }),

      broadcastChannel: null,
      setBroadcastChannel: (channel) => set({ broadcastChannel: channel }),

      syncEvents: {
        selectedSymbol: null,
        onSymbolChange: (symbol) => set((state) => ({
          syncEvents: { ...state.syncEvents, selectedSymbol: symbol },
        })),
      },

      institutionalEnabled: false,
      toggleInstitutional: () => set((s) => ({ institutionalEnabled: !s.institutionalEnabled })),
    }),
    {
      name: 'stockquant-layout',
      version: 1,
      partialize: (state) => ({
        mode: state.mode,
        zoneRatios: state.zoneRatios,
        infoFilter: state.infoFilter,
        multiScreenWindows: state.multiScreenWindows,
        institutionalEnabled: state.institutionalEnabled,
      }),
    }
  )
)
