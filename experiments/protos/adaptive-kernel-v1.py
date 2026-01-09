# experiments/protos/adaptive-kernel-v1.py
from typing import List, Optional

GridList = List[List[Optional[float]]]



def kernel_smooth(grid: GridList, passes: int = 2) -> GridList:
    """Adaptive 4-neighbor smoothing.
    - Use fewer neighbors when surroundings are sparse to avoid borrowing too much.
    - If all neighbors exist, average center + 4-neighbors.
    - Never create values in None cells.
    """
    result = [row[:] for row in grid]
    rows = len(result)
    cols = len(result[0]) if rows else 0
    for _ in range(max(1, passes)):
        if rows == 0 or cols == 0:
            return result
        tmp: GridList = [[None for _ in range(cols)] for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                v = result[r][c]
                if v is None:
                    continue
                pool = [v]
                if r > 0 and result[r-1][c] is not None:
                    pool.append(result[r-1][c])  # type: ignore[arg-type]
                if r < rows-1 and result[r+1][c] is not None:
                    pool.append(result[r+1][c])  # type: ignore[arg-type]
                if c > 0 and result[r][c-1] is not None:
                    pool.append(result[r][c-1])  # type: ignore[arg-type]
                if c < cols-1 and result[r][c+1] is not None:
                    pool.append(result[r][c+1])  # type: ignore[arg-type]
                if len(pool) < 3:
                    tmp[r][c] = 0.7*pool[0] + 0.3*(sum(pool)/len(pool))
                else:
                    tmp[r][c] = sum(pool)/len(pool)
        result = tmp
    return result
