"""Pack side-card and native-preview regions without changing actor assets.

The engine owns champion selection and swaps through its native illustration
loader. Every available champion has a texture, so layout never needs to guess
whether the current image is an illustration or a pixel actor.
"""
from __future__ import annotations

import io
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageOps, PngImagePlugin

MOD = Path(__file__).resolve().parents[1]
ATLAS_SIZE = (1024, 184)
CARD_SIZE = (284, 172)
BLUE_BOX = (0, 6, 284, 178)
RED_BOX = (740, 6, 1024, 178)


class Assets:
    def __init__(self, mod=MOD, *, export_from_game=False):
        self.mod = mod
        self.snapshot_root = mod / 'source/native/bp_full_cards'
        self.snapshot = None
        self.overrides = json.loads((mod / 'mod.override_info').read_text(encoding='utf8'))
        snapshot = self.snapshot_root / 'manifest.json'
        if snapshot.is_file() and not export_from_game:
            self.snapshot = json.loads(snapshot.read_text(encoding='utf8'))
            return
        bundle = next(p for p in (mod.parents[2] / 'bundle.game_data',
                                   mod.parents[1] / 'bundle.game_data') if p.is_file())
        self.bundle = bundle
        self.index = {}
        with bundle.open('rb') as f:
            def u32(): return struct.unpack('<I', f.read(4))[0]
            for _ in range(u32()):
                kind = f.read(u32()).decode()
                key = f.read(u32()).decode()
                n = u32()
                self.index[key] = (f.tell(), n, kind)
                f.seek(n, 1)

    def resolved(self, key):
        seen = set()
        while key not in seen:
            seen.add(key)
            override = self.overrides.get(key, {})
            if override.get('type') != 'override':
                return key
            key = override['remapping']
        raise ValueError(f'Cyclic asset remapping: {key}')

    def read(self, key, remap=True):
        override = self.overrides.get(key) if remap else None
        if override and override.get('type') == 'override':
            return self.read(override['remapping'])
        if key.startswith('asset/lol_mod/'):
            stem = self.mod / key.removeprefix('asset/lol_mod/')
            matches = [p for p in stem.parent.glob(stem.name + '.*') if p.is_file()]
            if len(matches) != 1:
                raise ValueError(f'Ambiguous/missing asset: {key}: {matches}')
            return matches[0].read_bytes()
        if self.snapshot is not None:
            values = {
                'asset/base/setting/champion_info': {name: {} for name in self.snapshot['base_ids']},
                'asset/base/style/champion_view': self.snapshot['base_styles'],
            }
            if key not in values:
                raise ValueError(f'Native asset not in portable BP source: {key}')
            return json.dumps(values[key]).encode('utf8')
        offset, n, _ = self.index[key]
        with self.bundle.open('rb') as f:
            f.seek(offset)
            return f.read(n)

    def json(self, key):
        data = json.loads(self.read(key))
        override = self.overrides.get(key)
        if override and override.get('type') == 'merge':
            def merge(base, patch):
                for k, v in patch.items():
                    if isinstance(v, dict) and isinstance(base.get(k), dict): merge(base[k], v)
                    else: base[k] = v
            merge(data, self.json(override['remapping']))
        return data


