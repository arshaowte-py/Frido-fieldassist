#!/usr/bin/env python3
"""
Frido FieldAssist GT dashboard - ETL
Reads the raw FieldAssist exports and emits aggregates.json.

Usage:  python3 etl.py [SRC_DIR] [OUT_JSON]
Default SRC_DIR = ./raw
"""
import sys, os, glob, json, re
import pandas as pd
import numpy as np
from enrich import enrich

SRC = sys.argv[1] if len(sys.argv) > 1 else "./raw"
OUT = sys.argv[2] if len(sys.argv) > 2 else "./aggregates.json"

MONTH_ORDER = ["April", "May", "June", "July", "August"]


def one(pattern):
    hits = sorted(glob.glob(os.path.join(SRC, pattern)))
    if not hits:
        raise FileNotFoundError(f"no file matching {pattern} in {SRC}")
    return hits[0]


def many(pattern):
    return sorted(glob.glob(os.path.join(SRC, pattern)))


def unarmour(s):
    """FieldAssist CSV exports wrap every cell as ="value" to stop Excel mangling."""
    if not isinstance(s, str):
        return s
    m = re.match(r'^="(.*)"$', s.strip())
    return m.group(1) if m else s


def num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)


def clean_str(series):
    return series.fillna("").astype(str).str.strip()


# ---------------------------------------------------------------- load
print("reading order dump(s) ...")
dump_files = many("Secondary_Order_Dump*.xlsx")
assert dump_files, "no Secondary_Order_Dump file found in raw/"
parts = []
for f in dump_files:
    p = pd.read_excel(f, sheet_name=0)
    print(f"  {os.path.basename(f)}: {len(p):,} rows")
    parts.append(p)
dump = pd.concat(parts, ignore_index=True, sort=False)
# NOTE: Order No is repeated once per product line within an order, so we do NOT
# de-dupe it. FieldAssist exports are pulled on non-overlapping date ranges, so
# duplicate Order Nos across files should not occur - flag if they do.
overlap = dump["Order No"].duplicated(keep=False).sum() - dump.groupby("Order No").size().gt(1).sum() * 0
if len(parts) > 1:
    per_file = [set(p["Order No"]) for p in parts]
    common = set.intersection(*per_file)
    if common:
        print(f"  WARNING: {len(common)} Order Nos appear in more than one export file - dedupe recommended")
dump["Order Date"] = pd.to_datetime(dump["Order Date"], errors="coerce")
dump["NetValue"] = num(dump["NetValue"])
dump["Qty ( StdUnit )"] = num(dump["Qty ( StdUnit )"])
for c in ["Zone", "Region", "Outlet Type", "PrimaryCategory", "ProductDivision",
          "SecondaryCategory", "Product", "No Sales Reason Category",
          "No Sales Reason", "User", "User Position Level", "Beat", "Order Type"]:
    dump[c] = clean_str(dump[c])
dump.loc[dump["Zone"] == "", "Zone"] = "Unmapped"
dump.loc[dump["Outlet Type"] == "", "Outlet Type"] = "Untagged"

print("reading outlet master ...")
outl = pd.read_excel(one("Outlet_Dump_GeoHierarchy*.xlsx"), sheet_name="Details")
outl = outl.drop_duplicates(subset=["Outlet Erp Id"]).copy()
for c in ["Zone", "Region", "Outlets Type", "Outlets Channel", "Territory"]:
    outl[c] = clean_str(outl[c])
outl.loc[outl["Outlets Type"] == "", "Outlets Type"] = "Untagged"
outl.loc[outl["Zone"] == "", "Zone"] = "Unmapped"

print("reading users ...")
users = pd.read_csv(one("Frido_Users*.csv"))
for c in users.columns:
    users[c] = users[c].map(unarmour)
