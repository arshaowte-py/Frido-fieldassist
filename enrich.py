#!/usr/bin/env python3
"""
Frido FieldAssist GT dashboard - Product Performance enrichment.

The three Product Performance Flexible Report exports all land with the same
filename prefix, so they are told apart by their header shape rather than name:

  upc      rep x SKU x month pivot of Unique Productive Calls
  sku      one row per visit-line: rep, distributor, beat, shop, SKU, value
  summary  shop channel x category totals (used only as a reconciliation check)

Called by etl.py. Every block degrades to absent if its source is missing.
"""
import os, glob, json
import pandas as pd
import numpy as np

MONTHS = ["April", "May", "June", "July", "August"]


def _num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def classify(path):
    head = pd.read_excel(path, header=None, nrows=2)
    cells = {str(v).strip() for v in head.values.ravel()}
    if "L2Position User" in cells:
        return "upc"
    if "Visit Id" in cells:
        return "sku"
    if "Shop Channel" in cells:
        return "summary"
    return None


def find_sources(src):
    out = {}
    for f in sorted(glob.glob(os.path.join(src, "*ProductPerformance*.xlsx"))):
        kind = classify(f)
        if kind:
            out.setdefault(kind, []).append(f)
    return out


# ------------------------------------------------------------------ upc pivot
def read_upc(paths):
    frames = []
    for p in paths:
        df = pd.read_excel(p, header=[0, 1])
        cols = ["L2", "L1code", "L1", "Product"] + [f"{a}_{b}" for a, b in df.columns[4:]]
        df.columns = cols
        # the export leaves the four key columns blank on repeat rows
        df[["L2", "L1code", "L1", "Product"]] = df[["L2", "L1code", "L1", "Product"]].ffill()
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    for c in ["L2", "L1code", "L1", "Product"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    df.loc[df["L2"] == "", "L2"] = "Unassigned"
    months = [m for m in MONTHS if f"{m}_UPC" in df.columns]
    for m in months:
        df[f"{m}_UPC"] = _num(df[f"{m}_UPC"])
    return df, months


def build_assortment(df, months, sku_cat=None):
    """SKU distribution: how many unique outlets bought each SKU, by month."""
    ucols = [f"{m}_UPC" for m in months]
    df["_total"] = df[ucols].sum(axis=1)

    totals = []
    for m in months:
        c = f"{m}_UPC"
        live = df[df[c] > 0]
        upc = float(df[c].sum())
        reps = int(live["L1"].nunique())
        totals.append({
            "month": m,
            "upc": upc,
            "skus": int(live["Product"].nunique()),
            "reps": reps,
            "skus_per_rep": round(live.groupby("L1")["Product"].nunique().mean(), 1) if reps else 0,
            "upc_per_rep": round(upc / reps, 0) if reps else 0,
        })

    # the final month of a pull is usually mid-month; flag it rather than let it
    # read as a collapse in distribution
    full = list(range(len(totals)))
    if len(totals) > 1 and totals[-1]["upc"] < totals[-2]["upc"] * 0.7:
        full = full[:-1]
    first_m, last_m = months[full[0]], months[full[-1]]

    per_sku = df.groupby("Product").agg(
        total=("_total", "sum"), reps=("L1", "nunique")).reset_index()
    by_month = df.groupby("Product")[ucols].sum()
    per_sku = per_sku.join(by_month, on="Product")
    per_sku = per_sku[per_sku["total"] > 0].sort_values("total", ascending=False)

    grand = float(per_sku["total"].sum())
    cum = per_sku["total"].cumsum()

    def share(n):
        return round(float(cum.iloc[min(n, len(cum)) - 1]) / grand * 100, 1) if len(cum) else 0

    skus = []
    for _, r in per_sku.head(150).iterrows():
        row = {
            "name": str(r["Product"]),
            "total": float(r["total"]),
            "reps": int(r["reps"]),
            "by_month": [float(r[c]) for c in ucols],
        }
        if sku_cat:
            row["cat"] = sku_cat.get(row["name"], "Uncategorised")
        skus.append(row)

    # movement between the first and last complete month in the pull
    fc, lc = f"{first_m}_UPC", f"{last_m}_UPC"
    mv = per_sku.set_index("Product")[[fc, lc]].copy()
    mv["delta"] = mv[lc] - mv[fc]
    gaining = [{"name": str(i), "first": float(r[fc]), "last": float(r[lc]), "delta": float(r["delta"])}
               for i, r in mv.sort_values("delta", ascending=False).head(12).iterrows() if r["delta"] > 0]
    fading = [{"name": str(i), "first": float(r[fc]), "last": float(r[lc]), "delta": float(r["delta"])}
              for i, r in mv.sort_values("delta").head(12).iterrows() if r["delta"] < 0]

    live_last = df[df[lc] > 0]
    reps = []
    for rep, g in df.groupby("L1"):
        sold = g[g["_total"] > 0]
        if not len(sold):
            continue
        top = sold.sort_values("_total", ascending=False).iloc[0]
        reps.append({
            "rep": rep,
            "manager": g["L2"].iloc[0],
            "skus": int(sold["Product"].nunique()),
            "skus_last": int(live_last.loc[live_last["L1"] == rep, "Product"].nunique()),
            "upc": float(sold["_total"].sum()),
            "top_sku": str(top["Product"]),
            "top_share": round(float(top["_total"]) / float(sold["_total"].sum()) * 100, 1),
        })
    reps.sort(key=lambda r: -r["upc"])

    return {
        "months": months,
        "full_months": [months[i] for i in full],
        "partial_month": months[-1] if len(full) < len(months) else None,
        "totals": totals,
        "skus": skus,
        "sku_count": int(len(per_sku)),
        "reps": reps,
        "top10_share": share(10),
        "top25_share": share(25),
        "gaining": gaining,
        "fading": fading,
        "first_month": first_m,
        "last_month": last_m,
    }


def build_hierarchy(df, users):
    """Roll the existing per-rep table up to the L2 manager the UPC pivot names."""
    rep_mgr = (df.groupby("L1")["L2"].agg(lambda s: s.mode().iat[0])).to_dict()
    width = df[df[[c for c in df.columns if c.endswith("_UPC")]].sum(axis=1) > 0] \
        .groupby("L1")["Product"].nunique().to_dict()

    for u in users:
        u["manager"] = rep_mgr.get(u["user"], "Unmapped")
        u["skus"] = int(width.get(u["user"], 0))

    mgrs = {}
    for u in users:
        m = mgrs.setdefault(u["manager"], {
            "name": u["manager"], "reps": 0, "tc": 0, "pc": 0,
            "net": 0.0, "days": 0.0, "outlets": 0, "skus": set()})
        m["reps"] += 1
        m["tc"] += u["tc"]
        m["pc"] += u["pc"]
        m["net"] += u["net"]
        m["days"] += u["days"]
        m["outlets"] += u["outlets"]

    for rep, mgr in rep_mgr.items():
        sub = df[df["L1"] == rep]
        ucols = [c for c in df.columns if c.endswith("_UPC")]
        if mgr in mgrs:
            mgrs[mgr]["skus"] |= set(sub.loc[sub[ucols].sum(axis=1) > 0, "Product"])

    rows = []
    for m in mgrs.values():
        rows.append({
            "name": m["name"], "reps": m["reps"], "tc": m["tc"], "pc": m["pc"],
            "conv": round(m["pc"] / m["tc"] * 100, 1) if m["tc"] else 0,
            "net": m["net"], "days": m["days"], "outlets": m["outlets"],
            "skus": len(m["skus"]),
            "vpd": round(m["tc"] / m["days"], 1) if m["days"] else 0,
            "spd": round(m["net"] / m["days"], 0) if m["days"] else 0,
            "avg_order": round(m["net"] / m["pc"], 0) if m["pc"] else 0,
        })
    rows.sort(key=lambda r: -r["net"])
    return {
        "managers": rows,
        "mapped_reps": int(sum(1 for u in users if u["manager"] != "Unmapped")),
        "unmapped_reps": int(sum(1 for u in users if u["manager"] == "Unmapped")),
    }


# ------------------------------------------------------------------- sku dump
def read_sku(paths):
    df = pd.concat([pd.read_excel(p) for p in paths], ignore_index=True)
    df = df.drop_duplicates()
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    df["Net Value (Order)"] = _num(df["Net Value (Order)"])
    df["Order In Unit"] = _num(df["Order In Unit"])
    for c in ["L1Position User", "Distributor", "Beats", "Shop", "Product Name"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    df.loc[df["Distributor"] == "", "Distributor"] = "Unmapped"
    return df


def build_distributors(df, national_net=None):
    net = float(df["Net Value (Order)"].sum())

    rows = []
    for name, g in df.groupby("Distributor"):
        gnet = float(g["Net Value (Order)"].sum())
        top = g.groupby("Product Name")["Net Value (Order)"].sum().sort_values(ascending=False)
        rows.append({
            "name": name, "net": gnet,
            "visits": int(g["Visit Id"].nunique()),
            "outlets": int(g["Shop"].nunique()),
            "beats": int(g["Beats"].nunique()),
            "skus": int(g["Product Name"].nunique()),
            "reps": int(g["L1Position User"].nunique()),
            "units": float(g["Order In Unit"].sum()),
            "avg_order": round(gnet / g["Visit Id"].nunique(), 0) if g["Visit Id"].nunique() else 0,
            "per_outlet": round(gnet / g["Shop"].nunique(), 0) if g["Shop"].nunique() else 0,
            "top_sku": str(top.index[0]) if len(top) else "",
            "share": round(gnet / net * 100, 1) if net else 0,
        })
    rows.sort(key=lambda r: -r["net"])

    cum, top5, top10 = 0.0, 0.0, 0.0
    for i, r in enumerate(rows):
        cum += r["net"]
        if i == 4:
            top5 = cum
        if i == 9:
            top10 = cum

    # how sticky is a billed outlet inside the window
    per_outlet = df.groupby("Shop")["Visit Id"].nunique()
    repeat = {
        "once": int((per_outlet == 1).sum()),
        "twice": int((per_outlet == 2).sum()),
        "thrice_plus": int((per_outlet >= 3).sum()),
        "total": int(len(per_outlet)),
    }
    repeat["repeat_pct"] = round((repeat["total"] - repeat["once"]) / repeat["total"] * 100, 1) \
        if repeat["total"] else 0

    beats = []
    for (b, d), g in df.groupby(["Beats", "Distributor"]):
        beats.append({
            "beat": b, "distributor": d,
            "net": float(g["Net Value (Order)"].sum()),
            "outlets": int(g["Shop"].nunique()),
            "visits": int(g["Visit Id"].nunique()),
            "skus": int(g["Product Name"].nunique()),
        })
    beats.sort(key=lambda r: -r["net"])

    velocity = []
    vg = df.groupby("Product Name").agg(
        net=("Net Value (Order)", "sum"), units=("Order In Unit", "sum"),
        outlets=("Shop", "nunique"), dists=("Distributor", "nunique")).reset_index()
    vg = vg.sort_values("net", ascending=False)
    for r in vg.head(40).itertuples():
        velocity.append({
            "name": r._1, "net": float(r.net), "units": float(r.units),
            "outlets": int(r.outlets), "dists": int(r.dists),
            "per_outlet": round(float(r.units) / int(r.outlets), 1) if r.outlets else 0,
        })

    out = {
        "rows": rows,
        "count": len(rows),
        "net": net,
        "outlets": int(df["Shop"].nunique()),
        "visits": int(df["Visit Id"].nunique()),
        "beats": int(df["Beats"].nunique()),
        "skus": int(df["Product Name"].nunique()),
        "reps": int(df["L1Position User"].nunique()),
        "from": df["Date"].min().strftime("%d %b %Y") if df["Date"].notna().any() else "",
        "to": df["Date"].max().strftime("%d %b %Y") if df["Date"].notna().any() else "",
        "top5_share": round(top5 / net * 100, 1) if net else 0,
        "top10_share": round(top10 / net * 100, 1) if net else 0,
        "repeat": repeat,
        "beat_rows": beats[:60],
        "velocity": velocity,
    }
    if national_net:
        out["coverage_of_national"] = round(net / national_net * 100, 1)
    return out


# ---------------------------------------------------------------------- entry
def enrich(src, payload, sku_cat=None):
    """Merge Product Performance blocks into an existing aggregates payload."""
    found = find_sources(src)
    if not found:
        print("  no Product Performance exports found - skipping enrichment")
        return payload

    if "upc" in found:
        print(f"  upc pivot: {len(found['upc'])} file(s)")
        df, months = read_upc(found["upc"])
        payload["assortment"] = build_assortment(df, months, sku_cat)
        payload["hierarchy"] = build_hierarchy(df, payload["users"])

    if "sku" in found:
        print(f"  sku dump: {len(found['sku'])} file(s)")
        sdf = read_sku(found["sku"])
        payload["distributors"] = build_distributors(
            sdf, payload.get("kpis", {}).get("net"))

    if "summary" in found:
        payload.setdefault("quality", {})["channel_check"] = True

    return payload


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "./raw"
    agg = sys.argv[2] if len(sys.argv) > 2 else "./aggregates.json"
    p = json.load(open(agg))
    p = enrich(src, p)
    with open(agg, "w") as f:
        json.dump(p, f, separators=(",", ":"), default=float)
    print(f"wrote {agg} ({os.path.getsize(agg)/1024:.0f} KB)")
