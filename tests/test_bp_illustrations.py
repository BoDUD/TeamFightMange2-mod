"""Presentation gates; these do not substitute for target-visible live QA."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def builder():
    sys.path.insert(0, str(MOD / "tools"))
    try:
        spec = importlib.util.spec_from_file_location("bp_cards", MOD / "tools" / "build_bp_pick_cards.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_leaf_templates_preserve_exact_native_controls_and_fixed_sources():
    b = builder()
    manifest = json.loads((MOD / "runtime_manifest.json").read_text(encoding="utf-8"))
    included = {row["path"] for row in manifest["files"]}
    for side in ("blue", "red"):
        text = (b.OUTPUT / f"{side}_pick_slot.ui").read_text(encoding="utf-8")
        assert text == b.build_template(side)
        assert text.replace(b.illustration_block(side), "") == b.base_template(side)
        assert f"ui/bp_pick_cards/{side}_pick_slot.ui" in included
        block = b.illustration_block(side)
        assert block.count(":image {") == 9
        assert "z:" not in block
        done = text.split("  #done:empty {", 1)[1].split("#player_tooltip:", 1)[0]
        for native_child in ("#bar:", "#name:", "#position:", "#proficiency_badge:",
                             "#proficiency_badge_title:", "#proficiency_top:", "#center:", "#champion:"):
            assert done.index("#lol_bp_illustrations") > done.index(native_child)
        assert "#tint:" not in block
        backing = block.split("#opaque_backing:color {", 1)[1].split("}", 1)[0]
        assert "x: 8px; y: 1px; width: 284px; height: 172px;" in backing
        assert "color: #07080bff;" in backing
        for hero in b.HEROES:
            source = f"asset/lol_mod/ui/banpick/champion_illustration/{hero}_{side}"
            assert source in block
            assert block.index("#opaque_backing:") < block.index(f"#{hero}:image")
            assert f"ui/banpick/champion_illustration/{hero}_{side}.png" in included
            with Image.open(MOD / f"ui/banpick/champion_illustration/{hero}_{side}.png") as image:
                assert image.size == (284, 172)
                # Some existing artwork has alpha 249 at its edges. A matte
                # BELOW the art prevents native details showing through it.
                composite = Image.alpha_composite(Image.new("RGBA", image.size, "#07080bff"), image.convert("RGBA"))
                assert composite.getchannel("A").getextrema() == (255, 255)


def test_actual_rust_resolver_and_visibility_fallback(tmp_path):
    compiler = shutil.which("rustc")
    if not compiler:
        pytest.skip("Rust compiler unavailable; CI installs it for stable DLL build")
    exe = tmp_path / ("bp_tests.exe" if sys.platform == "win32" else "bp_tests")
    built = subprocess.run([compiler, "--edition", "2021", "--test",
                            str(MOD / "src" / "bp_illustrations.rs"), "-o", str(exe)],
                           capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    tested = subprocess.run([str(exe)], capture_output=True, text=True)
    assert tested.returncode == 0, tested.stdout + tested.stderr


def test_runtime_never_reads_athlete_name_or_late_binds_illustration_source():
    runtime = (MOD / "src" / "stable_runtime.rs").read_text(encoding="utf-8")
    source = (MOD / "src" / "bp_illustrations.rs").read_text(encoding="utf-8")
    assert "bp_champion_id_from_name" not in runtime
    assert "lol_bp_runtime_illustration:image" not in runtime
    assert 'join_ui_path(&done, "name")' not in runtime
    assert '"{marker}.text"' in source
    assert '"{root}.swap"' in source  # guarded native fallback; no guessed swap permutation
    post_update = runtime.split("impl StableExtension for QualityBpExtension", 1)[1]
    assert post_update.index("bp_illustrations::sync") < post_update.index("BP_RUNTIME_SCAN_INTERVAL_MICROS")


def test_rejected_native_portrait_classifier_cannot_ship():
    runtime = (MOD / "src" / "stable_runtime.rs").read_text(encoding="utf-8")
    assert "bp_native_presentation" not in runtime
    assert not (MOD / "src" / "bp_native_presentation.rs").exists()
    for path in (MOD / "banpick_illustrations").glob("*.png"):
        with Image.open(path) as image:
            assert image.size == (1024, 184), "Old one-region classifier experiment must not ship"
    source = (MOD / "tools" / "build_lol_mod.py").read_text(encoding="utf-8")
    method = source.split("def build_runtime_bp_illustrations()", 1)[1].split("def split_grid", 1)[0]
    assert 'save_png(native_output' not in method
    assert 'build_bp_full_cards(MOD_ROOT)' in method


def test_full_card_catalog_and_crop_contract():
    catalog = (MOD / "ui/bp_full_cards/catalog.txt").read_text().splitlines()
    assert len(catalog) == len(set(catalog)) >= 61
    assert set(catalog) == {p.stem for p in (MOD / "banpick_illustrations").glob("*.png")}
    for path in (MOD / "champion").glob("*.data_champion"):
        assert json.loads(path.read_text(encoding="utf8"))["id"] in catalog
    for hero in catalog:
        with Image.open(MOD / "banpick_illustrations" / f"{hero}.png") as atlas:
            assert atlas.size == (1024, 184)
            assert "srgb" in atlas.info
            blue = atlas.crop((0, 6, 284, 178)).convert("RGBA")
            red = atlas.crop((740, 6, 1024, 178)).convert("RGBA")
            if (MOD / "BanPickIllust" / f"{hero}.png").exists():
                assert blue.getchannel("A").getextrema() == (255, 255)
                assert red.tobytes() == blue.transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
            else:
                assert blue.crop((0, 0, 152, 172)).getchannel("A").getbbox() is None
                assert red.crop((137, 0, 284, 172)).getchannel("A").getbbox() is None


def test_full_card_runtime_owns_no_champion_assignment():
    source = (MOD / "src/bp_full_cards.rs").read_text(encoding="utf8")
    assert 'ui_node_rect(' not in source
    assert 'ui_text(' not in source
    assert 'source:' not in source
    assert '.swap' not in source
    assert 'champion_names()' in source
    assert 'installed_catalog_ready()' in source
    assert '0.27734375' in source  # exact card width / atlas width
    assert '0.72265625' in source  # exact red card origin / atlas width
    assert 'width: 284px; height: 172px' in source
