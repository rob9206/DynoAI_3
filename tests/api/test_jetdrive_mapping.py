"""
Tests for JetDrive Channel Mapping Service

Tests:
1. Provider signature computation
2. Transform functions
3. Mapping persistence (save/load)
4. Template system
5. Auto-mapping heuristics
6. Signature change detection
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from api.services.jetdrive_mapping import (
    # Signature
    compute_provider_signature,
    parse_provider_signature,
    # Transforms
    lambda_to_afr,
    afr_to_lambda,
    nm_to_ftlb,
    ftlb_to_nm,
    kw_to_hp,
    hp_to_kw,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    apply_transform,
    TRANSFORMS,
    # Data classes
    ChannelMapping,
    ProviderMapping,
    # Persistence
    get_mapping,
    save_mapping,
    delete_mapping,
    list_mappings,
    MAPPING_DIR,
    # Templates
    get_templates,
    get_template,
    create_mapping_from_template,
    BUILTIN_TEMPLATES,
    # Auto-mapping
    auto_map_channels,
    create_auto_mapping,
    # Application
    apply_mapping_to_sample,
)


# =============================================================================
# Fixtures
# =============================================================================

@dataclass
class MockChannelInfo:
    """Mock ChannelInfo for testing."""
    chan_id: int
    name: str
    unit: int


@dataclass
class MockProvider:
    """Mock JetDriveProviderInfo for testing."""
    provider_id: int
    name: str
    host: str
    port: int
    channels: dict


@pytest.fixture
def mock_provider():
    """Create a mock provider with standard channels."""
    return MockProvider(
        provider_id=0x1001,
        name="Test Dyno",
        host="192.168.1.100",
        port=22344,
        channels={
            10: MockChannelInfo(chan_id=10, name="Digital RPM 1", unit=8),
            15: MockChannelInfo(chan_id=15, name="Air/Fuel Ratio 1", unit=11),
            16: MockChannelInfo(chan_id=16, name="Air/Fuel Ratio 2", unit=11),
            3: MockChannelInfo(chan_id=3, name="Torque", unit=5),
            4: MockChannelInfo(chan_id=4, name="Horsepower", unit=4),
            20: MockChannelInfo(chan_id=20, name="MAP kPa", unit=7),
        },
    )


@pytest.fixture
def temp_mapping_dir(tmp_path):
    """Create a temporary mapping directory."""
    mapping_dir = tmp_path / "jetdrive_mappings"
    mapping_dir.mkdir()
    return mapping_dir


# =============================================================================
# Provider Signature Tests
# =============================================================================

class TestProviderSignature:
    """Test provider signature computation."""

    def test_signature_includes_provider_id(self, mock_provider):
        """Signature should include provider ID."""
        sig = compute_provider_signature(mock_provider)
        assert sig.startswith("4097_")  # 0x1001 = 4097

    def test_signature_includes_host(self, mock_provider):
        """Signature should include host IP."""
        sig = compute_provider_signature(mock_provider)
        assert "192.168.1.100" in sig

    def test_signature_includes_channel_hash(self, mock_provider):
        """Signature should include channel config hash."""
        sig = compute_provider_signature(mock_provider)
        parts = sig.split("_")
        assert len(parts) == 3
        assert len(parts[2]) == 12  # 12-char hash

    def test_signature_changes_with_channels(self, mock_provider):
        """Signature should change when channels change."""
        sig1 = compute_provider_signature(mock_provider)

        # Add a new channel
        mock_provider.channels[30] = MockChannelInfo(chan_id=30, name="TPS", unit=16)
        sig2 = compute_provider_signature(mock_provider)

        assert sig1 != sig2, "Signature should change when channels are added"

    def test_signature_stable_for_same_config(self, mock_provider):
        """Signature should be deterministic for same config."""
        sig1 = compute_provider_signature(mock_provider)
        sig2 = compute_provider_signature(mock_provider)
        assert sig1 == sig2

    def test_parse_signature(self, mock_provider):
        """Test parsing signature back to components."""
        sig = compute_provider_signature(mock_provider)
        provider_id, host, channel_hash = parse_provider_signature(sig)

        assert provider_id == 0x1001
        assert host == "192.168.1.100"
        assert len(channel_hash) == 12

    def test_parse_invalid_signature(self):
        """Test parsing invalid signature raises error."""
        with pytest.raises(ValueError):
            parse_provider_signature("invalid")


# =============================================================================
# Transform Tests
# =============================================================================

class TestTransforms:
    """Test value transform functions."""

    def test_lambda_to_afr(self):
        """Lambda 1.0 = AFR 14.7 (stoich for gasoline)."""
        assert lambda_to_afr(1.0) == pytest.approx(14.7)
        assert lambda_to_afr(0.9) == pytest.approx(13.23)
        assert lambda_to_afr(1.1) == pytest.approx(16.17)

    def test_afr_to_lambda(self):
        """AFR 14.7 = Lambda 1.0."""
        assert afr_to_lambda(14.7) == pytest.approx(1.0)
        assert afr_to_lambda(12.0) == pytest.approx(0.816, rel=0.01)

    def test_nm_to_ftlb(self):
        """100 Nm ≈ 73.76 ft-lb."""
        assert nm_to_ftlb(100) == pytest.approx(73.76, rel=0.01)

    def test_ftlb_to_nm(self):
        """100 ft-lb ≈ 135.6 Nm."""
        assert ftlb_to_nm(100) == pytest.approx(135.6, rel=0.01)

    def test_kw_to_hp(self):
        """100 kW ≈ 134.1 HP."""
        assert kw_to_hp(100) == pytest.approx(134.1, rel=0.01)

    def test_hp_to_kw(self):
        """100 HP ≈ 74.57 kW."""
        assert hp_to_kw(100) == pytest.approx(74.57, rel=0.01)

    def test_celsius_to_fahrenheit(self):
        """0°C = 32°F, 100°C = 212°F."""
        assert celsius_to_fahrenheit(0) == 32
        assert celsius_to_fahrenheit(100) == 212

    def test_fahrenheit_to_celsius(self):
        """32°F = 0°C, 212°F = 100°C."""
        assert fahrenheit_to_celsius(32) == 0
        assert fahrenheit_to_celsius(212) == 100

    def test_apply_transform(self):
        """Test apply_transform function."""
        assert apply_transform(1.0, "lambda_to_afr") == pytest.approx(14.7)
        assert apply_transform(100, "identity") == 100
        assert apply_transform(100, "unknown_transform") == 100  # Falls back to identity

    def test_all_transforms_registered(self):
        """All documented transforms should be in registry."""
        expected = [
            "lambda_to_afr", "afr_to_lambda",
            "nm_to_ftlb", "ftlb_to_nm",
            "kw_to_hp", "hp_to_kw",
            "c_to_f", "f_to_c",
            "identity",
        ]
        for name in expected:
            assert name in TRANSFORMS, f"Transform {name} should be registered"


# =============================================================================
# Data Class Tests
# =============================================================================

class TestDataClasses:
    """Test mapping data classes."""

    def test_channel_mapping_to_dict(self):
        """Test ChannelMapping serialization."""
        mapping = ChannelMapping(
            canonical_name="rpm",
            source_id=10,
            source_name="Digital RPM 1",
            transform="identity",
            enabled=True,
        )
        d = mapping.to_dict()

        assert d["source_id"] == 10
        assert d["source_name"] == "Digital RPM 1"
        assert d["transform"] == "identity"
        assert d["enabled"] is True

    def test_channel_mapping_from_dict(self):
        """Test ChannelMapping deserialization."""
        data = {
            "source_id": 15,
            "source_name": "Air/Fuel Ratio 1",
            "transform": "lambda_to_afr",
            "enabled": True,
        }
        mapping = ChannelMapping.from_dict("afr_front", data)

        assert mapping.canonical_name == "afr_front"
        assert mapping.source_id == 15
        assert mapping.transform == "lambda_to_afr"

    def test_provider_mapping_roundtrip(self, mock_provider):
        """Test ProviderMapping serialization/deserialization roundtrip."""
        original = ProviderMapping(
            provider_signature="4097_192.168.1.100_abc123",
            provider_id=0x1001,
            provider_name="Test Dyno",
            host="192.168.1.100",
            channels={
                "rpm": ChannelMapping("rpm", 10, "Digital RPM 1"),
                "afr_front": ChannelMapping("afr_front", 15, "Air/Fuel Ratio 1", "lambda_to_afr"),
            },
        )

        # Serialize
        data = original.to_dict()
        json_str = json.dumps(data)

        # Deserialize
        restored = ProviderMapping.from_dict(json.loads(json_str))

        assert restored.provider_signature == original.provider_signature
        assert restored.provider_id == original.provider_id
        assert len(restored.channels) == 2
        assert restored.channels["rpm"].source_id == 10

    def test_get_missing_required(self):
        """Test detection of missing required channels."""
        # Only RPM mapped
        mapping = ProviderMapping(
            channels={"rpm": ChannelMapping("rpm", 10, "Digital RPM 1")}
        )
        missing = mapping.get_missing_required()
        assert "afr (any)" in missing  # Missing AFR

        # RPM + AFR mapped
        mapping.channels["afr_front"] = ChannelMapping("afr_front", 15, "AFR 1")
        missing = mapping.get_missing_required()
        assert len(missing) == 0


# =============================================================================
# Persistence Tests
# =============================================================================

class TestMappingPersistence:
    """Test mapping file persistence."""

    def test_save_and_load_mapping(self, mock_provider, temp_mapping_dir):
        """Test saving and loading a mapping file."""
        with patch("api.services.jetdrive_mapping.MAPPING_DIR", temp_mapping_dir):
            sig = "4097_192.168.1.100_abc123"
            mapping = ProviderMapping(
                provider_signature=sig,
                provider_id=0x1001,
                provider_name="Test Dyno",
                host="192.168.1.100",
                channels={
                    "rpm": ChannelMapping("rpm", 10, "Digital RPM 1"),
                },
            )

            # Save
            assert save_mapping(mapping) is True

            # Load
            loaded = get_mapping(sig)
            assert loaded is not None
            assert loaded.provider_signature == sig
            assert "rpm" in loaded.channels

    def test_get_nonexistent_mapping(self, temp_mapping_dir):
        """Test loading a mapping that doesn't exist."""
        with patch("api.services.jetdrive_mapping.MAPPING_DIR", temp_mapping_dir):
            mapping = get_mapping("nonexistent_signature")
            assert mapping is None

    def test_delete_mapping(self, temp_mapping_dir):
        """Test deleting a mapping file."""
        with patch("api.services.jetdrive_mapping.MAPPING_DIR", temp_mapping_dir):
            sig = "to_delete"
            mapping = ProviderMapping(provider_signature=sig)
            save_mapping(mapping)

            # Verify it exists
            assert get_mapping(sig) is not None

            # Delete
            assert delete_mapping(sig) is True

            # Verify it's gone
            assert get_mapping(sig) is None

    def test_list_mappings(self, temp_mapping_dir):
        """Test listing all mappings."""
        with patch("api.services.jetdrive_mapping.MAPPING_DIR", temp_mapping_dir):
            # Save a few mappings
            for i in range(3):
                mapping = ProviderMapping(
                    provider_signature=f"sig_{i}",
                    provider_name=f"Dyno {i}",
                )
                save_mapping(mapping)

            mappings = list_mappings()
            assert len(mappings) == 3


