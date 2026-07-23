import sys
import os
import json
import subprocess
import time
import winreg
from pathlib import Path
import argparse

from game_launcher import vdf

def get_state_path():
    dir_path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "game_launcher"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path / "state.json"

def load_state():
    path = get_state_path()
    if not path.exists():
        return {"games": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Back up corrupted state and reset
        backup = path.with_suffix(".json.bak")
        try:
            path.rename(backup)
            print(f"Warning: state.json was corrupted. Backed up to {backup.name}", file=sys.stderr)
        except OSError:
            pass
        return {"games": {}}

def save_state(state):
    path = get_state_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        print(f"Error saving tracking data: {e}", file=sys.stderr)

def get_steam_install_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "SteamPath")
        return Path(path)
    except OSError:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "InstallPath")
            return Path(path)
        except OSError:
            return None

def find_main_exe(dir_path: Path) -> Path:
    if not dir_path.exists():
        return None
    try:
        exes = list(dir_path.glob("*.exe"))
        exes.extend(dir_path.glob("*/*.exe"))
    except OSError:
        return None
        
    if not exes:
        return None
        
    filtered = []
    for exe in exes:
        name_lower = exe.name.lower()
        # Ignore common companion or setup utilities
        if any(x in name_lower for x in ["uninst", "crashreport", "setup", "vcredist", "unitycrash", "config", "tool"]):
            continue
        filtered.append(exe)
        
    if not filtered:
        filtered = exes
        
    try:
        filtered.sort(key=lambda p: p.stat().st_size, reverse=True)
        return filtered[0]
    except (OSError, IndexError):
        return filtered[0] if filtered else None

def find_steam_games():
    steam_path = get_steam_install_path()
    if not steam_path:
        return []
        
    # print(f"DEBUG: Found Steam installation path: {steam_path}")
    
    library_folders_vdf = steam_path / "steamapps" / "libraryfolders.vdf"
    if not library_folders_vdf.exists():
        return []
        
    try:
        folders_data = vdf.parse_file(library_folders_vdf)
    except Exception:
        return []
        
    library_paths = [steam_path]
    
    # Check folders structure
    lf = folders_data.get("libraryfolders", {})
    for key, value in lf.items():
        if isinstance(value, dict) and "path" in value:
            p = Path(value["path"])
            if p not in library_paths:
                library_paths.append(p)
                
    games = []
    for lib in library_paths:
        steamapps = lib / "steamapps"
        if not steamapps.exists():
            continue
            
        for manifest in steamapps.glob("appmanifest_*.acf"):
            try:
                manifest_data = vdf.parse_file(manifest)
            except Exception:
                continue
                
            app_state = manifest_data.get("AppState", {})
            if not app_state:
                continue
                
            appid = app_state.get("appid")
            name = app_state.get("name") or app_state.get("UserConfig", {}).get("name")
            installdir = app_state.get("installdir")
            
            if not appid or not name or not installdir:
                continue
                
            common_dir = steamapps / "common" / installdir
            exe_path = find_main_exe(common_dir)
            
            games.append({
                "id": f"steam_{appid}",
                "name": name,
                "type": "steam",
                "appid": appid,
                "exe": str(exe_path) if exe_path else None,
                "dir": str(common_dir)
            })
    return games

def is_process_running(exe_name):
    try:
        CREATE_NO_WINDOW = 0x08000000
        # NH flag strips column headers
        cmd = ["tasklist", "/NH", "/FI", f"IMAGENAME eq {exe_name}"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)
        return exe_name.lower() in res.stdout.lower()
    except OSError:
        return False

def scan_steam_games():
    discovered = find_steam_games()
    if not discovered:
        print("No Steam installation or libraries resolved.")
        return
        
    state = load_state()
    added_count = 0
    updated_count = 0
    
    for g in discovered:
        gid = g["id"]
        if gid in state["games"]:
            state["games"][gid].update({
                "name": g["name"],
                "exe": g["exe"],
                "dir": g["dir"]
            })
            updated_count += 1
        else:
            state["games"][gid] = {
                "name": g["name"],
                "type": "steam",
                "appid": g["appid"],
                "exe": g["exe"],
                "dir": g["dir"],
                "launches": 0,
                "playtime_mins": 0
            }
            added_count += 1
            
    save_state(state)
    print(f"Scan complete. Added {added_count} new Steam games, updated {updated_count} existing entries.")

