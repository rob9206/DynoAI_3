import math

from api.config import DynoConfig


def test_calculate_hp_from_force_matches_formula():
    """
    HP = (Force_lbs × Circumference_ft × RPM) / 33000
    Using defaults: circumference_ft ≈ 4.673 (RT-150 Drum 1)
    """
    cfg = DynoConfig()

    force_lbs = 100.0
    rpm = 3000.0

    hp = cfg.calculate_hp_from_force(force_lbs, rpm)

    expected = (force_lbs * cfg.drum1_circumference_ft * rpm) / 33000.0
    assert abs(hp - expected) < 1e-6


def test_calculate_torque_from_force_uses_radius():
    """
    Torque_ftlb = Force_lbs × Radius_ft
    Radius = Circumference / (2π)
    """
    cfg = DynoConfig()

    force_lbs = 100.0
    radius_ft = cfg.drum1.radius_ft

    tq = cfg.calculate_torque_from_force(force_lbs)

    expected = force_lbs * radius_ft
    assert abs(tq - expected) < 1e-6


