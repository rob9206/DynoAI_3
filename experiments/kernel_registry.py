# experiments/kernel_registry.py
"""Central registry for experimental smoothing kernels.

Maps idea-id → (module_path, function_name, default_params) for all
known kernel variants. Enforces consistent resolution and versioning.
"""

from importlib import import_module
from typing import Any, Callable, Dict, Tuple

RegistryEntry = Tuple[str, str, Dict[str, Any]]  # (module, func, defaults)

REGISTRY: Dict[str, RegistryEntry] = {
    "baseline": (
        "experiments.protos.kernel_weighted_v1",
        "kernel_smooth",
        {"passes": 2, "alpha": 0.20, "center_bias": 1.25, "min_hits": 1, "dist_pow": 1},
    ),
    "kernel_weighted_v1": (
        "experiments.protos.kernel_weighted_v1",
        "kernel_smooth",
        {"passes": 2, "alpha": 0.20, "center_bias": 1.25, "min_hits": 1, "dist_pow": 1},
    ),
    "kernel_knock_aware_v1": (
        "experiments.protos.kernel_knock_aware_v1",
        "kernel_smooth",
        {"passes": 2, "gate_lo": 1.0, "gate_hi": 3.0},
    ),
    "k1": (
        "experiments.protos.k1_gradient_limit_v1",
        "kernel_smooth",
        {"passes": 2, "gradient_threshold": 1.0},
    ),
    "k1_gradient_limit_v1": (
        "experiments.protos.k1_gradient_limit_v1",
        "kernel_smooth",
        {"passes": 2, "gradient_threshold": 1.0},
    ),
    "k2": (
        "experiments.protos.k2_coverage_adaptive_v1",
        "kernel_smooth",
        {"passes": 2, "clamp_lo": 7.0, "clamp_hi": 15.0},
    ),
    "k2_coverage_adaptive_v1": (
        "experiments.protos.k2_coverage_adaptive_v1",
        "kernel_smooth",
        {"passes": 2, "clamp_lo": 7.0, "clamp_hi": 15.0},
    ),
    "k3": (
        "experiments.protos.k3_bilateral_v1",
        "kernel_smooth",
        {"passes": 2, "sigma": 0.75},
    ),
    "k3_bilateral_v1": (
        "experiments.protos.k3_bilateral_v1",
        "kernel_smooth",
        {"passes": 2, "sigma": 0.75},
    ),
}


def resolve_kernel(idea_id: str) -> Tuple[Callable, Dict[str, Any], str, str]:
    """Resolve idea-id to (kernel_fn, defaults, module_path, func_name).

    Args:
        idea_id: Kernel identifier from registry keys.

    Returns:
        Tuple of (callable kernel function, default params dict, module path, function name)

    Raises:
        ValueError: Unknown idea-id
        RuntimeError: Registry entry invalid (missing symbol)
    """
    if idea_id not in REGISTRY:
        raise ValueError(
            f"Unknown idea-id '{idea_id}'. Known: {', '.join(sorted(REGISTRY.keys()))}"
        )

    module_path, func_name, defaults = REGISTRY[idea_id]

    try:
        mod = import_module(module_path)
    except ImportError as e:
        raise RuntimeError(
            f"Failed to import module '{module_path}' for idea-id '{idea_id}': {e}"
        )

    fn = getattr(mod, func_name, None)
    if fn is None or not callable(fn):
        raise RuntimeError(
            f"Registry entry invalid for '{idea_id}': {module_path}.{func_name} missing or not callable"
        )

    return fn, dict(defaults), module_path, func_name
