import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { configDefaults } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/admin-api': {
        target: 'http://127.0.0.1:5174',
        changeOrigin: true
      }
    }
  },
  test: {
    environment: 'jsdom',
    exclude: [...configDefaults.exclude, 'tests/e2e/**'],
    setupFiles: './src/test/setup.ts',
    globals: true,
    coverage: {
      reporter: ['text', 'html']
    }
  }
});
