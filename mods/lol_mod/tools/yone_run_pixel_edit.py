"""User-authorized, final-resolution leg repaint on the approved Yone model.

Each row is an explicitly authored pixel cluster, not a bone/line renderer or a
mirrored half-cycle. Coordinates are relative to the original pelvis and floor.
The far leg is composited first; the same near leg stays in front at crossings.
Only pants/boots below the retained waist may change. No torso or sword redraw.
"""
import hashlib
from PIL import Image

BASE_RGBA_SHA256 = (
    '63b4f679b99c70867260a22efe283bcc53980ce8316677160b65d1aee67f24e6',
    '5c18bccbaf0ba57d197f3a722707c4f020ca6e73c36e4479dadaea39de2216a9',
    'ca197d0ba14697964a13b3dd85303519994026f8d69a145c822321bcb15c60ae',
    'c63f10d66435ea14511db78897b5a17f0f16aa576c0ed7baea985f70e22a4fdc',
    'e9a3bb775f034cb80ab6e34c318fec4b7bfee9a6934dd850469b9944c2a05ac7',
    '34c00653623a00aedbec54de71fc516c307a7d17feea8496537d2e93c37e4b89',
    '91a58b0211d0a5cd9bc2d544e4cabe5a2668bcbd91fd56d896d712e79f6e6a66',
    '0db2cb43be4cd9088d40377610dcf55b77922e40e8f6520bd632ce005eaa9f01',
)

# Existing navy cloth, outline and leather colors from the accepted source.
PALETTE = {
    'o': (18, 22, 38, 255), 'a': (27, 36, 53, 255),
    'b': (43, 51, 69, 255), 'c': (59, 70, 94, 255),
    't': (48, 37, 43, 255), 'u': (92, 48, 29, 255),
    'v': (115, 75, 33, 255),
}
FAR_PALETTE = {**PALETTE, 'b': PALETTE['a'], 'c': PALETTE['b'], 'v': PALETTE['u']}

# Ten scanlines, from below the waist through the floor. Missing final rows
# are actual swing-foot clearance, not alpha-stacked copies of another limb.
NEAR = (
    ((-3,'oabco'),(-2,'obcco'),(-1,'obcco'),(0,'oabco'),(1,'oabco'),(2,'obbo'),(2,'otuo'),(3,'otvo'),(3,'otvto'),(3,'ottto')),
    ((-3,'oabco'),(-3,'obcco'),(-2,'obcco'),(-2,'oabco'),(-1,'oabco'),(0,'obbo'),(0,'otuo'),(1,'otvo'),(1,'otvto'),(1,'ottto')),
    ((-3,'oabco'),(-3,'obcco'),(-3,'obcco'),(-3,'oabco'),(-3,'oabco'),(-2,'obbo'),(-2,'otuo'),(-1,'otvo'),(-1,'otvto'),(-1,'ottto')),
    ((-3,'oabco'),(-3,'obcco'),(-4,'obcco'),(-4,'oabco'),(-5,'oabco'),(-5,'obbo'),(-4,'otuo'),(-3,'otvo'),(-3,'otvto'),(-3,'ottto')),
    ((-3,'oabco'),(-4,'obcco'),(-5,'obcco'),(-6,'oabco'),(-7,'obbo'),(-7,'otuo'),(-6,'otvto'),(-5,'ottto')),
    ((-3,'oabco'),(-4,'obcco'),(-4,'obcco'),(-4,'oabco'),(-5,'otuo'),(-5,'otvto'),(-4,'ottto')),
    ((-3,'oabco'),(-2,'obcco'),(-1,'obcco'),(0,'oabco'),(1,'obbo'),(1,'otuo'),(0,'otvto'),(0,'ottto')),
    ((-3,'oabco'),(-2,'obcco'),(-1,'obcco'),(0,'oabco'),(1,'oabco'),(2,'obbo'),(3,'otuo'),(3,'otvto'),(3,'ottto')),
)
FAR = (
    ((1,'oabo'),(0,'obco'),(-1,'obco'),(-2,'oabo'),(-3,'obbo'),(-4,'otuo'),(-5,'otvto'),(-5,'ottto')),
    ((1,'oabo'),(0,'obco'),(-1,'obco'),(-2,'oabo'),(-3,'otuo'),(-4,'otvto'),(-4,'ottto')),
    ((1,'oabo'),(1,'obco'),(2,'obco'),(3,'oabo'),(3,'obbo'),(2,'otuo'),(0,'otvto'),(0,'ottto')),
    ((1,'oabo'),(2,'obco'),(3,'obco'),(4,'oabo'),(4,'oabo'),(4,'obbo'),(4,'otuo'),(4,'otvto'),(4,'ottto')),
    ((1,'oabo'),(2,'obco'),(3,'obco'),(4,'oabo'),(4,'oabo'),(4,'obbo'),(4,'otuo'),(4,'otvo'),(4,'otvto'),(4,'ottto')),
    ((1,'oabo'),(1,'obco'),(2,'obco'),(2,'oabo'),(2,'oabo'),(2,'obbo'),(2,'otuo'),(2,'otvo'),(2,'otvto'),(2,'ottto')),
    ((1,'oabo'),(1,'obco'),(1,'obco'),(0,'oabo'),(0,'oabo'),(0,'obbo'),(0,'otuo'),(0,'otvo'),(0,'otvto'),(0,'ottto')),
    ((1,'oabo'),(0,'obco'),(-1,'obco'),(-2,'oabo'),(-3,'oabo'),(-3,'obbo'),(-3,'otuo'),(-2,'otvo'),(-2,'otvto'),(-2,'ottto')),
)

