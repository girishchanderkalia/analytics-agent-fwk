from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="ANALYTICS_FOUNDATION_")
    data_dir: Path=Path("data")
    trend_rows_file: str="trend_rows_v2.json"
    wafer_rows_file: str="large_data/wafer_rows_v2.json"
    trend_table: str="lanadb.trend_rows"
    wafer_table: str="starrocks.overlay_wafer_points"
@lru_cache
def get_settings()->Settings:return Settings()
