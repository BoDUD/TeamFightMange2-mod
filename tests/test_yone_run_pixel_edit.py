"""Protect real authored anatomical sources; pixel metrics are not live QA."""
import importlib
import json
import sys
from pathlib import Path
import pytest
from PIL import Image

MOD=Path(__file__).resolve().parents[1]/'mods/lol_mod'
sys.path.insert(0,str(MOD/'tools'))
edit=importlib.import_module('yone_run_anatomy')
builder=importlib.import_module('build_yone')

def test_packed_anatomy_is_exact_and_every_other_action_is_unchanged():
    manifest=json.loads((MOD/'source/native/yone_v7/frames.json').read_text())
    sheet=Image.open(MOD/'aseprite_resources/champions/yone_v7#sheet.png').convert('RGBA')
    distinct=[]
    for row in manifest['frames']:
        original=Image.open(MOD/'source/native/yone_v7'/row['file']).convert('RGBA')
        x,y,w,h=row['rect']; actual=sheet.crop((x,y,x+w,y+h))
        if row['action']!='run':
            assert actual.tobytes()==original.tobytes(),row['action']
            continue
        expected,proof=edit.load_frame(original,row['index'])
        edit.verify_packed(original,actual,row['index'])
        assert actual.size==original.size
        top=proof['original_upper_body_rows']
        assert actual.crop((0,0,w,top)).tobytes()==original.crop((0,0,w,top)).tobytes()
        for fx,fy,fw,fh in proof['feet']:
            foot=actual.crop((fx,fy,fx+fw,fy+fh))
            assert foot.getbbox() and sum(bool(a) for a in foot.getchannel('A').tobytes())>=7
        assert actual.getbbox()[3]==proof['original_floor']+1
        assert set(actual.getchannel('A').tobytes())=={0,255}
        distinct.append(expected.tobytes())
    assert len(distinct)==len(set(distinct))==8

def test_build_does_not_use_rejected_scanline_patch_or_synthesize_new_legs():
    source=(MOD/'tools/yone_run_anatomy.py').read_text()
    build=(MOD/'tools/build_yone.py').read_text()
    assert 'from yone_run_pixel_edit import' not in build
    for forbidden in ('.resize(','.transpose(','.putpixel(', 'NEAR =', 'FAR ='):
        assert forbidden not in source

def test_byte_gate_rejects_removed_boot_and_changed_original_body():
    original=Image.open(MOD/'source/native/yone_v7/frames/run_00.png').convert('RGBA')
    frame,proof=edit.load_frame(original,0)
    x,y,w,h=proof['feet'][0]
    for yy in range(y,y+h):
        for xx in range(x,x+w):frame.putpixel((xx,yy),(0,0,0,0))
    with pytest.raises(ValueError,match='packed anatomy differs'):
        edit.verify_packed(original,frame,0)
    original.putpixel((0,0),(255,0,0,255))
    with pytest.raises(ValueError,match='base model changed'):
        edit.load_frame(original,0)

def test_new_sources_do_not_claim_unobserved_live_acceptance():
    source=json.loads((edit.ROOT/'frames.json').read_text(encoding='utf8'))
    assert source['route']=='hand-authored original-model leg pixels'
    assert source['source_file']=='legs.pixel.json'
    assert source['live_battle_verified'] is False


def test_native_leg_art_has_eight_explicit_cels():
    art=json.loads((edit.ROOT/'legs.pixel.json').read_text(encoding='utf8'))
    assert (art['width'],art['height'])==(19,12)
    assert len(art['frames'])==8
    assert len({tuple(cel['pixels']) for cel in art['frames']})==8
    for cel in art['frames']:
        assert len(cel['pixels'])==12
        assert all(len(row)==19 for row in cel['pixels'])
        assert all(symbol in art['palette_roles'] for row in cel['pixels'] for symbol in row)


def test_literal_cels_reproduce_reviewed_frames(tmp_path):
    compiler=importlib.import_module('compile_yone_run_handdrawn')
    rows=compiler.compile_to(tmp_path/'compiled')
    for row in rows:
        original=Image.open(MOD/f'source/native/yone_v7/frames/run_{row["index"]:02}.png').convert('RGBA')
        expected,proof=edit.load_frame(original,row['index'])
        assert row['rgba_sha256']==proof['rgba_sha256']
        assert row['protected_sha256']==proof['protected_sha256']
        assert Image.open(tmp_path/'compiled'/row['file']).convert('RGBA').tobytes()==expected.tobytes()
