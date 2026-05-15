# TanStack Query v5 Compliance Audit

**Date:** 2026-05-07  
**Auditor:** Context7-assisted analysis (`/tanstack/query`, benchmark 89.15, High reputation, version `v5_84_1`)  
**Scope:** `frontend/src/hooks/**`, `frontend/src/components/**` (17 files using Query), `frontend/src/App.tsx`, `frontend/src/hooks/__tests__/useV3Session.test.tsx`

---

## Summary

The DynoAI frontend installs **`@tanstack/react-query@^5.83.1`** ([frontend/package.json](frontend/package.json):49) and is largely v5-compliant on every breaking change from v4. Zero `useQuery` callbacks (`onSuccess`/`onError`/`onSettled`) exist on query definitions. Zero `cacheTime` usages. Zero `keepPreviousData`. The v5-form `refetchInterval: (query) => ...` callback is used correctly. `useInfiniteQuery` carries the required v5 `initialPageParam`. All `useMutation` callbacks are correctly retained (they were not removed in v5). Mutation loading states uniformly use the v5-renamed `isPending` rather than the deprecated `isLoading`.

Two items need attention:

1. **Test fixture missing `gcTime: Infinity`** -- minor, prevents potential Vitest open-handle warnings ([testing.md](https://github.com/tanstack/query/blob/main/docs/framework/react/guides/testing.md)).
2. **`isLoading` semantics shift for disabled queries** -- `isLoading` in v5 is `isPending && isFetching`, so disabled queries (`enabled: false`) now return `isLoading: false` where v4 returned `true`. Six hook files expose `isLoading*` fields derived from conditional-enabled queries; this is a silent behavioral change worth knowing.

Four v5-only patterns the codebase could opt into are documented below as adoption candidates.

---

## Method

Documentation sourced via **Context7** on 2026-05-07:

| Topic | Query | Source URL returned |
|---|---|---|
| v4->v5 breaking changes: callbacks removed, `cacheTime`→`gcTime`, `keepPreviousData`→`placeholderData`, `isLoading`/`isPending` rename | "v4 to v5 migration breaking changes onSuccess onError onSettled removed from useQuery cacheTime renamed gcTime keepPreviousData placeholderData isLoading isPending semantics" | `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md` |
| `refetchInterval` v5 callback shape, `useSuspenseQuery`, `useMutation` callbacks retained | "refetchInterval function callback query object v5 useSuspenseQuery suspense API combine option select notifyOnChangeProps useMutation callbacks retained mutationKey" | `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md` |
| Testing `QueryClient` setup: `gcTime: Infinity`, `retry: false` | "testing React Query QueryClient setup gcTime Infinity retry false wrapper renderHook waitFor v5 best practices" | `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/testing.md` |

---

## Findings

### OK -- v5-correct patterns

#### OK-1: No `useQuery` callbacks -- the main v5 break

**Files:** All 24 hook files and 17 component files. Zero matches for `useQuery({ ..., onSuccess/onError/onSettled })`.

**Context7 citation (the breaking change this confirms avoided):**

> "The `onSuccess`, `onError`, and `onSettled` callbacks have been removed from Queries in v5, though they remain available for Mutations."  
> Source: `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md`

All `onSuccess`/`onError` callbacks in the codebase are exclusively on `useMutation` calls, which is correct.

---

#### OK-2: `refetchInterval` uses v5 `query` object form

**File:line:** [`frontend/src/hooks/useV3Session.ts:67-71`](frontend/src/hooks/useV3Session.ts)

```ts
refetchInterval: (query) => {
  const state = query.state.data?.state;
  return state === "in_progress" || state === "ready" ? 2_000 : false;
},
```

**Context7 citation:**

> "In TanStack Query v5, the `refetchInterval` callback function now only receives the `query` object as an argument ... To access query data within the callback, use `query.state.data`."  
> Source: `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md`

```tsx
refetchInterval: number | false | ((query: Query) => number | false | undefined)
```

The hook reads `query.state.data?.state` -- exactly the v5 access pattern. In v4 this callback received `data` directly; the codebase never used the v4 form.

---

#### OK-3: `useInfiniteQuery` with required `initialPageParam`

**File:line:** [`frontend/src/hooks/useTimeline.ts:94-105`](frontend/src/hooks/useTimeline.ts)

```ts
useInfiniteQuery({
  queryKey: ['timeline', runId],
  queryFn: ({ pageParam }) => getTimeline(runId, { limit: 50, offset: pageParam as number }),
  initialPageParam: 0,   // <-- required in v5
  getNextPageParam: (lastPage) => { ... },
  ...
})
```

`initialPageParam` is a v5 requirement that did not exist in v4. The field is present and set correctly to `0`.

---

#### OK-4: All mutation loading states use `isPending` (not deprecated `isLoading`)

**Files:** [`useV3Session.ts:317-324`](frontend/src/hooks/useV3Session.ts), [`useApplyRollback.ts:123-124`](frontend/src/hooks/useApplyRollback.ts), [`useCalibrationLibrary.ts:90-92`](frontend/src/hooks/useCalibrationLibrary.ts)

```ts
// useV3Session.ts:317-324
isCreating:              createMutation.isPending,
isIngesting:             ingestMutation.isPending,
isImportingVE:           importVEMutation.isPending,
isFinalizing:            finalizeMutation.isPending,
isSimulating:            simulateMutation.isPending,
isMaterializingRun:      materializeRunMutation.isPending,
```

**Context7 citation:**

> "The `loading` status has been renamed to `pending`, and the derived `isLoading` flag has been renamed to `isPending`. This change applies to both queries and mutations."  
> Source: `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md`

Every mutation uniformly uses `.isPending`, never `.isLoading`.

---

#### OK-5: `invalidateQueries` uses v5 object-form query key

**Files:** All mutation `onSuccess` handlers across `useV3Session.ts`, `useTuningWorkspace.ts`, `useCalibrationLibrary.ts`, `useJetstream.ts`

```ts
// Correct v5 form:
void queryClient.invalidateQueries({ queryKey: ["v3", "session", sessionId] });
```

In v4, both `invalidateQueries("key")` (string) and `invalidateQueries({ queryKey: [...] })` (object) were accepted. v5 requires the object form. The codebase uniformly uses the object form.

---

#### OK-6: Query key factory pattern

**File:** [`frontend/src/hooks/useNextGenAnalysis.ts:19-24`](frontend/src/hooks/useNextGenAnalysis.ts)

```ts
export const nextGenKeys = {
  all:        ['nextgen'] as const,
  analysis:   (runId: string) => [...nextGenKeys.all, 'analysis', runId] as const,
  surfaces:   (runId: string) => [...nextGenKeys.all, 'surfaces', runId] as const,
  hypotheses: (runId: string) => [...nextGenKeys.all, 'hypotheses', runId] as const,
};
```

This is the recommended TanStack Query pattern for typed, hierarchical key management. It prevents invalidation scope errors and provides IntelliSense on keys.

---

#### OK-7: Typed explicit generic on `useMutation`

**Files:** [`useCalibrationLibrary.ts:49`](frontend/src/hooks/useCalibrationLibrary.ts), [`useTuningWorkspace.ts:184`](frontend/src/hooks/useTuningWorkspace.ts)

```ts
const ingestMutation = useMutation<CalibrationLibraryIngestResponse, Error, IngestArgs>({
```

Explicit `<TData, TError, TVariables>` typing on mutations is a v5 best practice. Not all mutations have explicit generics, but the ones where type safety matters most do.

---

### DRIFTED -- Behavioral change, works but different from v4

#### Drift-1: `isLoading` semantics for disabled queries changed in v5

**Files:lines:** [`useV3Session.ts:60,77,90,101`](frontend/src/hooks/useV3Session.ts), [`useCalibrationLibrary.ts:88-89`](frontend/src/hooks/useCalibrationLibrary.ts), [`useNextGenAnalysis.ts:103`](frontend/src/hooks/useNextGenAnalysis.ts)

**The change:**

**Context7 citation:**

> "Additionally, a new derived `isLoading` flag has been added to queries, implemented as `isPending && isFetching`. The previous `isInitialLoading` flag is now deprecated and will be removed in the next major version, as it now represents the same concept as the new `isLoading`."  
> Source: `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md`

In v4: `isLoading` = `status === 'loading'`. A query with `enabled: false` had `status === 'loading'` → `isLoading: true` until it ever fetched.  
In v5: `isLoading` = `isPending && isFetching`. A query with `enabled: false` has `isPending: true` but `isFetching: false` → **`isLoading: false`**.

Affected hooks:

```ts
// useV3Session.ts -- four queries gated on !!sessionId
const { isLoading: isLoadingStatus }     = useQuery({ enabled: !!sessionId, ... });
const { isLoading: isLoadingConvergence } = useQuery({ enabled: !!sessionId && ..., ... });
const { isLoading: isLoadingUncertainty } = useQuery({ enabled: !!sessionId && ..., ... });
const { isLoading: isLoadingNextPull }    = useQuery({ enabled: !!sessionId && ..., ... });
```

When `sessionId` is `undefined`, all four now return `isLoading: false` in v5. In v4 they returned `true`. Any consumer that used these flags as a proxy for "no session yet, keep showing spinner" would silently stop seeing a spinner in v5.

**Practical severity:** Low if consumers already gate on `sessionId` being defined before showing results. High if they relied on `isLoadingStatus === true` as the "nothing to show yet" sentinel. Recommend adding explicit `isPending` destructuring alongside `isLoading` for the disabled-case or switching to:

```ts
const { isPending, isFetching, isLoading } = useQuery({ enabled: !!sessionId, ... });
// isPending: true when no data; isLoading: true only when actively fetching
```

---

### RISKY -- None found

Zero callsites matched the high-risk v4-to-v5 patterns:

| Pattern | Expected if upgraded from v4 | Found in codebase |
|---|---|---|
| `useQuery({ onSuccess, ... })` | High risk (removed in v5) | 0 occurrences |
| `cacheTime: N` | Renamed to `gcTime` | 0 occurrences |
| `keepPreviousData: true` | Replaced by `placeholderData: keepPreviousData` | 0 occurrences |
| `useMutation().isLoading` | Renamed to `isPending` | 0 occurrences |
| `useQuery(['key'], fn)` | Array-shorthand removed in v5 | 0 occurrences |
| `isInitialLoading` | Deprecated in v5 | 0 occurrences |

---

### COULD-ADOPT -- v5-only patterns not yet used

#### Adopt-1: `useSuspenseQuery` for data-required routes

**Context7 citation:**

> "This code snippet demonstrates how to use the new `useSuspenseQuery` hook in TanStack Query v5. This hook enables stable suspense for data fetching, guaranteeing that the `data` variable is always defined at the type level, eliminating the need for `undefined` checks."  
> Source: `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md`

```js
const { data: post } = useSuspenseQuery({
  // ^? const post: Post  -- never undefined at the type level
  queryKey: ['post', postId],
  queryFn: () => fetchPost(postId),
})
```

**App.tsx already wraps routes in `<Suspense>` ([App.tsx:493](frontend/src/App.tsx)).** This means all routes can adopt `useSuspenseQuery` without adding a new Suspense boundary. The benefit: `data` becomes non-nullable in TypeScript, eliminating `data?.field` optional chaining throughout the UI.

**Best candidates:**
- [`useVEData.ts`](frontend/src/hooks/useVEData.ts) -- single-query hook; every consumer already expects data to be defined when they render
- [`useCalibrationLibrary.ts`](frontend/src/hooks/useCalibrationLibrary.ts) -- two queries (`listQuery`, `statsQuery`) always needed together before the UI renders
- `useJetstreamConfig` in [`useJetstream.ts:36`](frontend/src/hooks/useJetstream.ts) -- config must be present before the config form renders

**Trade-off:** Suspense-based components cannot use `enabled` (conditional queries and `useSuspenseQuery` are incompatible). Hooks that have `enabled: !!someId` (most of `useV3Session.ts`) cannot be migrated directly.

---

#### Adopt-2: Query key factory across all hooks (extend the `nextGenKeys` pattern)

Only [`useNextGenAnalysis.ts`](frontend/src/hooks/useNextGenAnalysis.ts) uses a query key factory. The remaining hooks use inline arrays scattered across `useQuery` and `invalidateQueries` calls. A key factory provides:
- Single source of truth for key shape
- Type-checked keys in tests
- Hierarchical invalidation (`queryKey: nextGenKeys.all` invalidates all nextgen queries)

**Candidate:** Extract a `workspaceKeys` factory from [`useTuningWorkspace.ts`](frontend/src/hooks/useTuningWorkspace.ts), which has the most complex key structure (`['workspace', 'iterations', vehicleId, sessionId]` etc.).

---

#### Adopt-3: `gcTime: Infinity` in the test QueryClient

**File:line:** [`useV3Session.test.tsx:48-50`](frontend/src/hooks/__tests__/useV3Session.test.tsx) and [`useCalibrationLibrary.test.tsx`](frontend/src/hooks/__tests__/useCalibrationLibrary.test.tsx)

**Context7 citation:**

> "Configure gcTime to Infinity in QueryClient when using Jest to prevent the 'Jest did not exit one second after the test run completed' error. This mimics server-side behavior and is only necessary when explicitly setting gcTime."  
> Source: `https://github.com/tanstack/query/blob/main/docs/framework/react/guides/testing.md`

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: Infinity,
    },
  },
})
```

Current test fixture:

```ts
// useV3Session.test.tsx:48-50
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
  //                                           ^^ missing gcTime: Infinity
});
```

`retry: false` is correct per the docs. Adding `gcTime: Infinity` is a one-line change that prevents Vitest's "open handles" warning when tests run with garbage collection timers active.

---

#### Adopt-4: Convert `useIngestionHealth` and `useDiagnostics` from manual `useState`/`setInterval` to `useQuery`

**Files:** [`useIngestionHealth.ts`](frontend/src/hooks/useIngestionHealth.ts) (220 lines), [`useDiagnostics.ts`](frontend/src/hooks/useDiagnostics.ts) (100 lines)

Both hooks implement manual polling with `useState` + `useEffect` + `setInterval` (or `useCallback`). Neither uses TanStack Query at all. The equivalent `useQuery` implementation would be ~15 lines each with automatic deduplication, background refetch, error retries, staleTime control, and DevTools visibility.

**Sketch for `useDiagnostics`:**

```ts
// Current: ~100 lines of manual state + fetch + error handling
// Could be:
export function useDiagnostics({ runId, enabled = true }: UseDiagnosticsOptions) {
  return useQuery({
    queryKey: ['diagnostics', runId],
    queryFn: () => api.get<ApiDiagnosticsResponse>(`/api/results/${runId}`)
                      .then(r => transformApiResponse(r.data)),
    enabled: !!runId && enabled,
    staleTime: 30_000,
  });
}
```

**Note:** `useIngestionHealth` exposes `startPolling`/`stopPolling` controls. These would become `refetchInterval` with a dynamic enable/disable pattern, which is slightly more complex to port.

---

## QueryClient Root Setup Review

**File:lines:** [`frontend/src/App.tsx:478-485`](frontend/src/App.tsx)

```ts
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
```

**Assessment:**

| Setting | v5 status | Assessment |
|---|---|---|
| `refetchOnWindowFocus: false` | Valid v5 option | Correct. Appropriate for a dyno tool where the tab may not be in focus during a pull. |
| `retry: 1` | Valid v5 option | Correct. Single retry is reasonable. Per-query overrides (e.g., `useNextGenAnalysis.ts:49-55`) work correctly because per-query `retry` takes precedence over `defaultOptions`. |
| `gcTime` (not set) | Defaults to 5 min in v5 | Acceptable default for production. No change needed. |
| `staleTime` (not set) | Defaults to `0` in v5 | Each query sets its own `staleTime` (ranging from 1s to 30min). The lack of a global default is intentional. Acceptable. |

**Verdict:** The root `QueryClient` is a valid, well-reasoned v5 configuration. The only improvement worth considering is documenting the rationale in a comment, since `refetchOnWindowFocus: false` is a non-default that affects all queries globally.

---

## Test Fixture Review

**File:lines:** [`useV3Session.test.tsx:47-54`](frontend/src/hooks/__tests__/useV3Session.test.tsx)

```ts
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

