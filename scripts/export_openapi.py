"""Write contracts/openapi.json from the FastAPI app. Run from backend/ via `make types`."""

import json
import sys
from pathlib import Path

from app.api.main import app

out = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
spec = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
if "--check" in sys.argv:
    if out.read_text("utf-8") != spec:
        sys.exit("contracts/openapi.json is stale. Run `make types` and commit the result.")
    print("openapi.json is current")
else:
    out.write_text(spec, encoding="utf-8", newline="\n")
    print(f"wrote {out}")
