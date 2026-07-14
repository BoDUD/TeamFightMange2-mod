from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
SCALE_QA_SCRIPT = MOD / "tools" / "qa_legacy_battle_actor_scale.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_qa() -> dict[str, object]:
    return json.loads(
        (MOD / "qa/legacy_battle_actor_scale_qa.json").read_text(encoding="utf-8")
    )


def load_scale_qa_module():
    spec = importlib.util.spec_from_file_location(
        "legacy_battle_actor_scale_test_module", SCALE_QA_SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_official_native_snapshot_is_fixed_complete_and_auditable() -> None:
    module = load_scale_qa_module()
    snapshot_path = MOD / "qa/official_native_actor_contract_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == 1
    assert snapshot["source"] == {
        "bundle_filename": "bundle.game_data",
        "bundle_sha256": "0fa9cd7dfbcd85be55503ceb96336e8955f6fb5bb1d7a540e161d4aa92e1cc2d",
        "asset_key_pattern": "asset/base/aseprite_resources/champions/<native_id>#sheet + #anim",
        "animation_contract_canonicalization": (
            "SHA-256 of UTF-8 JSON for tag -> durations rounded to 8 decimals, "
            "sort_keys=true, separators=(',', ':')"
        ),
    }
    expected = {
        "archer": ([31, 33], [26, 31], "e2c6c7d68adf7aac81383265542f67bb32493680c1c26fa952e527a3b4145eca"),
        "barrier_magician": ([32, 34], [30, 33], "c7a905b72eba04effd990dabed15861c70e0edfb501a8f2e9d1c0b15f91fe4d2"),
        "berserker": ([37, 39], [36, 38], "4105635b6b299349b81d41de861cc6e2b6e2c5d48d6f0fbe74c16cb7cb3b86ef"),
        "boomerang_hunter": ([33, 35], [29, 34], "6c3428900194b4b4970117d932dc738c6d092f5f56f1f022a73040f577e1c6f1"),
    }
    evidence = module.load_repository_official_native_snapshot(set(expected))
    assert set(evidence) == set(expected)
    for native_id, (idle_range, run_range, contract_sha256) in expected.items():
        record = evidence[native_id]
        assert record["asset_key"] == (
            f"asset/base/aseprite_resources/champions/{native_id}"
        )
        assert record["idle_height_range"] == idle_range
        assert record["run_height_range"] == run_range
        assert record["animation_contract"]["sha256"] == contract_sha256
        assert record["animation_contract"]["tag_frame_counts"]["idle"] == 4
        assert record["animation_contract"]["tag_frame_counts"]["run"] == 8


def test_missing_bundle_uses_only_the_repository_snapshot(monkeypatch) -> None:
    module = load_scale_qa_module()

    def missing_bundle() -> Path:
        raise FileNotFoundError("CI checkout has no proprietary game bundle")

    def unexpected_asset_read(*_args, **_kwargs):
        pytest.fail("bundle loader must not run after bundle discovery fails")

    monkeypatch.setattr(module, "find_bundle_path", missing_bundle)
    monkeypatch.setattr(module, "load_official_assets", unexpected_asset_read)
    native_ids = {"archer", "barrier_magician", "berserker", "boomerang_hunter"}
    expected = module.load_repository_official_native_snapshot(native_ids)
    evidence, source = module.load_official_native_evidence(native_ids)
    assert source == "repository_snapshot"
    assert evidence == expected


def test_present_bundle_path_still_reads_and_measures_real_assets(monkeypatch) -> None:
    module = load_scale_qa_module()
    bundle_path = Path("C:/game/bundle.game_data")
    sheet = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    for y in range(2, 8):
        for x in range(1, 6):
            sheet.putpixel((x, y), (255, 255, 255, 255))
    for y in range(1, 9):
        for x in range(11, 18):
            sheet.putpixel((x, y), (255, 255, 255, 255))
    anim = {
        "anims": {
            "idle": {
                "frames": [
                    {
                        "duration": 0.18,
                        "data": {"x": 0, "y": 0, "w": 10, "h": 10},
                    }
                ]
            },
            "run": {
                "frames": [
                    {
                        "duration": 0.08,
                        "data": {"x": 10, "y": 0, "w": 10, "h": 10},
                    }
                ]
            },
        }
    }

    def fake_loader(native_ids: set[str], *, bundle: Path | None = None):
        assert native_ids == {"archer"}
        assert bundle == bundle_path
        return {"archer": (sheet, anim)}

    monkeypatch.setattr(module, "find_bundle_path", lambda: bundle_path)
    monkeypatch.setattr(module, "load_official_assets", fake_loader)
    evidence, source = module.load_official_native_evidence({"archer"})
    assert source == "bundle.game_data"
    assert evidence["archer"]["idle_height_range"] == [6, 6]
    assert evidence["archer"]["run_height_range"] == [8, 8]
    assert evidence["archer"]["animation_contract"] == (
        module.animation_contract_record(anim)
    )


def test_checked_in_snapshot_matches_real_bundle_when_available() -> None:
    module = load_scale_qa_module()
    native_ids = {"archer", "barrier_magician", "berserker", "boomerang_hunter"}
    try:
        module.find_bundle_path()
    except FileNotFoundError:
        pytest.skip("proprietary bundle.game_data is intentionally absent in CI")
    bundle_evidence, source = module.load_official_native_evidence(native_ids)
    snapshot_evidence = module.load_repository_official_native_snapshot(native_ids)
    assert source == "bundle.game_data"
    assert bundle_evidence == snapshot_evidence


def test_five_legacy_battle_actors_use_independent_native_like_targets() -> None:
    qa = load_qa()
    targets = qa["targets"]
    expected = {
        "lol_shen": (40, 36, [40, 38], 45),
        "archer": (40, 36, [36, 40], 45),
        "barrier_magician": (38, 36, [36, 36], 42),
        "berserker": (42, 38, [42, 40], 45),
        "boomerang_hunter": (44, 36, [44, 38], 45),
    }
    assert set(targets) == set(expected)
    for champion_id, (before, after, cap, baseline) in expected.items():
        record = targets[champion_id]
        assert record["idle_height_before_px"] == before
        assert record["idle_height_after_px"] == after
        assert record["height_reduction_px"] == before - after
        assert record["terrain_safe_cap"] == cap
        assert record["foot_baseline_exclusive_y"] == baseline
        assert record["terrain_safe"] is True
        assert record["foot_baseline_safe"] is True
        assert record["observed_core_max_size"][0] <= cap[0]
        assert record["observed_core_max_size"][1] <= cap[1]
        assert record["animation_contract"]["unchanged"] is True


def test_reference_scale_envelope_and_official_contract_evidence_are_recorded() -> None:
    qa = load_qa()
    references = qa["references"]
    assert references["demon"]["idle_height_range"] == [46, 46]
    assert references["cavalry_knight"]["idle_height_range"] == [40, 40]
    if "dual_blader" in references:
        assert references["dual_blader"]["idle_height_range"] == [37, 38]
        assert qa["reference_idle_height_envelope_px"] == [37, 46]
    else:
        # PR #9 is independently buildable before the Yone/009 branch lands.
        assert qa["reference_idle_height_envelope_px"] == [40, 46]

    targets = qa["targets"]
    assert targets["archer"]["official_native"]["idle_height_range"] == [31, 33]
    assert targets["barrier_magician"]["official_native"]["idle_height_range"] == [32, 34]
    assert targets["berserker"]["official_native"]["idle_height_range"] == [37, 39]
    assert targets["boomerang_hunter"]["official_native"]["idle_height_range"] == [33, 35]
    assert targets["barrier_magician"]["official_native"]["animation_contract_exact"] is True
    assert targets["berserker"]["official_native"]["animation_contract_exact"] is True
    assert targets["boomerang_hunter"]["official_native"]["animation_contract_exact"] is True
    # Lucian keeps his already accepted custom Lightslinger action table byte
    # identical; battle scaling does not pretend it is the original Archer table.
    assert targets["archer"]["official_native"]["animation_contract_exact"] is False


def test_battle_only_resize_preserves_all_21_ui_and_portrait_hashes() -> None:
    ui = load_qa()["ui_preservation"]
    assert ui["passed"] is True
    assert ui["file_count"] == 21
    for relative, record in ui["files"].items():
        path = MOD / relative
        assert path.is_file(), relative
        assert record["unchanged"] is True, relative
        assert record["before_sha256"] == record["after_sha256"], relative
        assert sha256(path) == record["after_sha256"], relative


def test_scale_contacts_use_the_canonical_png_writer(tmp_path: Path) -> None:
    module = load_scale_qa_module()
    for name in (
        "legacy_battle_actor_state_stability_contact.png",
        "legacy_battle_actor_reference_scale_contact.png",
    ):
        committed = MOD / "qa" / name
        rebuilt = tmp_path / name
        with Image.open(committed) as opened:
            module.save_png(rebuilt, opened.convert("RGBA"))
        assert rebuilt.read_bytes() == committed.read_bytes()


def test_builder_runs_the_battle_scale_gate_after_all_reference_builders() -> None:
    builder = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    assert "build_legacy_battle_actor_scale_qa" in builder
    assert builder.index("urgot_outputs = build_urgot_assets()") < builder.index(
        "legacy_battle_actor_scale_qa = build_legacy_battle_actor_scale_qa()"
    )
    if "yone_outputs = build_yone_assets()" in builder:
        assert builder.index("yone_outputs = build_yone_assets()") < builder.index(
            "legacy_battle_actor_scale_qa = build_legacy_battle_actor_scale_qa()"
        )


def test_all_declared_actor_tags_and_frames_have_full_stability_evidence() -> None:
    qa = load_qa()
    assert qa["schema_version"] == 2
    expected = {
        "lol_shen": (8, 41, 3),
        "archer": (20, 106, 5),
        "barrier_magician": (8, 41, 5),
        "berserker": (24, 103, 14),
        "boomerang_hunter": (12, 55, 12),
    }
    for champion_id, (action_count, frame_refs, before_failures) in expected.items():
        stability = qa["targets"][champion_id]["all_action_frame_stability"]
        after = stability["after_full_frame_audit"]
        assert stability["declared_action_count"] == action_count
        assert stability["declared_frame_reference_count"] == frame_refs
        assert stability["before_upright_height_failure_count"] == before_failures
        assert stability["after_live_body_failure_count"] == 0
        assert after["live_body_failure_count"] == 0
        assert after["frame_canvas_sizes"] == [[64, 64]]
        assert len(after["actions"]) == action_count
        assert sum(
            action["declared_frame_count"] for action in after["actions"].values()
        ) == frame_refs

        anim_path = MOD / "aseprite_resources/champions" / {
            "lol_shen": "shen#anim.fanim",
            "archer": "lucian#anim.fanim",
            "barrier_magician": "orianna#anim.fanim",
            "berserker": "briar#anim.fanim",
            "boomerang_hunter": "sivir#anim.fanim",
        }[champion_id]
        anim = json.loads(anim_path.read_text(encoding="utf-8"))["anims"]
        assert set(after["actions"]) == set(anim)
        for tag, action in after["actions"].items():
            assert action["declared_frame_count"] == len(anim[tag]["frames"])
            assert len(action["frames"]) == len(anim[tag]["frames"])
            if action["classification"] == "live_actor_body":
                for frame in action["frames"]:
                    assert False not in frame["stability_checks"].values(), (
                        champion_id,
                        tag,
                        frame["frame_index"],
                        frame["stability_checks"],
                    )

    lucian_compat = qa["targets"]["archer"]["all_action_frame_stability"][
        "action_before_after"
    ]
    assert {
        tag
        for tag, row in lucian_compat.items()
        if row.get("native_runtime_compatibility_added_after_baseline") is True
    } == {
        "ult_old",
        "ult_pre",
        "ult_loop",
        "ult_end",
        "ult_projectile",
        "old_ult_buff_effect",
        "skill_attack",
        "skill_dash",
        "old_ult_pre",
    }


def test_known_live_size_jumps_are_closed_in_every_target() -> None:
    targets = load_qa()["targets"]
    expected = {
        ("lol_shen", "skill2"): ([32, 36], [35, 36]),
        ("lol_shen", "hit"): ([31, 31], [33, 33]),
        ("archer", "skill2"): ([30, 35], [34, 36]),
        ("archer", "ult"): ([34, 40], [36, 39]),
        ("barrier_magician", "attack"): ([28, 34], [35, 36]),
        ("barrier_magician", "hit"): ([28, 28], [34, 34]),
        ("barrier_magician", "ult"): ([31, 32], [36, 36]),
        ("berserker", "attack2"): ([31, 38], [35, 38]),
        ("berserker", "skill2"): ([34, 40], [36, 38]),
        ("boomerang_hunter", "attack"): ([29, 36], [33, 36]),
        ("boomerang_hunter", "skill"): ([27, 36], [33, 36]),
    }
    for (champion_id, tag), (before, after) in expected.items():
        comparison = targets[champion_id]["all_action_frame_stability"][
            "action_before_after"
        ][tag]
        assert comparison["visible_height_range_before"] == before
        assert comparison["visible_height_range_after"] == after


def test_full_frame_before_after_artifacts_are_present_and_hashed() -> None:
    qa = load_qa()
    baseline = MOD / "qa/legacy_battle_actor_scale_before.json"
    contact = MOD / qa["stability_contact"]
    reference_contact = MOD / qa["reference_scale_contact"]
    assert baseline.is_file()
    assert contact.is_file()
    assert reference_contact.is_file()
    assert sha256(contact) == qa["stability_contact_sha256"]
    assert sha256(reference_contact) == qa["reference_scale_contact_sha256"]
    for record in qa["targets"].values():
        stability = record["all_action_frame_stability"]
        assert sha256(MOD / stability["before_full_frame_audit"]) == stability[
            "before_full_frame_audit_sha256"
        ]
        assert stability["before_sheet_sha256"] != stability["after_sheet_sha256"]
