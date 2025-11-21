# experiments/protos/edge-preserve-v1.py
import statistics as stats
from typing import List, Optional, cast

GridList = List[List[Optional[float]]]

def kernel_smooth(grid: GridList, passes: int = 2) -> GridList:
    """Median-biased smoothing.
    Pull each populated cell gently toward the median of its neighbor pool (center+4-neighbors) to avoid
    smearing sharp transitions while still removing isolated noise.
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
                    pool.append(cast(float, result[r-1][c]))
                if r < rows-1 and result[r+1][c] is not None:
                    pool.append(cast(float, result[r+1][c]))
                if c > 0 and result[r][c-1] is not None:
                    pool.append(cast(float, result[r][c-1]))
                if c < cols-1 and result[r][c+1] is not None:
                    pool.append(cast(float, result[r][c+1]))
                med = stats.median(pool)
                tmp[r][c] = 0.6*med + 0.4*v
        result = tmp
    return result