users["is Active"] = users["is Active"].astype(str).str.lower().eq("true")
users["is Field"] = users["is Field"].astype(str).str.lower().eq("true")
users["DOJ"] = pd.to_datetime(users["DOJ"], errors="coerce")
for c in ["Designation", "Position Level", "Region", "Position", "User Name"]:
    users[c] = clean_str(users[c])
users.loc[users["Designation"] == "", "Designation"] = "Unassigned"
users.loc[users["Position Level"] == "", "Position Level"] = "Unassigned"
users.loc[users["Region"] == "", "Region"] = "Unmapped"

print("reading beats ...")
beats = pd.read_csv(one("Frido_Beats*.csv"))
for c in beats.columns:
    beats[c] = beats[c].map(unarmour)
beats["Mapped Outlets"] = num(beats["Mapped Outlets"])
beats["is Active"] = beats["is Active"].astype(str).str.lower().eq("true")

print("reading productivity ...")
prod_frames = []
for f in many("Employee_Productivity_Report*.xlsx"):
    tag = re.search(r"(\d{2})-(\d{2})-(\d{2})_to_", os.path.basename(f))
    mon = int(tag.group(2))
    p = pd.read_excel(f, sheet_name="Employee Productivity Report")
    p.columns = [str(c).strip() for c in p.columns]
    p["_month"] = MONTH_ORDER[mon - 4] if 4 <= mon <= 8 else str(mon)
    prod_frames.append(p)
prod = pd.concat(prod_frames, ignore_index=True)
for c in ["TC", "PC", "Total Present", "Absent", "Count Retailing Days", "Count Total Days"]:
    prod[c] = num(prod[c])
prod["User"] = clean_str(prod["User"])
prod["Zone"] = clean_str(prod["Zone"])
prod["Region"] = clean_str(prod["Region"])
prod["Position of Employee"] = clean_str(prod["Position of Employee"])
prod.loc[prod["Position of Employee"] == "", "Position of Employee"] = "Unassigned"

print("reading beat coverage ...")
bvc = pd.read_excel(one("Beat_Visit_Coverage*.xlsx"), sheet_name="BVCR")
bvc["Net Sale Value"] = num(bvc["Net Sale Value"])
bvc["Zone"] = clean_str(bvc["Zone"])

# --------------------------------------------------- quarter scope
PERIODS = ["April", "May", "June", "July", "August"]
Q = dump[dump["Period"].isin(PERIODS)].copy()
prodQ = prod[prod["_month"].isin(PERIODS)].copy()

# A "call" is one Order No. Productive = that call booked value.
call = (Q.groupby("Order No")
          .agg(zone=("Zone", "first"),
               region=("Region", "first"),
               otype=("Outlet Type", "first"),
               user=("User", "first"),
               level=("User Position Level", "first"),
               outlet=("Outlet Erp Id", "first"),
               period=("Period", "first"),
               date=("Order Date", "first"),
               value=("NetValue", "sum"),
               lines=("Product", lambda s: (s != "").sum()),
               reason_cat=("No Sales Reason Category", "first"),
               reason=("No Sales Reason", "first"))
          .reset_index())
call["productive"] = call["value"] > 0

TC = len(call)
PC = int(call["productive"].sum())
NET = float(call["value"].sum())
present_days = float(prodQ["Total Present"].sum())

# --------------------------------------------------- headline KPIs
kpis = {
    "quarter": "Apr–Aug 2026",
    "users_total": int(len(users)),
    "users_active": int(users["is Active"].sum()),
    "users_field": int((users["is Field"] & users["is Active"]).sum()),
    "outlets": int(len(outl)),
    "beats": int(len(beats)),
    "beats_active": int(beats["is Active"].sum()),
    "tc": TC,
    "pc": PC,
    "conv": round(PC / TC * 100, 1) if TC else 0,
    "net": NET,
    "avg_order": round(NET / PC, 0) if PC else 0,
    "present_days": present_days,
    "visits_per_day": round(TC / present_days, 1) if present_days else 0,
    "sales_per_day": round(NET / present_days, 0) if present_days else 0,
    "outlets_ordered": int(call.loc[call["productive"], "outlet"].nunique()),
    "outlets_visited": int(call["outlet"].nunique()),
    "lines": int(call["lines"].sum()),
    "lines_per_pc": round(call.loc[call["productive"], "lines"].mean(), 2) if PC else 0,
}
kpis["coverage_pct"] = round(kpis["outlets_visited"] / kpis["outlets"] * 100, 1)
kpis["billed_pct"] = round(kpis["outlets_ordered"] / kpis["outlets"] * 100, 1)

