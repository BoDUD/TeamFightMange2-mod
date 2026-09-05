"""REJECTED 0.12.18/0.12.19 experiment; never import in the active build.

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
FAR_PALETTE = {**PALETTE, 'c': (48,57,79,255), 'v': PALETTE['u']}

# Ten scanlines, from below the waist through the floor. Revision 2 restores
# the original baggy-trouser volume: 7-8px near thigh / 6-7px far thigh, rounded
# knee folds, a 5px boot shaft and a 6px toe. The rejected revision used 4-5px
# straight strips with only 2-3px of visible cloth between outlines.
# Missing final rows are actual swing-foot clearance, not stacked old limbs.
NEAR = (
    ((-4,'oaabbbo'),(-4,'oabbccao'),(-3,'oabcbbco'),(-2,'obcccbao'),(-1,'oabbcao'),(0,'oaabba'),(1,'ottuo'),(2,'otvuo'),(3,'otuvto'),(3,'otttto')),
    ((-4,'oaabbbo'),(-4,'oabbccao'),(-4,'oabcbbco'),(-3,'obcccbao'),(-3,'oabbcao'),(-2,'oaabba'),(-1,'ottuo'),(0,'otvuo'),(1,'otuvto'),(1,'otttto')),
    ((-4,'oaabbbo'),(-5,'oabbccao'),(-5,'oabcbbco'),(-5,'obcccbao'),(-4,'oabbcao'),(-3,'oaabba'),(-2,'ottuo'),(-1,'otvuo'),(-1,'otuvto'),(-1,'otttto')),
    ((-4,'oaabbbo'),(-5,'oabbccao'),(-6,'oabcbbco'),(-6,'obcccbao'),(-6,'oabbcao'),(-5,'oaabba'),(-4,'ottuo'),(-3,'otvuo'),(-3,'otuvto'),(-3,'otttto')),
    ((-4,'oaabbbo'),(-5,'oabbccao'),(-6,'oabcbbco'),(-7,'obcccbao'),(-7,'oabbcao'),(-7,'ottuo'),(-6,'otuvto'),(-5,'otttto')),
    ((-4,'oaabbbo'),(-5,'oabbccao'),(-6,'oabcbbco'),(-6,'obcccbao'),(-6,'oaabao'),(-5,'otuvto'),(-4,'otttto')),
    ((-4,'oaabbbo'),(-3,'oabbccao'),(-2,'oabcbbco'),(-1,'obcccbao'),(0,'oaabao'),(0,'ottuo'),(0,'otuvto'),(0,'otttto')),
    ((-4,'oaabbbo'),(-4,'oabbccao'),(-3,'oabcbbco'),(-2,'obcccbao'),(-1,'oabbcao'),(0,'oaabba'),(2,'ottuo'),(3,'otuvto'),(3,'otttto')),
)
FAR = (
    ((0,'oaabao'),(-1,'oabbcao'),(-2,'obcbcbo'),(-3,'oabbbao'),(-4,'oaabao'),(-5,'ottuo'),(-5,'otuvto'),(-5,'otttto')),
    ((0,'oaabao'),(-1,'oabbcao'),(-2,'obcbcbo'),(-3,'oabbbao'),(-4,'oaabao'),(-4,'otuvto'),(-4,'otttto')),
    ((0,'oaabao'),(0,'oabbcao'),(1,'obcbcbo'),(2,'oabbbao'),(2,'oaabao'),(1,'ottuo'),(0,'otuvto'),(0,'otttto')),
    ((0,'oaabao'),(1,'oabbcao'),(2,'obcbcbo'),(3,'oabbbao'),(3,'oaabao'),(3,'oabbao'),(4,'ottuo'),(4,'otuvto'),(4,'otttto')),
    ((0,'oaabao'),(1,'oabbcao'),(2,'obcbcbo'),(3,'oabbbao'),(3,'oaabao'),(3,'oabbao'),(4,'ottuo'),(4,'otvuo'),(4,'otuvto'),(4,'otttto')),
    ((0,'oaabao'),(0,'oabbcao'),(1,'obcbcbo'),(1,'oabbbao'),(1,'oaabao'),(1,'oabbao'),(2,'ottuo'),(2,'otvuo'),(2,'otuvto'),(2,'otttto')),
    ((0,'oaabao'),(0,'oabbcao'),(0,'obcbcbo'),(-1,'oabbbao'),(-1,'oaabao'),(-1,'oabbao'),(0,'ottuo'),(0,'otvuo'),(0,'otuvto'),(0,'otttto')),
    ((0,'oaabao'),(-1,'oabbcao'),(-2,'obcbcbo'),(-3,'oabbbao'),(-4,'oaabao'),(-4,'oabbao'),(-3,'ottuo'),(-2,'otvuo'),(-2,'otuvto'),(-2,'otttto')),
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
            # Retain the two original waist/thigh fold rows verbatim. They
            # carry the trousers' volume and leather trim, not a narrow stem.
            if y < top+2 or original.getpixel((x,y)) in weapon_colors:
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
                       'revision':2, 'original_upper_thigh_rows_preserved':2,
                       'minimum_authored_thigh_width':min(len(c) for rows in (NEAR[i],FAR[i]) for _,c in rows[:4]),
                       'minimum_boot_shaft_width':min(len(c) for rows in (NEAR[i],FAR[i]) for _,c in rows if 't' in c),
                       'feet':feet,'support_anatomical_leg':'near' if i<4 else 'far',
                       'outside_roi_unchanged':outside,'weapons_unchanged':weapons,
                       'base_rgba_sha256':hashlib.sha256(original.tobytes()).hexdigest(),
                       'edited_rgba_sha256':audit['packed_rgba_sha256']})
    return report