**Assessment:**

| Item | v5 docs recommendation | Status |
|---|---|---|
| `retry: false` | "Configure QueryClient with `defaultOptions` to disable retries for all queries in tests. This prevents test timeouts when testing error scenarios." | **Present** ✓ |
| Fresh `QueryClient` per test | "The wrapper provides an isolated QueryClientProvider instance to ensure test isolation" | **Present** ✓ (created inside `createWrapper()` called per `renderHook`) |
| `gcTime: Infinity` | "Configure gcTime to Infinity when using Jest to prevent open-handle warnings" | **Missing** -- add to `defaultOptions.queries` |
| `await waitFor(...)` pattern | v5 docs use `waitFor` from `@testing-library/react` | **Present** ✓ (lines 77-85) |
| `beforeEach(vi.clearAllMocks)` | Good practice | **Present** ✓ (line 57) |

The only gap is `gcTime: Infinity`. Since these tests run under Vitest (not Jest), the open-handle behavior depends on Vitest's fake timer setup. The fix is low-risk and takes one line.

---

## Recommended Path

### Option A -- No-op: sign off as v5-compliant

**Rationale:** All breaking v5 changes are correctly handled. The codebase was written with v5 in mind (or was carefully upgraded). There are no production bugs attributable to v5 migration drift.

