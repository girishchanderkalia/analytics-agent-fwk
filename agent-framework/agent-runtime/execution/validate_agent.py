"""Command-line validation for application-agent definition bundles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from definition_loader import DefinitionError, DefinitionLoader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Load and validate application-agent Markdown definitions."
        )
    )

    parser.add_argument(
        "agent",
        nargs="?",
        help=(
            "Agent directory name or metadata ID. "
            "When omitted, all agents are validated."
        ),
    )

    parser.add_argument(
        "--repository-root",
        default=".",
        help="Path to ai-enabled-analytics-v3.",
    )

    return parser


def describe_bundle(bundle) -> None:
    print(
        f"VALID {bundle.directory_name} "
        f"({bundle.agent.id}, version {bundle.agent.version})"
    )

    for filename in sorted(bundle.documents):
        document = bundle.documents[filename]
        print(
            f"  - {filename}: "
            f"id={document.id}, kind={document.kind}"
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    loader = DefinitionLoader.from_repository_root(repository_root)

    try:
        if args.agent:
            bundles = [loader.load(args.agent)]
        else:
            directory_names = loader.list_agent_directories()

            if not directory_names:
                raise DefinitionError(
                    f"No agents found under {loader.agents_root}"
                )

            bundles = [
                loader.load(directory_name)
                for directory_name in directory_names
            ]

        for bundle in bundles:
            describe_bundle(bundle)

        print()
        print(f"Validated {len(bundles)} agent definition bundle(s).")
        return 0

    except DefinitionError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
