# DebIDE Architecture

## Purpose
DebIDE is a lightweight, terminal-native Integrated Development Environment that focuses on common Debian packaging workflows. It combines a file explorer, code editor, and Debian task automation into a single pane to streamline daily packaging tasks without leaving the terminal.

## Design Goals
- **Debian-first UX**: Surface lintian, debuild, pbuilder, and other Debian tasks as first-class actions.
- **Fast feedback**: Provide an integrated console with live command output streamed inside the IDE.
- **Extensible config**: Allow projects to define reusable task recipes in a simple YAML file.
- **Low dependency footprint**: Build the UI with [Textual](https://textual.textualize.io/) so the IDE runs in a terminal on stock Debian systems.
- **Scriptable helpers**: Offer Python utilities for generating packaging skeletons and managing changelog entries.

## High-Level Components
- `debide.app.DebIDEApp`: Textual application orchestrating widgets, key bindings, and async command execution.
- `debide/layout.py`: View composition helpers for the file tree, editor, task list, task details, and console panes.
- `debide/editor.py`: Wraps Textual's `TextArea` to load/save files with basic syntax awareness.
- `debide/tasks.py`: Task models, YAML loader, and async runner for Debian tooling commands.
- `debide/scaffold.py`: Utilities to bootstrap a Debian `debian/` directory from templates.
- `debide/config.py`: Resolve configuration defaults and project-level overrides.
- `debide/plugins.py`: Entry-point discovery, task contributions, and lifecycle hooks.
- `debide/cli.py`: Entry point that parses arguments, selects the workspace directory, and launches the app.

## Data Flow
1. The CLI parses `debide` options (workspace path, config file, --create-package, etc.).
2. The app bootstraps configuration and subscribes widgets to global messages (events).
3. `DirectoryTree` selection events load files into `EditorPane`; save commands persist to disk.
4. Task selections dispatch to `TaskRunner`, which spawns subprocesses and streams stdout/stderr to the console widget.
5. Task completion messages update status indicators and history.

## Debian Integrations
- **Task Recipes**: Default recipes call `lintian`, `debuild -us -uc`, `dpkg-buildpackage`, `uscan`, and `sbuild` with optional per-task environment overrides.
- **Autosave Hooks**: Optional autosave before task execution keeps packaging files current when `autosave: true`.
- **Scaffolding**: Generates minimal `debian/control`, `debian/changelog`, `debian/rules`, and `debian/compat` files with sensible defaults.
- **Context Awareness**: Auto-detects `debian/` directories to pre-select packaging views and show helpful tips.

## Key Bindings (planned defaults)
- `Ctrl-o`: Open file explorer focus.
- `Ctrl-s`: Save active buffer.
- `Ctrl-r`: Run selected task.
- `Ctrl-n`: Prompt to scaffold Debian package metadata.
- `F1`: Toggle command palette with available tasks/actions.

## Future Enhancements
- Integrate `gbp` (git-buildpackage) workflows.
- Provide diff viewer for quilt patches.
- Offer Snippets/Templates for `debian/control` stanzas.
- Broaden the plugin API with additional UI integration points.

## Plugin System
Plugins are regular Python packages that expose a `debide.plugins` entry-point. During CLI startup the `PluginManager` loads each entry, calling `register(api)` with a `PluginAPI` helper. Plugins can:

- statically add task mappings via `api.add_task(mapping)`;
- provide workspace-dependent tasks with `api.provide_tasks(callback)`;
- subscribe to the Textual app lifecycle through `api.on_app_ready(callback)`;
- emit diagnostic messages with `api.info()`, `api.warning()`, or `api.error()`.

Messages from plugins feed into the console log so configuration issues surface alongside build output. Task definitions contributed by plugins are merged with the core defaults before YAML configuration is parsed, allowing user config to override or extend them naturally.
