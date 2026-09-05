"""Validate the actual packed repaint, not the retired half-cycle mirror."""
import importlib
import json
import sys
from pathlib import Path
import pytest
from PIL import Image

MOD=Path(__file__).resolve().parents[1]/'mods/lol_mod'
sys.path.insert(0,str(MOD/'tools'))
edit=importlib.import_module('yone_run_pixel_edit')
builder=importlib.import_module('build_yone')

def inputs():
    manifest=json.loads((MOD/'source/native/yone_v7/frames.json').read_text())
    palette=json.loads((MOD/'source/native/yone_v7/palette.json').read_text())
    weapons={tuple(c['rgba']) for c in palette['colors'] if c['role'].startswith(('steel_', 'azakana_'))}
    return manifest, weapons

def test_packed_run_edits_only_authorized_leg_region_and_preserves_every_other_action():
    manifest,weapons=inputs()
    sheet=Image.open(MOD/'aseprite_resources/champions/yone_v7#sheet.png').convert('RGBA')
    anchors=(19,18,18,19,21,20,19,19)
    foot_paths={'near':[],'far':[]}
    for row in manifest['frames']:
        source=Image.open(MOD/'source/native/yone_v7'/row['file']).convert('RGBA')
        x,y,w,h=row['rect']; actual=sheet.crop((x,y,x+w,y+h))
        if row['action']!='run':
            assert actual.tobytes()==source.tobytes(), row['action']
            continue
        i=row['index']; floor=h-builder.BODY_BOTTOM_MARGINS['run'][i]-1
        expected,layers,roi=edit.repaint(source,i,anchors[i],floor,weapons)
        assert actual.tobytes()==expected.tobytes()
        assert actual.size==source.size
        assert actual.getbbox()[3]==floor+1
        for yy in range(h):
            for xx in range(w):
                old=source.getpixel((xx,yy))
                if old in weapons or not(roi[0]<=xx<roi[2] and roi[1]<=yy<roi[3]):
                    assert actual.getpixel((xx,yy))==old
        for name,layer in layers.items():
            box=layer.getbbox(); sole_y=box[3]-1
            sole=[xx for xx in range(w) if layer.getpixel((xx,sole_y))[3]]
            # Anatomical masks have a fixed near/far identity even when x crosses.
            foot_paths[name].append((sum(sole)/len(sole)-anchors[i],floor-sole_y))
            assert sum(bool(a) for a in layer.getchannel('A').tobytes())>=28
            assert any(actual.getpixel((xx,sole_y))[3] for xx in sole)
        support='near' if i<4 else 'far'
        assert foot_paths[support][-1][1]==0
        assert foot_paths['far' if i<4 else 'near'][-1][1] in (1,2,3)
    for path in foot_paths.values():
        assert len(set(path))>=7
        # Includes the 7->0 wrap; no side teleport or giant crossover stride.
        assert max(abs(path[i][0]-path[(i+1)%8][0]) for i in range(8))<=4
        assert max(abs(path[i][1]-path[(i+1)%8][1]) for i in range(8))<=2

def test_repaint_does_not_resize_or_generate_mirrored_whole_body():
    text=(MOD/'tools/yone_run_pixel_edit.py').read_text()
    assert '.resize(' not in text and '.transpose(' not in text
    assert len(edit.NEAR)==len(edit.FAR)==8
    assert len(set(edit.NEAR))==len(set(edit.FAR))==8

def test_byte_gate_rejects_removed_support_foot():
    frames,manifest,_=builder._load_native_v7_body_frames()
    row=manifest['run_pixel_edit']['frames'][0]
    frame=frames[('run',0)].copy()
    floor=row['floor_y']
    for x in range(row['roi'][0],row['roi'][2]):
        frame.putpixel((x,floor),(0,0,0,0))
    original=Image.open(MOD/'source/native/yone_v7/frames/run_00.png').convert('RGBA')
    _,weapons=inputs()
    with pytest.raises(ValueError,match='packed leg edit differs'):
        edit.verify_packed(original,frame,0,row['pelvis_x'],floor,weapons)
    assert row['outside_roi_unchanged'] and row['weapons_unchanged']

def test_new_base_model_cannot_silently_reuse_old_hip_coordinates():
    original=Image.open(MOD/'source/native/yone_v7/frames/run_00.png').convert('RGBA')
    original.putpixel((0,0),(255,0,0,255))
    _,weapons=inputs()
    with pytest.raises(ValueError,match='base model changed'):
        edit.repaint(original,0,19,35,weapons)
