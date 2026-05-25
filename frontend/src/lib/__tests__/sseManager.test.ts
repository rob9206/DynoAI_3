import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  _activeConnectionCountForTests,
  _resetSseManagerForTests,
  _subscriberCountForTests,
  subscribeSse,
} from '../sseManager';

/**
 * Mock EventSource so we can drive open/error/named events synchronously.
 * The browser's auto-reconnect is replaced with our manager's reconnect
 * loop, so all retries happen through ``window.setTimeout``.
 */
class FakeEventSource {
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: ((evt: Event) => void) | null = null;
  onmessage: ((evt: MessageEvent<string>) => void) | null = null;
  private listeners = new Map<string, Set<(evt: MessageEvent<string>) => void>>();

  static instances: FakeEventSource[] = [];

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: (evt: MessageEvent<string>) => void) {
    let bucket = this.listeners.get(name);
    if (!bucket) {
      bucket = new Set();
      this.listeners.set(name, bucket);
    }
    bucket.add(listener);
  }

  removeEventListener(name: string, listener: (evt: MessageEvent<string>) => void) {
    this.listeners.get(name)?.delete(listener);
  }

  close() {
    this.readyState = FakeEventSource.CLOSED;
  }

  /** Test helper: emit a named event. */
  emit(name: string, data: string) {
    const listeners = this.listeners.get(name);
    if (!listeners) return;
    for (const listener of listeners) {
      listener({ data } as MessageEvent<string>);
    }
  }

  /** Test helper: fire onopen and mark as OPEN. */
  open() {
    this.readyState = FakeEventSource.OPEN;
    if (this.onopen) this.onopen();
  }

  /** Test helper: simulate a fatal error (server closed the stream). */
  failClosed() {
    this.readyState = FakeEventSource.CLOSED;
    if (this.onerror) this.onerror(new Event('error'));
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  // Plant the fake into globalThis. ``EventSource`` is read by the
  // sseManager via the global symbol, so this works in jsdom.
  // The fake also exposes static CLOSED so the manager can compare
  // ``readyState === EventSource.CLOSED``.
  (
    globalThis as unknown as { EventSource: typeof FakeEventSource }
  ).EventSource = FakeEventSource;
  vi.useFakeTimers();
});

afterEach(() => {
  _resetSseManagerForTests();
  vi.useRealTimers();
});

describe('sseManager', () => {
  it('opens at most one EventSource per URL even with multiple subscribers', () => {
    const url = 'http://localhost/api/jetdrive/hardware/live/stream';
    const onEventA = vi.fn();
    const onEventB = vi.fn();

    const unsubA = subscribeSse(url, { onEvent: onEventA });
    const unsubB = subscribeSse(url, { onEvent: onEventB });

    expect(FakeEventSource.instances.length).toBe(1);
    expect(_subscriberCountForTests(url)).toBe(2);

    // Each subscriber receives broadcast events.
    const es = FakeEventSource.instances[0];
    es.open();
    es.emit('data', '{"capturing":true}');
    es.emit('health', '{"hello":"world"}');

    expect(onEventA).toHaveBeenCalledWith('data', '{"capturing":true}');
    expect(onEventA).toHaveBeenCalledWith('health', '{"hello":"world"}');
    expect(onEventB).toHaveBeenCalledWith('data', '{"capturing":true}');
    expect(onEventB).toHaveBeenCalledWith('health', '{"hello":"world"}');

    unsubA();
    unsubB();
  });

  it('closes the EventSource when the last subscriber unsubscribes', () => {
    const url = 'http://localhost/api/jetdrive/hardware/live/stream';
    const unsubA = subscribeSse(url, { onEvent: () => undefined });
    const unsubB = subscribeSse(url, { onEvent: () => undefined });

    expect(_activeConnectionCountForTests()).toBe(1);
    unsubA();
    expect(_activeConnectionCountForTests()).toBe(1);
    unsubB();
    expect(_activeConnectionCountForTests()).toBe(0);
    // Underlying EventSource was closed.
    expect(FakeEventSource.instances[0].readyState).toBe(FakeEventSource.CLOSED);
  });

  it('emits status transitions: connecting -> open -> reconnecting on close', () => {
    const url = 'http://localhost/api/jetdrive/hardware/live/stream';
    const statusUpdates: string[] = [];
    const unsubscribe = subscribeSse(url, {
      onEvent: () => undefined,
      onStatus: (status) => statusUpdates.push(status.state),
    });

    // Subscriber receives the initial ``connecting`` immediately. The
    // sequence is idle -> connecting (manager opens before subscriber adds).
    expect(statusUpdates[0]).toBe('connecting');

    const es = FakeEventSource.instances[0];
    es.open();
    expect(statusUpdates).toContain('open');

    // Server-side close triggers the manager's exponential-backoff
    // reconnect path. The browser would auto-retry, but we want explicit
    // status visibility.
    es.failClosed();
    expect(statusUpdates).toContain('reconnecting');

    // Advance enough time for the first reconnect attempt (500 ms).
    vi.advanceTimersByTime(500);
    expect(FakeEventSource.instances.length).toBe(2);

    unsubscribe();
  });

  it('multiplexes events from one EventSource to multiple subscribers without duplication', () => {
    const url = 'http://localhost/api/jetdrive/hardware/live/stream';
    const ordered: string[] = [];
    const subA = subscribeSse(url, {
      onEvent: (name, data) => ordered.push(`A:${name}:${data}`),
    });
    const subB = subscribeSse(url, {
      onEvent: (name, data) => ordered.push(`B:${name}:${data}`),
    });

    const es = FakeEventSource.instances[0];
    es.open();
    es.emit('health', '{"v":1}');

    expect(ordered).toEqual(['A:health:{"v":1}', 'B:health:{"v":1}']);

    subA();
    es.emit('health', '{"v":2}');
    // After A unsubscribed, only B fires.
    expect(ordered).toEqual([
      'A:health:{"v":1}',
      'B:health:{"v":1}',
      'B:health:{"v":2}',
    ]);

    subB();
  });
});
