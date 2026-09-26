# game-launcher-minimal

A lightweight command line game launcher and playtime tracker for Windows. I built this to stop leaving heavy launchers open in the background and to keep a dead-simple, human-readable log of my gaming sessions.

It automatically scans your Steam libraries by reading the local Steam registry entries and parsing `libraryfolders.vdf`. You can also manually register non-Steam executables.

## How it works

- **Auto-discovery**: Finds your Steam installation, parses all configured library paths, and extracts installed games.
- **Direct Launching**: Launches games via Steam protocol or direct execution for manual games.
- **Playtime Tracking**: Monitors the launched process, tracks session duration, and appends raw session stats to a local JSON file.
- **No Background Daemons**: Runs only when you launch a game, exiting cleanly once the game is closed.

## Installation

No external pip dependencies required. It uses standard Windows libraries and APIs.

1. Clone the repository:
   ```cmd
   git clone https://github.com/yourusername/game-launcher-minimal.git
   cd game-launcher-minimal
   ```

2. Run the tool directly with Python:
   ```cmd
   python launcher.py --help
   ```

## Usage

### Sync with Steam
Sync and discover all installed Steam games on your system:
```cmd
python launcher.py sync
```

### List all games
Show tracked games, their configured paths/IDs, and total playtime:
```cmd
python launcher.py list
```

### Register a non-Steam game
```cmd
python launcher.py add "Cyberpunk 2077" "D:\Games\Cyberpunk 2077\bin\x64\Cyberpunk2077.exe"
```

### Launch a game
Launch by name (partial match supported, case-insensitive):
```cmd
python launcher.py play "cyberpunk"
```
Or launch a Steam game directly:
```cmd
python launcher.py play "Hades"
```

### View stats
Displays a summary of total play hours and individual session logs:
```cmd
python launcher.py stats
```

<!-- verified: 2026-09-26 -->
