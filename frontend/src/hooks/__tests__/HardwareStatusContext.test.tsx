import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import {
  HardwareStatusProvider,
  useHardwareStatusContext,
  __HARDWARE_STATUS_FALLBACK_FOR_TESTS,
} from '../HardwareStatusContext';
import {
  _resetSseManagerForTests,
  _activeConnectionCountForTests,
} from '../../lib/sseManager';

// Minimal EventSource fake — context tests don't drive events, they just
// verify that one shared subscription serves multiple consumers.
class IdleEventSource {
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: ((evt: Event) => void) | null = null;
  onmessage: ((evt: MessageEvent<string>) => void) | null = null;
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: IdleEventSource[] = [];
  constructor(url: string) {
    this.url = url;
    IdleEventSource.instances.push(this);
  }
  addEventListener() {
    /* noop */
  }
  removeEventListener() {
    /* noop */
  }
  close() {
    this.readyState = IdleEventSource.CLOSED;
  }
}

beforeEach(() => {
  IdleEventSource.instances = [];
  (
    globalThis as unknown as { EventSource: typeof IdleEventSource }
  ).EventSource = IdleEventSource;
  // Stub fetch so the polling fallback never throws during the test.
  const stubBody = JSON.stringify({
    timestamp: 0,
    provider: {
      connected: false,
      count: 0,
      providers: [],
      monitor_running: false,
      last_check: null,
    },
    capture: {
      capturing: false,
      last_update_ts: null,
      data_age_seconds: null,
      provider_id: null,
      provider_name: null,
      provider_host: null,
      error: null,
      error_code: null,
    },
    channels: {
      capturing: false,
      provider: { provider_id: null, name: null, host: null },
      all_required_ok: false,
      summary: {
        state: 'idle',
        message: 'idle',
        counts: { OK: 0, STALE: 0, UNMAPPED: 0, INVALID: 0, NO_SIGNAL: 0 },
      },
      afr_plausibility: { min: 10, max: 18 },
      lc2_ceiling: 22.38,
      stale_threshold_seconds: 2.5,
      wot_tps_threshold: 70,
      channels: [],
      timestamp: 0,
      error: null,
      error_code: null,
    },
    mapping: null,
    ingestion: {
      overall_health: 'unknown',
      healthy_channels: 0,
      total_channels: 0,
      drop_rate_percent: 0,
    },
  });
  globalThis.fetch = vi.fn(() =>
    Promise.resolve(new Response(stubBody, { status: 200 })),
  ) as unknown as typeof fetch;
});

afterEach(() => {
  _resetSseManagerForTests();
  vi.restoreAllMocks();
});

function ConsumerA() {
  const { source, status } = useHardwareStatusContext();
  return (
    <div data-testid="a">
      A: source={source}, hasStatus={String(status !== null)}
    </div>
  );
}

function ConsumerB() {
  const ctx = useHardwareStatusContext();
  return <div data-testid="b">B: source={ctx.source}</div>;
}

describe('HardwareStatusContext', () => {
  it('provides shared state to multiple consumers via one subscription', async () => {
    render(
      <HardwareStatusProvider apiUrl="http://localhost/api/jetdrive" pollIntervalMs={0}>
        <ConsumerA />
        <ConsumerB />
      </HardwareStatusProvider>,
    );

    // Both consumers render; one shared SSE subscription is open.
    expect(screen.getByTestId('a')).toBeInTheDocument();
    expect(screen.getByTestId('b')).toBeInTheDocument();
    expect(_activeConnectionCountForTests()).toBe(1);
    // Even with two consumers there is exactly one EventSource instance.
    expect(IdleEventSource.instances.length).toBe(1);

    await waitFor(() => {
      expect(IdleEventSource.instances.length).toBe(1);
    });
  });

  it('throws in dev when used outside the provider', () => {
    // import.meta.env.DEV is true under Vitest; the accessor must throw.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    expect(() => render(<ConsumerA />)).toThrowError(
      /useHardwareStatusContext must be used within <HardwareStatusProvider>/,
    );
    consoleError.mockRestore();
  });

  it('exposes a stable fallback object for non-dev consumers', () => {
    expect(__HARDWARE_STATUS_FALLBACK_FOR_TESTS.status).toBeNull();
    expect(__HARDWARE_STATUS_FALLBACK_FOR_TESTS.isFetching).toBe(false);
    expect(__HARDWARE_STATUS_FALLBACK_FOR_TESTS.error).toBeNull();
    expect(__HARDWARE_STATUS_FALLBACK_FOR_TESTS.source).toBe('none');
    expect(typeof __HARDWARE_STATUS_FALLBACK_FOR_TESTS.refresh).toBe(
      'function',
    );
  });
});
