import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// One bundle for every Amaterasu page. FastAPI keeps rendering each route
// with Jinja (auth, signed links and server data stay in Python); the
// template only names its page and passes data as JSON. main.ts mounts the
// matching page, and every page shares the same tokens, base CSS and ui/.
//
// Output lands in web/static/dist with content-hashed names plus
// .vite/manifest.json. FastAPI reads the manifest and base.html links the
// hashed entry, so caches never serve a
// stale bundle and every chunk imports the one shared runtime.
export default defineConfig({
  plugins: [svelte()],
  base: "/static/dist/",
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    target: "es2022",
    cssCodeSplit: true,
    manifest: true,
    rollupOptions: {
      input: { main: "src/main.ts" },
      output: {
        entryFileNames: "[name]-[hash].js",
        // Page chunks are named after their folder (pages/<name>/Page.svelte).
        chunkFileNames: (chunk) => {
          const m = chunk.facadeModuleId?.match(/pages[\/]([^\/]+)[\/]Page\.svelte/);
          return m ? `pages/${m[1]}-[hash].js` : "chunks/[name]-[hash].js";
        },
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  resolve: { conditions: ["browser"] },
});
