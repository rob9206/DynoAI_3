import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChannelMappingPanel } from "../ChannelMappingPanel";

const jsonResponse = (payload: unknown) =>
  Promise.resolve(new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));

describe("ChannelMappingPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads an existing saved mapping on mount", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input: RequestInfo | URL) => {
        const url = input.toString();

        if (url.endsWith("/mapping/transforms")) {
          return jsonResponse({ transforms: [{ id: "identity", name: "identity" }] });
        }

        if (url.endsWith("/mapping/templates")) {
          return jsonResponse({ templates: [] });
        }

        if (url.endsWith("/mapping")) {
          return jsonResponse({
            mappings: [
              {
                version: "1.0",
                provider_signature: "4097_192.168.1.100_abc123",
                provider_id: 4097,
                provider_name: "Saved Dyno",
                host: "192.168.1.100",
                created_at: "2026-05-15T00:00:00",
                updated_at: "2026-05-15T00:00:00",
                channels: {
                  rpm: {
                    source_id: 10,
                    source_name: "Digital RPM 1",
                    transform: "identity",
                    enabled: true,
                  },
                },
              },
            ],
            count: 1,
          });
        }

        return jsonResponse({});
      });

    render(<ChannelMappingPanel apiUrl="http://test/api/jetdrive" />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("http://test/api/jetdrive/mapping");
    });

    expect(await screen.findByText("Saved Dyno")).toBeInTheDocument();
    expect(screen.queryByText("No channel mapping configured")).not.toBeInTheDocument();
  });
});
