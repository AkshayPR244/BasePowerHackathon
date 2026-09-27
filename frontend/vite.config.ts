import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    proxy: {
      "/api": process.env.SLACKLINE_API_PROXY ?? "http://localhost:8000",
    },
  },
  test: { include: ["src/**/*.test.{ts,tsx}"] },
});
