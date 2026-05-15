# React Router v7 Audit

**Audit date:** 2026-05-07  
**Installed version:** `react-router-dom@^7.12.0` (resolved from `frontend/package.json`)  
**Auditor:** Context7 + static analysis (no runtime, no build)  
**Scope:** `frontend/src/App.tsx` route tree, all 16 page components, `Layout.tsx`, and high-use nav components.

---

## Summary

The DynoAI frontend operates in **React Router v7 Declarative mode** (the v7 successor to what was called "library mode" in migration docs). Every pattern in the current codebase — `BrowserRouter`, `Routes`, `Route`, `Navigate`, `useNavigate`, `useParams`, `useLocation`, `Link` — is **fully supported and unchanged in v7**. There are **zero breaking changes** that require a code edit before or after upgrading within the v7 line.

Headline results:

| Category     | Count | Detail |
|---|---|---|
| OK           | 13    | All core routing patterns work as-is |
| Drifted      | 1     | Import source (`react-router-dom` vs `react-router`) |
| Risky        | 0     | No silent behavior changes found |
| Could-adopt  | 3     | `errorElement`, route `lazy` property, `createBrowserRouter` + loaders |

The single drifted finding is cosmetic and does not affect runtime behavior.

---

## Method

**Context7 library ID:** `/remix-run/react-router`  
**Benchmark score:** 84.07 (High reputation)  
**Versions indexed:** 7.6.2, 7.5.3, 7.9.4 (latest stable branch)

Three doc queries were issued:

1. Library mode vs. framework mode; `BrowserRouter` support; v6-to-v7 upgrade path; `Routes`/`Route` API.
2. `createBrowserRouter` + `RouterProvider`; `loader`/`action` in library mode; `useLoaderData`/`useActionData`; `errorElement`; route `lazy` property.
3. `useParams`, `useNavigate`, `useLocation`, `useSearchParams`, `Link`, `NavLink`, `Navigate` hook/component API changes in v7.

**Why Context7 was necessary here:** React Router v7 is the merger of React Router v6 and Remix. The two modes ("Declarative" and "Framework"), the new canonical import path, and the status of `BrowserRouter` in v7 are all questions where LLM training data from 2024 or earlier is unreliable — the merger happened post-cutoff for most models. Without live docs, an agent would likely guess that `BrowserRouter` was deprecated or that the app needed `RouterProvider`, both of which are wrong.

---

## Findings

### OK — No changes needed

**1. `BrowserRouter` as router root (`App.tsx:1`, `491`)**  
v7 docs name this "Declarative mode" and document it as the first-class path for apps that do not need data loading. The API is identical to v6.

```
import { BrowserRouter as Router, ... } from 'react-router-dom';
// <Router> wraps the full app — valid, supported, documented.
```

**2. `<Routes>` / `<Route element={...}>` declarative JSX (`App.tsx:494–519`)**  
The `element` prop is unchanged. Nested `<Route>` composition is unchanged. `<Routes>` is the correct matching component in Declarative mode.

**3. `<Navigate to="..." replace />` redirects (`App.tsx:74`, `495`, `519`)**  
API unchanged. Both `replace` and the `to` string/object forms work identically.

**4. `React.lazy()` + `<Suspense>` for 16 code-split pages (`App.tsx:22–37`, `493`)**  
`React.lazy()` combined with `<Suspense fallback={...}>` continues to work as it did in v6. There is no v7 regression here.

**5. `useParams<{...}>()` typed generic form (`Results.tsx:18`, `RunDetailPage.tsx:57`, `TimeMachinePage.tsx:26`, `TuningSessionPage.tsx:53`)**  
Signature unchanged in v7. The TypeScript generic override is still the correct pattern for Declarative mode. (Framework mode gains automatic type inference from route files, but that is not applicable here.)

**6. `useNavigate()` including `navigate(-1)` and `{ replace: true }` options (`Dashboard.tsx:18`, `History.tsx:16`, `Results.tsx:19`, `RunDetailPage.tsx:58`, `TimeMachinePage.tsx:27`, `RunDetailPage.tsx:129`)**  
`useNavigate` is unchanged. `navigate(-1)` (history back), `navigate(path, { replace: true })`, and `navigate({ pathname, search })` object form are all valid.

