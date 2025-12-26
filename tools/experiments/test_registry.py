import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

print(f"Python: {sys.executable}")
print(f"ROOT: {ROOT}")
print(f"sys.path: {sys.path[:3]}")

try:
    from kernel_registry import resolve_kernel
    print("[OK] Import OK")
    
    kernel_fn, defaults, module_path, func_name = resolve_kernel("k3")
    print(f"[OK] Resolved k3: {module_path}.{func_name}")
    print(f"  Defaults: {defaults}")
except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()
