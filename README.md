# MacroEverything

> 🇫🇷 [Version française](README.FR.md)

---

Advanced automated macro builder — visual, user-friendly, no coding required.

### Quick start

| Option | How |
|--------|-----|
| **Standalone (recommended)** | Run `MacroEverything.exe` — Get it from the 'Release' section |
| **From source (Python installed)** | Run `run.bat` |
| **From source (no Python)** |Run `install_and_run.bat` — auto-installs Python(may not work if so install python 3 manually) + Pillow |

### Available node types

| Category  | Node                           | Description                                              |
|-----------|--------------------------------|----------------------------------------------------------|
| Action    | 🖱️ Mouse click                | Left/right/middle click at a position                    |
| Action    | ➡️ Move mouse                 | Move cursor to a position                                |
| Action    | 🖱️ Scroll                     | Mouse wheel up/down                                      |
| Action    | ⌨️ Press key                  | Keyboard shortcuts (ctrl+c, F5, enter…)                  |
| Action    | 📝 Type text                  | Types text into the active window                        |
| Action    | ⏱️ Wait                       | Pause for a number of milliseconds                       |
| Action    | ▶️ Run program                | Opens a file or shell command                            |
| Action    | 🔍 Focus window               | Activates a window by title                              |
| Action    | 🔍 Click on image             | Finds an image on screen and clicks it                   |
| Action    | ❖ Window layout               | Positions and/or resizes a window by title               |
| Action    | ⏺ Record & Replay             | Records keyboard/mouse actions and replays them          |
| Condition | 📸 If screen contains         | Image detection via screenshot                           |
| Condition | 🎨 If pixel = color           | Checks the color of a pixel on screen                    |
| Condition | 📊 If variable                | Compares a variable to a value                           |
| Condition | ⋇ Condition group             | Combines conditions (AND / OR / NAND / NOR)              |
| Condition | ⊟ Switch variable             | Multi-branch switch on a variable value (switch/case)    |
| Loop      | 🔁 Repeat N times             | Simple counter-based loop                                |
| Loop      | 🔄 While (screen)             | Loop based on screen image detection                     |
| Loop      | ∞ While (variable)            | Loop based on a variable condition                       |
| Variable  | 📦 Set variable               | Assigns a numeric value to a variable                    |
| Variable  | ➕ Modify variable            | Adds a delta to a variable                               |
| Control   | 🏷️ Label                      | Named bookmark                                           |
| Control   | ↩️ Goto label                  | Unconditional jump to a label                            |
| Control   | ↳ Call macro                  | Calls another macro from the same file                   |
| Control   | ↵ Stop / Return               | Stops the macro and returns True or False                |

### Switch variable

The **Switch variable** node routes execution to different branches based on a variable's value — like a `switch/case` statement:
- Define a variable to test
- Add one case value per branch (numeric or string equality)
- The last branch is always the **Default** (executed if no case matches)
- N cases → N+1 branches in the tree

### Click on image

The **Click on image** node searches for a reference image on screen and clicks it:
- Capture a reference screenshot region in the node editor
- Optionally restrict the search to a **defined region** (faster, avoids false positives)
- Configure click position: center of the found image, or custom pixel offset
- Adjustable match threshold (0.0 → 1.0)

### Record & Replay

The **Record & Replay** node captures a sequence of actions in real time:
- Choose a trigger key (e.g. F6)
- Press the key → recording starts (red indicator)
- Press again → recording stops and actions are saved
- When the macro runs, the sequence is replayed faithfully
- Options: mouse clicks, scroll, movements, keyboard input, absolute/relative mode

### Interface

- **Visual tree** — each node displays with a parameter summary and colored type badge
- **Right-click** a node → context menu (edit, move, duplicate, delete, copy/paste image)
- **Double-click** a node → opens the parameter editor
- **Properties panel** → detailed view of the selected node with:
  - **Coordinate minimap** — shows where the action lands on a scaled preview (click, move, scroll, pixel nodes)
  - **Image thumbnail** — preview of the captured reference image (image-search nodes)
  - **Screen overlay** — floating transparent crosshair showing the exact scaled real-screen position
  - **Region overlay** — floating rectangle showing the image search region at actual screen coordinates
- **Coordinate picker** → full-screen overlay for visual point selection across all monitors
- **Region selector** → drag to define a rectangular search area across all monitors
- **Global hotkeys** → run/stop/pause even when the app is in the background (configurable)
- **Settings panel** → debug overlay toggle (image detection visualization)
- **Resolution scaling** — coordinates are automatically scaled when the playback resolution differs from the recording resolution
- Bilingual **FR / EN** interface (add more languages via a JSON file)
- Saved as `.macros` files (human-readable JSON)

### Image detection (If screen contains / While screen / Click on image)

Detection runs in 3 passes, all heavy operations are C-level PIL (no Python pixel loops):

1. **Thumbnail scan** — both the template and the screenshot are shrunk to ≤ 16 px. The thumbnail slides across the screen with a 4 px step (~3 000 positions). Score = colour SAD via PIL histogram. The 15 best zones are kept.
2. **Full-resolution coarse scan** — SAD in greyscale around each of the 15 zones, step = template / 8. Finds the best candidate position.
3. **Pixel-precise refinement** — exhaustive 1 px step scan in a ±step2 window around the candidate. Guarantees sub-pixel accuracy without re-scanning the whole screen.

If the debug overlay is enabled (Settings), a coloured rectangle is drawn around the best match after each check: green = found, orange = close, red = not found.

# User Data
Everything is saved localy in '%localappdata%/RunFaster/MacroEverything' 

### Dependencies

- Python 3.10+ (only needed when running from source)
- Pillow (`pip install pillow`) — screenshot capture and image detection

### File structure

```
MacroEverything/
├── main.py                    ← Application entry point
├── run.bat                    ← Quick launch (Python required)
├── install_and_run.bat        ← Auto-install + launch
├── MacroEverything.spec       ← PyInstaller configuration
├── version_info.txt           ← Windows executable metadata
├── locales/
│   ├── en.json                ← English translations
│   ├── fr.json                ← French translations
│   └── langs.json             ← Available languages list
├── macros/                    ← Macro files folder (.macros) — dev mode
└── macro_app/
    ├── constants.py           ← Colors, fonts, node type definitions
    ├── engine.py              ← Macro execution engine
    ├── hotkeys.py             ← Global hotkey manager
    ├── i18n.py                ← Translation system
    ├── models.py              ← Data models
    ├── paths.py               ← Path resolution (dev vs .exe mode)
    ├── settings.py            ← Settings read/write
    ├── utils.py               ← System utilities
    └── ui/
        ├── app.py             ← Main window
        ├── dialogs.py         ← Node editors and region selector
        ├── panels.py          ← Properties panel with previews
        └── tree_canvas.py     ← Node tree renderer
```
