using System;
using System.Collections.Generic;
using System.Linq;
using DataConnection;
using Newtonsoft.Json;
using PluginContracts;

namespace DynoAIBridge
{
    /// <summary>
    /// Maps YourDyno's OneProcessedSample + plugin data into a flat JSON object
    /// suitable for DynoAI consumption.
    /// 
    /// JSON-lines format sent to DynoAI:
    /// {
    ///   "ts": 1234.567,           // timestamp (seconds)
    ///   "elapsed": 45.2,          // elapsed time (seconds)
    ///   "engine_rpm": 3500.0,     // engine RPM
    ///   "roller_rpm": 1200.0,     // roller/wheel RPM
    ///   "engine_hp": 85.3,        // engine horsepower
    ///   "engine_torque": 92.1,    // engine torque (ft-lb)
    ///   "wheel_hp": 72.5,         // wheel horsepower
    ///   "wheel_torque": 78.4,     // wheel torque (ft-lb)
    ///   "afr_front": 13.2,        // AFR front cylinder (from aux or plugin)
    ///   "afr_rear": 12.8,         // AFR rear cylinder (from aux or plugin)
    ///   "map_kpa": 65.0,          // MAP in kPa (from aux, CAN, or plugin)
    ///   "egt": [650.0, 680.0],    // EGT array (°F)
    ///   "aux": [0.5, 1.2, ...],   // raw aux values
    ///   "ambient_temp_f": 72.0,   // ambient temperature (°F)
    ///   "ambient_pressure_inhg": 29.92,  // barometric pressure (inHg)
    ///   "ambient_humidity": 45.0, // relative humidity (%)
    ///   "is_logging": true,       // YourDyno logging state
    ///   "dyno_type": "Ultimate"   // hardware type
    /// }
    /// </summary>
    public class ChannelMapper
    {
        private readonly BridgeConfig _config;

        // Reusable dictionary to avoid allocation per sample
        private readonly Dictionary<string, object> _snapshot = new Dictionary<string, object>(32);

        public ChannelMapper(BridgeConfig config)
        {
            _config = config;
        }

