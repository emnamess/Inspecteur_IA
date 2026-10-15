import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // En développement, les appels /api sont redirigés vers FastAPI (uvicorn sur le port 8000).
    proxy: { "/api": "http://localhost:8000" },
  },
});