# =============================================================================
# Template Tests
# =============================================================================

class TestTemplates:
    """Test mapping template system."""

    def test_builtin_templates_exist(self):
        """Built-in templates should be available."""
        templates = get_templates()
        assert len(templates) >= len(BUILTIN_TEMPLATES)

        # Check known templates
        template_ids = [t["id"] for t in templates]
        assert "dynojet_rt150" in template_ids
        assert "dynojet_424x" in template_ids

    def test_get_builtin_template(self):
        """Test getting a built-in template."""
        template = get_template("dynojet_rt150")
        assert template is not None
        assert "channels" in template
        assert "rpm" in template["channels"]

    def test_create_mapping_from_template(self, mock_provider):
        """Test creating a mapping from a template."""
        sig = compute_provider_signature(mock_provider)
        mapping = create_mapping_from_template("dynojet_rt150", mock_provider, sig)

        assert mapping is not None
        assert mapping.provider_signature == sig
        assert "rpm" in mapping.channels

    def test_nonexistent_template(self):
        """Test getting a template that doesn't exist."""
        template = get_template("nonexistent_template")
        assert template is None


# =============================================================================
# Auto-Mapping Tests
# =============================================================================

class TestAutoMapping:
    """Test automatic channel mapping heuristics."""

    def test_auto_map_rpm(self, mock_provider):
        """RPM channel should be auto-detected."""
        mappings = auto_map_channels(mock_provider)
        assert "rpm" in mappings
        assert mappings["rpm"].source_name == "Digital RPM 1"

    def test_auto_map_afr(self, mock_provider):
        """AFR channels should be auto-detected."""
        mappings = auto_map_channels(mock_provider)
        # Should detect afr_front from "Air/Fuel Ratio 1"
        assert "afr_front" in mappings or "afr_rear" in mappings

    def test_auto_map_torque_power(self, mock_provider):
        """Torque and Power should be auto-detected."""
        mappings = auto_map_channels(mock_provider)
        assert "torque" in mappings
        assert "power" in mappings

    def test_auto_map_creates_mapping(self, mock_provider):
        """create_auto_mapping should return valid ProviderMapping."""
        sig = compute_provider_signature(mock_provider)
        mapping = create_auto_mapping(mock_provider, sig)

        assert mapping.provider_signature == sig
        assert len(mapping.channels) > 0
        assert mapping.provider_id == mock_provider.provider_id