**Action:** Commit the audit report as a compliance record. Reference it in `AGENTS.md`.

---

### Option B -- Low-risk adoption (recommended)

Apply the four adoption items in ascending effort order. Each is self-contained and can be a single commit.

| Item | File(s) | Effort | Risk | v5 Doc Citation |
|---|---|---|---|---|
| B1: Add `gcTime: Infinity` to test `QueryClient` | `useV3Session.test.tsx`, `useCalibrationLibrary.test.tsx` | 2 min | None | [testing.md](https://github.com/tanstack/query/blob/main/docs/framework/react/guides/testing.md) |
| B2: Add `isPending` alongside `isLoading` in `useV3Session` disabled-query returns | `useV3Session.ts` | 15 min | None | [migrating-to-v5.md](https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md) |
| B3: Extract `workspaceKeys` factory in `useTuningWorkspace.ts` | `useTuningWorkspace.ts` | 30 min | Low | Pattern: `nextGenKeys` in `useNextGenAnalysis.ts` |
| B4: Migrate `useDiagnostics.ts` to `useQuery` | `useDiagnostics.ts` | 45 min | Low | [testing.md](https://github.com/tanstack/query/blob/main/docs/framework/react/guides/testing.md) |
| B5: Migrate `useVEData` and `useJetstreamConfig` to `useSuspenseQuery` | `useVEData.ts`, `useJetstream.ts` | 1 hr | Medium (requires Suspense boundary check) | [migrating-to-v5.md](https://github.com/tanstack/query/blob/main/docs/framework/react/guides/migrating-to-v5.md) |

**Recommended execution:** Do B1 and B2 immediately (zero risk, high documentation value). Schedule B3-B5 as a follow-up "Query housekeeping" story. Skip `useIngestionHealth` migration (B4 variant) until a decision is made on whether its manual `startPolling`/`stopPolling` API should be preserved.

---

## Appendix: Full Callsite Inventory

| Hook / Component | API used | v5 classification |
|---|---|---|
| `useV3Session.ts` | 6× `useQuery`, 9× `useMutation` | OK (callbacks on mutation only; `refetchInterval` v5 form; `isPending` on all mutations) |
| `useTuningWorkspace.ts` | 9× `useQuery`, 5× `useMutation` | OK (no callbacks on queries) |
| `useCalibrationLibrary.ts` | 2× `useQuery`, 3× `useMutation` | OK |
| `useTimeline.ts` | 1× `useInfiniteQuery`, 1× `useQuery` | OK (`initialPageParam: 0` present) |
| `useNextGenAnalysis.ts` | 1× `useQuery`, 1× `useMutation` | OK (key factory; typed mutation) |
| `useJetstream.ts` | 4× `useQuery`, 2× `useMutation` | OK |
| `useVEData.ts` | 1× `useQuery` | OK |
| `useApplyRollback.ts` | 2× `useMutation` | OK (`isPending` used; `onSuccess`/`onError` on mutations valid) |
| `usePowerOpportunities.ts` | 1× `useQuery` | OK |
| `useIngestionHealth.ts` | None (manual polling) | Could-adopt: `useQuery` + `refetchInterval` |
| `useDiagnostics.ts` | None (manual fetch) | Could-adopt: `useQuery` |
| `SessionReplayViewer.tsx` | 1× `useQuery` | OK (`retry: 1` per-query override valid) |
| Other jetdrive components | `useQuery`, `useMutation` via hooks | OK (all delegate to above hooks) |
| `App.tsx` | `QueryClient` setup | OK (see QueryClient review section) |
| `useV3Session.test.tsx` | Test `QueryClient` | Minor gap: `gcTime: Infinity` missing |
