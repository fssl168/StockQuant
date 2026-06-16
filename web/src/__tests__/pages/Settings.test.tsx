import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Settings from '@/pages/Settings'

describe('Settings Page', () => {
  it('should render page title', () => {
    render(<Settings />)
    expect(screen.getByText('运行配置中心')).toBeInTheDocument()
  })

  it('should render wizard mode tag', () => {
    render(<Settings />)
    expect(screen.getByText('向导模式')).toBeInTheDocument()
  })

  it('should render expert mode tag', () => {
    render(<Settings />)
    expect(screen.getByText('专家模式')).toBeInTheDocument()
  })

  it('should render all setting groups in expert mode', () => {
    render(<Settings />)
    expect(screen.getByText('系统总控')).toBeInTheDocument()
    expect(screen.getByText('数据源')).toBeInTheDocument()
    expect(screen.getByText('交易成本')).toBeInTheDocument()
    expect(screen.getByText('执行参数')).toBeInTheDocument()
    expect(screen.getByText('交易时段')).toBeInTheDocument()
    expect(screen.getByText('券商通道')).toBeInTheDocument()
    expect(screen.getByText('风控阈值')).toBeInTheDocument()
    expect(screen.getAllByText('AI 模型').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('策略进化').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('通知推送').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('基本面适配')).toBeInTheDocument()
    expect(screen.getByText('信号管理')).toBeInTheDocument()
    expect(screen.getByText('历史同步')).toBeInTheDocument()
    expect(screen.getByText('消息总线')).toBeInTheDocument()
  })

  it('should switch to wizard mode on click', async () => {
    const user = userEvent.setup()
    render(<Settings />)
    await user.click(screen.getByText('向导模式'))
    expect(screen.getByText('基础配置')).toBeInTheDocument()
  })

  it('should render wizard steps', async () => {
    const user = userEvent.setup()
    render(<Settings />)
    await user.click(screen.getByText('向导模式'))
    expect(screen.getByText('交易模式')).toBeInTheDocument()
    expect(screen.getByText('数据源')).toBeInTheDocument()
    expect(screen.getByText('回测设置')).toBeInTheDocument()
    expect(screen.getByText('风控参数')).toBeInTheDocument()
    expect(screen.getByText('完成')).toBeInTheDocument()
  })

  it('should render expand/collapse button', () => {
    render(<Settings />)
    expect(screen.getByText('全部折叠')).toBeInTheDocument()
  })

  it('should render key setting labels in expert mode', () => {
    render(<Settings />)
    expect(screen.getByText('交易模式')).toBeInTheDocument()
    expect(screen.getByText('日志级别')).toBeInTheDocument()
    expect(screen.getByText('Web 端口')).toBeInTheDocument()
  })

  it('should render save confirmation subtitle', () => {
    render(<Settings />)
    expect(screen.getByText('所有修改保存后热生效，无需重启服务')).toBeInTheDocument()
  })
})