# =============================================================================
# Mapping Application Tests
# =============================================================================

class TestMappingApplication:
    """Test applying mappings to samples."""

    def test_apply_mapping_direct(self):
        """Test applying mapping without transform."""
        mapping = ProviderMapping(
            channels={
                "rpm": ChannelMapping("rpm", 10, "Digital RPM 1", "identity"),
            }
        )

        canonical, value = apply_mapping_to_sample(mapping, 10, "Digital RPM 1", 3500)

        assert canonical == "rpm"
        assert value == 3500

    def test_apply_mapping_with_transform(self):
        """Test applying mapping with transform."""
        mapping = ProviderMapping(
            channels={
                "afr_front": ChannelMapping("afr_front", 15, "Lambda 1", "lambda_to_afr"),
            }
        )

        canonical, value = apply_mapping_to_sample(mapping, 15, "Lambda 1", 1.0)

        assert canonical == "afr_front"
        assert value == pytest.approx(14.7)

    def test_apply_mapping_unmapped_channel(self):
        """Unmapped channels should return original value."""
        mapping = ProviderMapping(
            channels={
                "rpm": ChannelMapping("rpm", 10, "Digital RPM 1"),
            }
        )

        canonical, value = apply_mapping_to_sample(mapping, 99, "Unknown", 123.4)

        assert canonical is None
        assert value == 123.4


