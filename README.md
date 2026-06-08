# MacroEverything

> 🇫🇷 [Version française](README.FR.md)

---

Advanced automated macro builder user friendly.  

### Quick start

1. **Double-click** `run.bat` (if Python is already installed)
2. **Or** double-click `install_and_run.bat` (auto-installs Python + Pillow if missing)

### Available node types

| Category  | Node                        | Description                                              |
|-----------|-----------------------------|----------------------------------------------------------|
| Action    | 🖱️ Mouse click             | Left/right/middle click at a position                    |
| Action    | ➡️ Move mouse              | Move cursor to a position                                |
| Action    | 🖱️ Scroll                  | Mouse wheel up/down                                      |
| Action    | ⌨️ Press key               | Keyboard shortcuts (ctrl+c, F5, enter…)                  |
| Action    | 📝 Type text               | Types text into the active window                        |
| Action    | ⏱️ Wait                    | Pause for a number of milliseconds                       |
| Action    | ▶️ Run program             | Opens a file or shell command                            |
| Action    | 🔍 Focus window            | Activates a window by title                              |
| Action    | ⏺ Record & Replay          | Records keyboard/mouse actions and replays them          |
| Condition | 📸 If screen contains       | Image detection via screenshot                           |
| Condition | 🎨 If pixel = color         | Checks the color of a pixel on screen                    |
| Condition | 📊 If variable              | Compares a variable to a value                           |
| Condition | 🔗 Condition group          | Combines conditions (AND / OR / NAND / NOR)              |
| Loop      | 🔁 Repeat N times           | Simple counter-based loop                                |
| Loop      | 🔄 While (screen)           | Loop based on screen image detection                     |
| Loop      | 🔁 While (variable)         | Loop based on a variable condition                       |
| Variable  | 📦 Set variable             | Assigns a numeric value to a variable                    |
| Variable  | ➕ Modify variable          | Adds a delta to a variable                               |
| Control   | 🏷️ Label                   | Named bookmark                                           |
| Control   | ↩️ Goto label               | Unconditional jump to a label                            |
| Control   | 📞 Call macro               | Calls another macro from the same file                   |
| Control   | ⏹️ Stop / Return            | Stops the macro and returns True or False                |

### Record & Replay

The **Record & Replay** node captures a sequence of actions in real time:
- Choose a trigger key (e.g. F6)
- Press the key → recording starts (red indicator)
- Press again → recording stops and actions are saved
- When the macro runs, the sequence is replayed faithfully
- Options: mouse clicks, scroll, movements, keyboard input, absolute/relative mode

### Interface

- **Visual tree** — each node displays with a parameter summary
- **Right-click** a node → context menu (edit, move, duplicate, delete, copy/paste image)
- **Double-click** a node → opens the parameter editor
- **Right panel** → detailed properties of the selected node
- **Coordinate picker** → overlay covering all monitors for visual point selection
- **Region capture** → rectangular screen area selection across all monitors
- **Global hotkeys** → run/stop/pause even when the app is in the background
- **Settings panel** → debug overlay toggle (image detection visualization)
- **Resolution scaling** — coordinates are automatically scaled when the playback resolution differs from the recording resolution
- Bilingual **FR / EN** interface (Easy to add localization with json file)
- Saved as `.macros` files (human-readable JSON)

### Image detection (If screen contains / While screen)

Detection runs in 3 passes, all heavy operations are C-level PIL (no Python pixel loops):

1. **Thumbnail scan** — both the template and the screenshot are shrunk to ≤ 16 px. The thumbnail slides across the screen with a 4 px step (~3 000 positions). Score = colour SAD via PIL histogram. The 15 best zones are kept.
2. **Full-resolution coarse scan** — SAD in greyscale around each of the 15 zones, step = template / 8. Finds the best candidate position.
3. **Pixel-precise refinement** — exhaustive 1 px step scan in a ±step2 window around the candidate. Guarantees sub-pixel accuracy without re-scanning the whole screen.

If the debug overlay is enabled (Settings), a coloured rectangle is drawn around the best match after each check: green = found, orange = close, red = not found; for you to change the correspondence ratio as needed.

### Dependencies

- Python 3.8+
- Pillow (`pip install pillow`) — screenshot capture and image detection

### File structure

```
MacroEverything/
├── main.py                    ← Application entry point
├── Lancer.bat                 ← Quick launch
├── install_and_run.bat        ← Auto-install + launch
├── settings.json              ← Settings (language, hotkeys…)
├── locales/
│   ├── en.json                ← English translations
│   ├── fr.json                ← French translations
│   └── langs.json             ← Available languages list
├── macros/                    ← Macro files folder (.macros)
└── macro_app/
    ├── constants.py           ← Colors, fonts, node type definitions
    ├── engine.py              ← Macro execution engine
    ├── hotkeys.py             ← Global hotkey manager
    ├── i18n.py                ← Translation system
    ├── models.py              ← Data models
    ├── settings.py            ← Settings read/write
    ├── utils.py               ← System utilities
    └── ui/
        ├── app.py             ← Main window
        ├── dialogs.py         ← Node editors and overlays
        ├── panels.py          ← Properties panel
        └── tree_canvas.py     ← Node tree renderer
```
