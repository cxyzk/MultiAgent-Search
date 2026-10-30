import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    // 监听所有网卡：手机等同一局域网设备可通过 http://<本机IP>:5173 访问
    host: '0.0.0.0',
    port: 5173,
    // 端口被占用时直接报错，而不是悄悄换到 5174——手机书签里端口一变就失效
    strictPort: false,
    // 允许局域网域名/IP 访问（Vite 6+ 的 Host 头校验）
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        // SSE 坑：dev 代理会攒着响应头，直到有第一块 body 数据才转发——
        // 实测直连后端 t+0.59s、经代理 t+15.47s（与首条 keepalive 同刻）。
        // 解决靠后端 generate() 开头立即 yield ": connected"，不是改这里。
        // 详见 README「流式推送迁移实录 · 坑 1」。
      },
    },
  },
});
