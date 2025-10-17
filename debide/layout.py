"""UI widgets and layout helpers for DebIDE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from textual.message import Message
from textual.widgets import DirectoryTree, ListItem, ListView, RichLog, Static

from .tasks import TaskSpec


class FileExplorer(DirectoryTree):
    """Wrapper around DirectoryTree with a friendlier default id."""

    def __init__(self, path: str | None = None) -> None:
        super().__init__(path or ".", id="file-tree")
        self.show_root = False


@dataclass
class TaskListItemData:
    task: TaskSpec


class TaskListItem(ListItem):
    """Individual entry in the task list."""

    def __init__(self, task: TaskSpec) -> None:
        super().__init__(Static(task.name))
        self.data = TaskListItemData(task=task)
        self.tooltip = task.description or task.command


class TaskList(ListView):
    """List of Debian task recipes."""

    class TaskActivated(Message):
        def __init__(self, task: TaskSpec) -> None:
            self.task = task
            super().__init__()

    class TaskHighlighted(Message):
        def __init__(self, task: TaskSpec) -> None:
            self.task = task
            super().__init__()

    def __init__(self, tasks: Iterable[TaskSpec]) -> None:
        super().__init__(id="task-list")
        self._items = list(tasks)

    def on_mount(self) -> None:
        for task in self._items:
            self.append(TaskListItem(task))
        if self.children:
            self.index = 0

    def set_tasks(self, tasks: Iterable[TaskSpec]) -> None:
        self._items = list(tasks)
        self.clear()
        for task in self._items:
            self.append(TaskListItem(task))
        if self._items:
            self.index = 0
        else:
            self.index = None

    def select_task(self, name: str) -> bool:
        for idx, task in enumerate(self._items):
            if task.name == name:
                self.index = idx
                return True
        return False

    def get_selected_task(self) -> Optional[TaskSpec]:
        if self.index is None:
            return None
        if self.index < 0 or self.index >= len(self._items):
            return None
        return self._items[self.index]

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        task = self.get_selected_task()
        if task:
            event.stop()
            self.post_message(self.TaskActivated(task))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        task = self.get_selected_task()
        if task:
            event.stop()
            self.post_message(self.TaskHighlighted(task))


class ConsolePane(RichLog):
    """Text log styled for command output."""

    def __init__(self) -> None:
        super().__init__(id="console", highlight=True, markup=True)
        self.write("DebIDE console ready. Select a task to run", expand=False)

    def write_section(self, heading: str) -> None:
        self.write(f"[bold underline]{heading}[/bold underline]")


class TaskDetails(Static):
    """Display contextual information about the currently highlighted task."""

    DEFAULT_CSS = """
    TaskDetails {
        border: round $surface;
        padding: 0 1;
        height: 6;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="task-details")
        self.update("Select a task to view details.")

    def show_task(self, task: TaskSpec) -> None:
        description = task.description or "No description provided."
        self.update(
            f"[bold]{task.name}[/bold]\n"
            f"[dim]{task.command}[/dim]\n"
            f"{description}"
        )
