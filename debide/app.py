"""Main Textual application for DebIDE."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
from pathlib import Path
from time import perf_counter
from typing import TypeVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label

from .config import DebIDEConfig, load_config
from .editor import EditorError, EditorPane
from .layout import ConsolePane, FileExplorer, TaskDetails, TaskList
from .scaffold import PackageMetadata, scaffold_debian_packaging
from .tasks import TaskSpec


class SaveAsScreen(ModalScreen[Path | None]):
    """Modal prompt to capture a target path for saving files."""

    DEFAULT_CSS = """
    SaveAsScreen {
        align: center middle;
    }

    #save-as-dialog {
        width: 60;
        border: round $surface;
        padding: 1 2;
        background: $panel;
    }

    #save-as-input {
        width: 100%;
    }

    #save-as-buttons {
        align-horizontal: right;
    }
    """

    def __init__(self, workspace: Path, initial: str = "") -> None:
        super().__init__()
        self.workspace = workspace
        self._initial = initial

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Save file as…"),
            Input(placeholder="Path (relative to workspace)", id="save-as-input"),
            Horizontal(
                Button("Cancel", id="save-as-cancel"),
                Button("Save", variant="primary", id="save-as-confirm"),
                id="save-as-buttons",
            ),
            id="save-as-dialog",
        )

    def on_mount(self) -> None:
        input_widget = self.query_one(Input)
        if self._initial:
            input_widget.value = self._initial
        input_widget.focus()

    def _resolve_path(self, raw_value: str) -> Path:
        candidate = Path(raw_value).expanduser()
        if not candidate.is_absolute():
            candidate = (self.workspace / candidate).resolve()
        return candidate

    def _submit(self) -> None:
        value = self.query_one(Input).value.strip()
        if not value:
            self.app.notify("Enter a file name", severity="warning")
            return
        target = self._resolve_path(value)
        if target.is_dir():
            self.app.notify("Cannot save to a directory", severity="error")
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.app.notify(f"Unable to create directory: {error}", severity="error")
            return
        self.dismiss(target)

    @on(Input.Submitted)
    def handle_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._submit()

    @on(Button.Pressed)
    def handle_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "save-as-confirm":
            self._submit()
        else:
            self.dismiss(None)


class SwitchWorkspaceScreen(ModalScreen[Path | None]):
    """Prompt the user for a new workspace directory."""

    DEFAULT_CSS = """
    SwitchWorkspaceScreen {
        align: center middle;
    }

    #switch-workspace-dialog {
        width: 60;
        border: round $surface;
        padding: 1 2;
        background: $panel;
    }

    #switch-workspace-input {
        width: 100%;
    }

    #switch-workspace-buttons {
        align-horizontal: right;
    }
    """

    def __init__(self, workspace: Path) -> None:
        super().__init__()
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Switch workspace"),
            Input(placeholder="Directory (relative or absolute)", id="switch-workspace-input"),
            Horizontal(
                Button("Cancel", id="switch-workspace-cancel"),
                Button("Open", variant="primary", id="switch-workspace-confirm"),
                id="switch-workspace-buttons",
            ),
            id="switch-workspace-dialog",
        )

    def on_mount(self) -> None:
        input_widget = self.query_one(Input)
        input_widget.value = str(self.workspace)
        input_widget.cursor_position = len(input_widget.value)
        input_widget.focus()

    def _resolve_path(self, raw_value: str) -> Path:
        candidate = Path(raw_value).expanduser()
        if not candidate.is_absolute():
            candidate = (self.workspace / candidate).resolve()
        return candidate

    def _submit(self) -> None:
        raw_value = self.query_one(Input).value.strip()
        if not raw_value:
            self.app.notify("Enter a workspace path", severity="warning")
            return
        target = self._resolve_path(raw_value)
        if not target.exists():
            self.app.notify(f"{target} does not exist", severity="error")
            return
        if not target.is_dir():
            self.app.notify(f"{target} is not a directory", severity="error")
            return
        self.dismiss(target)

    @on(Input.Submitted)
    def handle_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._submit()

    @on(Button.Pressed)
    def handle_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "switch-workspace-confirm":
            self._submit()
        else:
            self.dismiss(None)


ModalResult = TypeVar("ModalResult")


class DebIDEApp(App):
    """Terminal-native IDE tailored for Debian packaging."""

    CSS_PATH = "resources/app.tcss"
    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+shift+s", "save_all", "Save All"),
        Binding("ctrl+alt+s", "save_as", "Save As"),
        Binding("ctrl+r", "run_task", "Run task"),
        Binding("f5", "run_task", show=False),
        Binding("ctrl+o", "focus_files", "Files"),
        Binding("ctrl+shift+o", "switch_workspace", "Switch project"),
        Binding("ctrl+n", "scaffold", "Scaffold debian/"),
        Binding("f1", "show_shortcuts", "Shortcuts"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, workspace: Path, config: DebIDEConfig) -> None:
        super().__init__()
        self.workspace = workspace.expanduser().resolve()
        self.config = config
        self.editor = EditorPane()
        self.console_view = ConsolePane()
        self.task_list = TaskList(config.tasks)
        self.task_details = TaskDetails()
        self._running_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield FileExplorer(str(self.workspace))
            with Vertical(id="workspace-pane"):
                yield self.editor
                with Horizontal(id="lower-pane"):
                    with Vertical(id="task-pane"):
                        yield self.task_list
                        yield self.task_details
                    yield self.console_view
        yield Footer()

    def on_mount(self) -> None:
        self._apply_workspace(self.workspace, self.config, announce=False)

    def _get_selected_task(self) -> TaskSpec | None:
        task = self.task_list.get_selected_task()
        if not task and self.config.default_task:
            task_name = self.config.default_task
            task = next(
                (candidate for candidate in self.config.tasks if candidate.name == task_name),
                None,
            )
        return task

    def _log(self, message: str) -> None:
        self.console_view.write(message, expand=False)

    async def _prompt_save_as(self, editor: EditorPane) -> Path | None:
        initial = ""
        if editor.current_path:
            try:
                initial = str(editor.current_path.relative_to(self.workspace))
            except ValueError:
                initial = str(editor.current_path)
        screen = SaveAsScreen(self.workspace, initial=initial)
        result = await self._wait_for_modal(screen)
        return result

    async def action_save(self) -> None:
        try:
            self.editor.save()
        except EditorError as error:
            self.notify(str(error), severity="error")
            return

    async def action_save_all(self) -> None:
        editors = list(self.query(EditorPane))
        if not editors:
            self.notify("No editors available to save", severity="warning")
            return
        saved = 0
        skipped = 0
        errors: list[str] = []
        for editor in editors:
            if not editor.is_dirty:
                continue
            target_path = editor.current_path
            if target_path is None:
                target_path = await self._prompt_save_as(editor)
                if target_path is None:
                    skipped += 1
                    continue
            try:
                editor.save(target_path)
                saved += 1
            except EditorError as error:
                errors.append(str(error))
        if saved:
            self.notify(f"Saved {saved} file(s)", timeout=4)
        if skipped:
            self.notify(
                f"Skipped {skipped} buffer(s) without a saved path", severity="warning"
            )
        if errors:
            for message in errors:
                self._log(f"[red]{message}[/red]")
            self.notify(
                f"Failed to save {len(errors)} file(s). Check console for details.",
                severity="error",
            )
        if not any((saved, skipped, errors)):
            self.notify("All files already saved", timeout=3)

    async def action_save_as(self) -> None:
        target = await self._prompt_save_as(self.editor)
        if target is None:
            return
        try:
            self.editor.save(target)
        except EditorError as error:
            self.notify(str(error), severity="error")

    async def action_focus_files(self) -> None:
        self.query_one(FileExplorer).focus()

    async def action_switch_workspace(self) -> None:
        if self.editor.is_dirty:
            self.notify("Save changes before switching workspace", severity="warning")
            return
        screen = SwitchWorkspaceScreen(self.workspace)
        await self.push_screen(screen, callback=self._handle_workspace_selection)

    async def action_run_task(self) -> None:
        task = self._get_selected_task()
        if task is None:
            self.notify("No task selected", severity="warning")
            return
        self._start_task(task)

    def _start_task(self, task: TaskSpec) -> None:
        if self._running_task and not self._running_task.done():
            self.notify("A task is already running", severity="warning")
            return
        if self.config.autosave and self.editor.is_dirty and self.editor.current_path:
            try:
                self.editor.save()
            except EditorError as error:
                self.notify(f"Autosave failed: {error}", severity="error")
        missing = self._detect_missing_executable(task.command)
        if missing:
            message = (
                f"Command '{missing}' is not available on PATH. "
                "Check that required packages are installed."
            )
            self._log(f"[red]{message}[/red]")
            self.notify(message, severity="error")
            return
        self._running_task = asyncio.create_task(self._execute_task(task))
        self._running_task.add_done_callback(self._handle_task_completion)

    def _handle_task_completion(self, task: asyncio.Task) -> None:
        if task.cancelled():  # pragma: no cover - interactive cancellation
            self._log("[yellow]Task cancelled[/yellow]")
            self._running_task = None
            return
        exception = task.exception()
        if exception:
            self.console_view.write(f"[red]Task failed: {exception}[/red]")
            self.notify(str(exception), severity="error")
        self._running_task = None

    def _detect_missing_executable(self, command: str) -> str | None:
        """Return the referenced executable if it is unavailable."""
        snippet = self._extract_primary_command(command)
        if snippet is None:
            return None
        if shutil.which(snippet):
            return None
        return snippet

    @staticmethod
    def _extract_primary_command(command: str) -> str | None:
        """Best-effort guess of the first executable in a shell command string."""
        stripped = command.strip()
        if not stripped:
            return None
        for separator in ("&&", "||", "|", ";", "\n"):
            if separator in stripped:
                stripped = stripped.split(separator, 1)[0].strip()
        try:
            tokens = shlex.split(stripped, posix=True)
        except ValueError:
            return None
        for token in tokens:
            if "=" in token and not token.startswith(("'", '"')):
                # Skip leading environment assignments like FOO=bar cmd
                key = token.split("=", 1)[0]
                if key:
                    continue
            return token
        return None

    async def action_scaffold(self) -> None:
        maintainer_name = (
            os.getenv("DEBFULLNAME")
            or os.getenv("DEBNAME")
            or os.getenv("NAME")
            or "Debian Maintainer"
        )
        maintainer_email = (
            os.getenv("DEBEMAIL") or os.getenv("EMAIL") or "maintainer@example.com"
        )
        metadata = PackageMetadata(
            name=self.workspace.name.lower().replace("_", "-"),
            maintainer_name=maintainer_name,
            maintainer_email=maintainer_email,
            summary=f"{self.workspace.name} package",
            description="Initial Debian package generated via DebIDE.",
        )
        try:
            created = scaffold_debian_packaging(self.workspace, metadata)
        except FileExistsError as error:
            self.notify(str(error), severity="warning")
            return
        paths = ", ".join(str(path.relative_to(self.workspace)) for path in created)
        self._log(f"[cyan]Created Debian skeleton[/cyan]: {paths}")
        self.notify("debian/ skeleton generated", timeout=4)

    def action_show_shortcuts(self) -> None:
        shortcuts = "\n".join(
            f"{binding.key}: {binding.description}"
            for binding in self.BINDINGS
            if binding.description
        )
        self.console_view.write("[bold]Key bindings:[/bold]\n" + shortcuts)

    async def _execute_task(self, task: TaskSpec) -> None:
        start = perf_counter()
        self.console_view.write_section(f"Running {task.name}")
        env = os.environ.copy()
        env.update(task.env)
        cwd = task.resolve_working_dir(self.workspace)
        self.console_view.write(f"$ {task.command}  (cwd: {cwd})")
        process = await asyncio.create_subprocess_shell(
            task.command,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            self.console_view.write(line.decode().rstrip())
        return_code = await process.wait()
        duration = perf_counter() - start
        if return_code == 0:
            self._log(f"[green]✔[/green] {task.name} finished in {duration:.2f}s")
        else:
            self._log(
                f"[red]✖[/red] {task.name} failed with code {return_code} ({duration:.2f}s)"
            )
            self.notify(f"{task.name} failed", severity="error")

    @on(FileExplorer.FileSelected)
    def handle_file_selected(self, event: FileExplorer.FileSelected) -> None:
        event.stop()
        path = Path(event.path)
        if path.is_dir():
            return
        try:
            self.editor.load_file(path)
            self._log(f"Opened {path.relative_to(self.workspace)}")
        except EditorError as error:
            self.notify(str(error), severity="error")

    @on(TaskList.TaskActivated)
    def handle_task_activated(self, event: TaskList.TaskActivated) -> None:
        event.stop()
        self._start_task(event.task)

    @on(TaskList.TaskHighlighted)
    def handle_task_highlighted(self, event: TaskList.TaskHighlighted) -> None:
        event.stop()
        self.task_details.show_task(event.task)

    @on(EditorPane.FileLoaded)
    def handle_file_loaded(self, event: EditorPane.FileLoaded) -> None:
        event.stop()
        relative = event.path
        try:
            relative = event.path.relative_to(self.workspace)
        except ValueError:
            pass
        self.sub_title = str(relative)

    @on(EditorPane.FileSaved)
    def handle_file_saved(self, event: EditorPane.FileSaved) -> None:
        event.stop()
        relative = event.result.path
        try:
            relative = event.result.path.relative_to(self.workspace)
        except ValueError:
            pass
        self._log(f"[green]Saved[/green] {relative} ({event.result.bytes_written} bytes)")

    def _apply_workspace(
        self, workspace: Path, config: DebIDEConfig, *, announce: bool = True
    ) -> None:
        workspace = workspace.expanduser().resolve()
        self.workspace = workspace
        self.config = config
        self.title = f"DebIDE – {workspace}"
        self.sub_title = ""

        file_explorer = self.query_one(FileExplorer)
        file_explorer.path = str(workspace)
        file_explorer.reload()

        self.editor.load_blank()

        self.task_list.set_tasks(config.tasks)
        selected_task: TaskSpec | None = None
        if self.config.default_task and self.task_list.select_task(self.config.default_task):
            selected_task = self.task_list.get_selected_task()
        else:
            selected_task = self.task_list.get_selected_task()
        if selected_task:
            self.task_details.show_task(selected_task)
        else:
            self.task_details.update("Select a task to view details.")

        if self.config.default_task:
            self.console_view.write(
                f"Default task configured: [bold]{self.config.default_task}[/bold]"
            )

        if announce:
            self.console_view.write(f"[cyan]Switched workspace[/cyan]: {workspace}")
        file_explorer.focus()

    def _handle_workspace_selection(self, target: Path | None) -> None:
        if target is None:
            return
        if not target.exists():
            self.notify(f"{target} does not exist", severity="error")
            return
        if not target.is_dir():
            self.notify(f"{target} is not a directory", severity="error")
            return
        try:
            config = load_config(target)
        except Exception as error:  # pragma: no cover - configuration errors bubble to UI
            self.notify(str(error), severity="error")
            return
        self._apply_workspace(target, config)

    async def _wait_for_modal(
        self, screen: ModalScreen[ModalResult]
    ) -> ModalResult | None:
        loop = asyncio.get_running_loop()
        result_future: asyncio.Future[ModalResult | None] = loop.create_future()

        def _resolve(result: ModalResult | None) -> None:
            if not result_future.done():
                result_future.set_result(result)

        await_mount_or_future = self.push_screen(screen, callback=_resolve)
        if isinstance(await_mount_or_future, asyncio.Future):
            await await_mount_or_future
        else:
            await await_mount_or_future
        return await result_future
