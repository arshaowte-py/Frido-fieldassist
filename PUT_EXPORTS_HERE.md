Drop FieldAssist exports here, keeping default filenames:

  Secondary_Order_Dump__New__*.xlsx          (one or more; concatenated automatically)
  Outlet_Dump_GeoHierarchy_*.xlsx            (outlet master)
  Frido_Users_*.csv                          (user roster)
  Frido_Beats_*.csv                          (beat master)
  Employee_Productivity_Report__New__*.xlsx  (one per month)
  Attendance_Report__New__*.xlsx             (one per month)
  Beat_Visit_Coverage_Efficiency_Report__New__*.xlsx

Then: python3 etl.py raw aggregates.json && python3 build.py
