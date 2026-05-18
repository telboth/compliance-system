import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (
            id.includes("/react/") ||
            id.includes("/react-dom/") ||
            id.includes("/scheduler/")
          ) {
            return "vendor-react";
          }
          if (id.includes("/axios/")) return "vendor-axios";
          if (id.includes("@tanstack/react-table")) return "vendor-table";
          if (id.includes("react-leaflet") || id.includes("/leaflet/")) return "vendor-map";
          if (id.includes("@tanstack/react-query")) return "vendor-query";
          if (id.includes("react-router")) return "vendor-router";
          return "vendor-misc";
        },
      },
    },
  },
  server: {
    port: 5173,
    // host: true binder til 0.0.0.0 — nødvendig for LAN-tilgang fra kollega
    host: true,
    // HMR over LAN: Vite sender WebSocket-tilkoblingen tilbake til klientens
    // egen host (ikke hardkodet localhost), så auto-reload fungerer på LAN.
    hmr: {
      // clientPort: 5173 er standard — eksplisitt for klarhet
      clientPort: 5173,
    },
    proxy: {
      // Alle /api-kall proxyes server-side til FastAPI-containeren.
      // Kollegaens nettleser ser bare port 5173 — CORS er ikke involvert.
      // I Docker brukes service-navn "api"; utenfor Docker brukes localhost:8000.
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        // Logg proxy-feil i utvikling for enklere feilsøking
        configure: (proxy) => {
          proxy.on("error", (err) => {
            console.error("[vite proxy] API unreachable:", err.message);
          });
        },
      },
    },
  },
});
