using System;
using System.IO;
using Newtonsoft.Json;

namespace DynoAIBridge
{
    /// <summary>
    /// Persistent configuration for the DynoAI Bridge plugin.
    /// Stored as JSON in %AppData%\DynoAIBridge\config.json
    /// 
    /// Users configure which auxiliary input channels correspond to
    /// AFR, MAP, TPS, and temperature sensors via the settings dialog.
    /// A value of -1 means "not connected / auto-detect from plugins".
    /// </summary>
    public class BridgeConfig
    {
        /// <summary>TCP port for the JSON-lines server. Default 9877.</summary>
        public int TcpPort { get; set; } = 9877;

        /// <summary>Aux input index for front cylinder AFR (-1 = not mapped).</summary>
        public int AuxIndexAfrFront { get; set; } = -1;

        /// <summary>Aux input index for rear cylinder AFR (-1 = not mapped).</summary>
        public int AuxIndexAfrRear { get; set; } = -1;

        /// <summary>Aux input index for MAP sensor in kPa (-1 = not mapped).</summary>
        public int AuxIndexMap { get; set; } = -1;

        /// <summary>Aux input index for TPS (-1 = not mapped).</summary>
        public int AuxIndexTps { get; set; } = -1;

        /// <summary>Aux input index for intake air temperature (-1 = not mapped).</summary>
        public int AuxIndexIat { get; set; } = -1;

        /// <summary>Aux input index for engine/coolant temperature (-1 = not mapped).</summary>
        public int AuxIndexEngineTemp { get; set; } = -1;

        /// <summary>
        /// If true, the plugin will attempt to auto-detect AFR and MAP
        /// from other YourDyno plugins (CAN, wideband, etc.) when aux
        /// channels are not mapped (-1).
        /// </summary>
        public bool AutoDetectFromPlugins { get; set; } = true;

        /// <summary>
        /// Maximum samples per second to stream. 0 = unlimited (use YourDyno's native rate).
        /// Useful to reduce bandwidth if DynoAI only needs 20Hz.
        /// </summary>
        public int MaxSampleRateHz { get; set; } = 0;

        // ── File paths ───────────────────────────────────────────────

        private static string ConfigDir =>
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "DynoAIBridge");

        private static string ConfigPath =>
            Path.Combine(ConfigDir, "config.json");

        // ── Load / Save ──────────────────────────────────────────────

        public static BridgeConfig Load()
        {
            try
            {
                if (File.Exists(ConfigPath))
                {
                    var json = File.ReadAllText(ConfigPath);
                    var config = JsonConvert.DeserializeObject<BridgeConfig>(json);
                    return config ?? new BridgeConfig();
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[DynoAIBridge] Failed to load config: {ex.Message}");
            }

            return new BridgeConfig();
        }

        public void Save()
        {
            try
            {
                if (!Directory.Exists(ConfigDir))
                    Directory.CreateDirectory(ConfigDir);

                var json = JsonConvert.SerializeObject(this, Formatting.Indented);
                File.WriteAllText(ConfigPath, json);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[DynoAIBridge] Failed to save config: {ex.Message}");
            }
        }
    }
}
