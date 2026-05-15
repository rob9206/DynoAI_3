import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DynoConfigPanel } from "../DynoConfigPanel";

const jsonResponse = (payload: unknown) =>
  Promise.resolve(new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));

const configPayload = {
  success: true,
  config: {
    model: "Dynoware RT-150",
    serial_number: "RT00220413",
    location: "Dawson Dynamics",
    ip_address: "169.254.187.108",
    jetdrive_port: 22344,
    firmware_version: "2.1.7034.17067",
    atmo_version: "1.1",
    num_modules: 4,
    drum1: {
      serial_number: "1000588",
      mass_slugs: 14.121,
      retarder_mass_slugs: 0,
      circumference_ft: 4.673,
      num_tabs: 1,
      radius_ft: 0.7437,
      inertia_lbft2: 3.9054,
      configured: true,
    },
    drum2: {
      serial_number: "",
      mass_slugs: 0,
      retarder_mass_slugs: 0,
      circumference_ft: 0,
      num_tabs: 0,
      radius_ft: 0,
      inertia_lbft2: 0,
      configured: false,
    },
  },
};

describe("DynoConfigPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders backend live status instead of zero-filled local telemetry", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
      const url = input.toString();

      if (url.endsWith("/dyno/config")) {
        return jsonResponse(configPayload);
      }

      if (url.endsWith("/hardware/status")) {
        return jsonResponse({
          connected: false,
          live: {
            capturing: true,
            channel_count: 0,
            last_update: null,
          },
          providers: [],
        });
      }

      return jsonResponse({});
    });

    render(<DynoConfigPanel apiUrl="http://test/api/jetdrive" />);

    expect(await screen.findByText("Dynoware RT-150")).toBeInTheDocument();
    expect(await screen.findByText("Capture Status")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Channels")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.queryByText("RPM")).not.toBeInTheDocument();
  });
});
