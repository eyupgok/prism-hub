import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Geliştirmede panel aynı origin'den istek atar (VITE_API_URL boş), bu yüzden
  // /api ve /health çağrıları lokalde çalışan backend'e yönlendirilir.
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
  preview: {
    allowedHosts: ['.railway.app', '.example.com'],
    host: '0.0.0.0',
    port: process.env.PORT ? parseInt(process.env.PORT) : 4173
  }
})
