using System;
using System.Collections.Generic;
using System.ComponentModel.Composition;
using System.Windows.Forms;
using DataConnection;
using PluginContracts;

namespace DynoAIBridge
{
    /// <summary>
    /// DynoAI Bridge Plugin for YourDyno.
    /// 
    /// Implements IDataIOProvider to receive live dyno data from YourDyno,
    /// then streams it over TCP (JSON-lines) to the DynoAI Python backend.
    /// 
    /// Key API facts (discovered via DLL reflection):
    ///   - DynoDataConnection is a STATIC class -- all fields/methods accessed statically
    ///   - PluginCollection is a STATIC class -- PluginCollection.Instances gives all plugin channels
    ///   - initDynoDataConnection() takes ZERO parameters (static access, no instance needed)
    ///   - DynoDataConnection.OnDynoDataReceived is the push-based data event
    ///   - DynoDataConnection.polledDataSet holds the latest OneProcessedSample
    /// 
    /// Install: Copy DynoAIBridge.dll to %ProgramData%\YourDynoPlugins\
    /// </summary>
    [Export(typeof(IDataIOProvider))]
    public class DynoAIBridgePlugin : IDataIOProvider
    {
        // ── IDataIOProvider identity ──────────────────────────────────

        public string name => "DynoAI Bridge";
        public string pluginDescription => "Streams live YourDyno data to DynoAI for real-time VE auto-tuning";
        public string version => "1.0.0";

        // ── Hotkeys ──────────────────────────────────────────────────

        public List<Keys> hotkeys => new List<Keys>();
        public void hotkeyPressed(Keys hotkey) { }

        // ── Plugin data connections (channels exposed back to YourDyno) ──

        private readonly List<OnePlugInDataConnection> _pluginDataConnections;
        public List<OnePlugInDataConnection> pluginDataConnections => _pluginDataConnections;

        // ── Configuration change event ───────────────────────────────
        // Required by IDataIOProvider. Fire this to signal YourDyno that
        // plugin channel configuration has changed.

#pragma warning disable CS0067 // Event is required by interface but not currently raised
        public event ConfigChangeEventHandler OnConfigurationChange;
#pragma warning restore CS0067

        // ── Menu entry ───────────────────────────────────────────────

        private ToolStripMenuItem _menuEntry;
        public ToolStripMenuItem pluginMenuEntry => _menuEntry;

        // ── Internal state ───────────────────────────────────────────

        private TcpBridge _bridge;
        private ChannelMapper _channelMapper;
        private BridgeConfig _config;
        private volatile bool _initialized;

        // ── Constructor ──────────────────────────────────────────────

        public DynoAIBridgePlugin()
        {
            _config = BridgeConfig.Load();
            _channelMapper = new ChannelMapper(_config);
            _bridge = new TcpBridge(_config.TcpPort);

            // Status channel exposed back to YourDyno (shows connection state in gauges)
            _pluginDataConnections = new List<OnePlugInDataConnection>
            {
                new OnePlugInDataConnection
                {
                    pluginName = name,
                    name = "DynoAI Clients",
                    unit = "",
                    y = 0,
                    graphPane = 0,
                    isY2Axis = false,
                    showGaugeInRunWindow = true,
                    applyNoiseFiltering = false,
                    unitType = UnitType.None
                }
            };

            // Menu entry for settings
            _menuEntry = new ToolStripMenuItem("DynoAI Bridge Settings...");
            _menuEntry.Click += OnMenuSettingsClick;
        }

        // ── IDataIOProvider.initDynoDataConnection ───────────────────
        // Called by YourDyno after plugin load.
        // Takes NO parameters -- DynoDataConnection is a static class,
        // so we access data via DynoDataConnection.polledDataSet etc.
        // Other plugin data is accessed via static PluginCollection.Instances.

        public void initDynoDataConnection()
        {
            if (_initialized) return;

            // Subscribe to the static push-based data events
            DynoDataConnection.OnDynoDataReceived += OnDynoDataReceived;
            DynoDataConnection.OnDynoDataReady += OnDynoDataReady;

            // Start TCP server
            _bridge.Start();
            _initialized = true;

            Log($"DynoAI Bridge v{version} initialized. TCP server on port {_config.TcpPort}");
        }

        // ── Data event handlers ──────────────────────────────────────

        /// <summary>
        /// Called by YourDyno each time raw data is received from the dyno hardware.
        /// This is the highest-rate event -- fires at the dyno's native sample rate.
        /// </summary>
        private void OnDynoDataReceived(OnDataReceivedEventArgs e)
        {
            if (!_bridge.HasClients) return;

            try
            {
                var sample = e.processedDynoSample;
                if (sample == null) return;

                // Build the channel snapshot using static DynoDataConnection
                // and static PluginCollection for other plugin data
                var snapshot = _channelMapper.MapSample(sample);

                // Stream to all connected DynoAI clients
                _bridge.BroadcastLine(snapshot);

                // Update status gauge (visible in YourDyno's run window)
                _pluginDataConnections[0].y = _bridge.ClientCount;
            }
            catch (Exception ex)
            {
                Log($"Error in OnDynoDataReceived: {ex.Message}");
            }
        }

        /// <summary>
        /// Called when YourDyno has finished processing a data set (after filtering, etc.).
        /// Lower rate than OnDynoDataReceived. Not used currently but available for
        /// processed/filtered data if needed.
        /// </summary>
        private void OnDynoDataReady(OnDataReceivedEventArgs e)
        {
            // Reserved for future use -- could send processed data at lower rate
        }

        // ── Settings menu ────────────────────────────────────────────

        private void OnMenuSettingsClick(object sender, EventArgs e)
        {
            using (var form = new ConfigForm(_config))
            {
                if (form.ShowDialog() == DialogResult.OK)
                {
                    _config = form.GetConfig();
                    _config.Save();
                    _channelMapper = new ChannelMapper(_config);

                    // Restart TCP on new port if changed
                    if (_bridge.Port != _config.TcpPort)
                    {
                        _bridge.Stop();
                        _bridge = new TcpBridge(_config.TcpPort);
                        _bridge.Start();
                    }

                    Log($"Configuration updated. Port: {_config.TcpPort}");
                }
            }
        }

        // ── Logging helper ───────────────────────────────────────────

        private static void Log(string message)
        {
            System.Diagnostics.Debug.WriteLine($"[DynoAIBridge] {message}");
        }
    }
}
