import { Component, ErrorInfo, ReactNode } from 'react'
import { Result, Button } from 'antd'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <Result
            status="error"
            title="页面渲染异常"
            subTitle={this.state.error?.message || '未知错误'}
            extra={[
              <Button
                type="primary"
                key="reload"
                onClick={() => window.location.reload()}
              >
                刷新页面
              </Button>,
            ]}
          />
        )
      )
    }

    return this.props.children
  }
}