**7. `useLocation()` (`Layout.tsx:12`, `JetDriveAutoTunePage.tsx:110`)**  
Unchanged. `location.pathname` access pattern in `Layout.tsx:30` is valid.

**8. `<Link to="...">` (`Layout.tsx`, `WorkspacePage.tsx:9`, `TuningSessionPage.tsx:11`, `JetDriveAutoTunePage.tsx:18`, `Dashboard.tsx:2`)**  
API unchanged. No prop renames, no breaking option changes.

**9. `PortalGuard` render-prop auth guard (`App.tsx:45–78`)**  
This is a custom React component, not a routing primitive. The `<Navigate to="/jetdrive" replace />` it renders on auth failure is correct v7.

**10. `useJetstreamSync` `onSuccess` / `onError` on `useMutation` (`JetstreamPage.tsx:18–29`)**  
This is TanStack Query, not React Router — included here for completeness because it's in the route tree. Already audited in the TanStack Query v5 audit; mutation callbacks are valid.

**11. `WorkspacePage` / `TuningSessionPage` — React Query hooks, no `useEffect` data fetch.**  
`useVehicles`, `useSessions`, `useVehicle`, `useSession`, `useIterations`, `useSessionStatus` are all React Query hooks (`useQuery` / `useMutation`). These do not conflict with v7 routing.

**12. Absence of `NavLink` — no active styling mismatch risk.**  
`Layout.tsx` implements active detection manually via `location.pathname === path` rather than `NavLink`. This is valid; there is no forced `NavLink` adoption in v7.

**13. Absence of `<Outlet>` — flat route tree is fine.**  
The route tree has no nested child routes requiring `<Outlet>`. The `Layout` wrapper is injected by `App.tsx` outside `<Routes>`, which is the standard pattern for a persistent shell layout in Declarative mode.

---

### Drifted — Works today, diverges from v7 idiomatic style

**D1. Import source: `from 'react-router-dom'` instead of `from 'react-router'`**

| Files affected (11) |
|---|
| `frontend/src/App.tsx:1` |
| `frontend/src/pages/Results.tsx:2` |
| `frontend/src/pages/TimeMachinePage.tsx:8` |
| `frontend/src/pages/Dashboard.tsx:2` |
| `frontend/src/pages/RunDetailPage.tsx:6` |
| `frontend/src/pages/JetDriveAutoTunePage.tsx:18` |
| `frontend/src/pages/TuningSessionPage.tsx:11` |
| `frontend/src/components/common/Layout.tsx:2` |
| `frontend/src/pages/History.tsx:2` |
| `frontend/src/pages/WorkspacePage.tsx:9` |
| `frontend/src/components/jetstream/JetstreamRunCard.tsx` |

React Router v7 merged `react-router-dom` into `react-router`. The `react-router-dom` package is retained as a re-export shim for backwards compatibility, so **all 11 files compile and run correctly today**. Every v7 documentation example uses `from 'react-router'`.

**Severity:** Cosmetic. No runtime impact. Safe to migrate in a dedicated cleanup commit using a simple global find-replace: `'react-router-dom'` → `'react-router'`.

**Risk if not fixed:** If the shim is ever dropped in a future v8 release, all 11 imports break simultaneously. Low probability for a major version, but the divergence from docs means copy-pasted v7 examples will use the new import and the codebase will have two conventions.

---

### Risky — None found

No patterns were identified that compile correctly but behave differently in v7 compared to v6. Specific items checked and cleared:

- `navigate(-1)` — valid and unchanged
- `useNavigate` with `flushSync` — not used anywhere
- Scroll restoration — not configured; React Router v7 default scroll restoration behavior is the same as v6 for Declarative mode
- `setSearchParams` — not used anywhere
- `useParams` with undefined handling — all callsites use the TypeScript generic to narrow the type; the return shape is unchanged

---

### Could-adopt — v7-native features the app could opt into

