import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// BASE_PATH lets the app be served from a sub-path (GitHub Pages puts it
// under /ascentrylabs/). Locally and on Vercel it stays at the root.
export default defineConfig({
  plugins: [react()],
  base: process.env.BASE_PATH ?? '/',
})
