import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    // S4-09 Item 2: Docker Desktop's bind-mounted volumes don't reliably
    // deliver native filesystem change events into the container (the same
    // class of issue as the backend's WatchFiles flakiness) — Vite's
    // default watcher silently misses edits, so hot-reload looks "stuck"
    // until the container is restarted. Polling trades a little CPU for
    // reliably noticing changes instead.
    watch: {
      usePolling: true,
      interval: 1000,
    },
  },
})