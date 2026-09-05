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
