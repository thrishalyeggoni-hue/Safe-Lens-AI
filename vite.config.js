import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    // Runtime files and build artifacts must not refresh transient evidence views.
    watch: { ignored: ['**/backend/**', '**/*.db', '**/*.db-journal', '**/dist/**', '**/docs/**', '**/tests/**', '**/scripts/**'] },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
