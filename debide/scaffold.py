"""Helpers to scaffold Debian packaging assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Iterable, List


@dataclass(slots=True)
class PackageMetadata:
    """Metadata used to generate Debian packaging files."""

    name: str
    version: str = "0.1.0"
    revision: str = "1"
    maintainer_name: str = "Debian Maintainer"
    maintainer_email: str = "maintainer@example.com"
    summary: str = "Short summary of the package."
    description: str = "Longer description of the package."
    homepage: str | None = None
    section: str = "misc"
    priority: str = "optional"
    architecture: str = "any"
    standards_version: str = "4.7.0"
    build_depends: Iterable[str] = field(
        default_factory=lambda: ["debhelper-compat (= 13)"]
    )

    @property
    def full_version(self) -> str:
        return f"{self.version}-{self.revision}"


def _write_file(path: Path, content: str, *, overwrite: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists")
    path.write_text(content, encoding="utf-8")
    return path


def _render_control(metadata: PackageMetadata) -> str:
    homepage_line = f"Homepage: {metadata.homepage}\n" if metadata.homepage else ""
    long_description = (
        metadata.description.replace("\n", "\n ")
        if metadata.description
        else " TODO"
    )
    build_depends = ", ".join(metadata.build_depends)
    return dedent(
        f"""\
        Source: {metadata.name}
        Section: {metadata.section}
        Priority: {metadata.priority}
        Maintainer: {metadata.maintainer_name} <{metadata.maintainer_email}>
        Build-Depends: {build_depends}
        Standards-Version: {metadata.standards_version}
        {homepage_line}Package: {metadata.name}
        Architecture: {metadata.architecture}
        Depends: ${{misc:Depends}}, ${{shlibs:Depends}}
        Description: {metadata.summary}
         {long_description}
        """
    ).strip() + "\n"


def _render_changelog(metadata: PackageMetadata) -> str:
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    return dedent(
        f"""\
        {metadata.name} ({metadata.full_version}) unstable; urgency=medium

          * Initial release.

         -- {metadata.maintainer_name} <{metadata.maintainer_email}>  {date_str}
        """
    ).strip() + "\n"


def _render_rules(metadata: PackageMetadata) -> str:
    return dedent(
        """\
        #!/usr/bin/make -f
        %:
        \tdh $@
        """
    )


def _render_watch(metadata: PackageMetadata) -> str:
    return dedent(
        f"""\
        version=4
        opts=filenamemangle=s/.+/{metadata.name}-$1.tar.gz/ \\
          https://example.com/{metadata.name}/releases \
          .*/{metadata.name}-(.*)\\.tar\\.gz
        """
    )


def scaffold_debian_packaging(workspace: Path, metadata: PackageMetadata) -> List[Path]:
    """Create a Debian packaging skeleton within the workspace."""

    workspace = workspace.expanduser().resolve()
    debian_dir = workspace / "debian"
    created: List[Path] = []

    created.append(_write_file(debian_dir / "control", _render_control(metadata)))
    created.append(_write_file(debian_dir / "changelog", _render_changelog(metadata)))
    created.append(
        _write_file(debian_dir / "rules", _render_rules(metadata), overwrite=False)
    )
    (debian_dir / "rules").chmod(0o755)
    created.append(
        _write_file(debian_dir / "watch", _render_watch(metadata), overwrite=False)
    )
    created.append(
        _write_file(
            debian_dir / "source" / "format", "3.0 (quilt)\n", overwrite=False
        )
    )
    created.append(
        _write_file(
            debian_dir / "README.Debian",
            f"{metadata.name} for Debian\n=====================\n\nDescribe package specifics here.\n",
            overwrite=False,
        )
    )

    return created