        /// <summary>
        /// Map a single processed sample into a JSON-lines string.
        /// 
        /// DynoDataConnection is a STATIC class -- all environmental data,
        /// connection state, and logging status are accessed via static fields/props.
        /// PluginCollection is also STATIC -- PluginCollection.Instances gives
        /// a Dictionary&lt;string, OnePlugInDataConnection&gt; of all loaded plugins.
        /// </summary>
        public string MapSample(OneProcessedSample sample)
        {
            _snapshot.Clear();

            // ── Core timing ──────────────────────────────────────────
            _snapshot["ts"] = sample.timeStamp;
            _snapshot["elapsed"] = sample.elapsedTime;

            // ── RPM channels ─────────────────────────────────────────
            _snapshot["engine_rpm"] = sample.engineRPM;
            _snapshot["roller_rpm"] = sample.rollerRPM;

            if (sample.RPM1 != 0) _snapshot["rpm1"] = sample.RPM1;
            if (sample.RPM2 != 0) _snapshot["rpm2"] = sample.RPM2;
            if (sample.RPM3 != 0) _snapshot["rpm3"] = sample.RPM3;
            if (sample.RPM4 != 0) _snapshot["rpm4"] = sample.RPM4;
            if (sample.Freq1 != 0) _snapshot["freq1"] = sample.Freq1;
            if (sample.Freq2 != 0) _snapshot["freq2"] = sample.Freq2;

            // ── Power (HP) ───────────────────────────────────────────
            _snapshot["engine_hp"] = SafePowerHP(sample.engineHP);
            _snapshot["wheel_hp"] = SafePowerHP(sample.wheelHP);
            _snapshot["engine_kw"] = SafePowerKW(sample.engineHP);
            _snapshot["wheel_kw"] = SafePowerKW(sample.wheelHP);

            // ── Torque (ft-lb and Nm) ────────────────────────────────
            _snapshot["engine_torque_ftlb"] = SafeTorqueFtLb(sample.engineTorque);
            _snapshot["wheel_torque_ftlb"] = SafeTorqueFtLb(sample.wheelTorque);
            _snapshot["engine_torque_nm"] = SafeTorqueNm(sample.engineTorque);
            _snapshot["wheel_torque_nm"] = SafeTorqueNm(sample.wheelTorque);

            // ── Load cells ───────────────────────────────────────────
            if (sample.loadCell1Torque != null)
                _snapshot["load_cell_1"] = sample.loadCell1Torque.torqueInLbFt;
            if (sample.loadCell2Torque != null)
                _snapshot["load_cell_2"] = sample.loadCell2Torque.torqueInLbFt;

            // ── Angular acceleration ─────────────────────────────────
            if (sample.angularAcceleration1 != 0)
                _snapshot["angular_accel_1"] = sample.angularAcceleration1;

            // ── EGT array ────────────────────────────────────────────
            if (sample.EGT != null && sample.EGT.Length > 0)
            {
                _snapshot["egt"] = sample.EGT;
            }

            // ── Auxiliary sensor array ───────────────────────────────
            if (sample.aux != null && sample.aux.Length > 0)
            {
                _snapshot["aux"] = sample.aux;

                // Map configured aux channels to named fields
                MapAuxChannel("afr_front", _config.AuxIndexAfrFront, sample.aux);
                MapAuxChannel("afr_rear", _config.AuxIndexAfrRear, sample.aux);
                MapAuxChannel("map_kpa", _config.AuxIndexMap, sample.aux);
                MapAuxChannel("tps", _config.AuxIndexTps, sample.aux);
                MapAuxChannel("iat_f", _config.AuxIndexIat, sample.aux);
                MapAuxChannel("engine_temp_f", _config.AuxIndexEngineTemp, sample.aux);
            }

            // ── Named RPM/freq channels ──────────────────────────────
            if (sample.rpmFreqChannels != null && sample.rpmFreqChannels.Count > 0)
            {
                _snapshot["rpm_freq_channels"] = sample.rpmFreqChannels;
            }

            // ── Data from other plugins (wideband, CAN reader, etc.) ─
            // PluginCollection is static -- access all loaded plugin channels
            try
            {
                var pluginInstances = PluginCollection.Instances;
                if (pluginInstances != null && pluginInstances.Count > 0)
                {
                    MapPluginChannels(pluginInstances.Values);
                }
            }
            catch
            {
                // PluginCollection may not be initialized yet
            }

            // ── Environmental data from static DynoDataConnection ────
            _snapshot["ambient_temp_f"] = CtoF(DynoDataConnection.ambientTemperature);
            _snapshot["ambient_pressure_inhg"] = MbarToInHg(DynoDataConnection.ambientPressure);
            _snapshot["ambient_humidity"] = DynoDataConnection.ambientHumidity;
            _snapshot["is_logging"] = DynoDataConnection.isLogging;
            _snapshot["dyno_connected"] = DynoDataConnection.dynoConnectionEstablished;
            _snapshot["env_correction"] = DynoDataConnection.envCorrection;
            _snapshot["current_rpm"] = DynoDataConnection.currentRPM;
            _snapshot["gauge_power"] = DynoDataConnection.gaugePower;
            _snapshot["gauge_torque"] = DynoDataConnection.gaugeTorque;

            if (DynoDataConnection.dynoType != YourDynoType.None)
                _snapshot["dyno_type"] = DynoDataConnection.dynoType.ToString();

            return JsonConvert.SerializeObject(_snapshot, Formatting.None);
        }

        // ── Aux channel mapping ──────────────────────────────────────

        private void MapAuxChannel(string fieldName, int auxIndex, double[] aux)
        {
            if (auxIndex >= 0 && auxIndex < aux.Length && !double.IsNaN(aux[auxIndex]))
            {
                _snapshot[fieldName] = Math.Round(aux[auxIndex], 3);
            }
        }

        // ── Plugin channel scanning ──────────────────────────────────

