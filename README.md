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
- **Right-click** a node → context menu (edit, move, delete)
- **Double-click** a node → opens the parameter editor
- **Right panel** → detailed properties of the selected node
- **Coordinate picker** → fullscreen overlay for visual point selection
- **Region capture** → rectangular screen area selection
- **Global hotkeys** → run/stop/pause even when the app is in the background
- Bilingual **FR / EN** interface (Easy to add localization with json file)
- Saved as `.macros` files (human-readable JSON)

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
