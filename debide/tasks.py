"""Task models and helpers for DebIDE."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional


class TaskConfigurationError(RuntimeError):
    """Raised when a task definition is invalid."""


@dataclass(slots=True)
class TaskSpec:
    """Declarative description of a Debian-oriented task."""

    name: str
    command: str
    description: str = ""
    working_dir: Optional[str] = None
    env: MutableMapping[str, str] = field(default_factory=dict)

    def resolve_working_dir(self, workspace: Path) -> Path:
        """Return the directory the command should execute in."""
        if self.working_dir:
            candidate = (workspace / self.working_dir).resolve()
            return candidate
        return workspace


def coerce_tasks(items: Iterable[Mapping[str, object]]) -> list[TaskSpec]:
    """Convert raw mappings into validated TaskSpec instances."""
    tasks: list[TaskSpec] = []
    seen: set[str] = set()
    for item in items:
        name = str(item.get("name", "")).strip()
        command = str(item.get("command", "")).strip()
        if not name:
            raise TaskConfigurationError("Task definition missing 'name'")
        if not command:
            raise TaskConfigurationError(f"Task '{name}' missing 'command'")
        if name in seen:
            raise TaskConfigurationError(f"Duplicate task name '{name}' detected")
        seen.add(name)
        description = str(item.get("description", "") or "").strip()
        working_dir = item.get("working_dir")
        env_mapping = item.get("env") or {}
        if working_dir is not None:
            working_dir = str(working_dir)
        if not isinstance(env_mapping, Mapping):
            raise TaskConfigurationError(
                f"Task '{name}' provided 'env' but it is not a mapping"
            )
        env = {str(k): str(v) for k, v in env_mapping.items()}
        tasks.append(
            TaskSpec(
                name=name,
                command=command,
                description=description,
                working_dir=working_dir,
                env=env,
            )
        )
    return tasks

