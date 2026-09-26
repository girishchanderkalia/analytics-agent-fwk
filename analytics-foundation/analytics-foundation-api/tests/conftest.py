import json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
@pytest.fixture
def data_dir(tmp_path):
 (tmp_path/"trend_rows.json").write_text(json.dumps([{"machine":"M1","product":"P1","lot_id":"L1","layer_id":"Y1","date":"2026-09-20T10:00:00Z","kpi_value":3.2},{"machine":"M1","product":"P1","lot_id":"L1","layer_id":"Y1","date":"2026-09-21T10:00:00Z","kpi_value":3.4}]))
 (tmp_path/"wafer_rows.json").write_text(json.dumps([{"wafer_id":"W1","machine":"M1","overlay_x_um":0.2,"overlay_y_um":0.2},{"wafer_id":"W2","machine":"M2","overlay_x_um":0.01,"overlay_y_um":0.01}]))
 return tmp_path
