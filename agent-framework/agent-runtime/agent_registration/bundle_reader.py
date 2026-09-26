"""Safe reader for declarative agent ZIP bundles."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import PurePosixPath
from typing import Any

from .errors import InvalidAgentBundleError
from .models import AgentBundleDocument, FILE_TO_TYPE


MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_DOCUMENT_BYTES = 512 * 1024
MAX_FILES = 12
ALLOWED_FILES = frozenset({"manifest.json", *FILE_TO_TYPE})


def read_agent_bundle(
    archive_bytes: bytes,
) -> tuple[dict[str, Any], tuple[AgentBundleDocument, ...], str]:
    """Read a safe, flat UTF-8 bundle and return its digest."""

    if not isinstance(archive_bytes, bytes) or not archive_bytes:
        raise InvalidAgentBundleError("ZIP body must not be empty")
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise InvalidAgentBundleError("ZIP exceeds the maximum allowed size")

    digest = "sha256:" + hashlib.sha256(archive_bytes).hexdigest()

    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except zipfile.BadZipFile as exc:
        raise InvalidAgentBundleError("Request body is not a valid ZIP") from exc

    with archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) > MAX_FILES:
            raise InvalidAgentBundleError("ZIP contains too many files")

        names: set[str] = set()
        raw_files: dict[str, bytes] = {}
        for member in members:
            path = PurePosixPath(member.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise InvalidAgentBundleError(
                    f"Unsafe or nested ZIP member: {member.filename!r}"
                )
            name = path.name
            if name not in ALLOWED_FILES:
                raise InvalidAgentBundleError(
                    f"Unsupported bundle file: {name!r}"
                )
            if name in names:
                raise InvalidAgentBundleError(f"Duplicate bundle file: {name!r}")
            if member.file_size > MAX_DOCUMENT_BYTES:
                raise InvalidAgentBundleError(f"Bundle file is too large: {name!r}")
            names.add(name)
            raw_files[name] = archive.read(member)

    if "manifest.json" not in raw_files:
        raise InvalidAgentBundleError("manifest.json is required")

    try:
        manifest = json.loads(raw_files["manifest.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidAgentBundleError("manifest.json must be valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise InvalidAgentBundleError("manifest.json must contain an object")

    documents: list[AgentBundleDocument] = []
    for name, document_type in FILE_TO_TYPE.items():
        if name not in raw_files:
            continue
        try:
            content = raw_files[name].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidAgentBundleError(f"{name} must be UTF-8 text") from exc
        documents.append(
            AgentBundleDocument(
                document_type=document_type,
                file_name=name,
                content=content,
            )
        )

    return manifest, tuple(documents), digest
