import json
from pathlib import Path
from typing import Any
from ..errors import DatasetConfigurationError
class JsonFoundationRepository:
 def __init__(self,data_dir:Path,trend_rows_file:str="trend_rows.json",wafer_rows_file:str="wafer_rows.json"):
    self.data_dir=Path(data_dir);self.trend_rows_file=trend_rows_file;self.wafer_rows_file=wafer_rows_file
 def _read(self,name:str)->list[dict[str,Any]]:
  path=self.data_dir/name
  if not path.is_file():raise DatasetConfigurationError(f"Required mock dataset not found: {path}")
  try:value=json.loads(path.read_text(encoding="utf-8"))
  except (OSError,json.JSONDecodeError) as exc:raise DatasetConfigurationError(f"Invalid mock dataset: {path}") from exc
  if not isinstance(value,list) or any(not isinstance(x,dict) for x in value):raise DatasetConfigurationError(f"Mock dataset must be a list of objects: {path}")
  return value
 def trend_rows(self):return self._read(self.trend_rows_file)
 def wafer_rows(self):return self._read(self.wafer_rows_file)
 def table_rows(self,name:str):return self._read(f"{name}.json")
