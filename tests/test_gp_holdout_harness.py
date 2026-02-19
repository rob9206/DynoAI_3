"""Holdout validation harness for current sklearn gp_surrogate backend."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pytest

GRID_SHAPES: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
    "10x9_test": (
        np.array(
            [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500],
            dtype=np.float64,
        ),
        np.array([30, 40, 50, 60, 70, 80, 90, 100, 105], dtype=np.float64),
    ),
    "11x5_production": (
        np.array(
            [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500],
            dtype=np.float64,
        ),
        np.array([35, 50, 65, 80, 95], dtype=np.float64),
    ),
    "16x16_budget": (
        np.linspace(1000, 6500, 16).astype(np.float64),
        np.linspace(25, 105, 16).astype(np.float64),
    ),
}

BACKEND = "sklearn"


def _surface(rpm_bins: np.ndarray, map_bins: np.ndarray, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    rr = (rpm_bins - rpm_bins.min()) / max(rpm_bins.max() - rpm_bins.min(), 1.0)
    mm = (map_bins - map_bins.min()) / max(map_bins.max() - map_bins.min(), 1.0)
    out = np.zeros((len(rpm_bins), len(map_bins)))
    for i, r in enumerate(rr):
        for j, m in enumerate(mm):
            out[i, j] = 75.0 + 25.0 * m + 5.0 * np.sin(np.pi * r) + 3.0 * r * m
    out += rng.randn(*out.shape) * 0.5
    return out


def _obs(
    surface: np.ndarray,
    rpm_bins: np.ndarray,
    map_bins: np.ndarray,
    n_obs: int,
    seed: int = 1,
):
    rng = np.random.RandomState(seed)
    out = []
    for _ in range(n_obs):
        ri = rng.randint(0, len(rpm_bins))
        mi = rng.randint(0, len(map_bins))
        out.append(
            {
                "rpm": float(rpm_bins[ri] + rng.uniform(-100, 100)),
                "map": float(map_bins[mi] + rng.uniform(-3, 3)),
                "ve": float(surface[ri, mi] + rng.randn() * 0.5),
                "ri": ri,
                "mi": mi,
            }
        )
    return out


def _split(observations, holdout_frac: float = 0.3, seed: int = 3):
    rng = np.random.RandomState(seed)
    idx = rng.permutation(len(observations))
    n_hold = max(1, int(len(observations) * holdout_frac))
    hold_set = set(idx[:n_hold].tolist())
    train = [o for i, o in enumerate(observations) if i not in hold_set]
    hold = [o for i, o in enumerate(observations) if i in hold_set]
    return train, hold


def _surrogate(rpm_bins: np.ndarray, map_bins: np.ndarray):
    from dynoai_v3.gp_surrogate import VESurrogate

    return VESurrogate(rpm_bins, map_bins, "m8_114")


def _add_obs(s, rpm: float, map_kpa: float, ve: float, pull_number: int = 1):
    from dynoai_v3.gp_surrogate import Observation

    s.add_observation(
        Observation(rpm=rpm, map_kpa=map_kpa, ve_delta=ve, pull_number=pull_number)
    )


@dataclass
class Metrics:
    scenario: str
    grid: str
    mae: Optional[float] = None
    rmse: Optional[float] = None
    predict_ms: Optional[float] = None


_all: List[Metrics] = []


class TestUnfitted:
    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_unfitted(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        s = _surrogate(rpm_bins, map_bins)
        point = s.predict(3500, 90)
        assert point.uncertainty >= 5.0
        pred = s.predict_full_map()
        assert np.all(pred.uncertainty_map >= 5.0)


class TestTemplateOnly:
    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_template_passthrough(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        surf = _surface(rpm_bins, map_bins)
        s = _surrogate(rpm_bins, map_bins)
        s.seed_from_template(surf, rpm_bins, map_bins)
        pred = s.predict_full_map()
        np.testing.assert_array_equal(pred.ve_map, surf)


class TestHoldout:
    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_template_plus_real(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        surf = _surface(rpm_bins, map_bins)
        all_obs = _obs(
            surf,
            rpm_bins,
            map_bins,
            n_obs=min(80, len(rpm_bins) * len(map_bins) * 2),
            seed=10,
        )
        train, hold = _split(all_obs)
        s = _surrogate(rpm_bins, map_bins)
        s.seed_from_template(surf, rpm_bins, map_bins)
        for o in train:
            _add_obs(s, o["rpm"], o["map"], o["ve"], pull_number=1)
        t0 = time.perf_counter()
        pred = s.predict_full_map()
        elapsed = (time.perf_counter() - t0) * 1000

        errs = [pred.ve_map[o["ri"], o["mi"]] - surf[o["ri"], o["mi"]] for o in hold]
        errs = np.asarray(errs)
        mae = float(np.mean(np.abs(errs)))
        rmse = float(np.sqrt(np.mean(errs**2)))
        _all.append(
            Metrics(
                "template_plus_real", grid_name, mae=mae, rmse=rmse, predict_ms=elapsed
            )
        )
        assert mae < 5.0

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_real_only(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        surf = _surface(rpm_bins, map_bins)
        all_obs = _obs(
            surf,
            rpm_bins,
            map_bins,
            n_obs=min(120, len(rpm_bins) * len(map_bins) * 3),
            seed=20,
        )
        train, hold = _split(all_obs)
        s = _surrogate(rpm_bins, map_bins)
        for o in train:
            _add_obs(s, o["rpm"], o["map"], o["ve"], pull_number=1)
        pred = s.predict_full_map()
        errs = [pred.ve_map[o["ri"], o["mi"]] - surf[o["ri"], o["mi"]] for o in hold]
        mae = float(np.mean(np.abs(np.asarray(errs))))
        assert mae < 10.0


class TestEdgeAndCap:
    pytestmark = pytest.mark.validation

    def test_missing_alpha_fallback(self):
        rpm_bins, map_bins = GRID_SHAPES["10x9_test"]
        s = _surrogate(rpm_bins, map_bins)
        for rpm in [2500, 3000, 3500]:
            _add_obs(s, rpm, 100.0, 85.0)
        s._refit()
        if hasattr(s._gp_model, "alpha_"):
            delattr(s._gp_model, "alpha_")
        pred = s.predict_full_map()
        assert np.all(pred.uncertainty_map >= 5.0)

    @pytest.mark.parametrize("grid_name", ["11x5_production", "16x16_budget"])
    def test_cap_size_training(self, grid_name):
        from dynoai_v3.gp_surrogate import _MAX_OBS_FOR_REFIT

        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        surf = _surface(rpm_bins, map_bins)
        all_obs = _obs(
            surf, rpm_bins, map_bins, n_obs=min(_MAX_OBS_FOR_REFIT, 150), seed=30
        )
        train, hold = _split(all_obs, holdout_frac=0.2)
        s = _surrogate(rpm_bins, map_bins)
        for o in train:
            _add_obs(s, o["rpm"], o["map"], o["ve"], pull_number=1)

        t0 = time.perf_counter()
        pred = s.predict_full_map()
        first_ms = (time.perf_counter() - t0) * 1000
        cached = []
        for _ in range(3):
            t1 = time.perf_counter()
            s.predict_full_map()
            cached.append((time.perf_counter() - t1) * 1000)

        errs = [pred.ve_map[o["ri"], o["mi"]] - surf[o["ri"], o["mi"]] for o in hold]
        mae = float(np.mean(np.abs(np.asarray(errs))))
        assert mae < 5.0
        assert first_ms < 5000
        assert float(np.median(cached)) < 10


@pytest.fixture(scope="session", autouse=True)
def _report(request):
    def done():
        if _all:
            print(f"\nGP holdout metrics collected: {len(_all)} ({BACKEND})")

    request.addfinalizer(done)
