from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def copy_agent(tmp_path: Path) -> Path:
    source = ROOT.parent / "app-ui" / "opo-monitoring" / "agent"
    target = tmp_path / "agent"
    shutil.copytree(source, target)
    return target / "agent-package.yaml"
