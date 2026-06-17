import { defineConfig } from 'vitest/config'
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
  test: {
    env: {
      VITE_API_URL: '',
    },
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: true,
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
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
