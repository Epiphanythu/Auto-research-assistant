import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    sourcemap: process.env.VITE_ENABLE_SOURCEMAP === "true" ? "hidden" : false,
  },
  plugins: [
    react({
      babel: {
        plugins: mode === "development" ? ['react-dev-locator'] : [],
      },
    }),
    tsconfigPaths()
  ],
}))