# --------------------------------------------------- monthly trend
monthly = []
for m in PERIODS:
    c = call[call["period"] == m]
    p = prodQ[prodQ["_month"] == m]
    days = float(p["Total Present"].sum())
    monthly.append({
        "month": m,
        "tc": len(c),
        "pc": int(c["productive"].sum()),
        "conv": round(c["productive"].mean() * 100, 1) if len(c) else 0,
        "net": float(c["value"].sum()),
        "users": int((p["Total Present"] > 0).sum()),
        "days": days,
        "vpd": round(len(c) / days, 1) if days else 0,
        "spd": round(float(c["value"].sum()) / days, 0) if days else 0,
    })

# full 5-month headcount / activity arc from productivity
arc = []
for m in MONTH_ORDER:
    p = prod[prod["_month"] == m]
    if not len(p):
        continue
    arc.append({
        "month": m,
        "roster": int(len(p)),
        "active": int((p["User Status"].astype(str) == "Active").sum()) if "User Status" in p else int(len(p)),
        "tc": int(p["TC"].sum()),
        "pc": int(p["PC"].sum()),
        "conv": round(p["PC"].sum() / p["TC"].sum() * 100, 1) if p["TC"].sum() else 0,
    })

# --------------------------------------------------- people
def vc(series, label="name"):
    s = series.value_counts()
    return [{label: str(k), "n": int(v)} for k, v in s.items()]

people = {
    "by_designation": vc(users["Designation"]),
    "by_level": vc(users["Position Level"]),
    "by_region": vc(users.loc[users["is Active"], "Region"])[:14],
    "active": int(users["is Active"].sum()),
    "inactive": int((~users["is Active"]).sum()),
    "field": int(users["is Field"].sum()),
    "joiners": [],
}
j = users.dropna(subset=["DOJ"]).copy()
j["m"] = j["DOJ"].dt.to_period("M").astype(str)
for k, v in sorted(j["m"].value_counts().items()):
    people["joiners"].append({"month": k, "n": int(v)})
people["joiners"] = people["joiners"][-14:]

# per-user performance table (quarter)
pu = (call.groupby("user")
        .agg(tc=("Order No", "count"), pc=("productive", "sum"),
             net=("value", "sum"), zone=("zone", "first"),
             level=("level", "first"), outlets=("outlet", "nunique"))
        .reset_index())
days_u = prodQ.groupby("User")["Total Present"].sum()
pu["days"] = pu["user"].map(days_u).fillna(0)
pu["conv"] = (pu["pc"] / pu["tc"] * 100).round(1)
pu["vpd"] = np.where(pu["days"] > 0, (pu["tc"] / pu["days"]).round(1), 0)
pu["spd"] = np.where(pu["days"] > 0, (pu["net"] / pu["days"]).round(0), 0)
pu["level"] = pu["level"].replace("", "Unassigned")
pu = pu.sort_values("net", ascending=False)
user_rows = [{"user": r.user, "zone": r.zone, "level": r.level, "tc": int(r.tc),
              "pc": int(r.pc), "conv": float(r.conv), "net": float(r.net),
              "days": float(r.days), "vpd": float(r.vpd), "spd": float(r.spd),
              "outlets": int(r.outlets)} for r in pu.itertuples()]

