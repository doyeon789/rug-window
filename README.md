# Rug Window

Sweep your messy desktop under a 3D cloth rug. A carpet lies on your Windows
desktop, above the icons and below every other window. Grab it with the mouse
to drag it around or fold it over itself; it bumps up over the icons hidden
underneath.

Inspired by a macOS experiment by Terkel ([@terkelg](https://x.com/terkelg),
GitHub Next). This is an independent Windows implementation (Python, PySide6,
OpenGL) and shares no code with it.

## Download and run (Windows 10/11)

1. Download `RugWindow-v<version>-windows.zip` from
   [Releases](https://github.com/doyeon789/rug-window/releases).
2. Unzip it anywhere and double-click `RugWindow.exe`.
   - The exe is not code-signed, so Windows SmartScreen may warn
     ("Unknown publisher"). Choose **More info → Run anyway**.
3. A rug appears in the middle of the screen, and a rug icon appears in the
   notification area (tray; it may be under the `^` overflow).

## Use

| Action | How |
|---|---|
| Drag the rug | Press the left button on the rug and move |
| Fold it | Grab an edge or corner and pull it back over the rug |
| Hide / show | Tray icon → Hide rug / Show rug |
| Quit | Tray icon → Quit |

Clicks off the rug go to the desktop as usual. Only one copy runs at a time.
Logs are written to `%LOCALAPPDATA%\rug-window\rug-window.log`.

## Known limits

- Windows only. Needs OpenGL 3.3.
- Uses a full-screen transparent window: fast drags can stutter, and memory use
  is high (hundreds of MB).
- Desktop icons hosted under `WorkerW` (some setups) are not detected.

## Develop

```
uv sync
uv run python -m rug_window          # run from source
uv run pytest                        # tests
uv run python tools/build_release.py # build the release zip
```

Design notes and learning notes: `docs/explainers/rug-window.md`.

## Contributing

Bug reports, ideas, and pull requests are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Report security problems privately as
described in [SECURITY.md](SECURITY.md).

## License

MIT (see `LICENSE`). Bundled third-party software and assets are listed in
`THIRD_PARTY_NOTICES.md`; the carpet texture is CC0 from ambientCG.
