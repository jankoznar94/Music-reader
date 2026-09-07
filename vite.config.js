import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'public',
      filename: 'sw.js',
      registerType: 'autoUpdate',
      workbox: {
        maximumFileSizeToCacheInBytes: 5242880,
        globPatterns: ['**/*.{js,mjs,css,html,ico,png,svg}'],
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.mode === 'navigate',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'html-cache',
            },
          },
        ]
      },
      injectManifest: {
        maximumFileSizeToCacheInBytes: 5242880,
        globPatterns: ['**/*.{js,mjs,css,html,ico,png,svg}'],
      },
      manifest: {
        name: "Noty App",
        short_name: "Noty",
        start_url: "/",
        id: "/index.html",
        display: "standalone",
        theme_color: "#1a1a1a",
        background_color: "#111111",
        icons: [
          { src: "/assets/noty-app-logo-192.png", sizes: "192x192", type: "image/png" },
          { src: "/assets/noty-app-logo-512.png", sizes: "512x512", type: "image/png" }
        ]
      }
    })
  ]
});
