"""Install only the BP repair, retaining unrelated dirty actor/skill assets."""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

MOD = Path(__file__).resolve().parents[1]
PURPOSE = ('0.12.21 BP-only native-assignment full-card repair candidate; '
           'selection/swap source owned by game; user performs live verification; '
           'actor assets, encyclopedia positions, skills and saves not installed by this patch')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_manifest(root, name, changed):
    path = root / name
    if not path.exists(): return
    data = json.loads(path.read_text(encoding='utf8'))
    rows = {row['path']: row for row in data['files']}
    for relative in changed:
        file = root / relative
        rows[relative] = {'path': relative, 'size': file.stat().st_size, 'sha256': sha(file)}
    data['files'] = [rows[key] for key in sorted(rows)]
    data['purpose'] = PURPOSE
    if 'file_count' in data: data['file_count'] = len(rows)
    if 'total_size' in data: data['total_size'] = sum(row['size'] for row in rows.values())
    if 'within_soft_budget' in data:
        data['within_soft_budget'] = data['total_size'] <= data['soft_budget']
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def install(destination):
    game = MOD.parents[2].resolve()
    destination = destination.resolve()
    if destination != game / 'mods/lol_mod':
        raise ValueError('BP installer only targets this game installation / mods/lol_mod')
    catalog = (MOD / 'ui/bp_full_cards/catalog.txt').read_text().splitlines()
    changed = ['lol_mod.dll', 'mod.mod_info', 'ui/bp_full_cards/catalog.txt']
    changed += ['banpick_illustrations/' + hero + '.png' for hero in catalog]
    for relative in changed:
        file = MOD / relative
        if not file.is_file(): raise FileNotFoundError(file)
        if relative.endswith('.png'):
            raw = file.read_bytes()
            if raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[16:24] != b'\0\0\x04\0\0\0\0\xb8':
                raise ValueError(f'Not a current three-region atlas: {relative}')
    protected = {p.relative_to(destination).as_posix(): sha(p)
                 for folder in ['aseprite_resources/champions', 'champion', 'style', 'text']
                 for p in (destination / folder).rglob('*') if p.is_file()}
    backup = game / 'mod_backups' / ('bp_01221_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True, exist_ok=False)
    for relative in changed + ['runtime_manifest.json', 'build_manifest.json']:
        installed = destination / relative
        if installed.exists():
            archived = backup / relative
            archived.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(installed, archived)
    for relative in changed:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MOD / relative, target)
        if sha(target) != sha(MOD / relative): raise RuntimeError(f'Copy mismatch: {relative}')
    for root in [MOD, destination]:
        for name in ['runtime_manifest.json', 'build_manifest.json']:
            refresh_manifest(root, name, changed)
    if any(sha(destination / relative) != expected for relative, expected in protected.items()):
        raise RuntimeError('Unrelated runtime content changed during incremental install')
    print(json.dumps({'version': '0.12.21', 'installed_files': len(changed),
                      'unchanged_protected_files': len(protected), 'backup': str(backup),
                      'dll_sha256': sha(destination / 'lol_mod.dll'),
                      'live_verification': 'user-requested: not performed'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    args = parser.parse_args()
    install(args.install)
