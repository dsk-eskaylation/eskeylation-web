import { Component, type ErrorInfo, type ReactNode } from 'react'

/** Keep failures visible and recoverable, including rejected lazy imports. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() { return { failed: true } }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // The fallback deliberately avoids exposing internal error details.
  }

  render() {
    if (this.state.failed) return <main className="route-error" role="alert">
      <h1>Chưa tải được trang</h1>
      <p>Kết nối bị gián đoạn hoặc nội dung vừa được cập nhật. Hãy thử tải lại.</p>
      <button type="button" onClick={() => window.location.reload()}>Tải lại trang</button>
      <a href="/">Về trang chủ</a>
    </main>
    return this.props.children
  }
}
