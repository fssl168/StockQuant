import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/// <reference types="vitest" />
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // @ts-ignore — __dirname is available in vite.config.ts (Node.js ESM)
      '@': new URL('./src', import.meta.url).pathname,
    },
    },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
