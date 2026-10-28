import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/schedule': 'http://localhost:8000',
    },
  },
})
// proxy: -> any request with schedule goes to uvicorn
// with its parameters