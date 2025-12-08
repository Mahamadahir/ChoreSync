import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { quasar, transformAssetUrls } from '@quasar/vite-plugin';
import path from 'path';

const allowedHostsEnv = process.env.VITE_ALLOWED_HOSTS || '';
const allowedHosts = allowedHostsEnv
  ? allowedHostsEnv.split(',').map((h) => h.trim()).filter(Boolean)
  : ['localhost', '127.0.0.1'];

export default defineConfig({
  plugins: [
    vue({
      template: { transformAssetUrls },
    }),
    quasar({
      sassVariables: path.resolve(__dirname, 'src/quasar-variables.sass'),
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts,
  },
  build: {
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: "node",
    include: ["tests/**/*.spec.ts"],
    exclude: ["dist", "node_modules"],
  },
});
