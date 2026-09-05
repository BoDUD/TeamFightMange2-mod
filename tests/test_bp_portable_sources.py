"""BP generation is reproducible without a local game installation."""
import hashlib
import json
import sys
from pathlib import Path
import pytest
from PIL import Image

MOD=Path(__file__).resolve().parents[1]/'mods/lol_mod'
sys.path.insert(0,str(MOD/'tools'))
import build_bp_full_cards as builder


def test_portable_native_portraits_have_explicit_hashes_and_no_bundle_dependency():
    assets=builder.Assets(MOD)
    assert assets.snapshot is not None
    assert not hasattr(assets,'bundle')
    roster,styles=builder.roster_and_styles(assets)
    assert sorted(roster)==(MOD/'ui/bp_full_cards/catalog.txt').read_text().splitlines()
    for key,row in assets.snapshot['portraits'].items():
        path=assets.snapshot_root/row['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        sprite,prefix,center=json.loads(key)
        actor=builder.actor_portrait(assets,sprite,prefix,center)
        assert 0 < actor.width <= 137 and 0 < actor.height <= 184
        assert not assets.resolved(sprite+'#sheet').startswith('asset/lol_mod/')


def test_changed_native_crop_contract_is_rejected():
    assets=builder.Assets(MOD)
    key=next(iter(assets.snapshot['portraits']))
    sprite,prefix,center=json.loads(key)
    center=dict(center,x=987654)
    with pytest.raises(ValueError,match='contract changed'):
        builder.actor_portrait(assets,sprite,prefix,center)


def test_mod_actors_are_not_frozen_in_the_native_snapshot():
    assets=builder.Assets(MOD)
    roster,styles=builder.roster_and_styles(assets)
    for row in roster.values():
        if assets.resolved(row['sprite']+'#sheet').startswith('asset/lol_mod/'):
            center=styles.get(row['id'],{}).get('center',{})
            key=json.dumps([row['sprite'],row.get('anim_prefix',''),center],sort_keys=True)
            assert key not in assets.snapshot['portraits']
            assert builder.actor_portrait(assets,row['sprite'],row.get('anim_prefix',''),center).getbbox()
