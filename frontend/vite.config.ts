import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // "@/api/client" → "src/api/client" (shadcn/ui bileşenleri de bu kısayolu kullanır)
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
