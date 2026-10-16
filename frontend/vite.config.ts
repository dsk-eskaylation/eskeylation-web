import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API + media về backend FastAPI (dev). Backend chạy ở cổng 8000.
export default defineConfig({
  plugins: [react(), {
    name: 'production-csp',
    transformIndexHtml(html, context) {
      // Vite HMR có script inline; CSP chặt chỉ dành cho bản build production.
      return context.server ? html.replace(/\s*<meta http-equiv="Content-Security-Policy"[^>]*\/>/, '') : html
    },
  }],
  server: {
    proxy: {
      // ws: true -> proxy cả WebSocket cộng đồng (/api/community/{id}/ws)
      '/api': { target: 'http://localhost:8000', ws: true },
      '/media': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      // API quản trị (route SPA của CMS là /cms nên không đụng nhau)
      '/admin': 'http://localhost:8000',
    },
  },
})
