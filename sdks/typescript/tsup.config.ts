import { defineConfig } from "tsup";

// A csomag belépője a wrapper (kiterjesztett kliens + webhook-helper) —
// lásd src/wrapper/index.ts. Dual ESM+CJS, d.ts-sel.
export default defineConfig({
    entry: { index: "src/wrapper/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: true,
    target: "node20",
    platform: "node",
});
