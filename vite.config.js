import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'public',
      filename: 'sw-v2.js',
      registerType: 'prompt',
      workbox: {
        maximumFileSizeToCacheInBytes: 5242880,
        // woff2 = font dynamiky NotyDyn; bez něj by offline režim ukázal rozbité znaky.
        // POZOR: png tu být NESMÍ (ikony se přednačítají přes manifest.icons a vznikly by duplicity).
        globPatterns: ['**/*.{js,mjs,css,html,ico,svg,woff2}'],
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
        // Stejné jako workbox výše — v injectManifest strategii se čtou globy odtud.
        globPatterns: ['**/*.{js,mjs,css,html,ico,svg,woff2}'],
      },
      manifest: {
        name: "Noty App",
        short_name: "Noty",
        start_url: "/",
        id: "/noty-app-v2",
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
