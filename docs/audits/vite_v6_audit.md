# Vite v6 Audit

**Audit date:** 2026-05-07  
**Installed version:** `vite@^6.3.5` (`frontend/package.json`)  
**Related:** `vitest@^4.1.3`, `@vitejs/plugin-react-swc@^3.10.1`, `@tailwindcss/vite@^4.1.11`  
**Scope:** `frontend/vite.config.ts`, `frontend/vitest.config.ts`, env usage, dependency alignment

---

## Summary

The DynoAI frontend is a **standard client-only SPA** on Vite 6. Configuration uses supported APIs (`defineConfig`, React SWC plugin, Tailwind v4 Vite plugin, dev proxy, Rollup manual chunks, `optimizeDeps`). There is **no custom Vite plugin code** and **no SSR** in this repo, so the largest Vite 6 churn items (Environment API / `this.environment` in plugin hooks, Module Runner migration from the old experimental Runtime API) **do not apply to application code**.

| Category     | Count | Notes |
|--------------|-------|--------|
| OK           | 6     | Config and patterns match current v6 docs |
| Drifted      | 1     | Proxy env var name vs. app `VITE_API_URL` |
| Risky        | 0     | None identified |
| Could-adopt  | 3     | Optional alignment, docs follow-up, future toolchain |

---

## Method

**Context7 sources**

- Library ID: `/websites/v6_vite_dev` (Vite 6 site)
- Topics: migration (`vite.dev` v6 migration), Environment API / Module Runner, `defineConfig`, `mergeConfig`, server proxy, plugin hook context (`this.environment` vs `options.ssr`)

**Local scan**

- Read `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/package.json`
- Grep: `import.meta.env`, custom plugins, `ssr`, `worker.plugins`, Vite programmatic API

---

## Findings

### OK

1. **`defineConfig` and TypeScript config** — Matches v6 guidance for typed config (`frontend/vite.config.ts`).  
   Source: [Vite 6 config — defineConfig](https://v6.vite.dev/config)

2. **Plugins: `@vitejs/plugin-react-swc` + `@tailwindcss/vite`** — Standard v6 + Tailwind v4 integration path; no legacy PostCSS-only requirement in this setup.

3. **`resolve.alias` for `@` → `src`** — Normal pattern; uses `fileURLToPath` / `import.meta.url` for ESM-safe `__dirname`.

4. **`server.proxy` for `/api`** — Documented middleware/proxy pattern remains valid in v6.  
   Source: [Vite 6 API — middleware / proxy examples](https://v6.vite.dev/guide/api-javascript)

5. **`build.rollupOptions.output.manualChunks`** — Still the supported way to split vendor bundles; no deprecated `splitVendorChunkPlugin` usage.

6. **`optimizeDeps.include` + `esbuild` options** — Conventional; nothing flagged as v6-incompatible for a client build.

7. **Vitest** — `vitest.config.ts` uses `defineConfig` from `vitest/config` with `environment: "jsdom"` and the same `@` alias; typical Vitest 4 + Vite 6 layout.

### Drifted

**D1 — Dev proxy target env name vs. client bundle**

```27:36:frontend/vite.config.ts
  server: {
    port: 5173,
    host: true,
    strictPort: false,
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:5001',
        changeOrigin: true,
      }
    }
  },
```

The app and API clients overwhelmingly use **`import.meta.env.VITE_API_URL`** (and `.env.development` sets `VITE_API_URL`). The dev server proxy uses **`process.env.VITE_API_BASE_URL`**, which is a **different variable** and is not declared in `vite-env.d.ts`.

- **Runtime impact:** Low if you always rely on the default `http://localhost:5001`; if you need a custom API origin in dev, you must set **both** or align to one name.  
- **Recommendation:** Document in README or unify on `VITE_API_URL` for the proxy target (e.g. read `loadEnv` in `vite.config.ts`) so one env controls client + proxy.

### Risky

- **None** found for v6-specific breakage in this repo (no experimental Runtime API, no custom plugins using `options.ssr`).

### Could-adopt

1. **Plugin / SSR authors only:** If you later add a custom Vite plugin or SSR, migrate hook logic from `options.ssr` to **`this.environment`** per v6.  
   Source: [this.environment in hooks](https://v6.vite.dev/changes/this-environment-in-hooks)

2. **Experimental Runtime API users:** If any external tool depended on the old experimental Vite Runtime API, replace with the **Module Runner** / **Environment API** path described in the v6 migration guide. This repo does not use that API.  
   Source: [Migration — Vite Runtime → Module Runner](https://v6.vite.dev/guide/migration)

3. **Rolldown / Oxc track:** Vite’s docs describe a separate Rolldown-oriented toolchain; this project uses the **current stable Rollup + esbuild path** in `vite.config.ts`. Treat Rolldown adoption as an explicit future upgrade, not a v6 default requirement for this app.

---

## `import.meta.env` usage (sample)

Client code correctly uses Vite-prefixed env vars (`VITE_API_URL`, `VITE_API_KEY`, `VITE_V3_MATERIALIZE_FALLBACK`) and `import.meta.env.DEV` where relevant. Types are partially centralized in `frontend/src/vite-env.d.ts`.

---

## Recommendation

- **Sign off on Vite 6** for this frontend: configuration is aligned with v6 docs for a client SPA.  
- **Optional cleanup:** Resolve **D1** (proxy env vs `VITE_API_URL`) to avoid confusing local deployments.

---

*Audit performed with Context7 (`/websites/v6_vite_dev`) and repository static analysis. No source files were modified.*