# people on roster with zero calls in the quarter
called = set(call["user"])
idle = users[users["is Active"] & users["is Field"] & ~users["User Name"].isin(called)]
people["idle"] = int(len(idle))
people["idle_names"] = sorted(idle["User Name"].tolist())[:40]

# --------------------------------------------------- no-sale analysis
ns = call[~call["productive"]].copy()
ns.loc[ns["reason_cat"] == "", "reason_cat"] = "Not recorded"
ns.loc[ns["reason"] == "", "reason"] = "Not recorded"

nosale = {
    "total": int(len(ns)),
    "by_category": [{"name": k, "n": int(v)} for k, v in ns["reason_cat"].value_counts().items()],
    "by_reason": [],
    "by_zone": [],
    "by_type": [],
}
for z, g in ns.groupby("zone"):
    tot = int((call["zone"] == z).sum())
    nosale["by_zone"].append({"zone": z, "n": int(len(g)), "tc": tot,
                              "pct": round(len(g) / tot * 100, 1) if tot else 0})
reason_cat_map = ns.groupby("reason")["reason_cat"].agg(lambda s: s.mode().iat[0])
for k, v in ns["reason"].value_counts().head(14).items():
    nosale["by_reason"].append({"name": k, "n": int(v),
                                "cat": str(reason_cat_map.get(k, "Not recorded"))})

nosale["by_zone"].sort(key=lambda r: -r["tc"])

for t, g in call.groupby("otype"):
    nosale["by_type"].append({
        "type": t, "tc": int(len(g)), "pc": int(g["productive"].sum()),
        "conv": round(g["productive"].mean() * 100, 1),
        "net": float(g["value"].sum()),
        "avg": round(float(g["value"].sum()) / max(int(g["productive"].sum()), 1), 0),
    })
nosale["by_type"].sort(key=lambda r: -r["tc"])

# top reason per zone
rz = []
for z, g in ns.groupby("zone"):
    top = g["reason"].value_counts().head(3)
    rz.append({"zone": z, "top": [{"name": k, "n": int(v)} for k, v in top.items()]})
nosale["reason_by_zone"] = sorted(rz, key=lambda r: -sum(x["n"] for x in r["top"]))

# --------------------------------------------------- outlets
outlets = {
    "total": int(len(outl)),
    "by_type": [{"type": k, "n": int(v)} for k, v in outl["Outlets Type"].value_counts().items()],
    "by_zone": [{"zone": k, "n": int(v)} for k, v in outl["Zone"].value_counts().items()],
    "untagged": int((outl["Outlets Type"] == "Untagged").sum()),
    "channels": [{"name": k, "n": int(v)} for k, v in outl["Outlets Channel"].value_counts().items()],
}
ordered_ids = set(call.loc[call["productive"], "outlet"])
visited_ids = set(call["outlet"])
outl["_ordered"] = outl["Outlet Erp Id"].isin(ordered_ids)
outl["_visited"] = outl["Outlet Erp Id"].isin(visited_ids)
zone_cov = []
for z, g in outl.groupby("Zone"):
    zone_cov.append({
        "zone": z, "outlets": int(len(g)),
        "visited": int(g["_visited"].sum()), "ordered": int(g["_ordered"].sum()),
        "visited_pct": round(g["_visited"].mean() * 100, 1),
        "ordered_pct": round(g["_ordered"].mean() * 100, 1),
        "net": float(call.loc[call["zone"] == z, "value"].sum()),
    })
outlets["zone_coverage"] = sorted(zone_cov, key=lambda r: -r["outlets"])

type_cov = []
for t, g in outl.groupby("Outlets Type"):
    type_cov.append({
        "type": t, "outlets": int(len(g)),
        "ordered": int(g["_ordered"].sum()),
        "ordered_pct": round(g["_ordered"].mean() * 100, 1),
    })
