"""Load a registered generic agent package without repository discovery."""
from dataclasses import dataclass
from pathlib import Path
import yaml
from .errors import AgentPackageError, AgentPackageManifestError
from .package_models import AgentPackageManifest, parse_manifest_mapping
MANIFEST_FILENAME="agent-package.yaml"
@dataclass(frozen=True)
class LoadedAgentPackage:
    package_root: Path
    manifest_path: Path
    manifest: AgentPackageManifest
    resolved_sources: tuple[tuple[str,Path],...]
    def source(self,role):
        try:return dict(self.resolved_sources)[role]
        except KeyError as exc:raise AgentPackageError(f"Package source is not available: {role}") from exc

def load_agent_package(package_root):
    root=Path(package_root).expanduser().resolve()
    if not root.is_dir():raise AgentPackageError(f"Agent package directory does not exist: {root}")
    manifest_path=root/MANIFEST_FILENAME
    if not manifest_path.is_file():raise AgentPackageError(f"Agent package manifest is missing: {manifest_path}")
    try:raw=yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:raise AgentPackageManifestError(f"Manifest contains invalid YAML: {exc}") from exc
    manifest=parse_manifest_mapping(raw)
    resolved=tuple((role,_resolve(root,role,path)) for role,path in manifest.sources.all_sources())
    return LoadedAgentPackage(root,manifest_path,manifest,resolved)
def _resolve(root,role,path):
    if path.is_absolute():raise AgentPackageManifestError(f"Source {role!r} must be relative")
    resolved=(root/path).resolve()
    try:resolved.relative_to(root)
    except ValueError as exc:raise AgentPackageManifestError(f"Source {role!r} escapes the package root") from exc
    if not resolved.is_file():raise AgentPackageError(f"Source {role!r} does not exist: {resolved}")
    return resolved