def repaint(original, index, pelvis_x, ground_y, weapon_colors):
    """Return edited frame plus independently inspectable anatomical layers."""
    if hashlib.sha256(original.tobytes()).hexdigest() != BASE_RGBA_SHA256[index]:
        raise ValueError('Yone base model changed; re-author pixel edit for that source')
    result = original.copy()
    top = ground_y - 9
    # Retain the waist, upper body, hanging sash to the left, and all weapons.
    roi = (pelvis_x-9, top, pelvis_x+12, ground_y+1)
    for y in range(roi[1], roi[3]):
        for x in range(roi[0], roi[2]):
            if original.getpixel((x,y)) not in weapon_colors:
                result.putpixel((x,y), (0,0,0,0))
    layers = {}
    for name, rows, palette in [('far',FAR[index],FAR_PALETTE), ('near',NEAR[index],PALETTE)]:
        layer=Image.new('RGBA', original.size)
        for dy,(dx,cluster) in enumerate(rows):
            for offset, symbol in enumerate(cluster):
                x,y=pelvis_x+dx+offset,top+dy
                if not (roi[0] <= x < roi[2] and roi[1] <= y < roi[3]):
                    raise ValueError('authored leg escaped edit region')
                layer.putpixel((x,y), palette[symbol])
        result.alpha_composite(layer)
        layers[name]=layer
    # Blades are not reconstructed from endpoints: every original pixel stays.
    for y in range(original.height):
        for x in range(original.width):
            if original.getpixel((x,y)) in weapon_colors:
                result.putpixel((x,y),original.getpixel((x,y)))
    return result, layers, roi


def verify_packed(original, actual, index, pelvis_x, ground_y, weapon_colors):
    expected, _, _ = repaint(original, index, pelvis_x, ground_y, weapon_colors)
    if actual.size != original.size or actual.tobytes() != expected.tobytes():
        raise ValueError(f'run[{index}] packed leg edit differs from authored pixels')


def apply_to_frames(frames, audits, weapon_colors):
    """Apply only to run; keep legacy source immutable and audit the override."""
    anchors = (19,18,18,19,21,20,19,19)
    report=[]
    for i,pelvis in enumerate(anchors):
        original=frames[('run',i)]
        audit=audits[f'run[{i}]']
        ground=original.height-audit['bottom_margin']-1
        result,layers,roi=repaint(original,i,pelvis,ground,weapon_colors)
        zones=[]
        feet={}
        for name,layer in layers.items():
            bbox=layer.getbbox()
            points=[(x,y) for y in range(bbox[3]-2,bbox[3]) for x in range(layer.width) if layer.getpixel((x,y))[3]]
            left=min(x for x,y in points); right=max(x for x,y in points)+1
            zones.append([left,bbox[3]-2,right-left,2])
            feet[name]={'x':sum(x for x,y in points)/len(points), 'y':bbox[3]-1,
                        'clearance':ground-(bbox[3]-1),
                        'pixel_count':sum(bool(a) for a in layer.getchannel('A').tobytes())}
        outside=all(result.getpixel((x,y))==original.getpixel((x,y))
                    for y in range(original.height) for x in range(original.width)
                    if not(roi[0]<=x<roi[2] and roi[1]<=y<roi[3]))
        weapons=all(result.getpixel((x,y))==original.getpixel((x,y))
                    for y in range(original.height) for x in range(original.width)
                    if original.getpixel((x,y)) in weapon_colors)
        if not outside or not weapons or min(f['clearance'] for f in feet.values()) != 0:
            raise ValueError('Yone pixel edit changed protected art or lost floor contact')
        frames[('run',i)]=result
        audit.update(foot_zones=zones, pack_transform='user-authorized final-scale leg pixel edit',
                     source_alpha_bbox=list(result.getbbox()),
                     packed_rgba_sha256=hashlib.sha256(result.tobytes()).hexdigest())
        report.append({'index':i,'pelvis_x':pelvis,'floor_y':ground,'roi':list(roi),
                       'feet':feet,'support_anatomical_leg':'near' if i<4 else 'far',
                       'outside_roi_unchanged':outside,'weapons_unchanged':weapons,
                       'base_rgba_sha256':hashlib.sha256(original.tobytes()).hexdigest(),
                       'edited_rgba_sha256':audit['packed_rgba_sha256']})
    return report
