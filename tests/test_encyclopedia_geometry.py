"""Independent stock-renderer regression: old screenshots MUST fail this gate."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/lol_mod"
spec = importlib.util.spec_from_file_location("encyclopedia_geometry", MOD / "tools/qa_encyclopedia_geometry.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def test_actual_uv_direction_and_full_body_above_controls():
    report = qa.audit()
    for champion, row in report["champions"].items():
        assert row["before"]["source_pixels_clipped"] > 0, champion
        assert row["after"]["source_pixels_clipped"] == 0, champion
        assert row["after"]["tier_clearance"] >= 4, champion
        assert 56 <= row["after"]["fullbody_height"] <= 60, champion
        assert row["after"]["actor_bbox"][1] >= 6, champion


def test_layout_fit_preserves_native_texture_and_never_shrinks_repeatedly():
    runtime = (MOD / "src/stable_runtime.rs").read_text(encoding="utf-8")
    body = runtime.split("fn fit_encyclopedia_native_layout(", 1)[1].split("impl StableExtension", 1)[0]
    assert 'Some("GameInfo")' in body
    assert '("dual_blader", 63.75_f32)' in body
    assert '("dancer", 40.5_f32)' in body
    assert 'height: 69.75px; y: 76px;' in body
    assert 'Some("image")' in body
    for forbidden in ("ui_set_champion_icon", "ui_set_visible", "ui_spawn", "source:", "draw_", "ui_node_rect"):
        assert forbidden not in body
    update = runtime.split("impl StableExtension for QualityBpExtension", 1)[1]
    assert update.index("fit_encyclopedia_native_layout(client);") < update.index("fetch_add")
