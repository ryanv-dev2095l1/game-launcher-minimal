import re
from pathlib import Path

# Regex parses tokens: quoted string (group 1), braces (group 2), or unquoted words (group 3)
TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|([^\s{}]+)')

def parse_vdf(text: str) -> dict:
    """Parses Valve Data Format (VDF) text into a nested dictionary."""
    # Strip comments first. Steam VDFs are littered with single-line comments.
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        
        # FIXME: If inline comment is inside quotes, the parser gets confused and truncates the string.
        inline_idx = stripped.find('//')
        if inline_idx != -1:
            quote_count = stripped[:inline_idx].count('"')
            if quote_count % 2 == 0:
                stripped = stripped[:inline_idx].strip()
        lines.append(stripped)
    
    cleaned_text = '\n'.join(lines)

    tokens = []
    for match in TOKEN_RE.finditer(cleaned_text):
        quoted, brace, unquoted = match.groups()
        if quoted is not None:
            val = quoted.replace('\\\\', '\\').replace('\\"', '"')
            tokens.append(val)
        elif brace is not None:
            tokens.append(brace)
        elif unquoted is not None:
            tokens.append(unquoted)

    root = {}
    stack = [root]
    key = None

    for token in tokens:
        if token == '{':
            if key is None:
                continue
            new_dict = {}
            stack[-1][key] = new_dict
            stack.append(new_dict)
            key = None
        elif token == '}':
            if len(stack) > 1:
                stack.pop()
            key = None
        else:
            if key is None:
                key = token
            else:
                stack[-1][key] = token
                key = None

    return root

def read_library_folders(vdf_path: Path) -> list[Path]:
    rawContent = vdf_path.read_text(encoding='utf-8', errors='ignore')
    data = parse_vdf(rawContent)

    paths = []
    root_key = next(iter(data.keys()), None)
    if not root_key:
        return []
    
    folders_dict = data[root_key]
    if not isinstance(folders_dict, dict):
        return []

    for k, v in folders_dict.items():
        if isinstance(v, dict) and 'path' in v:
            p = Path(v['path'])
            if p.exists():
                paths.append(p)
    return paths

def get_steam_apps(library_path: Path) -> list[dict]:
    apps_dir = library_path / 'steamapps'
    if not apps_dir.exists():
        return []

    apps = []
    for acfFile in apps_dir.glob('appmanifest_*.acf'):
        content = acfFile.read_text(encoding='utf-8', errors='ignore')
        manifest = parse_vdf(content)
        
        app_state = manifest.get('AppState') or manifest.get('appstate')
        if not isinstance(app_state, dict):
            continue
        
        appid = app_state.get('appid') or app_state.get('AppId')
        name = app_state.get('name') or app_state.get('UserConfig', {}).get('name')
        install_dir = app_state.get('installdir')

        if appid and name and install_dir:
            exe_dir = apps_dir / 'common' / install_dir
            # print(f"DEBUG: found app {appid} inside {exe_dir}")
            apps.append({
                'id': appid,
                'name': name,
                'path': exe_dir
            })
    return apps
