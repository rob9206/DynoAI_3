/**
 * Shared SSE manager.
 *
 * Both ``useJetDriveLive`` and ``useHardwareStatus`` need to subscribe to
 * ``/hardware/live/stream``. Without coordination they each open their own
 * ``EventSource``. With two browser tabs that's up to four concurrent SSE
 * connections per session. This module guarantees at most ONE
 * ``EventSource`` per origin URL by ref-counting subscribers and
 * multiplexing ``data``/``health``/etc. events to all of them.
 *
 * Strict TypeScript renderer policy still applies: this module relays
 * server-pushed payloads verbatim. No physics, no math.
 */

/**
 * SSE event name. Well-known event names served today are ``data``,
 * ``health``, and ``samples``; we keep the type ``string`` so future
 * server-side event types are forwarded transparently.
 */
export type SseEventName = string;

export type SseConnectionState =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed';

export interface SseConnectionStatus {
  state: SseConnectionState;
  /** Number of consecutive reconnect attempts since the last successful open. */
  reconnectAttempts: number;
  /** Most recent error description, or null when connection is healthy. */
  lastError: string | null;
  /** Timestamp (ms) of the most recent ``open`` event. 0 if never opened. */
  lastOpenAt: number;
}

export interface SseSubscriber {
  /** Receive a typed event (matches ``EventSource`` typed events). */
  onEvent: (event: SseEventName, data: string) => void;
  /** Receive connection-state transitions (open / reconnecting / etc.). */
  onStatus?: (status: SseConnectionStatus) => void;
}

interface ManagedConnection {
  url: string;
  source: EventSource | null;
  subscribers: Set<SseSubscriber>;
  status: SseConnectionStatus;
  /** Names registered with ``addEventListener`` for auto-cleanup on close. */
  registeredEvents: Set<SseEventName>;
  reconnectTimer: number | null;
  closed: boolean;
}

const RECONNECT_BASE_MS = 500;
const RECONNECT_MAX_MS = 15_000;
const KNOWN_EVENT_NAMES: SseEventName[] = ['data', 'health', 'samples'];

const _connections = new Map<string, ManagedConnection>();

function _now(): number {
  return Date.now();
}

function _setStatus(
  conn: ManagedConnection,
  patch: Partial<SseConnectionStatus>,
): void {
  conn.status = { ...conn.status, ...patch };
  for (const sub of conn.subscribers) {
    if (sub.onStatus) {
      try {
        sub.onStatus(conn.status);
      } catch {
        /* swallow per-subscriber errors */
      }
    }
  }
}

function _broadcast(
  conn: ManagedConnection,
  event: SseEventName,
  data: string,
): void {
  for (const sub of conn.subscribers) {
    try {
      sub.onEvent(event, data);
    } catch {
      /* swallow per-subscriber errors */
    }
  }
}

function _scheduleReconnect(conn: ManagedConnection): void {
  if (conn.closed || conn.reconnectTimer !== null) return;
  const delay = Math.min(
    RECONNECT_BASE_MS * 2 ** conn.status.reconnectAttempts,
    RECONNECT_MAX_MS,
  );
  _setStatus(conn, {
    state: 'reconnecting',
    reconnectAttempts: conn.status.reconnectAttempts + 1,
  });
  conn.reconnectTimer = window.setTimeout(() => {
    conn.reconnectTimer = null;
    _openSource(conn);
  }, delay);
}

