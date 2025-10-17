# DebIDE

DebIDE is a terminal-native Integrated Development Environment tailored for Debian packaging workflows. It combines a project-aware file explorer, code editor, Debian task runner, and scaffolding helpers inside a single Textual interface.<img width="1902" height="1061" alt="Screenshot 2025-10-16 8 21 35 PM" src="https://github.com/user-attachments/assets/5cc17cdf-86f3-4d39-a5cd-7852e30bf683" />


## Highlights
- Debian-first task palette for `lintian`, `debuild`, `dpkg-buildpackage`, `uscan`, and `sbuild`
- Split-pane workspace with file tree, editor, task detail panel, and live console
- Configurable task recipes via `.debide.yml`, including per-task environment overrides
- One-shot Debian packaging skeleton generator (`Ctrl+N` or `debide scaffold`)
- Optional autosave before executing tasks, controlled through configuration

## Requirements
- Python ≥ 3.10
- Terminal with UTF-8 locale
- Debian tooling installed for the recipes you plan to run (`lintian`, `devscripts`, `sbuild`, etc.)

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
debide .
```

## Usage
- Navigate the file tree with the arrow keys and press `Enter` to open files.
- Edit files in the main pane; press `Ctrl+S` to save.
- Use `Ctrl+Alt+S` to save the active buffer under a new path.
- Press `Ctrl+Shift+O` to switch the active workspace to another directory.
- Press `Ctrl+Shift+S` to save every open editor buffer at once; unnamed buffers prompt for a path.
- Highlight Debian tasks with the arrow keys to view details; press `Enter` or `Ctrl+R` to run the selected task.
- Review live command output in the console pane; task results are timestamped and color-coded.
- Press `Ctrl+N` to scaffold a fresh `debian/` directory using maintainer metadata sourced from `DEBFULLNAME` and `DEBEMAIL` when available.

### Command-Line Interface
- `debide [workspace]` – launch the IDE in the given directory (defaults to `.`).
- `debide --config path/to/.debide.yml` – start with an explicit configuration file.
- `debide scaffold <name> [--version X] [--maintainer-name "Jane Doe"] [...]` – generate Debian packaging files without opening the UI.

### Configuration
Create `.debide.yml` in your workspace to customise tasks and behaviours:

```yaml
autosave: true
default_task: debuild
tasks:
  - name: pbuilder
    command: pdebuild --use-pdebuild-internal
    description: Build inside a pbuilder chroot
    working_dir: debian
    env:
      DEBUILD_DPKG_BUILDPACKAGE_OPTS: "-us -uc"
```

Any tasks declared here extend or override the built-in defaults.

## Project Layout
- `debide/app.py` – Textual application orchestration
- `debide/editor.py` – text editor wrapper
- `debide/layout.py` – reusable UI widgets
- `debide/tasks.py` – task models and validation
- `debide/config.py` – configuration loader and merger
- `debide/scaffold.py` – Debian skeleton generator
- `docs/ARCHITECTURE.md` – in-depth architectural notes

## Roadmap
- git-buildpackage integration
- Quilt patch viewer and editor
- Task output history with search and filter

## License
Unlicense License. See `LICENSE` for full text.
