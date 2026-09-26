from __future__ import annotations

import importlib.util
import sys
import sysconfig
from pathlib import Path


def preload_standard_library_debugging() -> None:
    code_path = (
        Path(sysconfig.get_path("stdlib"))
        / "code.py"
    )

    spec = importlib.util.spec_from_file_location(
        "code",
        code_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Cannot load standard-library code module "
            f"from {code_path}"
        )

    code_module = importlib.util.module_from_spec(
        spec
    )

    # Install it before execution so imports during
    # module initialization resolve to this instance.
    sys.modules["code"] = code_module
    spec.loader.exec_module(code_module)

    if not hasattr(
        code_module,
        "InteractiveConsole",
    ):
        raise RuntimeError(
            "The loaded standard-library code module "
            "does not define InteractiveConsole: "
            f"{code_path}"
        )

    # Preload pdb now, while the correct code module
    # is installed. Pytest will reuse this cached pdb.
    import pdb

    if not hasattr(pdb, "Pdb"):
        raise RuntimeError(
            "The standard-library pdb module "
            "did not initialize correctly"
        )


preload_standard_library_debugging()

import pytest

raise SystemExit(
    pytest.main(sys.argv[1:])
)
