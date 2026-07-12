from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
VARIANT_ROOT = MOD / "aseprite_resources" / "ingame" / "dragon_variants"
VARIANTS = ("infernal", "ocean", "mountain", "cloud", "hextech")
MASK_64 = (1 << 64) - 1


def _splitmix64_variant(seed: int) -> int:
    value = (seed + 0x9E3779B97F4A7C15) & MASK_64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK_64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK_64
    return (value ^ (value >> 31)) % len(VARIANTS)


def test_elemental_dragon_sheets_share_native_canvas_but_are_visually_distinct() -> None:
    hashes: set[str] = set()
    for variant in VARIANTS:
        path = VARIANT_ROOT / f"{variant}#sheet.png"
        with Image.open(path) as image:
            assert image.size == (1861, 226)
        hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())

    assert len(hashes) == len(VARIANTS)


def test_elemental_dragon_animations_are_uv_compatible() -> None:
    hashes = {
        hashlib.sha256((VARIANT_ROOT / f"{variant}#anim.fanim").read_bytes()).hexdigest()
        for variant in VARIANTS
    }
    assert len(hashes) == 1


def test_splitmix64_uses_every_variant_without_material_bias() -> None:
    counts = [0] * len(VARIANTS)
    for seed in range(10_000):
        counts[_splitmix64_variant(seed)] += 1

    assert all(1_800 <= count <= 2_200 for count in counts), counts


def test_runtime_rewrites_the_final_dragon_sprite_from_the_authoritative_seed() -> None:
    source = (MOD / "src" / "lib.rs").read_text(encoding="utf-8")

    assert "fn rewrite_dragon_render_commands(" in source
    assert "rewrite_dragon_render_commands(ui, state)" in source
    assert "RenderCommand::Sprite { texture, .. }" in source
    assert "ui_tree_has_match_runner(&ui.root)" in source
    assert '"asset/base/aseprite_resources/ingame/serpen#sheet"' in source
    assert '"asset/lol_mod/aseprite_resources/ingame/serpen#sheet"' in source
    for variant in VARIANTS:
        assert (
            f'"asset/lol_mod/aseprite_resources/ingame/dragon_variants/{variant}#sheet"'
            in source
        )

    assert "current_dragon_selection()" in source
    assert "current_dragon_variant_index()" in source
    assert 'write_dragon_telemetry("render_apply"' in source
    assert "rewrite_count" in source
    assert "entity.view_name" not in source
    assert 'write_dragon_telemetry("entity_apply"' not in source
    assert "last_applied" not in source
