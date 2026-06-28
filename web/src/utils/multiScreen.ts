/**
 * 多屏窗口协调工具
 *
 * 使用 BroadcastChannel 实现跨 `window.open()` 窗口的状态同步。
 * 适用于方案 B（Browser Window API 多窗口）。
 *
 * 频道名称: 'stockquant-sync'
 */

export const SYNC_CHANNEL_NAME = 'stockquant-sync'

export type SyncEventType =
  | 'layout'
  | 'symbol'
  | 'alert'
  | 'order'
  | 'position'
  | 'heartbeat'

export interface SyncMessage {
  type: SyncEventType
  payload: Record<string, unknown>
  source?: string // 窗口标识，用于去重
}

let _channel: BroadcastChannel | null = null

/**
 * 获取或创建 BroadcastChannel 实例
 */
export function getSyncChannel(): BroadcastChannel {
  if (!_channel) {
    _channel = new BroadcastChannel(SYNC_CHANNEL_NAME)
  }
  return _channel
}

/**
 * 发布同步消息
 */
export function postSyncMessage(
  type: SyncEventType,
  payload: Record<string, unknown>,
  source: string = window.location.href
): void {
  const channel = getSyncChannel()
  const message: SyncMessage = { type, payload, source }
  channel.postMessage(message)
}

/**
 * 监听同步消息
 * @returns unsubscribe 函数
 */
export function onSyncMessage(
  type: SyncEventType | null, // null = 监听所有类型
  handler: (message: SyncMessage) => void
): () => void {
  const channel = getSyncChannel()

  const wrapper = (e: MessageEvent<SyncMessage>) => {
    if (type && e.data.type !== type) return
    handler(e.data)
  }

  channel.addEventListener('message', wrapper)

  return () => {
    channel.removeEventListener('message', wrapper)
  }
}

/**
 * 发送心跳（用于检测其他窗口是否存活）
 */
export function sendHeartbeat(source: string = window.location.href): void {
  postSyncMessage('heartbeat', { ts: Date.now(), source })
}

/**
 * 打开一个新的副屏窗口
 */
export function openSubScreen(
  path: string,
  name: string,
  width: number,
  height: number
): Window | null {
  const features = `width=${width},height=${height},left=${window.screenX + 20},top=${window.screenY + 20},resizable=yes,scrollbars=yes`
  const url = `${import.meta.env.VITE_API_URL ? '' : window.location.origin}${path}?mode=sub-screen`
  const win = window.open(url, name, features)

  if (win) {
    postSyncMessage('layout', {
      opened: name,
      path,
      ts: Date.now(),
    })
  }

  return win
}

/**
 * 一键展开多屏模式
 *
 * 打开三个子窗口：主屏（盯盘）、副屏一（大盘）、副屏二（交易）
 */
export function openMultiScreenLayout(): void {
  const primary = openSubScreen('/monitor?mode=watchlist', 'sq-primary', 1200, 800)
  const secondary = openSubScreen('/dashboard?mode=indices', 'sq-secondary', 1000, 800)
  const tertiary = openSubScreen('/trading?mode=order', 'sq-tertiary', 900, 800)

  // 通过 layoutStore 保存窗口引用
  import('../stores/layoutStore').then(({ useLayoutStore }) => {
    useLayoutStore.getState().setBroadcastChannel(getSyncChannel())
  })

  // 广播布局变更
  postSyncMessage('layout', {
    mode: 'multi-screen',
    primary: primary?.name,
    secondary: secondary?.name,
    tertiary: tertiary?.name,
    ts: Date.now(),
  })
}

/**
 * 关闭所有副屏
 */
export function closeMultiScreen(): void {
  postSyncMessage('layout', { mode: 'single', ts: Date.now() })

  window.close()
}

/**
 * 检查当前窗口是否是从多屏模式打开的子窗口
 */
export function isSubScreen(): boolean {
  return new URLSearchParams(window.location.search).get('mode') === 'sub-screen'
}

/**
 * 关闭 BroadcastChannel（应用卸载时调用）
 */
export function destroySyncChannel(): void {
  if (_channel) {
    _channel.close()
    _channel = null
  }
}

// 页面卸载时清理
window.addEventListener('beforeunload', destroySyncChannel)
