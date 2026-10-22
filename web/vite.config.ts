/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// The API (uvicorn f1lab.api.main:app) listens here; dev and preview servers proxy /api to it.
// Override with F1LAB_API_URL when uvicorn runs on another port.
const API_TARGET = process.env.F1LAB_API_URL ?? 'http://127.0.0.1:8000'
const apiProxy = { '/api': { target: API_TARGET, changeOrigin: true } }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