**C1. Route `errorElement` + `useRouteError` for per-route error boundaries**

Zero `errorElement` or `useRouteError` usage was found in any page or route config. When a page throws during render or during an async operation, the error propagates to the nearest React error boundary — but there are none configured at the route level either. Uncaught errors currently reach the browser's default error screen.

In Declarative mode, React Router v7 does **not** support `errorElement` on `<Route>` — that feature is data router (`createBrowserRouter`) only. However, the app can add standard React `<ErrorBoundary>` wrappers around `<Suspense>` in `App.tsx` to catch lazy-load and render errors per-route without touching the router config:

```tsx
// In App.tsx — wraps the existing Suspense fallback
<ErrorBoundary fallback={<ErrorPage />}>
  <Suspense fallback={<LoadingSpinner />}>
    <Routes>...</Routes>
  </Suspense>
</ErrorBoundary>
```

To get route-level `errorElement` (which renders the error component at the route's position without blowing away the full page), Option B (data router migration) is required.

**C2. Route `lazy` property instead of `React.lazy()` + `<Suspense>`**

All 16 pages are code-split via `React.lazy()`. v7's data router introduces a `lazy` property on route objects that integrates code-splitting directly into the route config and enables loader execution to begin before the component bundle downloads:

```tsx
// In createBrowserRouter config:
{
  path: "/results/:runId",
  lazy: () => import("./pages/Results"),   // loader runs in parallel with bundle fetch
}
```

This requires Option B (data router migration). With `BrowserRouter`, `React.lazy()` + `<Suspense>` is the correct approach and there is no v7-native equivalent available.

**C3. `createBrowserRouter` + `RouterProvider` + `loader` for data-loading routes**

Three routes currently use `useEffect` + raw `fetch` / API calls inside the component body for initial data load. These are the strongest candidates for v7 `loader` migration if the team ever moves to the data router:

See the [Loader Candidate Table](#loader-candidate-table) below for full detail.

---

## Loader Candidate Table

All 18 route entries in `App.tsx:494–519` are assessed below. "Fetch pattern" describes how the route's initial data reaches the component.

| Route | Page Component | Fetch pattern | Loader candidacy | Effort |
|---|---|---|---|---|
| `/` | Navigate redirect | None | N/A | — |
| `/jetdrive` | `JetDriveAutoTunePage` | `useQuery` (polling, live hardware) | ❌ Not suitable — live telemetry polling cannot be a one-shot loader | — |
| `/jetstream` | `JetstreamPage` | `useMutation` (manual sync button) | ❌ No mount fetch | — |
| `/runs/:runId` | `RunDetailPage` | `useJetstreamRun`, `useJetstreamProgress`, `useVEData` (React Query) | ⚠️ Moderate — could pre-fetch initial run status in loader, but RQ handles staleness well | Medium |
| `/dashboard` | `Dashboard` | `useEffect` + `healthCheck()` (raw `fetch`) | ⚠️ Moderate — health check is one-shot; loader would pre-fetch before render | Low |
| `/workspace` | `WorkspacePage` | `useVehicles`, `useSessions` (React Query) | ⚠️ Moderate — could prime query cache in loader | Medium |
| `/workspace/:vehicleId/sessions/:sessionId` | `TuningSessionPage` | `useVehicle`, `useSession`, `useIterations`, `useSessionStatus` (React Query) | ⚠️ Moderate — params available; loader could fetch vehicle + session before render | Medium |
| `/results/:runId` | `Results` | `useEffect` + `loadResults()` (raw `useState` / `fetch`) | ✅ **Strong** — params available, no React Query, plain useEffect waterfall | Low-Medium |
| `/time-machine/:runId` | `TimeMachinePage` | `useTimeline` (`useInfiniteQuery`) | ⚠️ Moderate — pagination makes loader awkward; initial page could be a loader | High |
| `/history` | `History` | `useEffect` + `loadHistory()` (raw `useState` / `fetch`) | ✅ **Strong** — no params, simple list fetch, no React Query | Low |
| `/wizards` | `TuningWizardsPage` | `useQuery` + `useMutation` | ⚠️ Moderate — could pre-fetch wizard config in loader | Medium |
| `/training` | `OperatorTrainingPage` | None (simulator) | ❌ No data fetch | — |
| `/engine-analyzer` | `EngineAnalyzerPage` | `useEffect` + `fetchStats()` + `fetchComponents()` (raw `fetch`) | ✅ **Strong** — multiple useEffect data calls; loader would clean up waterfall and debounce-search pattern | Medium |
| `/ve-heatmap-demo` | `VEHeatmapDemo` | None (static sample data) | ❌ No data fetch | — |
| `/autotune-demo` | `AutoTuneDemo` | None (local simulation) | ❌ No data fetch | — |
| `/portal/tech` | `TechView` (via `PortalGuard`) | `useEffect` + raw fetch inside `AllRunsTable` | ⚠️ Has auth guard — loader would need token from localStorage; awkward pattern | High |
| `/portal/admin` | `AdminView` (via `PortalGuard`) | `useEffect` + raw fetch for users + runs | ⚠️ Has auth guard — same complexity as `/portal/tech` | High |
| `*` | Navigate redirect | None | N/A | — |

**Strong loader candidates (3):**
- `/results/:runId` — `Results.tsx` — replaces a `useEffect` waterfall calling 4 sequential API endpoints with a single parallel `loader` function.
- `/history` — `History.tsx` — simplest possible migration; one list fetch, no params.
- `/engine-analyzer` — `EngineAnalyzerPage.tsx` — replaces `fetchStats()` in `useEffect` with a loader; the search/filter `useEffect` calls stay in the component (they respond to user input, not route entry).

---

## Recommended Paths

### Option A — No-op: Declarative mode sign-off

**Recommendation: Sign off as-is for the current release.**

React Router v7 Declarative mode fully supports every pattern the app uses. There are no breaking changes that require code edits. The one drifted finding (import path) is cosmetic and can be deferred to a cleanup sprint.

**When to choose Option A:**
- Active F1 autotune work is in progress — the routing setup has zero coupling to the autotune/VE correction pipeline and changing it adds noise.
- The `react-router-dom` shim provides full backwards compatibility within the v7 line.
- No user-visible bugs are traced to routing.

**Cleanup commit (optional, low risk):**
```bash
# Rename all react-router-dom imports to react-router
# Replace in: App.tsx, Results.tsx, TimeMachinePage.tsx, Dashboard.tsx,
#             RunDetailPage.tsx, JetDriveAutoTunePage.tsx, TuningSessionPage.tsx,
#             Layout.tsx, History.tsx, WorkspacePage.tsx, JetstreamRunCard.tsx
```

---

### Option B — Progressive loader adoption: migrate to `createBrowserRouter`

**Recommendation: Consider after F1 autotune work completes, targeted at the 3 strong candidates.**

This requires converting `App.tsx` from `<BrowserRouter>` + `<Routes>` to `createBrowserRouter` + `<RouterProvider>`. All existing `<Route element={...}>` entries remain unchanged — only the 3 strong candidates gain a `loader` function.

**Prerequisites:**
1. Replace `<BrowserRouter>` / `<Routes>` / `<Route>` in `App.tsx` with a `createBrowserRouter([...])` config object + `<RouterProvider router={router} />`.
2. The `QueryClientProvider` + `ThemeProvider` + `Toaster` shell stays outside `RouterProvider`.
3. Add `loader` to `/results/:runId`, `/history`, and `/engine-analyzer`.
4. Replace `useEffect` + manual `useState` fetch logic in `Results.tsx`, `History.tsx`, `EngineAnalyzerPage.tsx` with `useLoaderData()`.
5. Add `errorElement` to those 3 routes for route-level error handling.
6. Replace `React.lazy()` on those 3 pages with the route `lazy` property for parallel bundle + loader fetch.

**Estimated scope:** 5–7 files changed, ~200 lines modified, no backend changes.

**What stays the same:**
- All other 13 routes continue using `element={<Component />}` — no change required.
- All React Query hooks in other pages are unaffected.
- `useNavigate`, `useParams`, `useLocation`, `Link` usage in all pages is unchanged.
- `PortalGuard` auth pattern still works (it renders `<Navigate>` imperatively, which is valid in data router mode).

**When to choose Option B:**
- The team wants `errorElement`-level error isolation per route (show a per-route error UI without unmounting the nav bar).
- The waterfall data fetch in `Results.tsx` is causing a visible loading gap (4 sequential fetches).
- The project is ready to standardize on `from 'react-router'` imports at the same time.

---

## Decision Aids

### Does Option B block the F1 autotune feature?

No. The F1 autotune work lives entirely in `JetDriveAutoTunePage.tsx`, `tools/autotune/`, and the backend pipeline. The routing layer is a wrapper — no autotune logic touches `BrowserRouter`, `Routes`, or `Route`. Option A and Option B are both safe to run in parallel with the F1 work.

### Is the `react-router-dom` shim a liability?

Low risk within the v7 line. The shim is maintained by the React Router team as a deliberate migration aid. It is not expected to disappear before v8. There is no performance penalty — it re-exports the same functions. The only risk is the import convention diverging from docs and new code pasted from examples using `from 'react-router'`.

### Is there a v7 framework mode consideration?

Framework mode (Remix-style SSR with file-based routing, `vite-plugin-react-router`, and route convention files) would require rewriting the entire frontend structure. It is not applicable to this SPA and should not be considered.

### Priority order if starting Option B

1. `/history` (History.tsx) — lowest effort, pure useEffect + fetch, no params, clear win.
2. `/results/:runId` (Results.tsx) — highest user impact, eliminates 4-step sequential waterfall.
3. `/engine-analyzer` (EngineAnalyzerPage.tsx) — improves initial stats fetch; search stays in component.

---

## Files Covered

| File | Lines read | Notes |
|---|---|---|
| `frontend/src/App.tsx` | 531 | Full file — route tree, QueryClient, PortalGuard |
| `frontend/src/components/common/Layout.tsx` | 212 | Full file — Link, useLocation, isActive |
| `frontend/src/pages/JetDriveAutoTunePage.tsx` | ~3600 | First 60 lines + grep for routing + useQuery calls |
| `frontend/src/pages/Dashboard.tsx` | ~425 | First 60 lines + useEffect pattern |
| `frontend/src/pages/Results.tsx` | ~471 | First 60 lines + full useEffect waterfall |
| `frontend/src/pages/History.tsx` | ~130 | Full file |
| `frontend/src/pages/RunDetailPage.tsx` | ~724 | First 60 lines + React Query hooks |
| `frontend/src/pages/TimeMachinePage.tsx` | ~499 | First 60 lines + useTimeline (infinite query) |
| `frontend/src/pages/WorkspacePage.tsx` | ~263 | First 60 lines + React Query hooks |
| `frontend/src/pages/TuningSessionPage.tsx` | ~500 | First 60 lines + React Query hooks |
| `frontend/src/pages/JetstreamPage.tsx` | ~98 | Full file — useMutation only |
| `frontend/src/pages/TuningWizardsPage.tsx` | ~732 | First 30 lines + useQuery/useMutation |
| `frontend/src/pages/VEHeatmapDemo.tsx` | ~164 | Full file — no data fetch |
| `frontend/src/pages/AutoTuneDemo.tsx` | ~908 | First 30 lines — no data fetch |
| `frontend/src/pages/EngineAnalyzerPage.tsx` | ~812 | First 30 lines + useEffect scan (lines 245–260) |
| `frontend/src/pages/OperatorTrainingPage.tsx` | ~951 | First 30 lines — simulator, no data fetch |
| `frontend/src/pages/AdminView.tsx` | ~266 | First 30 lines + useEffect fetch |
| `frontend/src/pages/TechView.tsx` | 19 | Full file — delegates to AllRunsTable |

---

*Audit performed with Context7 library ID `/remix-run/react-router` (versions 7.6.2, 7.5.3, 7.9.4). No source files were modified.*
