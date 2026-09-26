import json
from pathlib import Path

from opo_response_compatibility import shape_response

ROOT = Path(__file__).resolve().parent


def test_complete_response_matches_golden_contract() -> None:
    state = json.loads((ROOT / "fixtures" / "complete-state.json").read_text(encoding="utf-8"))
    expected = json.loads((ROOT / "fixtures" / "complete-response.json").read_text(encoding="utf-8"))
    assert shape_response(state, "thread-13j") == expected
