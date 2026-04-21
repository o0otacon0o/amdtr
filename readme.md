# amdtr (Another Markdown Editor) v1.2.0

![amdtr Logo](amdtr-logo.png)

**amdtr** is a professional, high-performance Markdown editor built with **Python 3** and **PyQt6**. It bridges the gap between raw text editing and rich visual previews, focusing on speed, extensibility, and portable document workflows.

## 📸 Screenshots

| ![sc_01](screenshots/sc_01.png) | ![sc_02](screenshots/sc_02.png) |
| :--- | :--- |
| **Dark Theme & Auto-Outline**: Comprehensive workspace with automated Table of Contents. | **Light Theme & Mermaid**: High-performance rendering of complex diagrams. |

## 🚀 Key Features

*   **⚡ High-Speed Live Preview:** Real-time rendering (150ms debounced) of Markdown, Mermaid diagrams, KaTeX math, and syntax-highlighted code blocks.
*   **💨 Streamlined Workspace:** Incremental batch indexing (FTS5) for lightning-fast loading of large folders. Only changed files are re-indexed based on their modification time.
*   **🛠️ Unified Header Bar:** A streamlined UI that merges menu and toolbar into a single, space-saving element for maximum focus.
*   **📂 Clean Projects:** All metadata (search index, session, and local configuration) is stored centrally in platform-standard application data folders.
*   **📂 Smart Management:** Integrated sidebar with file management (Rename/Delete), Wikilink support, and workspace-wide full-text search.
*   **📑 Document Outline:** Automatic Table of Contents (ToC) generation from Markdown headings for lightning-fast navigation.
*   **🎨 Custom Themes:** Fully skinnable UI and editor (JSON-based themes like One Dark or GitHub Light).
*   **⌨️ Experimental Vim Mode:** Opt-in modal editing for power users (navigation, basic editing, and mode visualization).
*   **📍 Change Indicators:** Real-time gutter markers highlighting added, modified, and deleted lines since the last save.
*   **🔄 Session Restoration:** Automatically restores opened files, active tabs, and cursor positions from your last session.
*   **📂 Recent History:** Quickly re-open your latest files and workspaces from the "File" menu.
*   **🔍 Enhanced Navigation:** Tab tooltips and status bar paths for better orientation. Right-click any tab or editor to "Reveal in Explorer".
*   **📦 Portable Export:** One-click standalone HTML or professional PDF export (including Mermaid and KaTeX) with embedded assets for offline viewing.
*   **🔗 Scroll Sync:** Optional bi-directional scrolling between editor and preview.
*   **📋 Hover Actions:** Hover over any rendered code block or Mermaid diagram to reveal copy (text/image) and save (PNG) buttons for instant clipboard integration.
*   **📥 Drag & Drop:** Open Markdown files by dragging them directly into the editor window.

## ⌨️ Experimental Vim Mode (Opt-In)

**amdtr** includes a lightweight, experimental Vim state machine. This feature is disabled by default.

### Activation
Open the **Command Palette** (`Ctrl+P`) and type `:> Toggle Vim Mode`.

### Supported Commands (Normal Mode)
| Key | Action |
| :--- | :--- |
| `h` / `j` / `k` / `l` | Move cursor Left / Down / Up / Right |
| `i` | Enter **Insert Mode** (Standard typing) |
| `Esc` | Return to **Normal Mode** |
| `x` | Delete character under cursor |
| `0` (Zero) | Jump to start of line |
| `$` | Jump to end of line |
| `dd` | Delete current line |
| `u` | Undo last action |

The current mode and pending commands (like `dd`) are displayed in the status bar.

## 🛠️ Getting Started (Windows)

### 1. Create and activate virtual environment
```sh
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies
```sh
pip install -r requirements.txt
```

### 3. Setup vendor assets (JS/CSS)
Download required resources for the preview engine (one-time setup):
```sh
python setup_vendor.py
```

### 4. Run application
```sh
python main.py
# Or open specific files
python main.py path/to/file.md
```

## 📦 Windows Context Menu Integration

To open files with **amdtr** directly from the Windows Explorer context menu, you can add it to the registry.

### Manual Setup
1. Open `regedit`.
2. Navigate to `HKEY_CLASSES_ROOT\*\shell`.
3. Create a new key named `amdtr`.
4. Set the `(Default)` value to `Open with amdtr`.
5. Create a new key under `amdtr` named `command`.
6. Set the `(Default)` value to the path of your executable followed by `%1`, for example:
   `"C:\path\to\amdtr.exe" "%1"`
   *(If running from source, use the python executable and script path)*

## 📦 Build Standalone Executable
To create a standalone binary for your platform:
```sh
pip install pyinstaller
python build_app.py
```
The result will be available in the `dist/` directory.

## 📜 License
This project is licensed under the terms of the LICENSE file included in the repository.
