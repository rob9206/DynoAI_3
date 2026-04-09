import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach } from "vitest";
import type { ReactNode } from "react";

vi.mock("@/api/v3Session", () => ({
  createSession: vi.fn().mockResolvedValue({
    session_id: "sess-001",
    engine_family: "m8_114",
    estimated_pulls: 6,
    template_match: null,
    seed_source: "default",
    calibration_seed: null,
    seed_warning: "",
    initial_plan: [],
  }),
  getSession: vi.fn().mockResolvedValue({
    session_id: "sess-001",
    state: "in_progress",
    pull_count: 3,
  }),
  ingestPull: vi.fn().mockResolvedValue({ accepted: true }),
  importBaseVE: vi.fn().mockResolvedValue({ ok: true }),
  importCorrections: vi.fn().mockResolvedValue({ ok: true }),
  finalizeSession: vi.fn().mockResolvedValue({ final_ve: [[80]] }),
  suggestNextPull: vi.fn().mockResolvedValue({
    rpm: 2500,
    map_kpa: 70,
    reason: "coverage gap",
  }),
  checkConvergence: vi.fn().mockResolvedValue({
    converged: false,
    confidence: 0.6,
  }),
  operatorVeto: vi.fn().mockResolvedValue({ ok: true }),
  getUncertaintyMap: vi.fn().mockResolvedValue({ zones: [] }),
  getOverlayStatus: vi.fn().mockResolvedValue({ active: false }),
  activateKillSwitch: vi.fn().mockResolvedValue({ killed: true }),
  listTemplates: vi.fn().mockResolvedValue({ templates: [] }),
  simulatePull: vi.fn().mockResolvedValue({ simulated: true }),
  autoSimulate: vi.fn().mockResolvedValue({ pulls: 5 }),
  materializeRun: vi.fn().mockResolvedValue({ run_id: "run-abc" }),
}));

import { useV3Session } from "../useV3Session";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useV3Session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns idle phase when no sessionId", () => {
    const { result } = renderHook(() => useV3Session(), {
      wrapper: createWrapper(),
    });

    expect(result.current.sessionPhase).toBe("idle");
    expect(result.current.isConverged).toBe(false);
    expect(result.current.pullCount).toBe(0);
  });

  it("fetches session status when sessionId provided", async () => {
    const { getSession } = await import("@/api/v3Session");
    const { result } = renderHook(() => useV3Session("sess-001"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(getSession).toHaveBeenCalledWith("sess-001");
    });

    await waitFor(() => {
      expect(result.current.sessionStatus).toBeDefined();
      expect(result.current.pullCount).toBe(3);
      expect(result.current.sessionPhase).toBe("tuning");
    });
  });

  it("exposes all action functions", () => {
    const { result } = renderHook(() => useV3Session("sess-001"), {
      wrapper: createWrapper(),
    });

    expect(typeof result.current.startSession).toBe("function");
    expect(typeof result.current.submitPull).toBe("function");
    expect(typeof result.current.importVE).toBe("function");
    expect(typeof result.current.finalize).toBe("function");
    expect(typeof result.current.veto).toBe("function");
    expect(typeof result.current.killSwitch).toBe("function");
    expect(typeof result.current.simulate).toBe("function");
    expect(typeof result.current.runAutoSimulate).toBe("function");
    expect(typeof result.current.importSessionCorrections).toBe("function");
    expect(typeof result.current.materializeLatestRun).toBe("function");
    expect(typeof result.current.refreshSessionData).toBe("function");
  });

  it("returns loading states", () => {
    const { result } = renderHook(() => useV3Session("sess-001"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isCreating).toBe(false);
    expect(result.current.isIngesting).toBe(false);
    expect(result.current.isFinalizing).toBe(false);
    expect(result.current.isSimulating).toBe(false);
  });
});
