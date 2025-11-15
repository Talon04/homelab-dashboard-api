import os
from typing import Dict, Any, List, Optional

CODE_ROOT = os.path.join(os.path.dirname(__file__), 'data', 'user_code')

ALLOWED_BASE = CODE_ROOT

os.makedirs(CODE_ROOT, exist_ok=True)

def _safe_path(rel_path: str) -> str:
    rel_path = rel_path or ''
    joined = os.path.normpath(os.path.join(CODE_ROOT, rel_path))
    if not joined.startswith(ALLOWED_BASE):
        raise ValueError('Invalid path')
    return joined

def list_tree(rel_path: str = '') -> Dict[str, Any]:
    base = _safe_path(rel_path)
    tree = { 'path': rel_path or '', 'dirs': [], 'files': [] }
    try:
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, CODE_ROOT)
            if os.path.isdir(full):
                tree['dirs'].append({ 'name': name, 'path': rel })
            else:
                tree['files'].append({ 'name': name, 'path': rel })
    except FileNotFoundError:
        pass
    return tree

def read_file(rel_path: str) -> Dict[str, Any]:
    full = _safe_path(rel_path)
    if not os.path.exists(full) or not os.path.isfile(full):
        raise FileNotFoundError('File not found')
    with open(full, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return { 'path': rel_path, 'content': content }

def write_file(rel_path: str, content: str) -> Dict[str, Any]:
    full = _safe_path(rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(content or '')
    return { 'path': rel_path, 'ok': True }

def delete_path(rel_path: str) -> Dict[str, Any]:
    full = _safe_path(rel_path)
    if os.path.isdir(full):
        # Only allow deletion of empty directories for safety
        try:
            os.rmdir(full)
        except OSError:
            return { 'path': rel_path, 'ok': False, 'error': 'Directory not empty' }
        return { 'path': rel_path, 'ok': True }
    if os.path.exists(full):
        os.remove(full)
        return { 'path': rel_path, 'ok': True }
    return { 'path': rel_path, 'ok': False, 'error': 'Path not found' }

def ensure_scaffold(rel_path: str, widget_type: Optional[str] = None) -> Dict[str, Any]:
    full = _safe_path(rel_path)
    if os.path.exists(full):
        return { 'path': rel_path, 'ok': True, 'created': False }
    os.makedirs(os.path.dirname(full), exist_ok=True)
    content = ''
    # Provide sensible defaults depending on extension
    if rel_path.endswith('.py'):
        content = (
            "#!/usr/bin/env python3\n"
            "import sys, json\n"
            "# Context is passed as first argument (JSON)\n"
            "ctx = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}\n"
            "# Example: print something to stdout\n"
            "print('Hello from Python widget script')\n"
            "# You can access container info via ctx['container']\n"
        )
    elif rel_path.endswith('.js'):
        content = (
            "// Widget script template\n"
            "// This will be executed in browser via new Function('context','api', code)\n"
            "// context.container contains the Docker container info\n"
            "// api provides helper functions specific to widget type\n"
            "(function(context, api){\n"
            "  console.log('Hello from JS widget script', context);\n"
            "  // For text widgets, you can call api.setText('New text');\n"
            "})(context, api);\n"
        )
    with open(full, 'w', encoding='utf-8') as f:
        f.write(content)
    return { 'path': rel_path, 'ok': True, 'created': True }
