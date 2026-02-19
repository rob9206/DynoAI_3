using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace DynoAIBridge
{
    /// <summary>
    /// Lightweight TCP server that streams JSON-lines to connected DynoAI clients.
    /// 
    /// Protocol:
    ///   - Server listens on localhost:{Port} (default 9877)
    ///   - Each connected client receives newline-delimited JSON objects
    ///   - Each line is a complete JSON snapshot of the current dyno state
    ///   - Clients that fall behind or disconnect are silently removed
    ///   
    /// Thread safety:
    ///   - BroadcastLine() is called from YourDyno's data thread
    ///   - Accept loop runs on its own background thread
    ///   - Each client has a bounded send queue to prevent backpressure
    /// </summary>
    public class TcpBridge : IDisposable
    {
        public int Port { get; }
        public int ClientCount => _clients.Count;
        public bool HasClients => !_clients.IsEmpty;

        private TcpListener _listener;
        private Thread _acceptThread;
        private volatile bool _running;

        // Each connected client gets a bounded queue; writer thread drains it
        private readonly ConcurrentDictionary<int, ClientConnection> _clients
            = new ConcurrentDictionary<int, ClientConnection>();

        private int _nextClientId;

        private const int MaxQueueDepth = 200;    // ~10 seconds at 20Hz
        private const int SendTimeoutMs = 2000;

        public TcpBridge(int port)
        {
            Port = port;
        }

        public void Start()
        {
            if (_running) return;

            _running = true;
            _listener = new TcpListener(IPAddress.Loopback, Port);
            _listener.Start();

            _acceptThread = new Thread(AcceptLoop)
            {
                Name = "DynoAIBridge-Accept",
                IsBackground = true
            };
            _acceptThread.Start();

            Log($"TCP server started on 127.0.0.1:{Port}");
        }

        public void Stop()
        {
            _running = false;

            try { _listener?.Stop(); }
            catch { /* ignore */ }

            foreach (var kv in _clients)
            {
                kv.Value.Dispose();
            }
            _clients.Clear();

            Log("TCP server stopped");
        }

        /// <summary>
        /// Broadcast a single JSON line to all connected clients.
        /// Called from YourDyno's data thread -- must be fast and non-blocking.
        /// </summary>
        public void BroadcastLine(string jsonLine)
        {
            if (_clients.IsEmpty) return;

            var data = Encoding.UTF8.GetBytes(jsonLine + "\n");

            foreach (var kv in _clients)
            {
                var client = kv.Value;
                if (!client.IsAlive)
                {
                    RemoveClient(kv.Key);
                    continue;
                }

                // Enqueue for async send; drop if queue full (client too slow)
                if (client.SendQueue.Count < MaxQueueDepth)
                {
                    client.SendQueue.Enqueue(data);
                    client.SendSignal.Set();
                }
                else
                {
                    // Client is too slow -- drop oldest samples
                    byte[] discard;
                    client.SendQueue.TryDequeue(out discard);
                    client.SendQueue.Enqueue(data);
                    client.SendSignal.Set();
                }
            }
        }

        // ── Accept loop ──────────────────────────────────────────────

        private void AcceptLoop()
        {
            while (_running)
            {
                try
                {
                    var tcp = _listener.AcceptTcpClient();
                    tcp.NoDelay = true;
                    tcp.SendTimeout = SendTimeoutMs;

                    var id = Interlocked.Increment(ref _nextClientId);
                    var client = new ClientConnection(tcp);

                    if (_clients.TryAdd(id, client))
                    {
                        // Start sender thread for this client
                        var senderThread = new Thread(() => ClientSendLoop(id, client))
                        {
                            Name = $"DynoAIBridge-Send-{id}",
                            IsBackground = true
                        };
                        senderThread.Start();

                        Log($"Client {id} connected from {tcp.Client.RemoteEndPoint}");
                    }
                    else
                    {
                        tcp.Close();
                    }
                }
                catch (SocketException) when (!_running)
                {
                    // Expected when Stop() is called
                    break;
                }
                catch (Exception ex)
                {
                    if (_running)
                        Log($"Accept error: {ex.Message}");
                    Thread.Sleep(100);
                }
            }
        }

        // ── Per-client send loop ─────────────────────────────────────

        private void ClientSendLoop(int clientId, ClientConnection client)
        {
            try
            {
                var stream = client.TcpClient.GetStream();

                // Send handshake line so client knows they're connected
                var hello = Encoding.UTF8.GetBytes(
                    "{\"type\":\"hello\",\"plugin\":\"DynoAIBridge\",\"version\":\"1.0.0\"," +
                    $"\"port\":{Port}}}\n");
                stream.Write(hello, 0, hello.Length);
                stream.Flush();

                while (_running && client.IsAlive)
                {
                    // Wait for data to send
                    client.SendSignal.Wait(500);
                    client.SendSignal.Reset();

                    // Drain the queue
                    byte[] data;
                    while (client.SendQueue.TryDequeue(out data))
                    {
                        try
                        {
                            stream.Write(data, 0, data.Length);
                        }
                        catch
                        {
                            client.MarkDead();
                            break;
                        }
                    }

                    // Flush after draining batch
                    try
                    {
                        stream.Flush();
                    }
                    catch
                    {
                        client.MarkDead();
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"Client {clientId} send error: {ex.Message}");
            }
            finally
            {
                RemoveClient(clientId);
                Log($"Client {clientId} disconnected");
            }
        }

        private void RemoveClient(int clientId)
        {
            ClientConnection removed;
            if (_clients.TryRemove(clientId, out removed))
            {
                removed.Dispose();
            }
        }

        private static void Log(string message)
        {
            System.Diagnostics.Debug.WriteLine($"[DynoAIBridge.TCP] {message}");
        }

        public void Dispose()
        {
            Stop();
        }

        // ── Client connection wrapper ────────────────────────────────

        private class ClientConnection : IDisposable
        {
            public TcpClient TcpClient { get; }
            public ConcurrentQueue<byte[]> SendQueue { get; } = new ConcurrentQueue<byte[]>();
            public ManualResetEventSlim SendSignal { get; } = new ManualResetEventSlim(false);
            public bool IsAlive => _alive && TcpClient.Connected;

            private volatile bool _alive = true;

            public ClientConnection(TcpClient tcp)
            {
                TcpClient = tcp;
            }

            public void MarkDead()
            {
                _alive = false;
                SendSignal.Set();
            }

            public void Dispose()
            {
                _alive = false;
                SendSignal.Set();
                try { TcpClient.Close(); } catch { }
                SendSignal.Dispose();
            }
        }
    }
}
