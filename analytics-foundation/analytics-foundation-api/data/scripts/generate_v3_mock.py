"""Generate v3 mock data: synthetic OPO trend rows and the mock TDBB run index.

Writes data/trend_rows_v3.json and data/tdbb_runs_v3.json (one completed
10par AVG/W2W run per lot, like the real run); existing data files are left
untouched. Identifiers extend real ones
(AAA, OV_NO_ID, OV_KTDB, GW02, LotOV, Carrier). Per-wafer X/Y KPIs are
|mean|+3 sigma of foundation_api.synthetic_overlay points, which the mock TDBB
run data regenerates. Run from any folder:
  python data/scripts/generate_v3_mock.py
"""

import json
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from random import Random

API_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_DIR))

from foundation_api.synthetic_overlay import PROFILES, m3s, wafer_points  # noqa: E402

OUTPUT = API_DIR / "data" / "trend_rows_v3.json"
RUNS_OUTPUT = API_DIR / "data" / "tdbb_runs_v3.json"
FIRST_DAY = date(2026, 8, 1)
LAST_DAY = date(2026, 9, 30)
WAFERS_PER_LOT = 8
# (product, layer, scanner) -> (lot number start, lots per day)
SCOPES = {
    ("AAA2", "OV_NO_ID2", "GW021"): (1001, 2),
    ("AAA2", "OV_KTDB2", "GW021"): (2001, 1),
    ("AAA2", "OV_NO_ID2", "GW022"): (3001, 1),
}


def main() -> None:
    rows = []
    runs = []
    carrier = 101
    job = 1000
    for (product, layer, scanner), (lot_number, lots_per_day) in SCOPES.items():
        profile = PROFILES[(product, layer, scanner)]
        clock = Random(f"schedule|{product}|{layer}|{scanner}")
        day = FIRST_DAY
        while day <= LAST_DAY:
            for slot in range(lots_per_day):
                hour = 6 + slot * 12 + clock.randint(0, 3)
                start = datetime(day.year, day.month, day.day, hour, clock.randint(0, 59), clock.randint(0, 59), tzinfo=timezone.utc)
                lot_id = f"LotOV{lot_number}"
                wafers = []
                for index in range(1, WAFERS_PER_LOT + 1):
                    wafer_id = f"Carrier {carrier}.{index}"
                    chuck_id = f"Waferstage chuck ID {1 if index % 2 else 2}"
                    wafers.append({"wafer_id": wafer_id, "chuck_id": chuck_id})
                    points = wafer_points(lot_id, wafer_id, chuck_id, start.isoformat(), profile)
                    rows.append({
                        "productId": product,
                        "lotId": lot_id,
                        "layerId": layer,
                        "waferId": wafer_id,
                        "chuckId": chuck_id,
                        "measureProcessJobId": float(job),
                        "exposureEquipmentId": scanner,
                        "measurementEquipmentId": "0000",
                        "lotStart": start.isoformat(),
                        "kpiValue1": m3s([point["overlay_x"] for point in points]),
                        "kpiValue2": m3s([point["overlay_y"] for point in points]),
                        "needsIngestion": False,
                    })
                runs.append({
                    "run_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"tdbb-run/{lot_id}")),
                    "status": "COMPLETED",
                    "model_step": "10par",
                    "context_levels": ["AVG", "W2W"],
                    "product_id": product,
                    "layer_id": layer,
                    "exposure_equipment_id": scanner,
                    "lot_id": lot_id,
                    "lot_start": start.isoformat(),
                    "wafers": wafers,
                })
                lot_number += 1
                carrier += 1
                job += 1
            day += timedelta(days=1)
    rows.sort(key=lambda row: (row["lotStart"], row["lotId"], row["waferId"]))
    OUTPUT.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    print(f"{OUTPUT.name}: {len(rows)} rows")
    runs.sort(key=lambda run: (run["lot_start"], run["lot_id"]))
    RUNS_OUTPUT.write_text(json.dumps(runs, indent=1), encoding="utf-8")
    print(f"{RUNS_OUTPUT.name}: {len(runs)} runs")


if __name__ == "__main__":
    main()
