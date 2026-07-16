import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        flued: resolve(__dirname, "flued.html"),
        fluedEvidence: resolve(__dirname, "flued-evidence.html"),
        fluedExperiments: resolve(__dirname, "flued-experiments.html"),
      },
    },
  },
});
