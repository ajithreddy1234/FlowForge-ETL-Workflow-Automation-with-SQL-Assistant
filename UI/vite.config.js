import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  envDir: resolve(__dirname, '..'),
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws':  { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('@xyflow')) return 'pipeline-canvas'
          if (id.includes('react') || id.includes('scheduler')) return 'react-core'
          if (id.includes('lucide')) return 'icons'
          if (id.includes('axios') || id.includes('zustand')) return 'data-client'
          return 'vendor'
        },
      },
    },
  },
})
