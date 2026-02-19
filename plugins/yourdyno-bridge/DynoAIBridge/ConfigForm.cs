using System;
using System.Drawing;
using System.Windows.Forms;

namespace DynoAIBridge
{
    /// <summary>
    /// Settings dialog for the DynoAI Bridge plugin.
    /// Allows users to configure:
    ///   - TCP port for DynoAI connection
    ///   - Aux channel mappings (which aux input carries AFR, MAP, etc.)
    ///   - Auto-detection from other plugins
    ///   - Sample rate limiting
    /// </summary>
    public class ConfigForm : Form
    {
        private readonly BridgeConfig _original;

        // Controls
        private NumericUpDown _nudPort;
        private NumericUpDown _nudAfrFront;
        private NumericUpDown _nudAfrRear;
        private NumericUpDown _nudMap;
        private NumericUpDown _nudTps;
        private NumericUpDown _nudIat;
        private NumericUpDown _nudEngineTemp;
        private CheckBox _chkAutoDetect;
        private NumericUpDown _nudMaxRate;
        private Button _btnOk;
        private Button _btnCancel;

        public ConfigForm(BridgeConfig config)
        {
            _original = config;
            InitializeComponent();
            LoadValues(config);
        }

        private void InitializeComponent()
        {
            Text = "DynoAI Bridge Settings";
            Size = new Size(420, 520);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterParent;

            var y = 15;
            const int labelX = 15;
            const int controlX = 250;
            const int rowHeight = 32;

            // ── TCP Port ─────────────────────────────────────────────

            AddSectionLabel("Connection", labelX, ref y);
            AddLabel("TCP Port:", labelX, y);
            _nudPort = AddNumericUpDown(controlX, y, 1, 65535, 9877);
            y += rowHeight;

            // ── Separator ────────────────────────────────────────────
            y += 10;
            AddSectionLabel("Auxiliary Channel Mapping", labelX, ref y);
            AddLabel("(-1 = not connected)", labelX + 10, y, italic: true, small: true);
            y += 22;

            // ── Aux mappings ─────────────────────────────────────────

            AddLabel("AFR Front Cylinder (aux index):", labelX, y);
            _nudAfrFront = AddNumericUpDown(controlX, y, -1, 15, -1);
            y += rowHeight;

            AddLabel("AFR Rear Cylinder (aux index):", labelX, y);
            _nudAfrRear = AddNumericUpDown(controlX, y, -1, 15, -1);
            y += rowHeight;

            AddLabel("MAP Sensor kPa (aux index):", labelX, y);
            _nudMap = AddNumericUpDown(controlX, y, -1, 15, -1);
            y += rowHeight;

            AddLabel("TPS (aux index):", labelX, y);
            _nudTps = AddNumericUpDown(controlX, y, -1, 15, -1);
            y += rowHeight;

            AddLabel("Intake Air Temp (aux index):", labelX, y);
            _nudIat = AddNumericUpDown(controlX, y, -1, 15, -1);
            y += rowHeight;

            AddLabel("Engine Temp (aux index):", labelX, y);
            _nudEngineTemp = AddNumericUpDown(controlX, y, -1, 15, -1);
            y += rowHeight;

            // ── Auto-detect ──────────────────────────────────────────
            y += 10;
            AddSectionLabel("Advanced", labelX, ref y);

            _chkAutoDetect = new CheckBox
            {
                Text = "Auto-detect AFR/MAP from other YourDyno plugins",
                Location = new Point(labelX, y),
                Size = new Size(350, 24),
                Checked = true
            };
            Controls.Add(_chkAutoDetect);
            y += rowHeight;

            AddLabel("Max sample rate (Hz, 0=unlimited):", labelX, y);
            _nudMaxRate = AddNumericUpDown(controlX, y, 0, 1000, 0);
            y += rowHeight;

            // ── Buttons ──────────────────────────────────────────────
            y += 15;

            _btnOk = new Button
            {
                Text = "OK",
                DialogResult = DialogResult.OK,
                Location = new Point(200, y),
                Size = new Size(80, 30)
            };

            _btnCancel = new Button
            {
                Text = "Cancel",
                DialogResult = DialogResult.Cancel,
                Location = new Point(290, y),
                Size = new Size(80, 30)
            };

            Controls.Add(_btnOk);
            Controls.Add(_btnCancel);

            AcceptButton = _btnOk;
            CancelButton = _btnCancel;
        }

        private void LoadValues(BridgeConfig config)
        {
            _nudPort.Value = config.TcpPort;
            _nudAfrFront.Value = config.AuxIndexAfrFront;
            _nudAfrRear.Value = config.AuxIndexAfrRear;
            _nudMap.Value = config.AuxIndexMap;
            _nudTps.Value = config.AuxIndexTps;
            _nudIat.Value = config.AuxIndexIat;
            _nudEngineTemp.Value = config.AuxIndexEngineTemp;
            _chkAutoDetect.Checked = config.AutoDetectFromPlugins;
            _nudMaxRate.Value = config.MaxSampleRateHz;
        }

        public BridgeConfig GetConfig()
        {
            return new BridgeConfig
            {
                TcpPort = (int)_nudPort.Value,
                AuxIndexAfrFront = (int)_nudAfrFront.Value,
                AuxIndexAfrRear = (int)_nudAfrRear.Value,
                AuxIndexMap = (int)_nudMap.Value,
                AuxIndexTps = (int)_nudTps.Value,
                AuxIndexIat = (int)_nudIat.Value,
                AuxIndexEngineTemp = (int)_nudEngineTemp.Value,
                AutoDetectFromPlugins = _chkAutoDetect.Checked,
                MaxSampleRateHz = (int)_nudMaxRate.Value
            };
        }

        // ── Helper methods for building the form ─────────────────────

        private void AddSectionLabel(string text, int x, ref int y)
        {
            var label = new Label
            {
                Text = text,
                Location = new Point(x, y),
                Size = new Size(360, 20),
                Font = new Font(Font, FontStyle.Bold)
            };
            Controls.Add(label);
            y += 22;
        }

        private void AddLabel(string text, int x, int y, bool italic = false, bool small = false)
        {
            var label = new Label
            {
                Text = text,
                Location = new Point(x, y + 3),
                AutoSize = true
            };
            if (italic || small)
            {
                var size = small ? Font.Size - 1 : Font.Size;
                var style = italic ? FontStyle.Italic : FontStyle.Regular;
                label.Font = new Font(Font.FontFamily, size, style);
                label.ForeColor = Color.Gray;
            }
            Controls.Add(label);
        }

        private NumericUpDown AddNumericUpDown(int x, int y, int min, int max, int defaultVal)
        {
            var nud = new NumericUpDown
            {
                Location = new Point(x, y),
                Size = new Size(80, 24),
                Minimum = min,
                Maximum = max,
                Value = defaultVal
            };
            Controls.Add(nud);
            return nud;
        }
    }
}
