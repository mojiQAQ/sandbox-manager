import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 15173,
    proxy: {
      '/api': {
        target: 'http://localhost:19000',
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: 'ws://localhost:19000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