function _openSource(conn: ManagedConnection): void {
  if (conn.closed) return;
  if (conn.source && conn.source.readyState !== EventSource.CLOSED) {
    return;
  }

  let es: EventSource;
  try {
    es = new EventSource(conn.url);
  } catch (err) {
    _setStatus(conn, {
      state: 'closed',
      lastError: err instanceof Error ? err.message : 'EventSource constructor failed',
    });
    _scheduleReconnect(conn);
    return;
  }

  conn.source = es;
  _setStatus(conn, { state: 'connecting' });

  es.onopen = () => {
    _setStatus(conn, {
      state: 'open',
      reconnectAttempts: 0,
      lastError: null,
      lastOpenAt: _now(),
    });
  };

  es.onmessage = (event: MessageEvent<string>) => {
    _broadcast(conn, 'data', typeof event.data === 'string' ? event.data : '');
  };

  es.onerror = () => {
    // EventSource has its own auto-reconnect, but it doesn't expose
    // explicit state changes; if the source has actually closed, schedule
    // our exponential-backoff reconnect. Otherwise let the browser retry.
    if (es.readyState === EventSource.CLOSED) {
      try {
        es.close();
      } catch {
        /* ignore */
      }
      conn.source = null;
      _setStatus(conn, {
        state: 'reconnecting',
        lastError: 'SSE connection lost',
      });
      _scheduleReconnect(conn);
    } else {
      _setStatus(conn, { lastError: 'SSE error' });
    }
  };

  // Wire up named events. Re-register on every open because EventSource
  // listeners survive the same EventSource instance, but we recreate ``es``
  // on every reconnect.
  conn.registeredEvents.clear();
  for (const name of KNOWN_EVENT_NAMES) {
    const handler = (event: MessageEvent<string>) => {
      _broadcast(conn, name, typeof event.data === 'string' ? event.data : '');
    };
    es.addEventListener(name, handler as EventListener);
    conn.registeredEvents.add(name);
  }
}

function _closeConnection(conn: ManagedConnection): void {
  conn.closed = true;
  if (conn.reconnectTimer !== null) {
    window.clearTimeout(conn.reconnectTimer);
    conn.reconnectTimer = null;
  }
  if (conn.source) {
    try {
      conn.source.close();
    } catch {
      /* ignore */
    }
    conn.source = null;
  }
  _setStatus(conn, { state: 'closed' });
  _connections.delete(conn.url);
}

/**
 * Subscribe to the shared SSE connection at ``url``.
 *
 * - First subscriber opens the underlying EventSource.
 * - Subsequent subscribers reuse it.
 * - When the last subscriber unsubscribes the connection is torn down.
 * - Reconnection on error is exponential-backoff; ``onStatus`` fires for
 *   every state transition.
 */
export function subscribeSse(
  url: string,
  subscriber: SseSubscriber,
): () => void {
  let conn = _connections.get(url);
  if (!conn) {
    conn = {
      url,
      source: null,
      subscribers: new Set<SseSubscriber>(),
      status: {
        state: 'idle',
        reconnectAttempts: 0,
        lastError: null,
        lastOpenAt: 0,
      },
      registeredEvents: new Set<SseEventName>(),
      reconnectTimer: null,
      closed: false,
    };
    _connections.set(url, conn);
    _openSource(conn);
  }

  conn.subscribers.add(subscriber);
  // Replay current status to the freshly subscribed listener so it can
  // render immediately if the connection is already open.
  if (subscriber.onStatus) {
    try {
      subscriber.onStatus(conn.status);
    } catch {
      /* ignore */
    }
  }

  let unsubscribed = false;
  return () => {
    if (unsubscribed) return;
    unsubscribed = true;
    if (!conn) return;
    conn.subscribers.delete(subscriber);
    if (conn.subscribers.size === 0) {
      _closeConnection(conn);
    }
  };
}

/** Test seam: drop every active connection. */
export function _resetSseManagerForTests(): void {
  for (const conn of Array.from(_connections.values())) {
    _closeConnection(conn);
  }
  _connections.clear();
}

/** Test seam: introspect active connection count. */
export function _activeConnectionCountForTests(): number {
  return _connections.size;
}

/** Test seam: introspect subscriber count for a given URL. */
export function _subscriberCountForTests(url: string): number {
  return _connections.get(url)?.subscribers.size ?? 0;
}
