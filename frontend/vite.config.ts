import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API + media về backend FastAPI (dev). Backend chạy ở cổng 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
    },
  },
})
