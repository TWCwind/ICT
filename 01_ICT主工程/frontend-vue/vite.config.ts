import { fileURLToPath, URL } from 'node:url'
import { Agent } from 'node:http'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendAgent = new Agent({
  keepAlive: true,
  maxSockets: 32,
  maxFreeSockets: 8,
})

const backendProxy = {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  ws: true,
  agent: backendAgent,
}

// https://vite.dev/config/
export default defineConfig({
  build: {
    sourcemap: 'hidden',
    // 分包：把稳定不动的大依赖拆成独立 chunk，页面 chunk 只留业务代码，二次访问直接命中缓存。
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/three/')) return 'vendor-three'
          if (id.includes('node_modules/katex/') || id.includes('node_modules/markdown-it/') || id.includes('node_modules/dompurify/')) {
            return 'vendor-markdown'
          }
          if (id.includes('node_modules/vue/') || id.includes('node_modules/@vue/') || id.includes('node_modules/vue-router/')) {
            return 'vendor-vue'
          }
          if (id.includes('node_modules/@fontsource/')) return 'vendor-fonts'
          return undefined
        },
      },
    },
  },
  server: {
    strictPort: true,
    proxy: {
      '/api': backendProxy,
      '/files': backendProxy,
      '/exports': backendProxy,
    },
  },
  preview: {
    proxy: {
      '/api': backendProxy,
      '/files': backendProxy,
      '/exports': backendProxy,
    },
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
})
