from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


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
        "archer": (11, 67, 5),
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