outlets["type_coverage"] = sorted(type_cov, key=lambda r: -r["outlets"])

# beats with no sales
bsum = bvc.groupby("Beats")["Net Sale Value"].sum()
outlets["beats_total"] = int(bvc["Beats"].nunique())
outlets["beats_zero"] = int((bsum <= 0).sum())

# --------------------------------------------------- product / category x region
lines = Q[Q["Product"] != ""].copy()
lines.loc[lines["PrimaryCategory"] == "", "PrimaryCategory"] = "Uncategorised"
lines.loc[lines["ProductDivision"] == "", "ProductDivision"] = "Unassigned"

zones_ord = [z["zone"] for z in outlets["zone_coverage"]
             if z["zone"] != "Unmapped"
             and float(Q.loc[Q["Zone"] == z["zone"], "NetValue"].sum()) > 0]
cats = (lines.groupby("PrimaryCategory")["NetValue"].sum()
        .sort_values(ascending=False))
cat_names = [c for c in cats.index]

matrix = []
for c in cat_names:
    sub = lines[lines["PrimaryCategory"] == c]
    row = {"cat": c, "total": float(sub["NetValue"].sum()),
           "outlets": int(sub["Outlet Erp Id"].nunique()), "cells": []}
    for z in zones_ord:
        s = sub[sub["Zone"] == z]
        zone_total = float(lines.loc[lines["Zone"] == z, "NetValue"].sum())
        v = float(s["NetValue"].sum())
        row["cells"].append({
            "zone": z, "net": v,
            "share": round(v / zone_total * 100, 1) if zone_total else 0,
            "outlets": int(s["Outlet Erp Id"].nunique()),
        })
    matrix.append(row)

# keep the top categories explicit, roll the rest into one honest line
TOP_N = 18
if len(matrix) > TOP_N:
    tail_rows = matrix[TOP_N:]
    rolled = {"cat": f"All other categories ({len(tail_rows)})",
              "total": sum(r["total"] for r in tail_rows),
              "outlets": int(lines[lines["PrimaryCategory"].isin(
                  [r["cat"] for r in tail_rows])]["Outlet Erp Id"].nunique()),
              "cells": []}
    for i, z in enumerate(zones_ord):
        rolled["cells"].append({
            "zone": z,
            "net": sum(r["cells"][i]["net"] for r in tail_rows),
            "share": round(sum(r["cells"][i]["share"] for r in tail_rows), 1),
            "outlets": 0,
        })
    matrix = matrix[:TOP_N] + [rolled]

zone_totals = [{"zone": z, "net": float(lines.loc[lines["Zone"] == z, "NetValue"].sum()),
                "outlets": int(lines.loc[lines["Zone"] == z, "Outlet Erp Id"].nunique())}
               for z in zones_ord]

# white space: category sells nationally but is absent/thin in a zone that has reach
national_share = {c: float(cats[c]) / float(cats.sum()) * 100 for c in cat_names}
nat_total = float(lines["NetValue"].sum())
# a zone needs real volume before "under-indexing" there means anything
big_zones = {z["zone"] for z in zone_totals if nat_total and z["net"] / nat_total * 100 >= 3.0}
whitespace = []
for row in matrix:
    if row["cat"] not in national_share:   # the rolled-up "all other" line
        continue
    for cell in row["cells"]:
        nat = national_share[row["cat"]]
        if nat < 1.5 or cell["zone"] not in big_zones:
            continue
        gap = nat - cell["share"]
        if gap > 1.5:
            zt = next(z for z in zone_totals if z["zone"] == cell["zone"])
            whitespace.append({
                "cat": row["cat"], "zone": cell["zone"],
                "zone_share": cell["share"], "national_share": round(nat, 1),
                "gap": round(gap, 1), "net": cell["net"],
                "upside": round(zt["net"] * gap / 100, 0),
                "outlets": cell["outlets"],
            })
