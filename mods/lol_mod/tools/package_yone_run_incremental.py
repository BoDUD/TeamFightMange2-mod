"""Install authored Yone run pixels without rebuilding any other game surface.

The installed atlas is the baseline, not a full rebuild from the dirty source
tree. No animation tables, DLL, UI, skill, version, or save files are copied.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image, ImageChops, ImageDraw

from build_yone import NATIVE_CONTRACT, save_png
import yone_run_anatomy

MOD = Path(__file__).resolve().parents[1]
SHEETS = [f'aseprite_resources/champions/{name}#sheet.png'
          for name in ('yone_v7', 'yone')]
MANIFESTS = ['runtime_manifest.json', 'build_manifest.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_run(baseline, frames, entries):
    """Byte-copy complete authored frames; assert all other pixels unchanged."""
    result = baseline.copy()
    allowed = Image.new('L', baseline.size)
    draw = ImageDraw.Draw(allowed)
    for frame, entry in zip(frames, entries, strict=True):
        d = entry['data']
        x, y, w, h = (d[k] for k in ('x', 'y', 'w', 'h'))
        if frame.size != (w, h):
            raise ValueError('Authored run frame violates the native canvas')
        result.paste(frame, (x, y))
        draw.rectangle((x, y, x+w-1, y+h-1), fill=255)
    outside = ImageChops.invert(allowed)
    if Image.composite(baseline, result, outside).tobytes() != result.tobytes():
        raise ValueError('A non-run atlas pixel changed')
    return result


def refresh_manifest(root, name):
    path = root / name
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding='utf8'))
    rows = {row['path']: row for row in data['files']}
    for relative in SHEETS:
        file = root / relative
        rows[relative] = dict(path=relative, size=file.stat().st_size,
                              sha256=sha(file))
    data['files'] = [rows[key] for key in sorted(rows)]
    if 'file_count' in data:
        data['file_count'] = len(rows)
    if 'total_size' in data:
        data['total_size'] = sum(row['size'] for row in rows.values())
    if 'within_soft_budget' in data:
        data['within_soft_budget'] = data['total_size'] <= data['soft_budget']
    data['yone_run_patch'] = {
        'source_manifest_sha256': sha(yone_run_anatomy.ROOT/'frames.json'),
        'scope': 'eight run frames only; all other installed atlas pixels retained',
        'live_verification': 'not performed; user requested self-verification',
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def install(destination):
    game = MOD.parents[2].resolve()
    destination = destination.resolve()
    if destination != game/'mods/lol_mod':
        raise ValueError('Only this game installation is a valid destination')
    source = json.loads((yone_run_anatomy.ROOT/'frames.json').read_text(encoding='utf8'))
    if source.get('status') != 'candidate-ready-for-user-test':
        raise ValueError('Unreviewed or rejected art cannot be installed')
    anim = json.loads((destination/'aseprite_resources/champions/yone_v7#anim.fanim').read_text())
    entries = anim['anims']['run']['frames']
    contract = NATIVE_CONTRACT['run']
    if [r['duration'] for r in entries] != contract['durations']:
        raise ValueError('Installed run timing differs from native contract')
    if [tuple(r['data'][k] for k in ('x','y','w','h')) for r in entries] != contract['rects']:
        raise ValueError('Installed run layout differs from native contract')
    frames = []
    for i in range(8):
        original = Image.open(MOD/f'source/native/yone_v7/frames/run_{i:02}.png').convert('RGBA')
        frame, _ = yone_run_anatomy.load_frame(original, i)
        frames.append(frame)
    baseline = Image.open(destination/SHEETS[0]).convert('RGBA')
    if baseline.tobytes() != Image.open(destination/SHEETS[1]).convert('RGBA').tobytes():
        raise ValueError('Installed Yone compatibility atlases have diverged')
    result = patch_run(baseline, frames, entries)
    protected = {p.relative_to(destination).as_posix(): sha(p)
                 for p in destination.rglob('*') if p.is_file()
                 and p.relative_to(destination).as_posix() not in SHEETS+MANIFESTS
                 and p.relative_to(destination).parts[0] not in ('qa', 'source', 'tools')}
    backup = game/'mod_backups'/('yone_run_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    for label, root in [('installed', destination), ('repository', MOD)]:
        for relative in SHEETS+MANIFESTS:
            original = root/relative
            if original.exists():
                target = backup/label/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, target)
    for root in (MOD, destination):
        for relative in SHEETS:
            save_png(root/relative, result)
            if Image.open(root/relative).convert('RGBA').tobytes() != result.tobytes():
                raise ValueError('Packed PNG differs from authored run patch')
        for name in MANIFESTS:
            refresh_manifest(root, name)
    if any(sha(destination/path) != expected for path, expected in protected.items()):
        raise RuntimeError('Unrelated installed files changed; inspect backup before proceeding')
    print(json.dumps(dict(backup=str(backup), changed_runtime_images=SHEETS,
                          protected_runtime_files=len(protected),
                          original_timing_preserved=True, live_test=False), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', required=True, type=Path)
    install(parser.parse_args().install)
