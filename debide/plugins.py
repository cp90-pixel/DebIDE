"""Plugin discovery and lifecycle hooks for DebIDE."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from .app import DebIDEApp


ENTRY_POINT_GROUP = "debide.plugins"

AppHook = Callable[["DebIDEApp"], None]
TaskProvider = Callable[[Path], Iterable[Mapping[str, object]]]


@dataclass(slots=True)
class PluginMessage:
    """Represents feedback collected while loading or running plugins."""

    source: str
    level: str
    text: str


class PluginAPI:
    """API surface exposed to third-party plugins."""

    __slots__ = ("_manager", "_source")

    def __init__(self, manager: PluginManager, source: str) -> None:
        self._manager = manager
        self._source = source

    def add_task(self, mapping: Mapping[str, object]) -> None:
        """Register a static task definition."""
        self._manager._register_task(self._source, mapping)

    def provide_tasks(self, provider: TaskProvider) -> None:
        """Register a callable that returns task mappings for each workspace."""
        self._manager._register_task_provider(self._source, provider)

    def on_app_ready(self, callback: AppHook) -> None:
        """Invoke the callback once the Textual app has mounted."""
        self._manager._register_app_hook(self._source, callback)

    def log(self, message: str, *, level: str = "info") -> None:
        """Emit a plugin-scoped diagnostic message."""
        self._manager._add_message(self._source, message, level=level)

    def info(self, message: str) -> None:
        """Emit an informational message."""
        self.log(message, level="info")

    def warning(self, message: str) -> None:
        """Emit a warning message."""
        self.log(message, level="warning")

    def error(self, message: str) -> None:
        """Emit an error message."""
        self.log(message, level="error")


class PluginManager:
    """Discover entry point plugins and manage their contributions."""

    def __init__(self, *, entry_point_group: str = ENTRY_POINT_GROUP) -> None:
        self.entry_point_group = entry_point_group
        self._loaded_plugins: list[str] = []
        self._messages: list[PluginMessage] = []
        self._static_tasks: list[tuple[str, dict[str, object]]] = []
        self._task_providers: list[tuple[str, TaskProvider]] = []
        self._app_hooks: list[tuple[str, AppHook]] = []
        self._app_hooks_dispatched = False

    @property
    def loaded_plugins(self) -> Sequence[str]:
        """Return the names of successfully loaded plugins."""
        return tuple(self._loaded_plugins)

    def discover(self) -> None:
        """Load entry point plugins available on the system."""
        for entry_point in _select_entry_points(self.entry_point_group):
            name = entry_point.name
            try:
                plugin_obj = entry_point.load()
            except Exception as error:  # pragma: no cover - defensive
                self._add_message(
                    name, f"Failed to import plugin: {error!r}", level="error"
                )
                continue
            self._activate_plugin(plugin_obj, name)

    def collect_tasks(self, workspace: Path) -> list[dict[str, object]]:
        """Return plugin-provided task mappings for the workspace."""
        tasks = [dict(mapping) for _, mapping in self._static_tasks]
        for source, provider in list(self._task_providers):
            try:
                provided = provider(workspace)
            except Exception as error:
                self._add_message(
                    source,
                    f"Task provider raised {error!r}",
                    level="error",
                )
                continue
            if provided is None:
                continue
            for item in provided:
                if not isinstance(item, Mapping):
                    self._add_message(
                        source,
                        "Task provider returned a non-mapping item",
                        level="error",
                    )
                    continue
                tasks.append(dict(item))
        return tasks

    def dispatch_app_ready(self, app: DebIDEApp) -> None:
        """Invoke app hooks once the Textual application is ready."""
        if self._app_hooks_dispatched:
            return
        self._app_hooks_dispatched = True
        for source, hook in list(self._app_hooks):
            try:
                hook(app)
            except Exception as error:
                self._add_message(
                    source,
                    f"App hook raised {error!r}",
                    level="error",
                )

    def consume_messages(self) -> list[PluginMessage]:
        """Return and clear accumulated plugin messages."""
        messages, self._messages = self._messages, []
        return messages

    def _activate_plugin(self, plugin_obj: Any, source: str) -> None:
        register_callable: Callable[[PluginAPI], None] | None = None
        candidate = getattr(plugin_obj, "register", None)
        if callable(candidate):
            register_callable = candidate
        elif callable(plugin_obj):
            register_callable = plugin_obj  # type: ignore[assignment]

        if register_callable is None:
            self._add_message(
                source,
                "Plugin exposes no callable entry point; expected 'register(api)'",
                level="warning",
            )
            return

        api = PluginAPI(self, source)
        try:
            register_callable(api)
        except Exception as error:
            self._add_message(
                source,
                f"Plugin raised {error!r} during registration",
                level="error",
            )
            return

        self._loaded_plugins.append(source)
        self._add_message(source, "Registered plugin", level="info")

    def _register_task(self, source: str, mapping: Mapping[str, object]) -> None:
        if not isinstance(mapping, Mapping):
            raise TypeError("Task definition must be a mapping")
        self._static_tasks.append((source, dict(mapping)))

    def _register_task_provider(self, source: str, provider: TaskProvider) -> None:
        if not callable(provider):
            raise TypeError("Task provider must be callable")
        self._task_providers.append((source, provider))

    def _register_app_hook(self, source: str, callback: AppHook) -> None:
        if not callable(callback):
            raise TypeError("App hook must be callable")
        self._app_hooks.append((source, callback))

    def _add_message(self, source: str, text: str, *, level: str = "info") -> None:
        level = level.lower()
        if level not in {"info", "warning", "error"}:
            level = "info"
        self._messages.append(PluginMessage(source=source, level=level, text=text))


def _select_entry_points(group: str) -> Iterable[metadata.EntryPoint]:
    """Return entry points for the given group, compatible with multiple Python versions."""
    try:
        return metadata.entry_points(group=group)
    except TypeError:  # pragma: no cover - legacy API path for Python <3.10.10
        all_entry_points = metadata.entry_points()
        if isinstance(all_entry_points, dict):  # Older setuptools behaviour
            return all_entry_points.get(group, [])
        return [entry_point for entry_point in all_entry_points if entry_point.group == group]