def add_game(name, exe_path):
    exe = Path(exe_path).resolve()
    if not exe.exists() or not exe.is_file():
        print(f"Error: Executable not found at {exe}", file=sys.stderr)
        sys.exit(1)
        
    state = load_state()
    game_id = name.lower().replace(" ", "_")
    counter = 1
    orig_id = game_id
    while game_id in state["games"]:
        game_id = f"{orig_id}_{counter}"
        counter += 1
        
    state["games"][game_id] = {
        "name": name,
        "exe": str(exe),
        "type": "custom",
        "launches": 0,
        "playtime_mins": 0
    }
    save_state(state)
    print(f"Registered '{name}' successfully with ID: {game_id}")

def list_games():
    state = load_state()
    if not state["games"]:
        print("No games tracked. Use 'scan' to scan Steam or 'add' to register a manual game.")
        return

    print(f"{'ID':<25} | {'Name':<35} | {'Type':<8} | {'Launches':<8} | {'Playtime (mins)':<15}")
    print("-" * 98)
    
    sorted_games = sorted( 
        state["games"].items(),
        key=lambda item: (item[1].get("playtime_mins", 0), item[1].get("name", "")),
        reverse=True
    )
    
    for gid, info in sorted_games:
        name = info.get("name", "Unknown")
        if len(name) > 32:
            name = name[:29] + "..."
        gtype = info.get("type", "custom")
        launches = info.get("launches", 0)
        playtime = int(info.get("playtime_mins", 0))
        print(f"{gid:<25} | {name:<35} | {gtype:<8} | {launches:<8} | {playtime:<15}")

def launch_game(game_id):
    state = load_state()
    if game_id not in state["games"]:
        print(f"Error: Game '{game_id}' not found.", file=sys.stderr)
        sys.exit(1)
        
    game = state["games"][game_id]
    game_type = game.get("type", "custom")
    
    print(f"Launching {game['name']}...")
    start_time = time.time()
    
    game["launches"] = game.get("launches", 0) + 1
    save_state(state)
    
    tracked_ok = False
    
    if game_type == "custom":
        exe_path = Path(game["exe"])
        if not exe_path.exists():
            print(f"Error: Executable for '{game['name']}' no longer exists at: {exe_path}", file=sys.stderr)
            sys.exit(1)
        try:
            proc = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
            proc.wait()
            tracked_ok = True
        except OSError as e:
            print(f"Failed to start executable: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif game_type == "steam":
        appid = game["appid"]
        exe_path_str = game.get("exe")
        exe_name = Path(exe_path_str).name if exe_path_str else None
        
        try:
            os.startfile(f"steam://rungameid/{appid}")
        except OSError as e:
            print(f"Failed to trigger Steam launch: {e}", file=sys.stderr)
            sys.exit(1)
            
        if exe_name:
            print(f"Waiting for process {exe_name} to spin up...")
            # Give Steam time to process installation/launch (up to 45 seconds)
            launched = False
            for _ in range(30):
                if is_process_running(exe_name):
                    launched = True
                    break
                time.sleep(1.5)
            
            if launched:
                print("Game detected. Tracking active playtime...")
                # FIXME: tasklist can sometimes be slow on older HDD systems. maybe cache?
                # Poll until process exits
                while is_process_running(exe_name):
                    time.sleep(5)
                tracked_ok = True
            else:
                print("Could not detect game process starting. Tracking skipped.")
        else:
            # TODO: handle games that launch a separate launcher (like Ubisoft/EA)
            print("No game executable resolved during scan. Playtime tracking skipped.")
            
    if tracked_ok:
        end_time = time.time()
        duration_mins = (end_time - start_time) / 60.0
        
        # Reload state in case of concurrent changes
        state = load_state()
        if game_id in state["games"]:
            state["games"][game_id]["playtime_mins"] = state["games"][game_id].get("playtime_mins", 0) + duration_mins
            save_state(state)
            print(f"Closed {game['name']}. Played for {duration_mins:.1f} minutes.")
    else:
        print(f"Closed {game['name']}.")

def main():
    """Command-line interface for the game launcher and tracker."""
    parser = argparse.ArgumentParser(
        description="A lightweight Windows CLI game launcher and playtime tracker.",
        epilog="Example: launcher.py launch steam_220"
    )
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("list", help="List all tracked games and play statistics")
    subparsers.add_parser("scan", help="Scan and register Steam library games")
    
    add_parser = subparsers.add_parser("add", help="Register a manual executable game")
    add_parser.add_argument("name", help="Display name of the game")
    add_parser.add_argument("exe", help="Full path to game executable")
    
    launch_parser = subparsers.add_parser("launch", help="Launch a game by ID")
    launch_parser.add_argument("id", help="The identifier of the game to run")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_games()
    elif args.command == "scan":
        scan_steam_games()
    elif args.command == "add":
        add_game(args.name, args.exe)
    elif args.command == "launch":
        launch_game(args.id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
