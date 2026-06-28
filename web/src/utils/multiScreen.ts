/**
 * 多屏窗口协调工具
 *
 * 使用 BroadcastChannel 实现跨 `window.open()` 窗口的状态同步。
 * 适用于方案 B（Browser Window API 多窗口）。
 *
 * 频道名称: 'stockquant-sync'
 */

import type { ScreenZone } from '@/stores/layoutStore'

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
 * 模块级 Window 引用表：保存通过 window.open 打开的子窗口引用。
 * 不放入 layoutStore 是因为 Window 对象不可序列化（layoutStore 会 persist）。
 */
const windowRefs = new Map<ScreenZone, Window | null>()

/**
 * 心跳定时器句柄
 */
let heartbeatTimer: ReturnType<typeof setInterval> | null = null

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
 * 启动心跳定时器（每 intervalMs 毫秒发送一次 heartbeat 消息）
 * @param intervalMs 心跳间隔，默认 5000ms
 */
export function startHeartbeat(intervalMs: number = 5000): void {
  stopHeartbeat()
  heartbeatTimer = setInterval(() => {
    sendHeartbeat()
  }, intervalMs)
}

/**
 * 停止心跳定时器
 */
export function stopHeartbeat(): void {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
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
 * 保存 Window 引用便于 closeMultiScreen 关闭
 */
export function openMultiScreenLayout(): void {
  const primary = openSubScreen('/monitor?mode=watchlist', 'sq-primary', 1200, 800)
  const secondary = openSubScreen('/dashboard?mode=indices', 'sq-secondary', 1000, 800)
  const tertiary = openSubScreen('/trading?mode=order', 'sq-tertiary', 900, 800)

  // 保存 Window 引用（不可序列化，不存 layoutStore）
  windowRefs.set('primary', primary)
  windowRefs.set('secondary', secondary)
  windowRefs.set('tertiary', tertiary)

  // 通过 layoutStore 保存 BroadcastChannel 引用
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

  // 启动心跳检测
  startHeartbeat()
}

/**
 * 关闭所有副屏并停止心跳
 *
 * 主窗口调用：关闭所有子窗口
 * 子窗口调用：仅关闭自身
 */
export function closeMultiScreen(): void {
  stopHeartbeat()
  postSyncMessage('layout', { mode: 'single', ts: Date.now() })

  // 关闭所有保存的子窗口引用
  for (const [, win] of windowRefs) {
    try {
      win?.close()
    } catch {
      // 跨标签页或已关闭则忽略
    }
  }
  windowRefs.clear()

  // 自身也关闭（如果是子窗口）
  if (isSubScreen()) {
    window.close()
  }
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
  stopHeartbeat()
  if (_channel) {
    _channel.close()
    _channel = null
  }
}

// 页面卸载时清理
window.addEventListener('beforeunload', destroySyncChannel)
