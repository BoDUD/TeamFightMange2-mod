"""Pack side-card and native-preview regions without changing actor assets.

The engine owns champion selection and swaps through its native illustration
loader. Every available champion has a texture, so layout never needs to guess
whether the current image is an illustration or a pixel actor.
"""
from __future__ import annotations

import io
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
    def __init__(self, mod=MOD):
        self.mod = mod
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
        self.overrides = json.loads((mod / 'mod.override_info').read_text(encoding='utf8'))

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


def build(mod=MOD):
    assets = Assets(mod)
    info = assets.json('asset/base/setting/champion_info')
    styles = assets.json('asset/base/style/champion_view').get('entries', {})
    roster = {name: {'sprite': 'asset/base/aseprite_resources/champions/' + name,
                     'anim_prefix': ''} for name, value in info.items() if isinstance(value, dict)}
    for path in sorted((mod / 'champion').glob('*.data_champion')):
        row = json.loads(path.read_text(encoding='utf8'))
        roster[row['id']] = row
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