whitespace.sort(key=lambda r: -r["upside"])

prods = (lines.groupby("Product")
         .agg(net=("NetValue", "sum"), qty=("Qty ( StdUnit )", "sum"),
              outlets=("Outlet Erp Id", "nunique"), lines=("Product", "count"))
         .reset_index().sort_values("net", ascending=False))
prod_cat = lines.drop_duplicates("Product").set_index("Product")["PrimaryCategory"].to_dict()
top_products = [{"name": r.Product, "net": float(r.net), "qty": float(r.qty),
                 "outlets": int(r.outlets), "lines": int(r.lines)}
                for r in prods.head(20).itertuples()]
# a searchable long tail — the two 20-row cards only ever show the extremes
all_products = [{"name": r.Product, "cat": prod_cat.get(r.Product, "Uncategorised"),
                 "net": float(r.net), "qty": float(r.qty),
                 "outlets": int(r.outlets), "lines": int(r.lines)}
                for r in prods[prods["net"] > 0].head(250).itertuples()]
tail = prods[prods["net"] > 0].tail(20).sort_values("net")
tail_products = [{"name": r.Product, "net": float(r.net), "qty": float(r.qty),
                  "outlets": int(r.outlets), "lines": int(r.lines)}
                 for r in tail.itertuples()]
prod_count = int((prods["net"] > 0).sum())
dead_skus = int((prods["net"] <= 0).sum())

divisions = [{"name": k, "net": float(v)} for k, v in
             lines.groupby("ProductDivision")["NetValue"].sum().sort_values(ascending=False).items()]

# category performance by outlet type — where does each category actually land
cat_by_type = []
top_cats = cat_names[:8]
type_names = [t["type"] for t in outlets["type_coverage"][:7]]
for c in top_cats:
    sub = lines[lines["PrimaryCategory"] == c]
    cells = []
    for t in type_names:
        cells.append({"type": t, "net": float(sub.loc[sub["Outlet Type"] == t, "NetValue"].sum())})
    cat_by_type.append({"cat": c, "cells": cells})

payload = {
    "kpis": kpis,
    "monthly": monthly,
    "arc": arc,
    "people": people,
    "users": user_rows,
    "nosale": nosale,
    "outlets": outlets,
    "category": {
        "zones": zones_ord,
        "zone_totals": zone_totals,
        "matrix": matrix,
        "whitespace": whitespace[:24],
        "top_products": top_products,
        "tail_products": tail_products,
        "all_products": all_products,
        "divisions": divisions,
        "cat_by_type": cat_by_type,
        "types": type_names,
        "cat_count": len(cat_names),
        "sku_selling": prod_count,
        "sku_dead": dead_skus,
    },
    "quality": {
        "outlets_untagged": outlets["untagged"],
        "outlets_untagged_pct": round(outlets["untagged"] / len(outl) * 100, 1),
        "lines_uncategorised": int((lines["PrimaryCategory"] == "Uncategorised").sum()),
        "no_mt": int((outl["Outlets Channel"] == "MT").sum()),
        "users_no_designation": int((users["Designation"] == "Unassigned").sum()),
        "pjp_zero": True,
        "targets": False,
        "beats_zero": outlets["beats_zero"],
        "beats_total": outlets["beats_total"],
        "reason_blank": int((ns["reason"] == "Not recorded").sum()),
    },
}

print("reading product performance exports ...")
sku_cat = (lines.drop_duplicates("Product")
                .set_index("Product")["PrimaryCategory"].to_dict())
payload = enrich(SRC, payload, sku_cat)

with open(OUT, "w") as f:
    json.dump(payload, f, separators=(",", ":"), default=float)
print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
print(f"  TC={TC:,}  PC={PC:,}  conv={kpis['conv']}%  net=Rs {NET/1e7:.2f} Cr")
print(f"  whitespace rows={len(whitespace)}  users={len(user_rows)}")
