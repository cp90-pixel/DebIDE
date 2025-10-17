"""Configuration loading for DebIDE."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

import yaml
from importlib import resources

from .tasks import TaskSpec, coerce_tasks, TaskConfigurationError


DEFAULT_CONFIG_FILENAMES: Sequence[str] = (".debide.yaml", ".debide.yml")


@dataclass(slots=True)
class DebIDEConfig:
    """Resolved configuration for the IDE runtime."""

    tasks: list[TaskSpec] = field(default_factory=list)
    autosave: bool = False
    default_task: Optional[str] = None


def _load_yaml_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise TaskConfigurationError(f"Configuration at {path} must be a mapping")
    return loaded


def _load_default_tasks() -> Iterable[dict]:
    with resources.files("debide.resources").joinpath("default_tasks.yaml").open(
        "r", encoding="utf-8"
    ) as handle:
        data = yaml.safe_load(handle) or {}
    return data.get("tasks", []) or []


def _load_user_tasks(config_mapping: dict) -> Iterable[dict]:
    tasks = config_mapping.get("tasks")
    if tasks is None:
        return []
    if not isinstance(tasks, list):
        raise TaskConfigurationError("'tasks' must be a list in configuration")
    return tasks


def load_config(workspace: Path, override_config: Optional[Path] = None) -> DebIDEConfig:
    """Load configuration for the given workspace."""

    workspace = workspace.expanduser().resolve()
    raw_tasks = list(_load_default_tasks())
    autosave = False
    default_task: Optional[str] = None

    config_path: Optional[Path] = None
    if override_config:
        config_path = override_config.expanduser().resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file {config_path} does not exist")
    else:
        for candidate_name in DEFAULT_CONFIG_FILENAMES:
            candidate = workspace / candidate_name
            if candidate.exists():
                config_path = candidate
                break

    if config_path:
        config_mapping = _load_yaml_file(config_path)
        raw_tasks.extend(_load_user_tasks(config_mapping))
        autosave = bool(config_mapping.get("autosave", False))
        if "default_task" in config_mapping:
            default_task = str(config_mapping["default_task"])

    tasks = coerce_tasks(raw_tasks)
    if default_task and default_task not in {task.name for task in tasks}:
        raise TaskConfigurationError(
            f"default_task '{default_task}' is not defined in tasks list"
        )

    return DebIDEConfig(tasks=tasks, autosave=autosave, default_task=default_task)
