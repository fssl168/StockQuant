import { useLayoutStore } from '../stores/layoutStore'

/**
 * 信息过滤 Hook
 * 用于各面板组件判断自身是否应该渲染
 */
export function useInfoFilter() {
  const shouldShow = useLayoutStore((s) => s.shouldShow)
  const infoFilter = useLayoutStore((s) => s.infoFilter)
  const toggleInfoFilter = useLayoutStore((s) => s.toggleInfoFilter)
  const setHidePanel = useLayoutStore((s) => s.setHidePanel)

  /**
   * 判断指定面板是否应该显示
   * 如果 infoFilter 未启用，返回 true（全部显示）
   * 如果面板在隐藏列表中，返回 false
   */
  const isVisible = (panelId: string) => shouldShow(panelId as never)

  /**
   * 切换面板可见性
   */
  const togglePanelVisibility = (panelId: string) => {
    const hidden = infoFilter.hidePanels.includes(panelId as never)
    setHidePanel(panelId as never, !hidden)
  }

  /**
   * 批量设置面板可见性
   */
  const setPanelsVisible = (panelIds: string[], visible: boolean) => {
    panelIds.forEach((id) => setHidePanel(id as never, visible))
  }

  return {
    enabled: infoFilter.enabled,
    isVisible,
    toggleInfoFilter,
    togglePanelVisibility,
    setPanelsVisible,
    hidePanels: infoFilter.hidePanels,
  }
}
