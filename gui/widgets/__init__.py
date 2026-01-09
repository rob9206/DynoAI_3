"""DynoAI GUI Widgets Module - Complex custom widgets"""

from .tuning_config import TuningConfigWidget
from .advanced_features import AdvancedFeaturesWidget
from .ve_heatmap import VEHeatmapWidget
from .live_gauge import NeedleGauge, CompactGauge, GaugeConfig
from .live_ve_table import LiveVETable, EnginePreset
from .afr_target_table import AFRTargetTable, AFRPreset, RPM_BINS, MAP_BINS
from .dyno_config_panel import DynoConfigPanel, DynoConfig, DrumSpec
from .innovate_afr_panel import InnovateAFRPanel, AFRGaugeWidget
from .ingestion_health_panel import IngestionHealthPanel, ChannelHealth, FrameStats

__all__ = [
    # Core tuning widgets
    'TuningConfigWidget', 
    'AdvancedFeaturesWidget', 
    'VEHeatmapWidget',
    
    # Live gauge widgets
    'NeedleGauge',
    'CompactGauge', 
    'GaugeConfig',
    
    # Live VE table
    'LiveVETable',
    'EnginePreset',
    
    # AFR target table
    'AFRTargetTable',
    'AFRPreset',
    'RPM_BINS',
    'MAP_BINS',
    
    # Hardware panels
    'DynoConfigPanel',
    'DynoConfig',
    'DrumSpec',
    
    # Innovate wideband
    'InnovateAFRPanel',
    'AFRGaugeWidget',
    
    # Ingestion health
    'IngestionHealthPanel',
    'ChannelHealth',
    'FrameStats',
]

