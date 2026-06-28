/**
 * AntD message 工具函数
 *
 * 1. 非阻塞调用：使用 setTimeout defer 到下一个 tick，避免阻塞主线程
 * 2. 符合 AntD 5.x 规范：使用 App.useApp() 获取 message 实例，支持动态主题
 *
 * 使用方式（推荐）：
 *   import { messageSuccess, messageError, messageWarning, messageInfo, message } from '@/utils/message'
 *   message.success('操作成功')
 *   message.error('出错了')
 *
 * 旧组件中直接 import { message } from '@/utils/message' 依然可用，
 * 返回一个兼容 AntD MessageInstance 的对象。
 */

import type { MessageInstance } from 'antd/es/message/interface'

// 创建全局 message 实例（单例）
let _messageInstance: MessageInstance | null = null

export function setMessageInstance(message: MessageInstance) {
  _messageInstance = message
}

// 私有：内部调用 message 实例
function _call(
  fn: 'success' | 'error' | 'warning' | 'info' | 'loading',
  content: string | React.ReactNode,
  duration?: number,
) {
  if (!_messageInstance) {
    console.warn('[message] message instance not set, call setMessageInstance first')
    return
  }
  setTimeout(() => {
    _messageInstance![fn](content, duration)
  }, 0)
}

// 导出 AntD MessageInstance 兼容对象
// 供直接 import { message } from '@/utils/message' 的旧组件使用
export const message = {
  success: (content: string | React.ReactNode, duration = 3) =>
    _call('success', content, duration),
  error: (content: string | React.ReactNode, duration = 4) =>
    _call('error', content, duration),
  warning: (content: string | React.ReactNode, duration = 4) =>
    _call('warning', content, duration),
  info: (content: string | React.ReactNode, duration = 3) =>
    _call('info', content, duration),
  loading: (content: string | React.ReactNode, duration = 3) =>
    _call('loading', content, duration),
}

// 以下为命名函数导出（推荐新组件使用）
export function messageSuccess(content: string | React.ReactNode, duration = 3) {
  message.success(content, duration)
}

export function messageError(content: string | React.ReactNode, duration = 4) {
  message.error(content, duration)
}

export function messageWarning(content: string | React.ReactNode, duration = 4) {
  message.warning(content, duration)
}

export function messageInfo(content: string | React.ReactNode, duration = 3) {
  message.info(content, duration)
}

export function messageLoading(content: string | React.ReactNode, duration = 3) {
  message.loading(content, duration)
}
