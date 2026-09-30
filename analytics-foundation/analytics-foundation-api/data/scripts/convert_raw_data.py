"""Convert raw lanadb, OVERLAY and TDBB exports into Foundation API JSON datasets.

Requires pyarrow. Example:
  python convert_raw_data.py --lana-dir C:/data/lana --overlay-tar C:/data/OVERLAY.tar.gz \
      --tdbb-tar C:/data/run_ed11f447-d02c-4b7a-a339-67ea001d7ec7.tar.gz

Writes trend_rows_v2.json to data/ and the large wafer/TDBB files to data/large_data/ (git-ignored).
"""
import argparse
import io
import json
import math
import re
import tarfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq

DATA_DIR = Path(__file__).resolve().parent.parent
LARGE_DIR = DATA_DIR / "large_data"

WAFER_COLUMNS = [
    "exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_x",
    "exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_y",
    "measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_x",
    "measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_y",
    "exposureprocessjob_reticle_image_imagesize_width",
    "exposureprocessjob_reticle_image_imagesize_height",
    "overlay_x",
    "overlay_y",
    "overlay_valid_x",
    "overlay_valid_y",
    "exposureprocessjob_lotid",
    "exposureprocessjob_waferexposureprocessjob_waferid",
    "exposureprocessjob_waferexposureprocessjob_chuck_id",
    "measureprocessjob_layerid",
    "exposureprocessjob_equipment_equipmentid",
]


def parquet_members(tar_path, path_filter):
    """Yield (member_name, rows) for parquet files in a tar.gz whose name matches path_filter, sorted by name."""
    with tarfile.open(tar_path, "r:gz") as tar:
        members = sorted(
            (m for m in tar.getmembers()
             if m.isfile() and m.name.endswith(".parquet") and path_filter in m.name),
            key=lambda m: m.name,
        )
        for member in members:
            data = tar.extractfile(member).read()
            yield member.name, pq.read_table(io.BytesIO(data)).to_pylist()


def jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def iso_utc(text):
    if text is None:
        return None
    return datetime.fromisoformat(re.sub(r"\+00$", "+00:00", text)).isoformat()


def load_latest(lana_dir, prefix):
    files = sorted(Path(lana_dir).glob(f"{prefix}_*.json"))
    if not files:
        raise SystemExit(f"No {prefix}_*.json found in {lana_dir}")
    return json.loads(files[-1].read_text(encoding="utf-8"))


def dump(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, separators=(",", ":"), allow_nan=False)
    print(f"{path.relative_to(DATA_DIR)}: {len(rows)} rows, {path.stat().st_size / 1e6:.1f} MB")


def m3s(values):
    """Overlay KPI: |mean| + 3 sigma."""
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    sd = math.sqrt(sum((v - avg) ** 2 for v in values) / (len(values) - 1))
    return round(abs(avg) + 3 * sd, 3)


def convert_wafer_rows(overlay_tar):
    rows = []
    for _, records in parquet_members(overlay_tar, "/association.data/"):
        for r in records:
            row = {c: jsonable(r.get(c)) for c in WAFER_COLUMNS}
            row["overlay_valid_x"] = int(bool(r.get("overlay_valid_x")))
            row["overlay_valid_y"] = int(bool(r.get("overlay_valid_y")))
            rows.append(row)
    return rows


def convert_trend_rows(lana_dir, wafer_rows):
    samples = defaultdict(lambda: ([], []))
    for r in wafer_rows:
        key = (r["exposureprocessjob_lotid"], r["exposureprocessjob_waferexposureprocessjob_waferid"])
        if r["overlay_valid_x"] and r["overlay_x"] is not None:
            samples[key][0].append(r["overlay_x"])
        if r["overlay_valid_y"] and r["overlay_y"] is not None:
            samples[key][1].append(r["overlay_y"])

    lot_exposure = {r["id"]: r for r in load_latest(lana_dir, "lot_exposure_step")}
    metrology = {}
    for r in load_latest(lana_dir, "lot_metrology_step"):
        metrology.setdefault(r["lot_id"], r)

    rows = []
    for w in load_latest(lana_dir, "wafer_exposure_step"):
        lot = lot_exposure.get(w["lot_exposure_step_id"])
        if lot is None:
            continue
        met = metrology.get(lot["lot_id"])
        xs, ys = samples.get((lot["lot_id"], w["wafer_id"]), ([], []))
        kpi1, kpi2 = m3s(xs), m3s(ys)
        rows.append({
            "productId": lot["product_id"],
            "lotId": lot["lot_id"],
            "layerId": lot["layer_id"],
            "waferId": w["wafer_id"],
            "measureProcessJobId": float(met["id"]) if met else None,
            "exposureEquipmentId": lot["machine_id"],
            "measurementEquipmentId": met["machine_id"] if met else None,
            "lotStart": iso_utc(lot["lot_start"]),
            "kpiValue1": kpi1,
            "kpiValue2": kpi2,
            "needsIngestion": kpi1 is None and kpi2 is None,
        })
    rows.sort(key=lambda r: (r["lotStart"] or "", r["lotId"], r["waferId"]))
    return rows


def convert_tdbb(tdbb_tar):
    run_id = re.search(r"run_([0-9a-f-]{36})", Path(tdbb_tar).name).group(1)
    tables = defaultdict(list)
    for name, records in parquet_members(tdbb_tar, "/spark/data/"):
        table = name.split("/spark/data/")[1].split("/")[0].removeprefix("overlay_tdbb_")
        tables[table].extend({"run_id": run_id, **{k: jsonable(v) for k, v in r.items()}} for r in records)
    return tables


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lana-dir", required=True, help="Folder with lanadb *_step_*.json exports")
    parser.add_argument("--overlay-tar", required=True, help="OVERLAY.tar.gz containing association.data")
    parser.add_argument("--tdbb-tar", required=True, help="run_<id>.tar.gz with TDBB processing results")
    args = parser.parse_args()

    wafer_rows = convert_wafer_rows(args.overlay_tar)
    dump(LARGE_DIR / "wafer_rows_v2.json", wafer_rows)
    dump(DATA_DIR / "trend_rows_v2.json", convert_trend_rows(args.lana_dir, wafer_rows))
    for table, rows in convert_tdbb(args.tdbb_tar).items():
        dump(LARGE_DIR / f"tdbb_{table}_rows.json", rows)


if __name__ == "__main__":
    main()
