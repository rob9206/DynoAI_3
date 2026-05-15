import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useJetDriveLive } from "../useJetDriveLive";

function createFetchResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(body),
  };
}

describe("useJetDriveLive", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        createFetchResponse({
          capturing: false,
          simulated: false,
          channels: {},
        })
      )
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("does not poll the drain endpoint unless drained samples are enabled", async () => {
    const fetchMock = vi.mocked(fetch);

    renderHook(() =>
      useJetDriveLive({
        apiUrl: "http://api.test",
        isSimulatorActive: true,
        useSse: false,
      })
    );

    await Promise.resolve();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/hardware/live/data",
      expect.any(Object)
    );

    expect(
      fetchMock.mock.calls.some(([url]) =>
        typeof url === "string" && url.includes("/hardware/live/drain")
      )
    ).toBe(false);
  });
});