        /// <summary>
        /// Scan other YourDyno plugins for AFR/MAP data.
        /// Users may have a CAN plugin, wideband plugin, or OBD plugin
        /// that provides these channels. We look for common naming patterns.
        /// 
        /// PluginCollection.Instances is Dictionary&lt;string, OnePlugInDataConnection&gt;
        /// </summary>
        private void MapPluginChannels(IEnumerable<OnePlugInDataConnection> allPlugins)
        {
            foreach (var plugin in allPlugins)
            {
                if (plugin == null || string.IsNullOrEmpty(plugin.name))
                    continue;

                var nameLower = plugin.name.ToLowerInvariant();
                var value = plugin.y;

                // Skip our own status channel
                if (plugin.pluginName == "DynoAI Bridge")
                    continue;

                // Try to identify AFR channels from other plugins
                if (!_snapshot.ContainsKey("afr_front"))
                {
                    if (nameLower.Contains("afr") && (nameLower.Contains("front") || nameLower.Contains("1")))
                    {
                        _snapshot["afr_front"] = Math.Round(value, 2);
                        _snapshot["afr_front_source"] = $"plugin:{plugin.pluginName}";
                    }
                    else if (nameLower.Contains("lambda") && (nameLower.Contains("front") || nameLower.Contains("1")))
                    {
                        // Convert lambda to AFR (gasoline stoich = 14.7)
                        _snapshot["afr_front"] = Math.Round(value * 14.7, 2);
                        _snapshot["afr_front_source"] = $"plugin:{plugin.pluginName}(lambda)";
                    }
                }

                if (!_snapshot.ContainsKey("afr_rear"))
                {
                    if (nameLower.Contains("afr") && (nameLower.Contains("rear") || nameLower.Contains("2")))
                    {
                        _snapshot["afr_rear"] = Math.Round(value, 2);
                        _snapshot["afr_rear_source"] = $"plugin:{plugin.pluginName}";
                    }
                    else if (nameLower.Contains("lambda") && (nameLower.Contains("rear") || nameLower.Contains("2")))
                    {
                        _snapshot["afr_rear"] = Math.Round(value * 14.7, 2);
                        _snapshot["afr_rear_source"] = $"plugin:{plugin.pluginName}(lambda)";
                    }
                }

                // Single AFR (non-cylinder-specific)
                if (!_snapshot.ContainsKey("afr") && !_snapshot.ContainsKey("afr_front"))
                {
                    if (nameLower == "afr" || nameLower == "wideband" || nameLower == "wb o2")
                    {
                        _snapshot["afr"] = Math.Round(value, 2);
                        _snapshot["afr_source"] = $"plugin:{plugin.pluginName}";
                    }
                    else if (nameLower == "lambda")
                    {
                        _snapshot["afr"] = Math.Round(value * 14.7, 2);
                        _snapshot["afr_source"] = $"plugin:{plugin.pluginName}(lambda)";
                    }
                }

                // MAP
                if (!_snapshot.ContainsKey("map_kpa"))
                {
                    if (nameLower.Contains("map") && (nameLower.Contains("kpa") || plugin.unit == "kPa"))
                    {
                        _snapshot["map_kpa"] = Math.Round(value, 1);
                        _snapshot["map_source"] = $"plugin:{plugin.pluginName}";
                    }
                }

                // TPS
                if (!_snapshot.ContainsKey("tps"))
                {
                    if (nameLower == "tps" || nameLower == "throttle" || nameLower.Contains("throttle position"))
                    {
                        _snapshot["tps"] = Math.Round(value, 1);
                    }
                }
            }
        }

        // ── Unit conversions ─────────────────────────────────────────

        private static double SafePowerHP(Power p) => p?.HP ?? 0.0;
        private static double SafePowerKW(Power p) => p?.kW ?? 0.0;
        private static double SafeTorqueFtLb(Torque t) => t?.torqueInLbFt ?? 0.0;
        private static double SafeTorqueNm(Torque t) => t?.torqueInNm ?? 0.0;

        private static double CtoF(double celsius)
        {
            if (double.IsNaN(celsius)) return 0;
            return Math.Round(celsius * 9.0 / 5.0 + 32.0, 1);
        }

        private static double MbarToInHg(double millibar)
        {
            if (double.IsNaN(millibar) || millibar == 0) return 0;
            return Math.Round(millibar * 0.02953, 2);
        }
    }
}
