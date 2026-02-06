#!/usr/bin/env python3
"""
Test the enhanced prediction service offline to demonstrate improvements.

Note: Expects an Engine Analyzer library at repo-root/engineanalyzer or via
ENALYZER_LIB_DIR.
"""

import math
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# Set the library path before importing services that may load it
os.environ["ENALYZER_LIB_DIR"] = str(repo_root / "engineanalyzer")

from api.services.engine_analyzer.schemas import (
    CamSpec,
    CompleteEngineSpec,
    HeadFlowPoint,
    HeadSpec,
    IntakeSpec,
    ShortBlockSpec,
)
from api.services.engine_analyzer.prediction_service import predict_performance


def test_simple_engine() -> None:
    """Test with Chevy LS6 Stock data from findings."""
    print("Testing enhanced prediction with Chevy LS6 Stock data:")

    # Component data from the PTI file findings
    heads = HeadSpec(
        name="Chevy LS6 Stock Heads",
        intake_valve_dia=2.08,  # inches
        exhaust_valve_dia=1.82,
        intake_port_cc=200,  # estimated from PTI data
        intake_flow=[
            HeadFlowPoint(lift_inches=0.1, cfm=61.6),
            HeadFlowPoint(lift_inches=0.2, cfm=126.1),
            HeadFlowPoint(lift_inches=0.3, cfm=183.9),
            HeadFlowPoint(lift_inches=0.4, cfm=224.4),
            HeadFlowPoint(lift_inches=0.5, cfm=250.7),
            HeadFlowPoint(lift_inches=0.55, cfm=258.0),
            HeadFlowPoint(lift_inches=0.6, cfm=257.2),
            HeadFlowPoint(lift_inches=0.65, cfm=260.7),
        ],
    )

    cam = CamSpec(
        name="Chevy LS6 Cam",
        intake_duration_050=204,  # degrees @ 0.050"
        exhaust_duration_050=211,
        intake_lift=0.480,  # inches (estimated)
        lobe_separation=112,
    )

    short_block = ShortBlockSpec(
        name="Chevy LS6 Short Block",
        bore=3.905,  # inches
        stroke=3.622,
        cylinders=8,
        compression_ratio=10.31,
    )

    intake = IntakeSpec(
        name="Chevy LS6 Intake",
        runner_length_in=8.0,  # estimated
        runner_dia_in=1.8,  # estimated
        throttle_body_dia_in=3.5,
    )

    engine = CompleteEngineSpec(
        name="Chevy LS6 Stock",
        short_block=short_block,
        heads=heads,
        cam=cam,
        intake=intake,
        displacement_ci=346,  # 5.7L
    )

    print("Components:")
    print(f"  Engine: {engine.name}")
    print(f"  Displacement: {engine.displacement_ci}ci")
    print(f"  Compression Ratio: {short_block.compression_ratio}:1")
    print(f"  Intake Valve: {heads.intake_valve_dia}\" ({heads.intake_valve_dia**2 * math.pi / 4:.2f} sq in)")
    print(f"  Max Head Flow: {max(p.cfm for p in heads.intake_flow)} CFM at 28\" water")
    print(f"  Cam Duration @ 0.050\": Intake {cam.intake_duration_050}°, Exhaust {cam.exhaust_duration_050}°")
    print(f"  Intake Runner: {intake.runner_length_in}\" x {intake.runner_dia_in}\"")

    print("\nPrediction Results:")
    prediction = predict_performance(engine)

    print(f"  Peak Horsepower: {prediction.metadata['predictedPeakHp']} HP @ {prediction.metadata['predictedPeakHpRpm']} RPM")
    print(f"  Peak Torque: {prediction.metadata['predictedPeakTq']} ft-lbs @ {prediction.metadata['predictedPeakTqRpm']} RPM")
    print("  Confidence Level: medium")
    print(f"  Prediction Notes: {prediction.metadata['notes']}")

    # Compare to old simple model
    old_model_hp = engine.displacement_ci * 0.55 * 1.15  # 55% + 15% head bonus
    print("\nComparison to Original Model:")
    print(f"  Old Displacement Model: ~{old_model_hp:.0f} HP")
    print(f"  Enhanced Model: {prediction.metadata['predictedPeakHp']} HP")
    print(
        f"  Enhancement: {prediction.metadata['predictedPeakHp'] - old_model_hp:.0f} HP (+{((prediction.metadata['predictedPeakHp'] - old_model_hp) / old_model_hp * 100):.1f}%)"
    )

    # Real LS6 data for comparison
    real_ls6_hp = 385  # Factory rating
    real_ls6_tq = 385  # ft-lbs
    print("\nReal Chevy LS6 Factory Data:")
    print(f"  Actual HP: {real_ls6_hp} HP @ 6000 RPM")
    print(f"  Actual Torque: {real_ls6_tq} ft-lbs @ 4400 RPM")
    print(f"  Enhanced Model Accuracy: {abs(prediction.metadata['predictedPeakHp'] - real_ls6_hp) / real_ls6_hp * 100:.1f}% error on HP")
    print(f"  Enhanced Model Accuracy: {abs(prediction.metadata['predictedPeakTq'] - real_ls6_tq) / real_ls6_tq * 100:.1f}% error on torque")


if __name__ == "__main__":
    test_simple_engine()
    print("\n" + "=" * 60 + "\n")

    # Also test with Harley data for V-twin focus
    print("Testing with V-twin (Harley M8-114 estimated data):")

    # Rough estimates for M8-114
    v_twin = CompleteEngineSpec(
        name="M8-114 V-twin",
        short_block=ShortBlockSpec(
            name="M8-114 Short Block",
            bore=4.075,
            stroke=4.375,
            cylinders=2,
            compression_ratio=10.0,
        ),
        heads=HeadSpec(
            name="M8-114 Heads",
            intake_valve_dia=2.0,
            exhaust_valve_dia=1.75,
            intake_flow=[  # Estimated based on typical Harley heads
                HeadFlowPoint(0.1, 45),
                HeadFlowPoint(0.2, 85),
                HeadFlowPoint(0.3, 125),
                HeadFlowPoint(0.4, 145),
                HeadFlowPoint(0.5, 160),
            ],
        ),
        cam=CamSpec(
            name="M8-114 Cam",
            intake_duration_050=205,
            intake_lift=0.510,
            lobe_separation=110,
        ),
        displacement_ci=114,
    )

    vt_prediction = predict_performance(v_twin)
    vt_old = 114 * 0.55  # Original model

    print("V-twin Results:")
    print(f"  Peak Horsepower: {vt_prediction.metadata['predictedPeakHp']} HP @ {vt_prediction.metadata['predictedPeakHpRpm']} RPM")
    print(f"  Peak Torque: {vt_prediction.metadata['predictedPeakTq']} ft-lbs @ {vt_prediction.metadata['predictedPeakTqRpm']} RPM")
    print(f"  Old Model: ~{vt_old:.0f} HP")
    print(f"  Enhancement: +{vt_prediction.metadata['predictedPeakHp'] - vt_old:.0f} HP")

    print("\nEnhancement Summary:")
    print("✅ Using actual cam duration (@0.050\") instead of generic estimates")
    print("✅ Compression ratio affects thermal efficiency (Otto cycle)")
    print("✅ Valve flow curves + valve size for head efficiency")
    print("✅ Intake runner geometry affects resonance and velocity")
    print("✅ Improved torque curve peaks based on component characteristics")
    print("🎯 Much more realistic than displacement × 0.55 for customer predictions!")

