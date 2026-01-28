# JetDrive Complete Documentation

This folder contains all JetDrive-related documentation from the DynoAI_3 project, including the new NextGen physics-informed analysis features.

---

## Documentation Index

### Setup & Configuration
| File | Description |
|------|-------------|
| [JETDRIVE_HARDWARE_TESTING.md](./JETDRIVE_HARDWARE_TESTING.md) | Complete guide for connecting to real Dynojet hardware |
| [POWER_CORE_JETDRIVE_SETUP.md](./POWER_CORE_JETDRIVE_SETUP.md) | How to configure JetDrive in Power Core software |
| [POWER_CORE_JETDRIVE_FIX.md](./POWER_CORE_JETDRIVE_FIX.md) | Fixing common Power Core configuration issues |

### Testing & Troubleshooting
| File | Description |
|------|-------------|
| [JETDRIVE_TESTING_OPTIONS.md](./JETDRIVE_TESTING_OPTIONS.md) | Testing options (stub mode, CSV upload, simulation) |
| [JETDRIVE_TROUBLESHOOTING.md](./JETDRIVE_TROUBLESHOOTING.md) | Network/multicast diagnostics and troubleshooting |
| [JETDRIVE_DEBUGGING_FEATURES.md](./JETDRIVE_DEBUGGING_FEATURES.md) | Comprehensive debugging guide for real-time features |

### Features & Integration
| File | Description |
|------|-------------|
| [JETDRIVE_DATA_VALIDATION.md](./JETDRIVE_DATA_VALIDATION.md) | Data quality validation system |
| [JETDRIVE_POWER_OPPORTUNITIES_GUIDE.md](./JETDRIVE_POWER_OPPORTUNITIES_GUIDE.md) | "Find Me Power" feature integration |
| [SESSION_REPLAY_JETDRIVE_INTEGRATION.md](./SESSION_REPLAY_JETDRIVE_INTEGRATION.md) | Session replay feature |
| [CONFIDENCE_SCORING_JETDRIVE_INTEGRATION.md](./CONFIDENCE_SCORING_JETDRIVE_INTEGRATION.md) | Tune confidence scoring (A/B/C/D grades) |

### Implementation & History
| File | Description |
|------|-------------|
| [JETDRIVE_IMPLEMENTATION_SUMMARY.md](./JETDRIVE_IMPLEMENTATION_SUMMARY.md) | Complete implementation summary |
| [JETDRIVE_FEATURES_SUMMARY.md](./JETDRIVE_FEATURES_SUMMARY.md) | Feature summary (channel discovery, auto-detection, etc.) |
| [JETDRIVE_MIGRATION_REVIEW.md](./JETDRIVE_MIGRATION_REVIEW.md) | PyQt6 migration code review |

### Developer Reference
| File | Description |
|------|-------------|
| [AGENT_PROMPTS_JETDRIVE_REALTIME_FEATURES.md](./AGENT_PROMPTS_JETDRIVE_REALTIME_FEATURES.md) | AI agent prompts for debugging |

---

## NextGen Analysis Features

DynoAI now includes physics-informed ECU reasoning with mode detection, causal diagnosis, and intelligent test planning.

### Related Specifications
| File | Description |
|------|-------------|
| [NEXTGEN_IMPLEMENTATION_SPEC.md](../specs/NEXTGEN_IMPLEMENTATION_SPEC.md) | Full implementation specification for NextGen workflow |
| [ECU_CALIBRATION_MODEL.md](../specs/ECU_CALIBRATION_MODEL.md) | VE-spark-knock coupling and ECU control theory |
| [DYNO_SHOP_WORKFLOW_INTEGRATION.md](../specs/DYNO_SHOP_WORKFLOW_INTEGRATION.md) | How NextGen fits into real dyno shop operations |

### NextGen Core Modules
| Module | Purpose |
|--------|---------|
| `dynoai/core/log_normalizer.py` | Normalize data sources to canonical columns |
| `dynoai/core/mode_detection.py` | Label samples into operating modes (idle, cruise, WOT, tip-in, etc.) |
| `dynoai/core/surface_builder.py` | Build RPM/MAP surfaces for spark, knock, AFR error |
| `dynoai/core/spark_valley.py` | Detect WOT spark valley behavior per cylinder |
| `dynoai/core/cause_tree.py` | Deterministic hypothesis generation from surfaces |
| `dynoai/core/next_test_planner.py` | Generate prioritized next-test recommendations |
| `dynoai/core/nextgen_payload.py` | Stable JSON schema for all NextGen outputs |

### NextGen Workflow Output
The NextGen analysis produces a unified `NextGenAnalysisPayload` containing:
- **Mode Summary**: Operating region distribution (WOT %, cruise %, transient %)
- **2D Surfaces**: Spark, knock, AFR error grids with hit counts
- **Spark Valley Findings**: Front vs rear cylinder valley depth and RPM band
- **Cause Tree**: Ranked hypotheses with confidence scores and evidence
- **Next-Test Plan**: Prioritized steps to reduce uncertainty and fill coverage gaps

---

## Quick Reference

### Network Configuration
```bash
JETDRIVE_IFACE=<your-ip>           # Network interface IP
JETDRIVE_MCAST_GROUP=239.255.60.60 # Multicast address
JETDRIVE_PORT=22344                # UDP port
```

