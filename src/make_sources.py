"""Create a clean truth table, then render it as three messy source files.

Data generated with a fixed seed for three modelled sites.
- North Plant  -> CSV,  dd/mm/yyyy, gas in m3, numbers with thousands separators
- South Plant  -> Excel, mm/dd/yyyy, electricity in MWh, diesel in US gallons, inconsistent site names
- Depot        -> JSON, ISO dates, electricity and gas in GJ, one duplicate and one missing month
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SEED = 11
GAS_KWH_PER_M3 = 10.55      # representative gross calorific value
KWH_PER_GJ = 277.7778
L_PER_USGAL = 3.785411784


def make_truth(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    months = pd.period_range("2024-01", "2025-12", freq="M")
    base = {"North Plant": (520_000, 210_000, 5_200), "South Plant": (380_000, 160_000, 7_900),
            "Depot": (60_000, 25_000, 14_000)}
    rows = []
    for site, (e, g, d) in base.items():
        for m in months:
            s = 1 + 0.12 * np.cos(2 * np.pi * (m.month - 1) / 12)
            rows += [(site, str(m), "electricity", "kWh", round(e * (2 - s) * rng.normal(1, .04), 1)),
                     (site, str(m), "natural_gas", "kWh", round(g * s * rng.normal(1, .05), 1)),
                     (site, str(m), "diesel", "litre", round(d * rng.normal(1, .07), 1))]
    return pd.DataFrame(rows, columns=["site", "month", "carrier", "unit", "quantity"])


def render(truth: pd.DataFrame, seed: int = SEED) -> None:
    rng = np.random.default_rng(seed + 1)
    RAW.mkdir(parents=True, exist_ok=True)

    n = truth[truth.site == "North Plant"].copy()
    n["date"] = pd.PeriodIndex(n["month"], freq="M").to_timestamp().strftime("%d/%m/%Y")
    gas = n.carrier == "natural_gas"
    n.loc[gas, "quantity"] = n.loc[gas, "quantity"] / GAS_KWH_PER_M3
    n.loc[gas, "unit"] = "m3"
    n["quantity"] = n["quantity"].map(lambda x: f"{x:,.2f}")
    n.rename(columns={"carrier": "Fuel Type", "quantity": "Amount", "unit": "UoM", "site": "Facility"})[
        ["Facility", "date", "Fuel Type", "Amount", "UoM"]].to_csv(RAW / "north_plant.csv", index=False)

    s = truth[truth.site == "South Plant"].copy()
    s["Reading Date"] = pd.PeriodIndex(s["month"], freq="M").to_timestamp().strftime("%m/%d/%Y")
    e = s.carrier == "electricity"; dsl = s.carrier == "diesel"
    s.loc[e, "quantity"] = s.loc[e, "quantity"] / 1000; s.loc[e, "unit"] = "MWh"
    s.loc[dsl, "quantity"] = s.loc[dsl, "quantity"] / L_PER_USGAL; s.loc[dsl, "unit"] = "US gal"
    s["Site"] = rng.choice(["South Plant", "south plant", "S. Plant ", "SOUTH PLANT"], size=len(s))
    s["Energy"] = s["carrier"].map({"electricity": "Electricity", "natural_gas": "Gas", "diesel": "Diesel"})
    s.rename(columns={"quantity": "Qty", "unit": "Unit"})[["Site", "Reading Date", "Energy", "Qty", "Unit"]].to_excel(
        RAW / "south_plant.xlsx", index=False)

    d = truth[truth.site == "Depot"].copy()
    gj = d.carrier.isin(["electricity", "natural_gas"])
    d.loc[gj, "quantity"] = d.loc[gj, "quantity"] / KWH_PER_GJ; d.loc[gj, "unit"] = "GJ"
    d["period_start"] = pd.PeriodIndex(d["month"], freq="M").to_timestamp().strftime("%Y-%m-%d")
    recs = d[["period_start", "carrier", "quantity", "unit"]].to_dict("records")
    recs = [r for r in recs if not (r["period_start"] == "2025-03-01")]   # missing month (gap)
    recs.append(dict(recs[5]))                                               # duplicate record
    (RAW / "depot.json").write_text(json.dumps({"site_name": "Depot", "readings": recs}, indent=1))


if __name__ == "__main__":
    t = make_truth(); t.to_csv(ROOT / "data" / "truth.csv", index=False); render(t)
    print("written", len(t))
