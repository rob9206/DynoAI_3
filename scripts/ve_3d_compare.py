"""3D surface comparison: Generated VE vs Actual PVV VE (front cylinder)."""
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import numpy as np


def inhg_to_kpa(x: float) -> float:
    return round(float(x) * 3.38639, 1)


def read_generated_csv(path: Path):
    with path.open() as f:
        rows = list(csv.reader(f))
    map_bins = [float(x) for x in rows[1][1:]]
    rpms = []
    vals = []
    for row in rows[2:]:
        if not row:
            continue
        rpms.append(int(float(row[0])))
        vals.append([float(v) for v in row[1:]])
    return np.array(rpms), np.array(map_bins), np.array(vals)


def read_pvv_front(pvv_path: Path):
    root = ET.parse(pvv_path).getroot()
    for item in root.findall("Item"):
        if item.get("name") != "VE (MAP based/Front Cyl)":
            continue
        cols = [inhg_to_kpa(float(c.get("label"))) for c in item.find("Columns").findall("Col")]
        rows = []
        values = []
        for row in item.find("Rows").findall("Row"):
            rows.append(int(round(float(row.get("label")) * 1000.0)))
            values.append([float(c.get("value", "0")) for c in row.findall("Cell")])
        seen = set()
        dr, dv = [], []
        for i, r in enumerate(rows):
            if r in seen:
                continue
            seen.add(r)
            dr.append(r)
            dv.append(values[i])
        return np.array(dr), np.array(cols), np.array(dv)
    raise RuntimeError("Front VE table not found in PVV")


def plot_surfaces(gen_rpms, gen_maps, gen_ve, pvv_rpms, pvv_maps, pvv_ve, out_path: Path):
    shared_rpms = sorted(set(gen_rpms) & set(pvv_rpms))
    gen_idx = [list(gen_rpms).index(r) for r in shared_rpms]
    pvv_idx = [list(pvv_rpms).index(r) for r in shared_rpms]

    gen_sub = gen_ve[gen_idx, :]
    pvv_sub = pvv_ve[pvv_idx, :]

    MAP, RPM = np.meshgrid(gen_maps, shared_rpms)
    diff = gen_sub - pvv_sub

    fig = plt.figure(figsize=(20, 14))
    fig.patch.set_facecolor("#1a1a2e")

    cmap_gen = "plasma"
    cmap_pvv = "viridis"
    cmap_diff = "RdBu_r"

    # -- Generated surface --
    ax1 = fig.add_subplot(2, 2, 1, projection="3d")
    ax1.plot_surface(MAP, RPM, gen_sub, cmap=cmap_gen, alpha=0.85, edgecolor="none")
    ax1.set_title("Generated (Physics Model)", color="white", fontsize=13, fontweight="bold", pad=10)
    ax1.set_xlabel("MAP (kPa)", color="white", fontsize=9, labelpad=8)
    ax1.set_ylabel("RPM", color="white", fontsize=9, labelpad=8)
    ax1.set_zlabel("VE %", color="white", fontsize=9, labelpad=8)
    ax1.set_zlim(40, 135)
    ax1.view_init(elev=25, azim=-60)
    _style_3d_ax(ax1)

    # -- Actual PVV surface --
    ax2 = fig.add_subplot(2, 2, 2, projection="3d")
    ax2.plot_surface(MAP, RPM, pvv_sub, cmap=cmap_pvv, alpha=0.85, edgecolor="none")
    ax2.set_title("Actual (PVV Calibration)", color="white", fontsize=13, fontweight="bold", pad=10)
    ax2.set_xlabel("MAP (kPa)", color="white", fontsize=9, labelpad=8)
    ax2.set_ylabel("RPM", color="white", fontsize=9, labelpad=8)
    ax2.set_zlabel("VE %", color="white", fontsize=9, labelpad=8)
    ax2.set_zlim(40, 135)
    ax2.view_init(elev=25, azim=-60)
    _style_3d_ax(ax2)

    # -- Both overlaid --
    ax3 = fig.add_subplot(2, 2, 3, projection="3d")
    ax3.plot_surface(MAP, RPM, gen_sub, color="#ff6b6b", alpha=0.45, edgecolor="none", label="Generated")
    ax3.plot_surface(MAP, RPM, pvv_sub, color="#4ecdc4", alpha=0.45, edgecolor="none", label="Actual")
    ax3.set_title("Overlay (Red = Gen, Teal = Actual)", color="white", fontsize=13, fontweight="bold", pad=10)
    ax3.set_xlabel("MAP (kPa)", color="white", fontsize=9, labelpad=8)
    ax3.set_ylabel("RPM", color="white", fontsize=9, labelpad=8)
    ax3.set_zlabel("VE %", color="white", fontsize=9, labelpad=8)
    ax3.set_zlim(40, 135)
    ax3.view_init(elev=25, azim=-60)
    _style_3d_ax(ax3)

    # -- Difference heatmap (2D top-down) --
    ax4 = fig.add_subplot(2, 2, 4)
    vmax = max(abs(diff.min()), abs(diff.max()))
    im = ax4.pcolormesh(gen_maps, shared_rpms, diff, cmap=cmap_diff, vmin=-vmax, vmax=vmax, shading="auto")
    ax4.set_title("Error Heatmap (Gen - Actual)", color="white", fontsize=13, fontweight="bold", pad=10)
    ax4.set_xlabel("MAP (kPa)", color="white", fontsize=10)
    ax4.set_ylabel("RPM", color="white", fontsize=10)
    ax4.set_facecolor("#16213e")
    ax4.tick_params(colors="white")
    cb = fig.colorbar(im, ax=ax4, pad=0.02)
    cb.set_label("VE % difference", color="white", fontsize=9)
    cb.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color="white")

    mae = np.mean(np.abs(diff))
    rmse = np.sqrt(np.mean(diff ** 2))
    fig.suptitle(
        f"VE Table Comparison  |  Front Cylinder  |  MAE {mae:.1f}%  RMSE {rmse:.1f}%  |  {len(shared_rpms)} shared RPM rows",
        color="white", fontsize=15, fontweight="bold", y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved to: {out_path}")


def _style_3d_ax(ax):
    ax.set_facecolor("#16213e")
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor("#333")
    ax.yaxis.pane.set_edgecolor("#333")
    ax.zaxis.pane.set_edgecolor("#333")
    ax.tick_params(colors="white", labelsize=7)
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.zaxis.label.set_color("white")


if __name__ == "__main__":
    gen_rpms, gen_maps, gen_ve = read_generated_csv(
        Path(r"c:\Dev\DynoAI_3\output\fxdls_baseline\VE_Front_Baseline_FXDLS.csv")
    )
    pvv_rpms, pvv_maps, pvv_ve = read_pvv_front(
        Path(r"c:\Users\dawso\Downloads\valueseport.pvv")
    )
    out = Path(r"c:\Dev\DynoAI_3\output\fxdls_baseline\ve_3d_comparison.png")
    plot_surfaces(gen_rpms, gen_maps, gen_ve, pvv_rpms, pvv_maps, pvv_ve, out)