def actor_portrait(assets, sprite, prefix, center):
    if assets.snapshot is not None and not assets.resolved(sprite + '#sheet').startswith('asset/lol_mod/'):
        key = json.dumps([sprite, prefix, center], sort_keys=True)
        record = assets.snapshot['portraits'].get(key)
        if record is None:
            raise ValueError(f'Native portrait contract changed; re-export BP source: {key}')
        path = assets.snapshot_root / record['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError(f'Native BP source checksum mismatch: {path.name}')
        return Image.open(path).convert('RGBA')
    anim = assets.json(sprite + '#anim')
    frame = anim['anims'][prefix + 'idle']['frames'][0]['data']
    sheet = Image.open(io.BytesIO(assets.read(sprite + '#sheet'))).convert('RGBA')
    # Exact native set_entity_icon_center crop at 137x184 and scale 3.
    # Clamp each axis independently, then apply the champion's center offset.
    sw, sh = min(frame['w'], 137 / 3), min(frame['h'], 184 / 3)
    x = frame['x'] + max(0, (frame['w'] - sw) / 2) + center.get('x', 0)
    y = frame['y'] + max(0, (frame['h'] - sh) / 2) + center.get('y', 0)
    return sheet.transform((round(sw * 3), round(sh * 3)), Image.Transform.EXTENT,
                           (x, y, x + sw, y + sh), Image.Resampling.NEAREST)


def compose(actor, splash=None):
    atlas = Image.new('RGBA', ATLAS_SIZE)
    if splash is not None:
        card = Image.alpha_composite(Image.new('RGBA', CARD_SIZE, '#07080bff'),
                                    splash.convert('RGBA').resize(CARD_SIZE, Image.Resampling.LANCZOS))
        atlas.alpha_composite(card, BLUE_BOX[:2])
        atlas.alpha_composite(ImageOps.mirror(card), RED_BOX[:2])
        # Dedicated native center-crop area: confirmation/flying portrait must
        # never sample either side-card region.
        preview = ImageOps.contain(splash.convert('RGBA'), (456, 184), Image.Resampling.LANCZOS)
        middle = Image.new('RGBA', (456, 184), '#07080bff')
        middle.alpha_composite(preview, ((456 - preview.width) // 2, (184 - preview.height) // 2))
        atlas.alpha_composite(middle, (284, 0))
    else:
        blue, red = Image.new('RGBA', CARD_SIZE), Image.new('RGBA', CARD_SIZE)
        # Original parents were blue=(160,-10), red=(6,-10); card=(8,1).
        # Preserve the native actor's size and placement, not a stretched body.
        blue.alpha_composite(actor, (152, -11))
        red.alpha_composite(actor, (-2, -11))
        atlas.alpha_composite(blue, BLUE_BOX[:2])
        atlas.alpha_composite(red, RED_BOX[:2])
        atlas.alpha_composite(actor, ((1024 - actor.width) // 2, (184 - actor.height) // 2))
    return atlas


def roster_and_styles(assets):
    mod = assets.mod
    info = assets.json('asset/base/setting/champion_info')
    styles = assets.json('asset/base/style/champion_view').get('entries', {})
    roster = {name: {'sprite': 'asset/base/aseprite_resources/champions/' + name,
                     'anim_prefix': ''} for name, value in info.items() if isinstance(value, dict)}
    for path in sorted((mod / 'champion').glob('*.data_champion')):
        row = json.loads(path.read_text(encoding='utf8'))
        roster[row['id']] = row
    return roster, styles


def export_native_sources(mod=MOD):
    """Explicit one-time extraction; CI needs no local game installation.

    Store only compact native portraits plus their placement contract, never
    the full game bundle. Mod-owned actors are still rebuilt from their sources.
    """
    assets = Assets(mod, export_from_game=True)
    roster, styles = roster_and_styles(assets)
    root = assets.snapshot_root
    (root/'portraits').mkdir(parents=True,exist_ok=True)
    records = {}
    for name,row in sorted(roster.items()):
        sprite,prefix = row['sprite'],row.get('anim_prefix','')
        if assets.resolved(sprite+'#sheet').startswith('asset/lol_mod/'):
            continue
        center = styles.get(name,{}).get('center',{})
        actor = actor_portrait(assets,sprite,prefix,center)
        file = f'portraits/{name}.png'
        actor.save(root/file)
        records[json.dumps([sprite,prefix,center],sort_keys=True)] = {
            'file':file,'sha256':hashlib.sha256((root/file).read_bytes()).hexdigest()}
    base_info = json.loads(assets.read('asset/base/setting/champion_info',remap=False))
    base_styles = json.loads(assets.read('asset/base/style/champion_view',remap=False))
    snapshot = dict(schema_version=1,
        origin='Native 0.5.8 compact BP actor crops; mod actors are not cached',
        base_ids=sorted(name for name,value in base_info.items() if isinstance(value,dict)),
        base_styles=base_styles,portraits=records)
    (root/'manifest.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf8')
    return records


def build(mod=MOD):
    assets = Assets(mod)
    roster, styles = roster_and_styles(assets)
    outputs, records = [], []
    output_dir = mod / 'banpick_illustrations'
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, row in sorted(roster.items()):
        splash_path = mod / 'BanPickIllust' / (name + '.png')
        actor = actor_portrait(assets, row['sprite'], row.get('anim_prefix', ''),
                               styles.get(name, {}).get('center', {}))
        splash = Image.open(splash_path) if splash_path.exists() else None
        atlas = compose(actor, splash)
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add(b'sRGB', b'\x00')
        output = output_dir / (name + '.png')
        atlas.save(output, pnginfo=pnginfo)
        outputs.append(output)
        records.append({'id': name, 'illustration': splash is not None,
                        'sprite': row['sprite'], 'actor_size': list(actor.size)})
    catalog = mod / 'ui/bp_full_cards/catalog.txt'
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(''.join(row['id'] + '\n' for row in records), encoding='utf8')
    outputs.append(catalog)
    return outputs, records


if __name__ == '__main__':
    outputs, records = build()
    print(json.dumps({'count': len(outputs), 'champions': records}, ensure_ascii=False, indent=2))
