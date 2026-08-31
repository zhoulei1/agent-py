import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 后端 Spring Boot 服务，见 AIController @RequestMapping("/ai")
      '/ai': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        // SSE 流式响应必须关闭代理层缓冲，否则 token 会被攒到最后一次性吐出
        configure(proxy) {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache, no-transform'
            proxyRes.headers['x-accel-buffering'] = 'no'
          })
        },
      },
      // Socket.IO 握手与长连接（当前后端未实现，仅在切换到 socketio 传输时才会走到）
      '/socket.io': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
