"""Command line entry point for DebIDE."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .app import DebIDEApp
from .config import load_config
from .plugins import PluginManager
from .scaffold import PackageMetadata, scaffold_debian_packaging


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debide",
        description="Launch the DebIDE terminal IDE for Debian workflows.",
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory to open (default: current directory)",
    )
    parser.add_argument(
        "--config",
        "-c",
        dest="config_path",
        help="Path to a .debide.yml configuration file",
    )
    return parser


def build_scaffold_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debide scaffold",
        description="Generate a Debian packaging skeleton (debian/ directory).",
    )
    parser.add_argument("name", help="Source package name")
    parser.add_argument(
        "--version", default="0.1.0", help="Upstream version (default: 0.1.0)"
    )
    parser.add_argument(
        "--revision", default="1", help="Debian revision (default: 1)"
    )
    parser.add_argument(
        "--maintainer-name",
        default="Debian Maintainer",
        help="Maintainer name for changelog/control",
    )
    parser.add_argument(
        "--maintainer-email",
        default="maintainer@example.com",
        help="Maintainer email address",
    )
    parser.add_argument(
        "--summary", default="Short summary", help="Short package summary"
    )
    parser.add_argument(
        "--description",
        default="Longer package description.",
        help="Long description for debian/control",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Target directory to place the debian/ folder",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "scaffold":
        scaffold_parser = build_scaffold_parser()
        args = scaffold_parser.parse_args(argv[1:])
        workspace = Path(args.workspace).expanduser().resolve()
        metadata = PackageMetadata(
            name=args.name,
            version=args.version,
            revision=args.revision,
            maintainer_name=args.maintainer_name,
            maintainer_email=args.maintainer_email,
            summary=args.summary,
            description=args.description,
        )
        try:
            created = scaffold_debian_packaging(workspace, metadata)
        except FileExistsError as error:
            print(error, file=sys.stderr)
            return 1
        rel_paths = ", ".join(str(path.relative_to(workspace)) for path in created)
        print(f"Created: {rel_paths}")
        return 0

    run_parser = build_run_parser()
    args = run_parser.parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()
    config_path = (
        Path(args.config_path).expanduser().resolve()
        if args.config_path
        else None
    )
    plugin_manager = PluginManager()
    plugin_manager.discover()
    config = load_config(workspace, config_path, plugin_manager=plugin_manager)
    app = DebIDEApp(workspace=workspace, config=config, plugin_manager=plugin_manager)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
