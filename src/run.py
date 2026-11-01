from pathlib import Path
import json
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_sources import make_truth, render  # noqa: E402
from pipeline import extract, transform, accuracy  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> dict:
    truth = make_truth(); truth.to_csv(ROOT / "data" / "truth.csv", index=False); render(truth)
    t0 = time.perf_counter()
    clean, report = transform(extract())
    report["runtime_seconds"] = round(time.perf_counter() - t0, 3)
    clean.to_csv(ROOT / "data" / "clean" / "energy_monthly.csv", index=False)
    report["accuracy"] = accuracy(clean, truth)
    (ROOT / "outputs" / "etl_report.json").write_text(json.dumps(report, indent=2))

    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6), sharex=True)
    fig.suptitle("Unified monthly energy data from 3 heterogeneous sources",
                 fontweight="bold")
    for a, carrier in zip(ax, ["electricity", "natural_gas", "diesel"]):
        sub = clean[clean.carrier == carrier].pivot(index="month", columns="site", values="quantity_std")
        sub.plot(ax=a, marker=".")
        a.set_title(f"{carrier} ({clean[clean.carrier == carrier].unit_std.iloc[0]})")
        a.tick_params(axis="x", rotation=45); a.set_xlabel("")
    ax[1].annotate("gap detected: Depot 2025-03", xy=(0.5, 0.02), xycoords="axes fraction", ha="center", fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.92]); fig.savefig(ROOT / "outputs" / "unified_series.png", dpi=130); plt.close(fig)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
