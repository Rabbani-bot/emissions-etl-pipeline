"""Extract-transform-load: three heterogeneous sources -> one validated, standardised table."""
from pathlib import Path
import json
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
UNIT_TO_STD = {  # (carrier, unit) -> (standard unit, multiplier)
    ("electricity", "kWh"): ("kWh", 1.0), ("electricity", "MWh"): ("kWh", 1000.0),
    ("electricity", "GJ"): ("kWh", 277.7778),
    ("natural_gas", "kWh"): ("kWh", 1.0), ("natural_gas", "m3"): ("kWh", 10.55),
    ("natural_gas", "GJ"): ("kWh", 277.7778),
    ("diesel", "litre"): ("litre", 1.0), ("diesel", "US gal"): ("litre", 3.785411784),
}
CARRIER_ALIASES = {"electricity": "electricity", "gas": "natural_gas", "natural_gas": "natural_gas", "diesel": "diesel"}


def canonical_site(name: str) -> str:
    key = re.sub(r"[^a-z]", "", str(name).lower())
    mapping = {"northplant": "North Plant", "southplant": "South Plant", "splant": "South Plant", "depot": "Depot"}
    if key not in mapping:
        raise ValueError(f"Unknown site name: {name!r}")
    return mapping[key]


def extract() -> pd.DataFrame:
    n = pd.read_csv(RAW / "north_plant.csv")
    n = pd.DataFrame({"site": n["Facility"], "date": pd.to_datetime(n["date"], format="%d/%m/%Y"),
                      "carrier": n["Fuel Type"], "quantity": n["Amount"].str.replace(",", "").astype(float),
                      "unit": n["UoM"], "source": "north_plant.csv"})
    s = pd.read_excel(RAW / "south_plant.xlsx")
    s = pd.DataFrame({"site": s["Site"], "date": pd.to_datetime(s["Reading Date"], format="%m/%d/%Y"),
                      "carrier": s["Energy"], "quantity": s["Qty"].astype(float), "unit": s["Unit"],
                      "source": "south_plant.xlsx"})
    j = json.loads((RAW / "depot.json").read_text())
    d = pd.DataFrame(j["readings"])
    d = pd.DataFrame({"site": j["site_name"], "date": pd.to_datetime(d["period_start"], format="%Y-%m-%d"),
                      "carrier": d["carrier"], "quantity": d["quantity"].astype(float), "unit": d["unit"],
                      "source": "depot.json"})
    return pd.concat([n, s, d], ignore_index=True)


def transform(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.copy()
    df["site"] = df["site"].map(canonical_site)
    df["carrier"] = df["carrier"].str.strip().str.lower().map(CARRIER_ALIASES)
    if df["carrier"].isna().any():
        raise ValueError("Unrecognised energy carrier in source data")
    keys = list(zip(df["carrier"], df["unit"].str.strip()))
    unknown = {k for k in keys if k not in UNIT_TO_STD}
    if unknown:
        raise ValueError(f"No unit conversion for {unknown}")
    df["unit_std"] = [UNIT_TO_STD[k][0] for k in keys]
    df["quantity_std"] = df["quantity"] * [UNIT_TO_STD[k][1] for k in keys]
    df["month"] = df["date"].dt.to_period("M").astype(str)
    if (df["quantity_std"] < 0).any():
        raise ValueError("Negative quantities found")

    before = len(df)
    df = df.drop_duplicates(subset=["site", "month", "carrier"], keep="first")
    report = {"rows_extracted": before, "duplicates_removed": before - len(df)}

    expected = pd.MultiIndex.from_product([df["site"].unique(), sorted(df["month"].unique()), df["carrier"].unique()],
                                          names=["site", "month", "carrier"])
    present = pd.MultiIndex.from_frame(df[["site", "month", "carrier"]])
    gaps = expected.difference(present)
    report["gaps"] = [list(g) for g in gaps]
    report["rows_loaded"] = len(df)
    clean = df[["site", "month", "carrier", "unit_std", "quantity_std", "source"]].sort_values(
        ["site", "month", "carrier"]).reset_index(drop=True)
    return clean, report


def accuracy(clean: pd.DataFrame, truth: pd.DataFrame, rel_tol: float = 0.001) -> dict:
    m = truth.merge(clean, on=["site", "month", "carrier"], how="left")
    found = m["quantity_std"].notna()
    match = found & ((m["quantity_std"] - m["quantity"]).abs() <= rel_tol * m["quantity"])
    return {"truth_rows": len(truth), "rows_recovered": int(found.sum()),
            "values_within_0.1pct": int(match.sum()),
            "accuracy_pct_of_recovered": round(100 * match.sum() / found.sum(), 2),
            "max_relative_error": float(((m.loc[found, "quantity_std"] - m.loc[found, "quantity"]).abs()
                                         / m.loc[found, "quantity"]).max())}