### JetDrive API Endpoints

#### Hardware Discovery & Connection
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jetdrive/hardware/discover` | GET | Discover JetDrive providers |
| `/api/jetdrive/hardware/discover/multi` | GET | Multi-interface discovery |
| `/api/jetdrive/hardware/channels/discover` | GET | Discover available channels |
| `/api/jetdrive/hardware/connect` | POST | Connect to hardware |
| `/api/jetdrive/hardware/health` | GET | Check connection health |
| `/api/jetdrive/hardware/validate` | GET | Validate hardware configuration |
| `/api/jetdrive/hardware/diagnostics` | GET | Get diagnostic information |

#### Live Data Capture
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jetdrive/hardware/live/start` | POST | Start live data capture |
| `/api/jetdrive/hardware/live/stop` | POST | Stop live data capture |
| `/api/jetdrive/hardware/live/data` | GET | Get live channel data |
| `/api/jetdrive/hardware/live/debug` | GET | Debug live capture |
| `/api/jetdrive/hardware/live/health` | GET | Live capture health status |
| `/api/jetdrive/hardware/live/health/summary` | GET | Health summary |

#### Run Management
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jetdrive/run/<run_id>` | GET | Get run details |
| `/api/jetdrive/run/<run_id>/pvv` | GET | Get PVV data for run |
| `/api/jetdrive/run/<run_id>/report` | GET | Get run report |
| `/api/jetdrive/run/<run_id>/export-text` | GET | Export run as text |
| `/api/jetdrive/upload` | POST | Upload CSV data |

#### Analysis
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jetdrive/analyze` | POST | Run standard analysis |
| `/api/jetdrive/analyze-unified` | POST | Run unified analysis |
| `/api/jetdrive/power-opportunities/<run_id>` | GET | Get power opportunities |

#### Simulator
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jetdrive/simulator/start` | POST | Start dyno simulator |
| `/api/jetdrive/simulator/stop` | POST | Stop simulator |
| `/api/jetdrive/simulator/status` | GET | Get simulator status |
| `/api/jetdrive/simulator/profiles` | GET | List available profiles |
| `/api/jetdrive/simulator/pull` | POST | Execute simulated pull |
| `/api/jetdrive/simulator/pull-data` | GET | Get pull data |
| `/api/jetdrive/simulator/save-pull` | POST | Save pull data |

#### Innovate Wideband
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jetdrive/innovate/ports` | GET | List available serial ports |
| `/api/jetdrive/innovate/connect` | POST | Connect to Innovate device |
| `/api/jetdrive/innovate/disconnect` | POST | Disconnect from device |
| `/api/jetdrive/innovate/status` | GET | Get connection status |

### NextGen API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/nextgen/<run_id>/generate` | POST | Generate NextGen analysis |
| `/api/nextgen/<run_id>` | GET | Get cached analysis payload |
| `/api/nextgen/<run_id>/download` | GET | Download analysis JSON |
| `/api/nextgen/<run_id>/summary` | GET | Get analysis summary |
| `/api/nextgen/<run_id>/surfaces` | GET | Get surface data |
| `/api/nextgen/<run_id>/hypotheses` | GET | Get cause tree hypotheses |
| `/api/nextgen/<run_id>/test-plan` | GET | Get next-test recommendations |

### Required Channels

#### Basic Analysis
| Channel | Required | Purpose |
|---------|----------|---------|
| RPM | Yes | Engine speed |
| Torque | Yes | Load measurement |
| AFR/Lambda | Yes | Air/fuel ratio |
| TPS | Recommended | Throttle position |
| MAP | Recommended | Manifold pressure |

#### NextGen Analysis (Additional)
| Channel | Required | Purpose |
|---------|----------|---------|
| `rpm` | Yes | Engine speed |
| `map_kpa` | Yes | Manifold absolute pressure |
| `tps` | Yes | Throttle position |
| `iat` | Recommended | Intake air temperature |
| `ect` | Recommended | Engine coolant temperature |
| `afr_meas_f` | Recommended | Measured AFR front cylinder |
| `afr_meas_r` | Recommended | Measured AFR rear cylinder |
| `spark_f` | Recommended | Spark timing front cylinder |
| `spark_r` | Recommended | Spark timing rear cylinder |
| `knock` | Optional | Knock sensor activity |

NextGen gracefully degrades when channels are missing, building single-cylinder surfaces and reducing confidence in related hypotheses.

---

## Operating Modes (NextGen)

The mode detection system labels samples into operating states:

| Mode | Description |
|------|-------------|
| `idle` | Low RPM, low TPS, low MAP |
| `cruise` | Steady-state part throttle |
| `tip_in` | Throttle opening transient |
| `tip_out` | Throttle closing transient |
| `wot` | Wide open throttle |
| `decel` | Deceleration fuel cut |
| `heat_soak` | Thermal soak conditions |

---

## Dyno Type Considerations

| Dyno Type | Steady-State Coverage | Transient Data | WOT Coverage |
|-----------|----------------------|----------------|--------------|
| Inertia (Dynojet) | Poor (street logging needed) | Good (accel pulls) | Excellent |
| Eddy Current (Mustang, Dynapack) | Excellent (can dwell) | Moderate | Excellent |

NextGen analysis adapts to your data coverage and recommends targeted tests to fill gaps.

---

*Last Updated: January 27, 2026*
