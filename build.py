#!/usr/bin/env python3
"""Inject aggregates.json into template.html -> dist/index.html (self-contained)."""
import json, os, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else "aggregates.json"
TPL = sys.argv[2] if len(sys.argv) > 2 else "template.html"
OUT = sys.argv[3] if len(sys.argv) > 3 else "dist/index.html"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
data = open(SRC).read()
html = open(TPL).read()
assert "/*__DATA__*/" in html, "placeholder missing"
open(OUT, "w").write(html.replace("/*__DATA__*/", data))
print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")
