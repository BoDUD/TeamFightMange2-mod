"""Losslessly decode literal native-size leg art onto protected original pixels.

No pose generator, interpolation, limb resizing or scanline displacement.
The artist edits each of the eight cels in legs.pixel.json independently.
Outputs stay outside the active mod until separately reviewed and installed.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
from PIL import Image

MOD = Path(__file__).resolve().parents[1]
ORIGINAL = MOD/'source/native/yone_v7'
ART = MOD/'source/native/yone_run_handdrawn/legs.pixel.json'
PELVIS = (19,18,18,19,21,20,19,19)
FLOOR = (35,36,37,36,35,36,37,36)


def digest(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


def connected_blades(image, palette):
    protected = set()
    for prefix in ('steel_', 'azakana_'):
        colors = {tuple(row['rgba']) for row in palette if row['role'].startswith(prefix)}
        remaining = {(x,y) for y in range(image.height) for x in range(image.width)
                     if image.getpixel((x,y)) in colors}
        groups = []
        while remaining:
            start = remaining.pop()
            group, queue = {start}, deque([start])
            while queue:
                x,y = queue.popleft()
                for dy in (-1,0,1):
                    for dx in (-1,0,1):
                        point = (x+dx,y+dy)
                        if point in remaining:
                            remaining.remove(point)
                            group.add(point)
                            queue.append(point)
            groups.append(group)
        if not groups:
            raise ValueError(f'Missing original {prefix} blade')
        largest = max(groups,key=len)
        if any(len(group)>2 for group in groups if group is not largest):
            raise ValueError('Unexpected disconnected blade; inspect original')
        protected.update(largest)
    return protected


def compile_to(destination):
    destination = destination.resolve()
    if MOD in destination.parents or destination == MOD:
        raise ValueError('Review output must be outside active source/runtime assets')
    destination.mkdir(parents=True,exist_ok=True)
    for part in ('frames','protected'):
        (destination/part).mkdir(exist_ok=True)
    art = json.loads(ART.read_text(encoding='utf8'))
    palette = json.loads((ORIGINAL/'palette.json').read_text())['colors']
    by_role = {row['role']:tuple(row['rgba']) for row in palette}
    colors = {symbol:by_role[role] for symbol,role in art['palette_roles'].items()}
    if (art['width'],art['height'],len(art['frames'])) != (19,12,8):
        raise ValueError('Native cel contract changed')
    rows = []
    for i,cel in enumerate(art['frames']):
        if len(cel['pixels'])!=12 or any(len(line)!=19 for line in cel['pixels']):
            raise ValueError(f'Invalid literal cel {i}')
        original = Image.open(ORIGINAL/f'frames/run_{i:02}.png').convert('RGBA')
        layer = Image.new('RGBA',(19,12))
        layer.putdata([colors[s] for line in cel['pixels'] for s in line])
        top, pelvis = FLOOR[i]-11, PELVIS[i]
        dx = pelvis-9
        blades = connected_blades(original,palette)
        mask = Image.new('L',original.size)
        result = Image.new('RGBA',original.size)
        result.paste(layer,(dx,top))
        for y in range(original.height):
            for x in range(original.width):
                r,g,b,a = original.getpixel((x,y))
                sash = y<top+4 and a and r>=120 and g<60 and b<60 and r>g*2.8 and r>b*2.8
                arm = (x>=pelvis+9 and y<top+4) or (x<=pelvis-8 and y<top+2)
                if y<top or (x,y) in blades or sash or arm:
                    result.putpixel((x,y),original.getpixel((x,y)))
                    mask.putpixel((x,y),255)
        file, mask_file = f'frames/run_{i:02}.png', f'protected/run_{i:02}.png'
        result.save(destination/file)
        mask.save(destination/mask_file)
        rows.append(dict(index=i,file=file,protected_mask=mask_file,pose=cel['pose'],
            size=list(result.size),original_upper_body_rows=top,
            base_rgba_sha256=digest(original),rgba_sha256=digest(result),
            protected_sha256=digest(mask),feet=[[x+dx,y+top,w,h] for x,y,w,h in cel['feet']],
            alpha_bbox=list(result.getbbox()),original_floor=FLOOR[i]))
    (destination/'legs.pixel.json').write_bytes(ART.read_bytes())
    manifest=dict(schema_version=1,route='hand-authored original-model leg pixels',
        source_file='legs.pixel.json',source_sha256=hashlib.sha256(ART.read_bytes()).hexdigest(),
        preparation='Eight separately authored 19x12 pixel cels; exact original palette and protected actor composition. No geometric/scanline pose synthesis.',
        status='offline-review-candidate',live_battle_verified=False,frames=rows)
    (destination/'frames.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    print(len(compile_to(parser.parse_args().output)))
