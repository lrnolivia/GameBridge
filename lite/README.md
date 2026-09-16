# GameBridge Lite

GameBridge Lite is a small GTK4 utility for keeping supported player-name settings consistent across a local game library.

## Features

- **Review Games** performs a read-only inventory of recognized player-name settings.
- **Sync Player Names** previews supported player-name updates before making changes.
- Every modified configuration file is backed up before writing and verified afterward.
- Steam account information can be used to choose a player name automatically, or a name can be entered manually.
- Save data, executables, libraries, game assets, account IDs, user IDs, app IDs, and unrelated configuration values are left untouched.

GameBridge only inspects small text-based configuration files and only updates recognized player-name fields when the existing value matches a supported compatibility signature.

## Install on Linux

From the unpacked folder:

```bash
chmod +x install-user.sh gamebridge-lite GameBridge-Lite.py
./install-user.sh
```

Launch **GameBridge Lite** from the app menu or run:

```bash
gamebridge-lite
```

To run directly without installing:

```bash
./gamebridge-lite
```

## Requirements

- Python 3
- GTK4 Python bindings (`python3-gobject` / PyGObject)

## Application icon

The package includes the GameBridge icon at standard `hicolor` launcher sizes. The desktop entry uses `com.loew.gamebridgelite`, allowing desktop icon themes to fall back to the bundled artwork when no themed override is available.
