"""Emit SQL that loads the Foundation mock trend rows into a local LanaDB copy.

Each mock measureProcessJobId becomes one lot step (exposure + metrology) and
each of its wafers one wafer step with overlay KPIs, so getWaferLevelKpis
returns the same rows the mock Foundation API serves. Mock rows use ids from
MOCK_ID_BASE upwards; rerunning first deletes that range.

    python seed_lanadb_mock.py | docker exec -i lanadb-local psql -v ON_ERROR_STOP=1 -U lanadb_local -d lanadb
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1]
MOCK_FILES = ("trend_rows.json", "trend_rows_v3.json")
SCHEMA = "lisa"
MOCK_ID_BASE = 900_000_000
WAFERS_PER_JOB = 100

DELETE_ORDER = (
    "wafer_metrology_overlay_kpis",
    "wafer_kpi_mapping",
    "wafer_metrology_step",
    "wafer_exposure_step",
    "wafer_step",
    "lot_metrology_step",
    "lot_exposure_step",
    "lot_step",
)


def literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def timestamp(value: datetime) -> str:
    return literal(value.isoformat()) + "::timestamptz"


def insert(table: str, columns: tuple[str, ...], rows: list[tuple], suffix: str = "") -> str:
    values = ",\n".join("(" + ", ".join(row) + ")" for row in rows)
    return f"INSERT INTO {SCHEMA}.{table} ({', '.join(columns)}) VALUES\n{values}{suffix};"


def load_jobs() -> dict[int, list[dict]]:
    jobs: dict[int, list[dict]] = {}
    for name in MOCK_FILES:
        for row in json.loads((DATA_DIR / name).read_text(encoding="utf-8")):
            jobs.setdefault(int(row["measureProcessJobId"]), []).append(row)
    return jobs


def build_sql(jobs: dict[int, list[dict]]) -> str:
    lot_steps, exposures, metrologies = [], [], []
    wafer_steps, wafer_exposures, wafer_metrologies, mappings, kpis = [], [], [], [], []
    exposure_machines, metrology_machines = set(), set()

    for job, rows in sorted(jobs.items()):
        if len(rows) >= WAFERS_PER_JOB:
            raise ValueError(f"job {job} has too many wafers for the id scheme")
        head = rows[0]
        lot_id, layer_id, product = head["lotId"], head["layerId"], head["productId"]
        scanner, metrology_tool = head["exposureEquipmentId"], head["measurementEquipmentId"]
        exposed = datetime.fromisoformat(head["lotStart"])
        measured = exposed + timedelta(hours=2)
        lot_key = MOCK_ID_BASE + job
        exposure_machines.add(scanner)
        metrology_machines.add(metrology_tool)

        lot_steps.append((literal(lot_key), literal(lot_id), literal(layer_id),
                          timestamp(measured + timedelta(hours=2)), timestamp(exposed), literal(product)))
        exposures.append((literal(lot_key), literal(lot_id), literal(layer_id), literal(lot_key), literal(scanner),
                          timestamp(exposed), timestamp(exposed + timedelta(hours=1)),
                          literal(lot_id), literal(layer_id), literal(product)))
        metrologies.append((literal(lot_key), literal(lot_id), literal(layer_id), literal(lot_key),
                            literal(metrology_tool), timestamp(measured), timestamp(measured + timedelta(hours=1)),
                            literal(lot_id), literal(layer_id), literal(product), literal(str(job))))

        for index, row in enumerate(rows):
            wafer_key = MOCK_ID_BASE + job * WAFERS_PER_JOB + index
            wafer = row["waferId"]
            wafer_steps.append((literal(wafer_key), literal(lot_key), literal(lot_id), literal(layer_id),
                                literal(wafer), timestamp(measured)))
            wafer_exposures.append((literal(wafer_key), literal(wafer_key), literal(lot_key), literal(wafer),
                                    literal(wafer), literal(index + 1), literal(row.get("chuckId")),
                                    timestamp(exposed), timestamp(exposed + timedelta(hours=1))))
            wafer_metrologies.append((literal(wafer_key), literal(wafer_key), literal(lot_key), literal(wafer),
                                      literal(wafer), literal(index + 1), timestamp(measured)))
            mappings.append((literal(wafer_key), literal(wafer_key), literal(wafer_key), literal(wafer_key)))
            kpis.append((literal(wafer_key), literal(row["kpiValue1"]), literal(row["kpiValue2"])))

    statements = ["BEGIN;"]
    statements += [f"DELETE FROM {SCHEMA}.{table} WHERE id >= {MOCK_ID_BASE};" for table in DELETE_ORDER]
    keep_existing = "\nON CONFLICT (id) DO NOTHING"
    statements.append(insert("exposure_machine", ("id",), [(literal(m),) for m in sorted(exposure_machines)],
                             keep_existing))
    statements.append(insert("metrology_machine", ("id",), [(literal(m),) for m in sorted(metrology_machines)],
                             keep_existing))
    statements.append(insert("lot_step", ("id", "key_lot_id", "key_layer_id", "import_timestamp", "lot_start",
                                          "product_id"), lot_steps))
    statements.append(insert("lot_exposure_step", ("id", "key_lot_id", "key_layer_id", "lot_step_id", "machine_id",
                                                   "lot_start", "lot_end", "lot_id", "layer_id", "product_id"),
                             exposures))
    statements.append(insert("lot_metrology_step", ("id", "key_lot_id", "key_layer_id", "lot_step_id", "machine_id",
                                                    "lot_start", "lot_end", "lot_id", "layer_id", "product_id",
                                                    "process_job_id"), metrologies))
    statements.append(insert("wafer_step", ("id", "lot_step_id", "key_lot_id", "key_layer_id", "key_wafer_id",
                                            "last_update"), wafer_steps))
    statements.append(insert("wafer_exposure_step", ("id", "wafer_step_id", "lot_exposure_step_id", "key_wafer_id",
                                                     "wafer_id", "wafer_sequencenr", "chuck_id", "wafer_start",
                                                     "wafer_end"), wafer_exposures))
    statements.append(insert("wafer_metrology_step", ("id", "wafer_step_id", "lot_metrology_step_id", "key_wafer_id",
                                                      "wafer_id", "wafer_sequencenr", "measurement_start_time"),
                             wafer_metrologies))
    statements.append(insert("wafer_kpi_mapping", ("id", "wafer_step_id", "wafer_metrology_step_id",
                                                   "wafer_exposure_step_id"), mappings))
    statements.append(insert("wafer_metrology_overlay_kpis", ("id", "measured_raw_m3s_x", "measured_raw_m3s_y"),
                             kpis))
    statements.append("COMMIT;")
    return "\n".join(statements) + "\n"


if __name__ == "__main__":
    sys.stdout.write(build_sql(load_jobs()))
