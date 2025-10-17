"""Editor widget wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from textual import events
from textual.message import Message
from textual.widgets import Static, TextArea


class EditorError(RuntimeError):
    """Raised when the editor fails to load or save a file."""


LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".sh": "bash",
}


@dataclass
class SaveResult:
    path: Path
    bytes_written: int


class EditorPane(Static):
    """Encapsulates the editable text area plus load/save helpers."""

    DEFAULT_CSS = """
    EditorPane {
        border: round $primary;
    }
    """

    class FileLoaded(Message):
        def __init__(self, path: Path) -> None:
            self.path = path
            super().__init__()

    class FileSaved(Message):
        def __init__(self, result: SaveResult) -> None:
            self.result = result
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="editor-pane")
        self.text_area = TextArea(language=None, id="editor")
        self.current_path: Optional[Path] = None
        self._loaded_text: str = ""

    def compose(self):
        yield self.text_area

    def on_mount(self) -> None:
        self.text_area.focus()

    def _guess_language(self, path: Path) -> Optional[str]:
        suffix = path.suffix.lower()
        if suffix in LANGUAGE_BY_SUFFIX:
            return LANGUAGE_BY_SUFFIX[suffix]
        if path.name in LANGUAGE_BY_SUFFIX:
            return LANGUAGE_BY_SUFFIX[path.name]
        return None

    def load_file(self, path: Path) -> None:
        path = path.resolve()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - binary files
            raise EditorError(f"Unable to decode file {path}") from exc
        self.text_area.load_text(text)
        language = self._guess_language(path)
        if language:
            try:
                self.text_area.language = language
            except Exception:  # pragma: no cover - depends on optional extras
                self.text_area.language = None
        else:
            self.text_area.language = None
        self.current_path = path
        self._loaded_text = text
        self.post_message(self.FileLoaded(path))

    def load_blank(self, language: Optional[str] = None) -> None:
        self.text_area.clear()
        self.text_area.language = language
        self.current_path = None
        self._loaded_text = ""

    @property
    def text(self) -> str:
        return self.text_area.text

    @property
    def is_dirty(self) -> bool:
        return self.text != self._loaded_text

    def save(self, path: Optional[Path] = None) -> SaveResult:
        target = path or self.current_path
        if target is None:
            raise EditorError("No file selected to save")
        target = target.resolve()
        data = self.text
        try:
            target.write_text(data, encoding="utf-8")
        except OSError as error:
            raise EditorError(f"Unable to save file {target}: {error}") from error
        self.current_path = target
        self._loaded_text = data
        result = SaveResult(path=target, bytes_written=len(data.encode("utf-8")))
        self.post_message(self.FileSaved(result))
        return result

    async def on_focus(self, event: events.Focus) -> None:
        self.text_area.focus()
