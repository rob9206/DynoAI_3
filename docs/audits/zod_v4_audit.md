# Zod v4 Audit

**Audit date:** 2026-05-07  
**Declared dependency:** `zod@^3.25.76` (`frontend/package.json`)  
**Scope:** `frontend/` source, Zod v4 docs (Context7), compatibility with planned `@hookform/resolvers` usage

---

## Summary

DynoAI’s frontend **declares Zod v3** but **does not import or call Zod anywhere in application source** under this audit. `react-hook-form` and `@hookform/resolvers` are installed; **`zodResolver` is not used** in scanned TS/TSX.

| Category    | Count | Notes |
|-------------|-------|--------|
| OK          | 2     | No Zod v3 API surface in app code to break on v4 |
| Drifted     | 2     | Zod in `package.json` + manual chunk; zero callsites |
| Risky       | 0     | — |
| Could-adopt | 3     | Jump to v4 + Mini when you add schemas; align resolvers |

**Bottom line:** A move to **Zod v4** is a **greenfield** decision for this repo today—there is no migration diff inside `frontend/src`, only dependency and future integration choices.

---

## Method

**Context7**

- `/websites/zod_dev_v4` — Zod 4 changelog and migration snippets  
- `/colinhacks/zod` — indexed versions include v4.0.1 (reference)

**Repository scan**

- `grep` / search for `from "zod"`, `from 'zod'`, `zodResolver`, `z.` patterns  
- Read `frontend/package.json`, `frontend/vite.config.ts` (manual chunk lists `zod`)

---

## Findings

### OK

1. **No Zod v3-only patterns in app code** — No `errorMap`, `.parse` chains, or `z.*` schemas appear in `frontend/src`, so there is nothing to mechanically rewrite for v4.

2. **Forms stack is RHF-first without Zod wiring** — `frontend/src/components/ui/form.tsx` uses `react-hook-form` primitives only; validation can be added later with or without Zod.

### Drifted

**D1 — Unused direct dependency**

`zod` is listed in `dependencies` and grouped in `manualChunks` as `'form-vendor': ['react-hook-form', 'zod']`, but **no module imports `zod`**. That inflates the mental model (“we validate with Zod”) without evidence in source.

**D2 — `@hookform/resolvers` without `zodResolver`**

`@Hookform/resolvers` is installed; typical Zod integration (`zodResolver(schema)`) was **not found** in scanned files. Either schemas live elsewhere (they do not, in this tree) or the combo is reserved for future forms work.

### Risky

- **None** for v3→v4 migration in **this** codebase, because Zod is not invoked.

*(Risk appears only after you add schemas: then v4 breaking changes below apply.)*

### Could-adopt

1. **When introducing validation, target Zod 4** and `@hookform/resolvers` releases that document Zod 4 support, so you skip a second migration.

2. **Consider Zod Mini** (`import * as z from "zod/mini"`) for client bundles if schemas are small—docs emphasize smaller core size versus full Zod 3.

3. **Remove or use `zod`:** Either delete the dependency until needed, or add the first real schema + `zodResolver` so `package.json` matches reality.

---

## Zod v4 highlights (Context7 / official changelog themes)

Use these when you **do** add schemas or upgrade from v3:

| Area | v3 → v4 change (summary) |
|------|---------------------------|
| Custom errors | `errorMap` → unified `error` callback returning a **string** (or defer with `undefined`) |
| `z.coerce.*` | Input type inferred as **`unknown`** in v4, not the coerced primitive type |
| `z.record(z.enum([...]), z.number())` | Stricter / exhaustive key typing vs v3 partial-style inference |
| `z.number().safe()` | Aligns with integer-only safe integers (no floats)—behavior changed from v3 |
| Distribution | **`zod/mini`** for reduced bundle; functional API for tree-shaking |

Sources:

- [Zod v4 changelog / coerce](https://zod.dev/v4/changelog?id=deprecates-message-parameter)  
- [Zod v4 — error vs errorMap](https://zod.dev/v4)  
- [Zod v4 — Mini](https://zod.dev/v4?id=an-extensible-foundation-zodv4core)

---

## Recommendation

- **Short term:** Treat Zod as **optional**. If you are not shipping schemas, removing `zod` from `dependencies` (and from `manualChunks` if absent) reduces noise; or document “reserved for forms.”

- **When you add Zod:** Prefer **v4 + current resolvers**, adopt **`error`** instead of `errorMap`, and re-read `z.coerce` / `z.record` / `.safe()` behavior for your exact schemas.

---

*Audit used Context7 (`/websites/zod_dev_v4`, `/colinhacks/zod`) and static analysis. No source files were modified.*
