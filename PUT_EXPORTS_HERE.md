Drop the FieldAssist exports here, keeping their default filenames:

  Secondary_Order_Dump__New__*.xlsx          (required - the spine)
  Outlet_Dump_GeoHierarchy_*.xlsx            (required - outlet master)
  Frido_Users_*.csv                          (required - employee master)
  Frido_Beats_*.csv                          (required - beat master)
  Employee_Productivity_Report__New__*.xlsx  (required - one per month)
  Attendance_Report__New__*.xlsx             (one per month)
  Beat_Visit_Coverage_Efficiency_Report__New__*.xlsx
  Product_Category_Analysis__New__*.xlsx     (reconciliation check)

Then: python3 etl.py raw aggregates.json && python3 build.py
