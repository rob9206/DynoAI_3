import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MappingConfidencePanel } from "../MappingConfidencePanel";

describe("MappingConfidencePanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not retry provider-discovery failures", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 3,
          retryDelay: 1,
        },
      },
    });

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "No JetDrive providers found" }), {
        status: 404,
        statusText: "Not Found",
        headers: { "Content-Type": "application/json" },
      })
    );

    render(
      <QueryClientProvider client={queryClient}>
        <MappingConfidencePanel apiUrl="http://test/api/jetdrive" />
      </QueryClientProvider>
    );

    expect(await screen.findByText("Confidence Check Failed")).toBeInTheDocument();
    expect(screen.getByText(/No JetDrive providers found/)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });
});
