"""
Innovate Motorsports Serial Client

Supports direct serial communication with Innovate DLG-1 and LC-2 wideband O2 controllers.
These devices use Innovate's Modular Tuning System (MTS) protocol over serial/USB.

Protocol Notes:
- DLG-1: Dual wideband controller (2 channels)
- LC-2: Single wideband controller (1 channel)
- Default serial settings: 19200 baud, 8N1
- Data format: Typically sends AFR values in real-time

Usage:
    client = InnovateClient(port="COM3")
    client.connect()

    # Read single sample
    sample = client.read_sample()

    # Continuous reading with callback
    client.start_streaming(callback=lambda s: print(f"AFR: {s.afr}"))
    time.sleep(10)
    client.stop_streaming()
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None
    logger.warning("pyserial not installed. Innovate client will not work.")


class InnovateDeviceType(Enum):
    """Supported Innovate device types."""
    DLG1 = "DLG-1"  # Dual Lambda Gauge
    LC2 = "LC-2"    # Digital Wideband O2 Controller
    AUTO = "AUTO"   # Auto-detect


@dataclass
class InnovateSample:
    """A single data sample from an Innovate device."""
    timestamp: float
    afr: float  # Air/Fuel Ratio
    lambda_value: float | None = None  # Lambda (AFR / 14.7 for gasoline)
    channel: int = 1  # Channel number (1 or 2 for DLG-1)
    device_type: str = ""


class InnovateClient:
    """
    Client for Innovate DLG-1 and LC-2 wideband controllers.

    Connects via serial port and reads AFR data in real-time.
    """

    # Default serial settings for Innovate devices
    DEFAULT_BAUDRATE = 19200
    DEFAULT_BYTESIZE = serial.EIGHTBITS if serial else 8
    DEFAULT_PARITY = serial.PARITY_NONE if serial else 'N'
    DEFAULT_STOPBITS = serial.STOPBITS_ONE if serial else 1
    DEFAULT_TIMEOUT = 1.0

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = DEFAULT_BAUDRATE,
        device_type: InnovateDeviceType = InnovateDeviceType.AUTO,
        calibration_file: str | None = None,
    ):
        """
        Initialize Innovate client.

        Args:
            port: Serial port name (e.g., "COM3" on Windows, "/dev/ttyUSB0" on Linux).
                 If None, will attempt auto-detection.
            baudrate: Serial baud rate (default 19200 for Innovate devices)
            device_type: Device type for protocol selection
            calibration_file: Path to AFR calibration JSON file. If None, uses default config/afr_calibration.json
        """
        if serial is None:
            raise ImportError(
                "pyserial is required for Innovate client. "
                "Install with: pip install pyserial"
            )

        self.port = port
        self.baudrate = baudrate
        self.device_type = device_type
        self.serial_conn: serial.Serial | None = None
        self.connected = False
        self.running = False

        # Streaming
        self._stream_thread: threading.Thread | None = None
        self._stream_callbacks: list[Callable[[InnovateSample], None]] = []
        self._stream_lock = threading.Lock()

        # Latest sample cache
        self._latest_samples: dict[int, InnovateSample] = {}
        self._sample_lock = threading.Lock()
        
        # MTS packet buffer for continuous stream parsing
        self._mts_buffer = bytearray()
        self._mts_packet_size = 10  # DLG-1: B2 84 [ch1: 4 bytes] [ch2: 4 bytes]
        
        # Calibration data
        self._calibration = self._load_calibration(calibration_file)

    def _load_calibration(self, calibration_file: str | None = None) -> dict:
        """
        Load AFR calibration data from JSON file.
        
        Args:
            calibration_file: Path to calibration file. If None, uses default.
            
        Returns:
            Dictionary with calibration data for each channel
        """
        if calibration_file is None:
            # Default to config/afr_calibration.json relative to project root
            project_root = Path(__file__).parent.parent.parent
            calibration_file = project_root / "config" / "afr_calibration.json"
        else:
            calibration_file = Path(calibration_file)
        
        # Default calibration if file doesn't exist
        default_cal = {
            "base_divisor": 409.6,
            "channels": {
                "1": {"enabled": True, "offset_afr": 0.0, "multiplier": 1.0},
                "2": {"enabled": True, "offset_afr": 0.0, "multiplier": 1.0},
            }
        }
        
        if not calibration_file.exists():
            logger.info(f"Calibration file not found: {calibration_file}. Using defaults (no offsets).")
            return default_cal
        
        try:
            with open(calibration_file, 'r') as f:
                cal_data = json.load(f)
            logger.info(f"Loaded AFR calibration from {calibration_file}")
            
            # Log offsets if any
            for ch_num in ["1", "2"]:
                if ch_num in cal_data.get("channels", {}):
                    ch_cal = cal_data["channels"][ch_num]
                    offset = ch_cal.get("offset_afr", 0.0)
                    multiplier = ch_cal.get("multiplier", 1.0)
                    if offset != 0.0 or multiplier != 1.0:
                        logger.info(
                            f"Channel {ch_num}: offset={offset:+.2f} AFR, multiplier={multiplier:.4f}"
                        )
            
            return cal_data
        except Exception as e:
            logger.error(f"Failed to load calibration file {calibration_file}: {e}")
            logger.info("Using default calibration (no offsets)")
            return default_cal

    def _apply_calibration(self, afr: float, channel: int) -> float:
        """
        Apply calibration offset and multiplier to raw AFR reading.
        
        Args:
            afr: Raw AFR value from sensor
            channel: Channel number (1 or 2)
            
        Returns:
            Calibrated AFR value
        """
        ch_str = str(channel)
        
        # Get channel calibration
        channels = self._calibration.get("channels", {})
        if ch_str not in channels:
            return afr
        
        ch_cal = channels[ch_str]
        
        # Check if channel is enabled
        if not ch_cal.get("enabled", True):
            return afr
        
        # Apply offset first
        offset = ch_cal.get("offset_afr", 0.0)
        afr_with_offset = afr + offset
        
        # Then apply multiplier
        multiplier = ch_cal.get("multiplier", 1.0)
        calibrated_afr = afr_with_offset * multiplier
        
        # Log if significant correction
        if abs(calibrated_afr - afr) > 0.1:
            logger.debug(
                f"Channel {channel}: AFR {afr:.2f} -> {calibrated_afr:.2f} "
                f"(offset={offset:+.2f}, mult={multiplier:.4f})"
            )
        
        return calibrated_afr

    def get_calibration_info(self) -> dict:
        """
        Get current calibration information.
        
        Returns:
            Dictionary with calibration data
        """
        return self._calibration.copy()

    def connect(self) -> bool:
        """
        Connect to the Innovate device.

        Returns:
            True if connection successful, False otherwise
        """
        if self.connected:
            return True

        # Auto-detect port if not specified
        if self.port is None:
            self.port = self._auto_detect_port()
            if self.port is None:
                logger.error("No Innovate device found. Please specify port manually.")
                return False

        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.DEFAULT_BYTESIZE,
                parity=self.DEFAULT_PARITY,
                stopbits=self.DEFAULT_STOPBITS,
                timeout=self.DEFAULT_TIMEOUT,
            )

            # Give device time to initialize
            time.sleep(0.5)
            
            # Clear any stale data in buffer and reset MTS buffer
            if self.serial_conn.in_waiting > 0:
                self.serial_conn.reset_input_buffer()
            self._mts_buffer.clear()
            
            # DLG-1 streams MTS data automatically when powered on
            # No initialization command needed - just check for incoming data
            time.sleep(0.3)
            
            if self.serial_conn.in_waiting > 0:
                initial_data = self.serial_conn.read(self.serial_conn.in_waiting)
                logger.info(f"Device streaming: received {len(initial_data)} bytes")
                # Add to buffer for parsing
                self._mts_buffer.extend(initial_data)
            else:
                # Try sending 'G' command as fallback (some devices may need it)
                try:
                    self.serial_conn.write(b'G\r')
                    time.sleep(0.2)
                    if self.serial_conn.in_waiting > 0:
                        initial_data = self.serial_conn.read(self.serial_conn.in_waiting)
                        logger.info(f"Device responding to G command: {len(initial_data)} bytes")
                        self._mts_buffer.extend(initial_data)
                except Exception:
                    pass

            self.connected = True
            logger.info(f"Connected to Innovate device on {self.port}")
            return True

        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the device."""
        self.stop_streaming()

        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

        self.connected = False
        self.serial_conn = None
        logger.info("Disconnected from Innovate device")

    def read_sample(self, channel: int = 1) -> InnovateSample | None:
        """
        Read a single sample from the device using buffered MTS packet parsing.

        Args:
            channel: Channel number (1 or 2, only 1 for LC-2)

        Returns:
            InnovateSample if successful, None otherwise
        """
        if (not self.connected or not self.serial_conn) and not self.connect():
            return None

        try:
            # Read any available data into the buffer
            if self.serial_conn.in_waiting > 0:
                incoming = self.serial_conn.read(self.serial_conn.in_waiting)
                self._mts_buffer.extend(incoming)
            
            # Try to find and parse a complete MTS packet
            sample = self._extract_mts_packet(channel)
            if sample:
                with self._sample_lock:
                    self._latest_samples[channel] = sample
                return sample
            
            # Keep buffer size manageable (avoid memory growth)
            if len(self._mts_buffer) > 1000:
                # Find last sync marker and keep from there
                last_sync = -1
                for i in range(len(self._mts_buffer) - 1, 0, -1):
                    if self._mts_buffer[i] == 0xB2:
                        last_sync = i
                        break
                if last_sync > 0:
                    self._mts_buffer = self._mts_buffer[last_sync:]
                else:
                    self._mts_buffer = self._mts_buffer[-100:]
            
            return None

        except serial.SerialException as e:
            logger.error(f"Error reading from device: {e}")
            self.connected = False
            return None
    
    def _extract_mts_packet(self, channel: int = 1) -> InnovateSample | None:
        """
        Extract and parse a complete MTS packet from the buffer.
        
        Looks for sync pattern (B2 84) and extracts 10-byte packet.
        """
        # Need at least 10 bytes for a complete MTS packet
        while len(self._mts_buffer) >= self._mts_packet_size:
            # Find sync header (B2 84)
            sync_idx = -1
            for i in range(len(self._mts_buffer) - 1):
                if self._mts_buffer[i] == 0xB2 and self._mts_buffer[i + 1] == 0x84:
                    sync_idx = i
                    break
            
            if sync_idx < 0:
                # No sync found - discard all but last byte
                self._mts_buffer = self._mts_buffer[-1:]
                return None
            
            # Discard any data before sync
            if sync_idx > 0:
                self._mts_buffer = self._mts_buffer[sync_idx:]
            
            # Check if we have a complete packet
            if len(self._mts_buffer) < self._mts_packet_size:
                return None
            
            # Extract packet
            packet = bytes(self._mts_buffer[:self._mts_packet_size])
            self._mts_buffer = self._mts_buffer[self._mts_packet_size:]
            
            # Parse the packet
            sample = self._parse_mts_packet(packet, channel)
            if sample:
                return sample
            
            # If parse failed, continue looking for next packet
        
        return None

    def _extract_mts_packet_all_channels(self, channels: list[int]) -> list[InnovateSample]:
        """
        Extract all channel samples from a single MTS packet.
        
        DLG-1 packets contain both channels, so we parse both before
        removing the packet from the buffer.
        """
        samples = []
        
        # Need at least 10 bytes for a complete MTS packet
        if len(self._mts_buffer) < self._mts_packet_size:
            return samples
        
        # Find sync header (B2 84)
        sync_idx = -1
        for i in range(len(self._mts_buffer) - 1):
            if self._mts_buffer[i] == 0xB2 and self._mts_buffer[i + 1] == 0x84:
                sync_idx = i
                break
        
        if sync_idx < 0:
            # No sync found - discard all but last byte
            self._mts_buffer = self._mts_buffer[-1:]
            return samples
        
        # Discard any data before sync
        if sync_idx > 0:
            self._mts_buffer = self._mts_buffer[sync_idx:]
        
        # Check if we have a complete packet
        if len(self._mts_buffer) < self._mts_packet_size:
            return samples
        
        # Extract packet bytes (don't remove from buffer yet)
        packet = bytes(self._mts_buffer[:self._mts_packet_size])
        
        # Parse all requested channels from this packet
        for channel in channels:
            sample = self._parse_mts_packet(packet, channel)
            if sample:
                samples.append(sample)
                with self._sample_lock:
                    self._latest_samples[channel] = sample
        
        # Now remove the packet from the buffer
        self._mts_buffer = self._mts_buffer[self._mts_packet_size:]
        
        return samples

    def start_streaming(
        self, callback: Callable[[InnovateSample], None], channels: list[int] = None
    ) -> bool:
        """
        Start continuous data streaming.

        Args:
            callback: Function to call for each sample
            channels: List of channels to read (default: [1] for LC-2, [1, 2] for DLG-1)

        Returns:
            True if streaming started successfully
        """
        if not self.connected and not self.connect():
            return False

        if channels is None:
            # Auto-detect based on device type
            channels = [1, 2] if self.device_type == InnovateDeviceType.DLG1 else [1]

        with self._stream_lock:
            if self.running:
                logger.warning("Streaming already running")
                return True

            self._stream_callbacks.append(callback)
            self.running = True

            if self._stream_thread is None or not self._stream_thread.is_alive():
                self._stream_thread = threading.Thread(
                    target=self._stream_loop, args=(channels,), daemon=True
                )
                self._stream_thread.start()

        return True

    def stop_streaming(self) -> None:
        """Stop data streaming."""
        with self._stream_lock:
            self.running = False
            self._stream_callbacks.clear()

    def get_latest_sample(self, channel: int = 1) -> InnovateSample | None:
        """Get the most recent sample for a channel."""
        with self._sample_lock:
            return self._latest_samples.get(channel)

    def _stream_loop(self, channels: list[int]) -> None:
        """Background thread for continuous MTS data streaming."""
        logger.info(f"Starting Innovate MTS data stream for channels {channels}")
        
        consecutive_no_data = 0
        max_no_data_warnings = 50  # Warn after ~2.5 seconds of no data

        while self.running:
            try:
                # Read data into buffer first
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    incoming = self.serial_conn.read(self.serial_conn.in_waiting)
                    self._mts_buffer.extend(incoming)
                
                # Extract and process all complete packets in buffer
                got_data = False
                while len(self._mts_buffer) >= self._mts_packet_size:
                    # For DLG-1, each packet contains BOTH channels
                    # Extract all channels from one packet before removing it
                    samples = self._extract_mts_packet_all_channels(channels)
                    
                    if samples:
                        got_data = True
                        consecutive_no_data = 0
                        with self._stream_lock:
                            for sample in samples:
                                for callback in self._stream_callbacks:
                                    try:
                                        callback(sample)
                                    except Exception as e:
                                        logger.error(f"Error in stream callback: {e}")
                    else:
                        break  # No more complete packets
                
                if not got_data:
                    consecutive_no_data += 1
                    if consecutive_no_data == max_no_data_warnings:
                        logger.warning(
                            "No MTS data received from Innovate device. "
                            "Check device connection and ensure it's powered on."
                        )
                        consecutive_no_data = 0  # Reset to avoid spam

                # Small delay to prevent CPU spinning (~12 Hz matches DLG-1 output rate)
                time.sleep(0.08)

            except Exception as e:
                logger.error(f"Error in MTS stream loop: {e}")
                time.sleep(0.1)

        logger.info("Stopped Innovate MTS data stream")

    def _parse_data(self, data: bytes, channel: int = 1) -> InnovateSample | None:
        """
        Parse raw serial data into an InnovateSample.

        Supports Innovate MTS (Modular Tuning System) binary protocol.
        
        MTS Packet Format (DLG-1):
        - Byte 0: 0xB2 (sync header)
        - Byte 1: 0x84 (device/status byte)
        - Bytes 2-5: Channel 1 data (4 bytes)
        - Bytes 6-9: Channel 2 data (4 bytes)
        
        Each channel's 4 bytes contain lambda data encoded as 7-bit words.
        """
        if not data or len(data) < 2:
            return None

        try:
            # Method 1: MTS Binary Protocol (Primary for DLG-1/LC-2)
            sample = self._parse_mts_packet(data, channel)
            if sample:
                return sample
            
            # Method 2: Try to find MTS packet in data stream
            # Look for sync byte 0xB2 followed by 0x84
            for i in range(len(data) - 9):
                if data[i] == 0xB2 and data[i + 1] == 0x84:
                    sample = self._parse_mts_packet(data[i:i + 10], channel)
                    if sample:
                        return sample

            # Method 3: Try ASCII decoding (text-based protocols)
            try:
                text = data.decode('ascii', errors='ignore').strip()
                text = text.replace('\r', '').replace('\n', '').replace('\x00', '').strip()

                if text and len(text) > 0:
                    import re

                    # Look for AFR value (typically 10-20 range for gasoline)
                    afr_match = re.search(r'(\d+\.?\d*)', text)
                    if afr_match:
                        afr = float(afr_match.group(1))

                        if 8.0 <= afr <= 25.0:
                            lambda_value = afr / 14.7
                            return InnovateSample(
                                timestamp=time.time(),
                                afr=afr,
                                lambda_value=lambda_value,
                                channel=channel,
                                device_type=self.device_type.value,
                            )
            except Exception:
                pass

            return None

        except Exception as e:
            logger.debug(f"Error parsing data '{data!r}': {e}")
            return None

    def _parse_mts_packet(self, data: bytes, channel: int = 1) -> InnovateSample | None:
        """
        Parse a 10-byte MTS packet from DLG-1.
        
        Packet format: B2 84 [ch_b: 4 bytes] [ch_a: 4 bytes]
        Note: DLG-1 sends Channel B first (bytes 2-5), then Channel A (bytes 6-9)
        
        Each channel's 4 bytes contain 7-bit packed AFR data:
        - Byte 0: HIGH 7 bits of AFR value
        - Byte 1: LOW 7 bits of AFR value
        - Byte 2: Additional status/function byte
        - Byte 3: Additional status/function byte
        
        AFR calculation: ((byte0 & 0x7F) << 7) | (byte1 & 0x7F) / 409.6
        This formula empirically matches observed DLG-1 data (e.g., 0x47 0x13 -> ~22.4 AFR)
        """
        if len(data) < 10:
            return None
        
        # Verify header
        if data[0] != 0xB2 or data[1] != 0x84:
            return None
        
        # Extract channel data based on requested channel
        # Note: DLG-1 sends Channel B (Sensor B) first, then Channel A
        # So bytes 2-5 = Sensor B, bytes 6-9 = Sensor A
        if channel == 1:  # Sensor A
            ch_data = data[6:10]  # Sensor A: bytes 6-9
        elif channel == 2:  # Sensor B
            ch_data = data[2:6]   # Sensor B: bytes 2-5
        else:
            return None
        
        # Check for error/status conditions in byte 2 and 3
        # Innovate MTS protocol uses specific patterns to indicate errors
        # E2 error (sensor not ready/fault) is indicated by specific byte patterns
        status_byte_2 = ch_data[2]
        status_byte_3 = ch_data[3]
        
        # Debug: Log raw channel data (debug level to avoid spam)
        logger.debug(
            f"Channel {channel} raw bytes: [{ch_data[0]:02X} {ch_data[1]:02X} {status_byte_2:02X} {status_byte_3:02X}]"
        )
        
        # E2 error detection: bytes 2-3 are typically 0x01 0x51 for normal operation
        # However, 0x00 0x02 might indicate "warming up" or "active but not fully ready"
        # Only reject if we get 0x00 0x00 (complete signal loss)
        is_error_state = False
        
        # Check for known error patterns - only reject complete signal loss
        if status_byte_2 == 0x00 and status_byte_3 == 0x00:
            logger.warning(
                "Channel %s: Sensor error state detected (no signal) - bytes "
                "[%02X %02X %02X %02X]",
                channel,
                ch_data[0],
                ch_data[1],
                status_byte_2,
                status_byte_3,
            )
            is_error_state = True
        
        # Log non-standard status but don't reject (might be warming up or transitional state)
        if status_byte_2 == 0x00 and status_byte_3 == 0x02:
            logger.debug(
                "Channel %s: Non-standard status (possibly warming/transitional) "
                "- bytes [%02X %02X %02X %02X]",
                channel,
                ch_data[0],
                ch_data[1],
                status_byte_2,
                status_byte_3,
            )
        
        # If in error state, return None (don't report invalid AFR)
        if is_error_state:
            return None
        
        # Decode lambda using 7-bit word encoding
        # DLG-1 uses bytes 0 and 1 for the AFR data (7-bit packed)
        # Byte 0 is HIGH, Byte 1 is LOW
        low_byte = ch_data[1] & 0x7F   # Byte 1: low 7 bits
        high_byte = ch_data[0] & 0x7F  # Byte 0: high 7 bits
        
        # Combine into 14-bit value
        raw_value = (high_byte << 7) | low_byte
        
        # Get base divisor from calibration (defaults to 409.6)
        base_divisor = self._calibration.get("base_divisor", 409.6)
        
        # Convert to AFR using empirically determined DLG-1 formula
        # AFR = raw_value / 409.6 (matches observed data: 0x47 0x13 -> ~22.4 AFR)
        afr_raw = raw_value / base_divisor
        
        # Apply calibration offset and multiplier for this channel
        afr = self._apply_calibration(afr_raw, channel)
        
        # Calculate lambda from AFR (gasoline stoich = 14.7)
        lambda_value = afr / 14.7
        
        # Sanity check AFR range; allow lean warmup/free-air readings
        # Some sensors report ~28–30 AFR when not in exhaust, so keep a wider guard.
        if not (6.0 <= afr <= 35.0):
            logger.debug(f"AFR value {afr:.1f} out of range for raw={raw_value}")
            return None
        
        # Extract warmup status from byte 0 (bit 6 when masked)
        # Note: We already masked with 0x7F, so check original byte
        is_warmup = (ch_data[0] & 0x40) != 0
        
        logger.debug(
            f"MTS decode: ch{channel} raw={raw_value} AFR={afr:.1f} lambda={lambda_value:.3f} "
            f"status=[{ch_data[0]:02X} {ch_data[1]:02X} {status_byte_2:02X} {status_byte_3:02X}] warmup={is_warmup}"
        )
        
        return InnovateSample(
            timestamp=time.time(),
            afr=round(afr, 1),
            lambda_value=round(lambda_value, 3),
            channel=channel,
            device_type=self.device_type.value,
        )

    def _auto_detect_port(self) -> str | None:
        """
        Attempt to auto-detect Innovate device port.

        Looks for USB serial devices that might be Innovate controllers.
        """
        if serial is None:
            return None

        try:
            ports = serial.tools.list_ports.comports()

            # Look for common Innovate device identifiers
            # These may vary by system and driver
            innovate_keywords = ['innovate', 'ftdi', 'ch340', 'cp210']

            for port in ports:
                port_str = str(port).lower()
                if any(keyword in port_str for keyword in innovate_keywords):
                    logger.info(f"Auto-detected potential Innovate device: {port.device}")
                    return port.device

            # If no specific match, try first available port (user can override)
            if ports:
                logger.info(f"Using first available port: {ports[0].device}")
                return ports[0].device

            return None

        except Exception as e:
            logger.error(f"Error during port auto-detection: {e}")
            return None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


def list_available_ports() -> list[dict]:
    """
    List all available serial ports.

    Returns:
        List of dicts with port info: [{"port": "COM3", "description": "..."}, ...]
    """
    if serial is None:
        return []

    try:
        ports = serial.tools.list_ports.comports()
        return [
            {
                "port": port.device,
                "description": port.description,
                "manufacturer": port.manufacturer,
                "hwid": port.hwid,
            }
            for port in ports
        ]
    except Exception as e:
        logger.error(f"Error listing ports: {e}")
        return []

