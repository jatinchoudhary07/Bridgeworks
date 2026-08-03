// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],

  // --- OPTIMIZE DEPENDENCIES FOR INSTANT LOADING ---
  optimizeDeps: {
    include: [
      '@mui/material',
      '@mui/icons-material',
      '@emotion/react',
      '@emotion/styled',
      'react-router-dom',
      'axios',
    ],
  },
  
  // --- SERVER & PROXY CONFIGURATION ---
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // Django backend
        changeOrigin: true,
        secure: false,
      },
      '/accounts': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },

  // --- BUILD OPTIMIZATION ---
  build: {
    chunkSizeWarningLimit: 1000,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('mermaid')) return 'vendor-mermaid';
            if (id.includes('jspdf')) return 'vendor-jspdf';
            if (id.includes('firebase')) return 'vendor-firebase';
            if (id.includes('@mui') || id.includes('@emotion')) return 'vendor-mui';
            if (id.includes('recharts') || id.includes('d3')) return 'vendor-charts';
            return 'vendor-libs';
          }
        }
      }
    }
  }
})