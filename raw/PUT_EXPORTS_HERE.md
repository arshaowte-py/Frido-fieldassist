Drop FieldAssist exports here, keeping default filenames:

  Secondary_Order_Dump__New__*.xlsx          (one or more; concatenated automatically)
  Outlet_Dump_GeoHierarchy_*.xlsx            (outlet master)
  Frido_Users_*.csv                          (user roster)
  Frido_Beats_*.csv                          (beat master)
  Employee_Productivity_Report__New__*.xlsx  (one per month)
  Attendance_Report__New__*.xlsx             (one per month)
  Beat_Visit_Coverage_Efficiency_Report__New__*.xlsx

Optional — Product Performance Flexible Reports. All three share one filename prefix and
are told apart by header shape, so filenames do not matter:

  Frido_ProductPerformance_*.xlsx            rep x SKU x month pivot of UPC
                                             (L2Position User / L1Position User / Product / month UPC)
  Frido_ProductPerformance_*.xlsx            one row per visit line
                                             (L1Position User / Distributor / Beats / Shop / Visit Id / Product / Date / Qty / Net Value)
  Frido_ProductPerformance_*.xlsx            shop channel x category totals (reconciliation only)

Pull these with the position filter cleared, or the Assortment and Distributors tabs will
cover only the reps that filter allowed through.

Then: python3 etl.py raw aggregates.json && python3 build.py
