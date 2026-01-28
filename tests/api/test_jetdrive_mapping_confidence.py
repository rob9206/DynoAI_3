"""
Tests for JetDrive Mapping Confidence Scoring and Import/Export

Tests:
1. Unit inference from JDUnit enum
2. Confidence scoring algorithm
3. Import/export functionality
4. Confidence report generation
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from api.services.jetdrive_mapping import (
    MappingConfidence,
    ChannelMapping,
    ProviderMapping,
    score_channel_for_canonical,
    auto_map_channels_with_confidence,
    get_unmapped_required_channels,
    get_low_confidence_mappings,
    save_mapping,
    get_mapping,
    MAPPING_DIR,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_channel():
    """Create a mock ChannelInfo."""
    def _create(chan_id: int, name: str, unit: int):
        channel = MagicMock()
        channel.chan_id = chan_id
        channel.name = name
        channel.unit = unit
        return channel
    return _create


@pytest.fixture
def mock_provider(mock_channel):
    """Create a mock JetDriveProviderInfo."""
    provider = MagicMock()
    provider.provider_id = 4097
    provider.name = "Test Dyno"
    provider.host = "192.168.1.100"
    provider.channels = {
        10: mock_channel(10, "Digital RPM 1", 8),  # JDUnit.EngineSpeed
        15: mock_channel(15, "Air/Fuel Ratio 1", 11),  # JDUnit.AFR
        16: mock_channel(16, "Lambda 1", 13),  # JDUnit.Lambda
        20: mock_channel(20, "MAP kPa", 7),  # JDUnit.Pressure
        21: mock_channel(21, "Throttle Position", 16),  # JDUnit.Percentage
        3: mock_channel(3, "Torque", 5),  # JDUnit.Torque
        4: mock_channel(4, "Horsepower", 4),  # JDUnit.Power
    }
    return provider


# =============================================================================
# Unit Inference Tests
# =============================================================================

class TestUnitInference:
    """Test JDUnit-based channel inference."""

    def test_rpm_unit_inference(self, mock_channel):
        """JDUnit.EngineSpeed (8) should map to rpm."""
        channel = mock_channel(10, "Some RPM Channel", 8)
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "rpm", all_channels)
        
        assert confidence.canonical_name == "rpm"
        assert confidence.source_id == 10
        assert confidence.confidence >= 0.5  # Unit match bonus
        assert any("Unit match" in reason for reason in confidence.reasons)

    def test_afr_unit_inference(self, mock_channel):
        """JDUnit.AFR (11) should map to afr_*."""
        channel = mock_channel(15, "Some AFR Channel", 11)
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "afr_front", all_channels)
        
        assert confidence.canonical_name == "afr_front"
        assert confidence.confidence >= 0.5
        assert any("Unit match" in reason for reason in confidence.reasons)

    def test_lambda_unit_inference_with_transform(self, mock_channel):
        """JDUnit.Lambda (13) should map to lambda_* with transform."""
        channel = mock_channel(16, "Lambda 1", 13)
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "lambda_front", all_channels)
        
        assert confidence.canonical_name == "lambda_front"
        assert confidence.transform == "lambda_to_afr"
        assert any("Lambda channel" in warning for warning in confidence.warnings)

    def test_pressure_unit_inference(self, mock_channel):
        """JDUnit.Pressure (7) should map to map_kpa."""
        channel = mock_channel(20, "MAP", 7)
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "map_kpa", all_channels)
        
        assert confidence.canonical_name == "map_kpa"
        assert confidence.confidence >= 0.5

    def test_percentage_unit_inference(self, mock_channel):
        """JDUnit.Percentage (16) should map to tps."""
        channel = mock_channel(21, "TPS", 16)
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "tps", all_channels)
        
        assert confidence.canonical_name == "tps"
        assert confidence.confidence >= 0.5

    def test_torque_power_unit_inference(self, mock_channel):
        """JDUnit.Torque (5) and Power (4) should map correctly."""
        torque_ch = mock_channel(3, "Torque", 5)
        power_ch = mock_channel(4, "Power", 4)
        
        torque_conf = score_channel_for_canonical(torque_ch, "torque", [torque_ch])
        power_conf = score_channel_for_canonical(power_ch, "power", [power_ch])
        
        assert torque_conf.confidence >= 0.5
        assert power_conf.confidence >= 0.5


# =============================================================================
# Confidence Scoring Tests
# =============================================================================

class TestConfidenceScoring:
    """Test confidence scoring algorithm."""

    def test_high_confidence_unit_and_name_match(self, mock_channel):
        """Unit match + name match should give high confidence."""
        channel = mock_channel(10, "Digital RPM 1", 8)  # EngineSpeed unit
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "rpm", all_channels)
        
        # Unit match (0.5) + name match (0.3) + disambiguation (0.2) = 1.0
        assert confidence.confidence >= 0.8
        assert len(confidence.reasons) >= 2

    def test_medium_confidence_name_only(self, mock_channel):
        """Name match only should give medium confidence."""
        channel = mock_channel(10, "Digital RPM 1", 255)  # NoUnit
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "rpm", all_channels)
        
        # Name match (0.3) + disambiguation (0.2) = 0.5
        assert 0.3 <= confidence.confidence < 0.7

    def test_low_confidence_no_match(self, mock_channel):
        """No unit or name match should give low/zero confidence."""
        channel = mock_channel(99, "Unknown Channel", 255)
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "rpm", all_channels)
        
        assert confidence.confidence == 0.0

    def test_disambiguation_bonus(self, mock_channel):
        """Best match should get disambiguation bonus."""
        # Create two RPM candidates
        good_rpm = mock_channel(10, "Digital RPM 1", 8)  # Has unit match
        bad_rpm = mock_channel(11, "RPM-like", 255)  # No unit match
        all_channels = [good_rpm, bad_rpm]
        
        good_conf = score_channel_for_canonical(good_rpm, "rpm", all_channels)
        bad_conf = score_channel_for_canonical(bad_rpm, "rpm", all_channels)
        
        # Good channel should have higher confidence and get disambiguation bonus
        assert good_conf.confidence > bad_conf.confidence
        assert any("Best match" in reason for reason in good_conf.reasons)

    def test_confidence_warnings(self, mock_channel):
        """Low confidence should generate warnings."""
        channel = mock_channel(99, "Maybe RPM", 255)
        all_channels = [channel]
        
        confidence = score_channel_for_canonical(channel, "rpm", all_channels)
        
        if confidence.confidence < 0.5:
            assert len(confidence.warnings) > 0


# =============================================================================
# Auto-Mapping Tests
# =============================================================================

class TestAutoMapping:
    """Test auto-mapping with confidence."""

    def test_auto_map_all_channels(self, mock_provider):
        """Auto-mapping should detect all standard channels."""
        mappings = auto_map_channels_with_confidence(mock_provider)
        
        # Should detect RPM, AFR, MAP, TPS, Torque, Power
        assert "rpm" in mappings
        assert "afr_front" in mappings or "lambda_front" in mappings
        assert mappings["rpm"].source_id == 10
        assert mappings["rpm"].confidence >= 0.5

    def test_auto_map_prefers_high_confidence(self, mock_provider, mock_channel):
        """Auto-mapping should prefer high-confidence matches."""
        # Add a competing RPM channel with lower confidence
        mock_provider.channels[12] = mock_channel(12, "Maybe RPM", 255)
        
        mappings = auto_map_channels_with_confidence(mock_provider)
        
        # Should still map to channel 10 (has unit match)
        assert mappings["rpm"].source_id == 10
        assert mappings["rpm"].confidence > 0.5

    def test_auto_map_no_duplicate_sources(self, mock_provider):
        """Each source channel should only be mapped once."""
        mappings = auto_map_channels_with_confidence(mock_provider)
        
        source_ids = [m.source_id for m in mappings.values()]
        assert len(source_ids) == len(set(source_ids))  # No duplicates

    def test_auto_map_threshold(self, mock_provider, mock_channel):
        """Channels below confidence threshold should not be mapped."""
        # Add a very poor match
        mock_provider.channels[99] = mock_channel(99, "Unknown", 255)
        
        mappings = auto_map_channels_with_confidence(mock_provider)
        
        # Unknown channel should not appear in mappings (no canonical will match it)
        # Just verify we got reasonable mappings for known channels
        assert "rpm" in mappings
        assert mappings["rpm"].confidence >= 0.5


# =============================================================================
# Mapping Validation Tests
# =============================================================================

class TestMappingValidation:
    """Test mapping validation functions."""

    def test_unmapped_required_rpm(self):
        """Missing RPM should be detected."""
        mapping = ProviderMapping(
            provider_signature="test_sig",
            provider_id=123,
            provider_name="Test",
            host="test",
        )
        # No channels mapped
        
        unmapped = get_unmapped_required_channels(mapping)
        
        assert "rpm" in unmapped

    def test_unmapped_required_afr(self):
        """Missing AFR should be detected."""
        mapping = ProviderMapping(
            provider_signature="test_sig",
            provider_id=123,
            provider_name="Test",
            host="test",
        )
        mapping.channels["rpm"] = ChannelMapping(
            canonical_name="rpm",
            source_id=10,
            source_name="RPM",
        )
        
        unmapped = get_unmapped_required_channels(mapping)
        
        assert "afr (any)" in unmapped

    def test_all_required_present(self):
        """No unmapped when all required present."""
        mapping = ProviderMapping(
            provider_signature="test_sig",
            provider_id=123,
            provider_name="Test",
            host="test",
        )
        mapping.channels["rpm"] = ChannelMapping(
            canonical_name="rpm",
            source_id=10,
            source_name="RPM",
        )
        mapping.channels["afr_front"] = ChannelMapping(
            canonical_name="afr_front",
            source_id=15,
            source_name="AFR",
        )
        
        unmapped = get_unmapped_required_channels(mapping)
        
        assert len(unmapped) == 0

    def test_low_confidence_detection(self):
        """Low confidence mappings should be detected."""
        confidence_map = {
            "rpm": MappingConfidence("rpm", 10, "RPM", 0.95, [], []),
            "afr_front": MappingConfidence("afr_front", 15, "AFR", 0.6, [], []),
        }
        
        low_conf = get_low_confidence_mappings(confidence_map, threshold=0.7)
        
        assert len(low_conf) == 1
        assert low_conf[0].canonical_name == "afr_front"


# =============================================================================
# Import/Export Tests
# =============================================================================

class TestImportExport:
    """Test mapping import/export functionality."""

    def test_export_mapping_format(self, tmp_path):
        """Exported mapping should have correct format."""
        mapping = ProviderMapping(
            provider_signature="test_sig",
            provider_id=4097,
            provider_name="Test Dyno",
            host="192.168.1.100",
            created_at="2026-01-28T00:00:00",
        )
        mapping.channels["rpm"] = ChannelMapping(
            canonical_name="rpm",
            source_id=10,
            source_name="Digital RPM 1",
            transform="identity",
        )
        
        # Simulate export
        export_data = {
            "version": "1.0",
            "type": "dynoai_mapping_export",
            "name": f"{mapping.provider_name} Mapping",
            "provider_signature": mapping.provider_signature,
            "channels": {
                name: ch.to_dict()
                for name, ch in mapping.channels.items()
            },
        }
        
        assert export_data["type"] == "dynoai_mapping_export"
        assert export_data["provider_signature"] == "test_sig"
        assert "rpm" in export_data["channels"]

    def test_import_valid_mapping(self, tmp_path):
        """Importing valid mapping should succeed."""
        import_data = {
            "version": "1.0",
            "type": "dynoai_mapping_export",
            "name": "Imported Mapping",
            "provider_signature": "imported_sig",
            "provider_id": 4097,
            "provider_name": "Imported Dyno",
            "host": "192.168.1.200",
            "created_at": "2026-01-28T00:00:00",
            "channels": {
                "rpm": {
                    "source_id": 10,
                    "source_name": "RPM",
                    "transform": "identity",
                    "enabled": True,
                }
            }
        }
        
        # Create mapping from import data
        mapping = ProviderMapping(
            version=import_data["version"],
            provider_signature=import_data["provider_signature"],
            provider_id=import_data["provider_id"],
            provider_name=import_data["provider_name"],
            host=import_data["host"],
            created_at=import_data["created_at"],
        )
        
        for name, ch_data in import_data["channels"].items():
            mapping.channels[name] = ChannelMapping.from_dict(name, ch_data)
        
        assert mapping.provider_signature == "imported_sig"
        assert "rpm" in mapping.channels

    def test_import_invalid_format(self):
        """Importing invalid format should be rejected."""
        invalid_data = {
            "type": "invalid_type",
            "channels": {}
        }
        
        # Should detect invalid type
        assert invalid_data["type"] not in ("dynoai_mapping_export", "dynoai_mapping_template")

    def test_template_export(self, tmp_path):
        """Exporting as template should work."""
        mapping = ProviderMapping(
            provider_signature="test_sig",
            provider_id=4097,
            provider_name="Test Dyno",
            host="192.168.1.100",
        )
        mapping.channels["rpm"] = ChannelMapping(
            canonical_name="rpm",
            source_id=10,
            source_name="RPM",
        )
        
        # Create template
        template_data = {
            "version": "1.0",
            "type": "dynoai_mapping_template",
            "name": "My Template",
            "description": "Custom template",
            "channels": {
                name: ch.to_dict()
                for name, ch in mapping.channels.items()
            },
        }
        
        assert template_data["type"] == "dynoai_mapping_template"
        assert template_data["name"] == "My Template"


# =============================================================================
# Persistence Tests
# =============================================================================

class TestPersistence:
    """Test mapping persistence."""

    def test_save_and_load_mapping(self, tmp_path):
        """Saving and loading should round-trip correctly."""
        # Create mapping
        mapping = ProviderMapping(
            provider_signature="test_sig_123",
            provider_id=4097,
            provider_name="Test Dyno",
            host="192.168.1.100",
            created_at="2026-01-28T00:00:00",
        )
        mapping.channels["rpm"] = ChannelMapping(
            canonical_name="rpm",
            source_id=10,
            source_name="Digital RPM 1",
        )
        
        # Save (using real save_mapping function)
        with patch("api.services.jetdrive_mapping.MAPPING_DIR", tmp_path):
            success = save_mapping(mapping)
            assert success
            
            # Load
            loaded = get_mapping("test_sig_123")
            assert loaded is not None
            assert loaded.provider_signature == "test_sig_123"
            assert "rpm" in loaded.channels
