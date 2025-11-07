import { defineConfig } from "vite";

export default defineConfig({
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
