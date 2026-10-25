import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Rutas relativas (/api/...): en producción el backend sirve el sitio y la API
// desde el mismo origen; en desarrollo Vite hace proxy al backend local.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
    },
  },
  build: {
    outDir: "dist",
  },
});
