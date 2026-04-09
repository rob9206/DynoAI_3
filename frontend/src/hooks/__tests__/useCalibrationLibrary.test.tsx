import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach } from "vitest";
import type { ReactNode } from "react";

vi.mock("@/api/calibrationLibrary", () => ({
  listCalibrationLibraryEntries: vi.fn().mockResolvedValue({
    total: 2,
    offset: 0,
    limit: 100,
    entries: [
      {
        calibration_id: "abc-123",
        engine_family: "twin_cam",
        displacement_ci: 103,
        config: { engine_family: "twin_cam", displacement_ci: 103 },
        path: "/lib/abc-123",
        source_identity: "source-abc",
      },
      {
        calibration_id: "def-456",
        engine_family: "m8",
        displacement_ci: 114,
        config: { engine_family: "m8", displacement_ci: 114 },
        path: "/lib/def-456",
        source_identity: "source-def",
      },
    ],
  }),
  getCalibrationLibraryStats: vi.fn().mockResolvedValue({
    total_entries: 2,
    by_family: { twin_cam: 1, m8: 1 },
  }),
  ingestCalibrationLibrary: vi.fn().mockResolvedValue({
    calibration_id: "new-789",
    engine_family: "twin_cam",
    displacement_ci: 103,
    source_pvv: "test.pvv",
    source_identity: "source-new",
    grid: { rpm_bins: [1000], map_bins: [30], rows: 1, cols: 1 },
    has_rear: false,
    afr_targets_count: 1,
    ingest_count: 1,
  }),
  blendCalibrationLibrary: vi.fn().mockResolvedValue({
    engine_family: "twin_cam",
    match_count: 1,
    min_similarity: 0.55,
    matches: [],
    ve_front: [[80]],
    afr_targets: { "30": 13.2 },
    rpm_bins: [1000],
    map_bins: [30],
    confidence_map: [[0.9]],
    source_matches: [],
  }),
  deleteCalibrationLibraryEntry: vi.fn().mockResolvedValue({
    deleted: true,
    calibration_id: "abc-123",
  }),
}));

import { useCalibrationLibrary } from "../useCalibrationLibrary";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useCalibrationLibrary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches list and stats on mount", async () => {
    const { result } = renderHook(() => useCalibrationLibrary(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.list).toBeDefined();
      expect(result.current.stats).toBeDefined();
    });

    expect(result.current.list?.total).toBe(2);
    expect(result.current.stats?.total_entries).toBe(2);
    expect(result.current.stats?.by_family.twin_cam).toBe(1);
  });

  it("filters by engine family when provided", async () => {
    const { listCalibrationLibraryEntries } = await import(
      "@/api/calibrationLibrary"
    );
    renderHook(() => useCalibrationLibrary("m8"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(listCalibrationLibraryEntries).toHaveBeenCalledWith(
        expect.objectContaining({ engine_family: "m8" })
      );
    });
  });

  it("returns loading states correctly", () => {
    const { result } = renderHook(() => useCalibrationLibrary(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoadingList).toBe(true);
    expect(result.current.isIngesting).toBe(false);
    expect(result.current.isBlending).toBe(false);
    expect(result.current.isDeleting).toBe(false);
  });

  it("exposes action functions", () => {
    const { result } = renderHook(() => useCalibrationLibrary(), {
      wrapper: createWrapper(),
    });

    expect(typeof result.current.ingestCalibration).toBe("function");
    expect(typeof result.current.previewBlend).toBe("function");
    expect(typeof result.current.deleteCalibration).toBe("function");
    expect(typeof result.current.refetchList).toBe("function");
    expect(typeof result.current.refetchStats).toBe("function");
  });
});