# =============================================================================
# Signature Change Detection Tests
# =============================================================================

class TestSignatureChangeDetection:
    """Test detection of provider config changes."""

    def test_adding_channel_changes_signature(self, mock_provider):
        """Adding a channel should change the signature."""
        sig1 = compute_provider_signature(mock_provider)

        mock_provider.channels[99] = MockChannelInfo(99, "New Channel", 0)
        sig2 = compute_provider_signature(mock_provider)

        assert sig1 != sig2, "Signature should change when channel added"

    def test_removing_channel_changes_signature(self, mock_provider):
        """Removing a channel should change the signature."""
        sig1 = compute_provider_signature(mock_provider)

        del mock_provider.channels[10]  # Remove RPM
        sig2 = compute_provider_signature(mock_provider)

        assert sig1 != sig2, "Signature should change when channel removed"

    def test_renaming_channel_changes_signature(self, mock_provider):
        """Renaming a channel should change the signature."""
        sig1 = compute_provider_signature(mock_provider)

        mock_provider.channels[10] = MockChannelInfo(10, "Renamed RPM", 8)
        sig2 = compute_provider_signature(mock_provider)

        assert sig1 != sig2, "Signature should change when channel renamed"

    def test_host_change_changes_signature(self, mock_provider):
        """Different host should produce different signature."""
        sig1 = compute_provider_signature(mock_provider)

        mock_provider.host = "192.168.1.200"
        sig2 = compute_provider_signature(mock_provider)

        assert sig1 != sig2, "Signature should change when host changes"
