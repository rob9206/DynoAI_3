"""DynoAI GUI Widgets Module - Complex custom widgets"""

from .advanced_features import AdvancedFeaturesWidget
from .afr_target_table import MAP_BINS, RPM_BINS, AFRPreset, AFRTargetTable
from .dyno_config_panel import DrumSpec, DynoConfig, DynoConfigPanel
from .ingestion_health_panel import ChannelHealth, FrameStats, IngestionHealthPanel
from .innovate_afr_panel import AFRGaugeWidget, InnovateAFRPanel
from .live_gauge import CompactGauge, GaugeConfig, NeedleGauge
from .live_ve_table import EnginePreset, LiveVETable
from .tuning_config import TuningConfigWidget
from .ve_heatmap import VEHeatmapWidget

__all__ = [
    # Core tuning widgets
    "TuningConfigWidget",
    "AdvancedFeaturesWidget",
    "VEHeatmapWidget",
    # Live gauge widgets
    "NeedleGauge",
    "CompactGauge",
    "GaugeConfig",
    # Live VE table
    "LiveVETable",
    "EnginePreset",
    # AFR target table
    "AFRTargetTable",
    "AFRPreset",
    "RPM_BINS",
    "MAP_BINS",
    # Hardware panels
    "DynoConfigPanel",
    "DynoConfig",
    "DrumSpec",
    # Innovate wideband
    "InnovateAFRPanel",
    "AFRGaugeWidget",
    # Ingestion health
    "IngestionHealthPanel",
    "ChannelHealth",
    "FrameStats",
]
