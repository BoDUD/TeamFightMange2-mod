#!/usr/bin/env python3
"""Audit legacy battle-actor scale without changing any portrait/UI asset."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import struct
from typing import Any

from PIL import Image, ImageDraw


MOD_ROOT = Path(__file__).resolve().parents[1]
ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
QA_DIR = MOD_ROOT / "qa"
BEFORE_AUDIT_PATH = QA_DIR / "legacy_battle_actor_scale_before.json"


@dataclass(frozen=True)
class ActorSpec:
    label: str
    native_id: str
    prefix: str
    tags: tuple[str, ...]
    idle_height_before: int | None = None
    idle_height_target: int | None = None
    foot_baseline: int | None = None
    terrain_cap: tuple[int, int] | None = None
    official_native_id: str | None = None


TARGETS = (
    ActorSpec(
        "Shen",
        "lol_shen",
        "shen",
        ("idle", "run", "attack", "skill", "skill2", "ult", "hit"),
        40,
        36,
        45,
        (40, 38),
        None,
    ),
    ActorSpec(
        "Lucian",
        "archer",
        "lucian",
        (
            "idle",
            "run",
            "attack_right",
            "attack_left",
            "attack_double",
            "skill",
            "skill2",
            "ult",
            "hit",
        ),
        40,
        36,
        45,
        (36, 40),
        "archer",
    ),
    ActorSpec(
        "Orianna",
        "barrier_magician",
        "orianna",
        ("idle", "run", "attack", "skill1", "skill2", "ult", "hit"),
        38,
        36,
        42,
        (36, 36),
        "barrier_magician",
    ),
    ActorSpec(
        "Briar",
        "berserker",
        "briar",
        (
            "idle",
            "berserk_idle",
            "run",
            "berserk_run",
            "attack",
            "attack2",
            "berserk_attack",
            "skill1",
            "skill2",
            "skill2_berserk",
            "ult",
            "hit",
        ),
        42,
        38,
        45,
        (42, 40),
        "berserker",
    ),
    ActorSpec(
        "Sivir",
        "boomerang_hunter",
        "sivir",
        ("idle", "run", "attack", "skill", "skill2", "ult", "hit"),
        44,
        36,
        45,
        (44, 38),
        "boomerang_hunter",
    ),
)


# Every declared tag is audited. These exclusions only decide whether a frame
# is an actor-body stability candidate: projectile-only tags and death fades
# must retain their native timing/canvas, but must not be compared with a live
# standing body. A wide live pose (width > 1.30 * height) is treated as a real
# lunge/knockdown posture and checked by silhouette scale instead of height.
NON_BODY_TAGS = {
    "boomerang_hunter": {"big_boomerang", "boomerang", "ult_boomerang"},
}
DEATH_TAG_TOKENS = ("dead",)
UPRIGHT_ASPECT_RATIO_MAX = 1.30
UPRIGHT_HEIGHT_TOLERANCE_BELOW = 3
UPRIGHT_HEIGHT_TOLERANCE_ABOVE = 4
SILHOUETTE_SCALE_MIN = 0.90
SILHOUETTE_SCALE_MAX = 1.20
FOOT_ANCHOR_TOLERANCE = 1


REFERENCES = (
    ActorSpec(
        "Yone",
        "dual_blader",
        "yone",
        ("idle", "run", "attack", "skill2", "skill2_dash", "skill2_attack", "ult", "hit"),
    ),
    ActorSpec(
        "Urgot",
        "demon",
        "demon",
        ("idle", "run", "attack", "skill2", "ult", "hit"),
    ),
    ActorSpec(
        "Kled",
        "cavalry_knight",
        "kled",
        ("idle", "run", "attack", "skill1", "skill2", "ult", "hit"),
    ),
)


# Snapshot taken immediately before the battle-only resize. These files are
# deliberately source-direct and must not move when actor atlases are rebuilt.
PRESERVED_UI_SHA256 = {
    "style/champion_view.champion_view": "61c2afd331e239522c4b569312c4e5f38e513151b498133e8b0c7ab082ea4123",
    "ui/champion_fullbody/lol_shen.png": "b45e4e7b082875ca4d3243671723d19546fb4bb81715862c191163113b906dc4",
    "ui/champion_portrait/lol_shen_compact.png": "0605a6f72bf17605d7aeb94b19452c504003aab83822800dca8c622bbaaa5c39",
    "ui/champion_portrait/lol_shen_scoreboard.png": "47f2e6684facbd431e5f1340303dc7b0f000944c2308222987b07faed2d00cc0",
    "ui/champion_portrait/lol_shen_grid.png": "298170d01e5ab5c1cc0badc0a9d539fca21be4b64b6b1ca41a217d1c6a01d169",
    "ui/champion_fullbody/archer.png": "30405f7c747bab463ab091ae8c501e6d4ad981e41040865c72f8a9671c049bbf",
    "ui/champion_portrait/archer_compact.png": "55784dcc604f1ad171dca045b4b5feaaf92d69189d54d2f5cea2be8b98fa6be2",
    "ui/champion_portrait/archer_scoreboard.png": "8b877dae63d873be40f18d327227a73a699bc7c115999edd7213c45d782b8a69",
    "ui/champion_portrait/archer_grid.png": "8fe87e0707026766d6f840ba60c711f785cfb71d31e84d37bd5cc1524dc1c9c3",
    "ui/champion_fullbody/barrier_magician.png": "7ae9b9092a9ba6659f2383a0b83ef80bd289617cfb1b41c21c40c24f0977153b",
    "ui/champion_portrait/barrier_magician_compact.png": "2a42caa99f70c4f5e64b3b97fb626808dff8c3a88a786fb6d2dba9bb3e882079",
    "ui/champion_portrait/barrier_magician_scoreboard.png": "5d8fe52871dd7b84b5a0c7fc2fc3a13ca60214f439077cfbdbd3f1cd9bea6e3c",
    "ui/champion_portrait/barrier_magician_grid.png": "d665f19c68b7f88a2e35e929d4ba21df6115bb64b9391fec870f8cf6789cac11",
    "ui/champion_fullbody/berserker.png": "de737af5921979665e54a7155d5c9892f33db4e74af6f41ee84ee601ca877d8f",
    "ui/champion_portrait/berserker_compact.png": "ad493562203d4386e691f7e71f84171a709981be341a1fe808a25ded6a07b457",
    "ui/champion_portrait/berserker_scoreboard.png": "e3adc62bde3aea2dbc73bc5579e374d5077b65c6c81b250d0789577cd4b38191",
    "ui/champion_portrait/berserker_grid.png": "9df4c9dba3a291e29a19c38c7007fc666979e512e11e8837137de95a35737960",
    "ui/champion_fullbody/boomerang_hunter.png": "bdc2f630c7b81f2b7204e3e5da5fbe322e70645fe80de84ad2d4904d0cef2d73",
    "ui/champion_portrait/boomerang_hunter_compact.png": "1cd4c992f6e27e14c4b1eee302b48409810dbe1c9d151e7ff590183f83638cea",
    "ui/champion_portrait/boomerang_hunter_scoreboard.png": "622c5cbaa1d60a921fa9e03eb6b110a9a5e1aa0f8d1a393a3a87e1bb72bde350",
    "ui/champion_portrait/boomerang_hunter_grid.png": "852532e8af7f8573f81e708d54b7b5a51561ac4d3e4548f9e35fef52155bdd89",
}

# PR #9 can be built before or after the independent Yone/009 branch. Yone
# adds one champion_view entry but does not touch any of the five audited
# portrait cameras, so both exact pre-resize style hashes are valid baselines.
PRESERVED_UI_SHA256_ALTERNATES = {
    "style/champion_view.champion_view": {
        "66539e56d720673c0311d1dbdb19a0ed9d4db619a1fb0746b2c9a0eb43ea5309",
    },
}

PRESERVED_ANIMATION_SHA256 = {
    "shen": "4fcd4da62313dc2e5294310b2c1ba998f24ae063643b0bf0f29bd95845aa8e16",
    "lucian": "0c627dfc303f226262e72ad3871d0e763c53209199a020fa10860d56523dc88c",
    "orianna": "bf82a05db4934e9985761ca2bff06d88488465df21f41e34b10bb3af5926f9fe",
    "briar": "ebf73e93841103c66b32faa811a5009c654c89067948e1db65fd20796df898b3",
    "sivir": "74875b39afa10b6c5143327b0c53a9aa05b72457cbe62e51d6ff049ad11c3540",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_actor(spec: ActorSpec) -> tuple[Image.Image, dict[str, Any]]:
    sheet = Image.open(ACTOR_DIR / f"{spec.prefix}#sheet.png").convert("RGBA")
    anim = json.loads(
        (ACTOR_DIR / f"{spec.prefix}#anim.fanim").read_text(encoding="utf-8")
    )
    return sheet, anim


def frame_images(
    sheet: Image.Image, anim: dict[str, Any], tag: str
) -> list[Image.Image]:
    frames: list[Image.Image] = []
    for row in anim["anims"][tag]["frames"]:
        data = row["data"]
        frames.append(
            sheet.crop(
                (
                    int(data["x"]),
                    int(data["y"]),
                    int(data["x"]) + int(data["w"]),
                    int(data["y"]) + int(data["h"]),
                )
            )
        )
    return frames


def action_metrics(
    sheet: Image.Image, anim: dict[str, Any], tags: tuple[str, ...]
) -> dict[str, Any]:
    actions: dict[str, Any] = {}
    for tag in tags:
        if tag not in anim.get("anims", {}):
            continue
        bboxes: list[list[int]] = []
        for frame in frame_images(sheet, anim, tag):
            bbox = frame.getchannel("A").getbbox()
            if bbox is not None:
                bboxes.append(list(bbox))
        if not bboxes:
            continue
        widths = [row[2] - row[0] for row in bboxes]
        heights = [row[3] - row[1] for row in bboxes]
        actions[tag] = {
            "frame_count": len(bboxes),
            "alpha_bboxes": bboxes,
            "visible_width_range": [min(widths), max(widths)],
            "visible_height_range": [min(heights), max(heights)],
            "bottom_range": [min(row[3] for row in bboxes), max(row[3] for row in bboxes)],
        }
    return actions


def _alpha_depth(alpha: Image.Image) -> int:
    """Return a small pose-independent silhouette-thickness proxy."""

    remaining = {
        (x, y)
        for y in range(alpha.height)
        for x in range(alpha.width)
        if int(alpha.getpixel((x, y))) > 0
    }
    depth = 0
    while remaining:
        depth += 1
        remaining = {
            point
            for point in remaining
            if (
                (point[0] - 1, point[1]) in remaining
                and (point[0] + 1, point[1]) in remaining
                and (point[0], point[1] - 1) in remaining
                and (point[0], point[1] + 1) in remaining
            )
        }
    return depth


def _frame_audit(frame: Image.Image, row: dict[str, Any], index: int) -> dict[str, Any]:
    alpha = frame.getchannel("A")
    bbox = alpha.getbbox()
    histogram = alpha.histogram()
    nonzero_pixels = sum(histogram[1:])
    alpha_equivalent_pixels = round(
        sum(value * count for value, count in enumerate(histogram)) / 255.0,
        3,
    )
    if bbox is None:
        visible_size = [0, 0]
        bottom_y = None
        aspect_ratio = None
        solidity = None
    else:
        visible_size = [bbox[2] - bbox[0], bbox[3] - bbox[1]]
        bottom_y = bbox[3]
        aspect_ratio = round(visible_size[0] / max(1, visible_size[1]), 4)
        solidity = round(nonzero_pixels / max(1, visible_size[0] * visible_size[1]), 4)
    data = row["data"]
    return {
        "frame_index": index,
        "duration": round(float(row["duration"]), 8),
        "source_rect": [
            int(data["x"]),
            int(data["y"]),
            int(data["w"]),
            int(data["h"]),
        ],
        "alpha_bbox": list(bbox) if bbox is not None else None,
        "visible_size": visible_size,
        "bottom_y": bottom_y,
        "aspect_ratio": aspect_ratio,
        "nonzero_pixels": nonzero_pixels,
        "alpha_equivalent_pixels": alpha_equivalent_pixels,
        "silhouette_solidity": solidity,
        "silhouette_depth_4n": _alpha_depth(alpha),
        "rgba_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
    }


def full_actor_metrics(
    spec: ActorSpec, sheet: Image.Image, anim: dict[str, Any]
) -> dict[str, Any]:
    """Audit every declared frame and calculate action-switch scale jumps."""

    idle_records = [
        _frame_audit(frame, row, index)
        for index, (frame, row) in enumerate(
            zip(
                frame_images(sheet, anim, "idle"),
                anim["anims"]["idle"]["frames"],
                strict=True,
            )
        )
    ]
    idle_nonzero = [record["nonzero_pixels"] for record in idle_records if record["nonzero_pixels"]]
    if not idle_nonzero:
        raise ValueError(f"{spec.label} has no visible idle frame")
    idle_pixel_median = float(statistics.median(idle_nonzero))
    target_height = int(spec.idle_height_target or 0)
    min_upright_height = target_height - UPRIGHT_HEIGHT_TOLERANCE_BELOW
    max_upright_height = target_height + UPRIGHT_HEIGHT_TOLERANCE_ABOVE
    action_records: dict[str, Any] = {}
    canvas_sizes: set[tuple[int, int]] = set()
    live_failures: list[dict[str, Any]] = []
    for tag, value in anim.get("anims", {}).items():
        frames = frame_images(sheet, anim, tag)
        rows = value["frames"]
        records = [
            _frame_audit(frame, row, index)
            for index, (frame, row) in enumerate(zip(frames, rows, strict=True))
        ]
        for record in records:
            canvas_sizes.add(tuple(record["source_rect"][2:4]))
        if tag in NON_BODY_TAGS.get(spec.native_id, set()) or "effect" in tag:
            classification = "effect_surface"
        elif any(token in tag for token in DEATH_TAG_TOKENS):
            classification = "death_or_fade"
        else:
            classification = "live_actor_body"
        nonempty = [record for record in records if record["nonzero_pixels"]]
        for record in records:
            scale = (
                math.sqrt(record["nonzero_pixels"] / idle_pixel_median)
                if record["nonzero_pixels"]
                else 0.0
            )
            record["silhouette_scale_vs_idle"] = round(scale, 4)
            record["upright_pose"] = bool(
                record["aspect_ratio"] is not None
                and record["aspect_ratio"] <= UPRIGHT_ASPECT_RATIO_MAX
            )
            checks: dict[str, bool | None] = {
                "canvas_64x64": record["source_rect"][2:4] == [64, 64],
                "foot_anchor": None,
                "upright_height": None,
                "horizontal_pose_span": None,
                "silhouette_scale": None,
            }
            if classification == "live_actor_body" and record["nonzero_pixels"]:
                checks["foot_anchor"] = bool(
                    int(spec.foot_baseline or 0) - FOOT_ANCHOR_TOLERANCE
                    <= int(record["bottom_y"] or 0)
                    <= int(spec.foot_baseline or 0)
                )
                checks["silhouette_scale"] = bool(
                    SILHOUETTE_SCALE_MIN <= scale <= SILHOUETTE_SCALE_MAX
                )
                if record["upright_pose"]:
                    checks["upright_height"] = bool(
                        min_upright_height
                        <= int(record["visible_size"][1])
                        <= max_upright_height
                    )
                else:
                    checks["horizontal_pose_span"] = bool(
                        min_upright_height
                        <= max(int(value) for value in record["visible_size"])
                        <= max(int(value) for value in (spec.terrain_cap or (64, 64)))
                    )
                failed = [name for name, passed in checks.items() if passed is False]
                if failed:
                    live_failures.append(
                        {"tag": tag, "frame_index": record["frame_index"], "checks": failed}
                    )
            record["stability_checks"] = checks
        widths = [record["visible_size"][0] for record in nonempty]
        heights = [record["visible_size"][1] for record in nonempty]
        bottoms = [int(record["bottom_y"]) for record in nonempty]
        scales = [record["silhouette_scale_vs_idle"] for record in nonempty]
        adjacent_scale_jumps = [
            abs(scales[index] / scales[index - 1] - 1.0) * 100
            for index in range(1, len(scales))
            if scales[index - 1] > 0
        ]
        adjacent_height_jumps = [
            abs(heights[index] - heights[index - 1])
            for index in range(1, len(heights))
        ]
        action_records[tag] = {
            "classification": classification,
            "declared_frame_count": len(rows),
            "nonempty_frame_count": len(nonempty),
            "canvas_sizes": [
                list(size)
                for size in sorted(
                    {tuple(record["source_rect"][2:4]) for record in records}
                )
            ],
            "visible_width_range": [min(widths), max(widths)] if widths else [0, 0],
            "visible_height_range": [min(heights), max(heights)] if heights else [0, 0],
            "bottom_range": [min(bottoms), max(bottoms)] if bottoms else [0, 0],
            "silhouette_scale_vs_idle_range": [
                round(min(scales), 4),
                round(max(scales), 4),
            ] if scales else [0.0, 0.0],
            "entry_scale_jump_percent": round(abs(scales[0] - 1.0) * 100, 2) if scales else 0.0,
            "exit_scale_jump_percent": round(abs(scales[-1] - 1.0) * 100, 2) if scales else 0.0,
            "max_adjacent_scale_jump_percent": round(max(adjacent_scale_jumps, default=0.0), 2),
            "max_adjacent_visible_height_jump_px": max(adjacent_height_jumps, default=0),
            "frames": records,
        }
    return {
        "sheet_dimensions": list(sheet.size),
        "sheet_sha256": sha256(ACTOR_DIR / f"{spec.prefix}#sheet.png"),
        "animation_sha256": sha256(ACTOR_DIR / f"{spec.prefix}#anim.fanim"),
        "declared_action_count": len(action_records),
        "declared_frame_reference_count": sum(
            record["declared_frame_count"] for record in action_records.values()
        ),
        "frame_canvas_sizes": [list(size) for size in sorted(canvas_sizes)],
        "idle_silhouette_pixels_median": idle_pixel_median,
        "upright_height_gate_px": [min_upright_height, max_upright_height],
        "silhouette_scale_gate": [SILHOUETTE_SCALE_MIN, SILHOUETTE_SCALE_MAX],
        "live_body_failure_count": len(live_failures),
        "live_body_failures": live_failures,
        "actions": action_records,
    }


def capture_before_audit() -> Path:
    payload: dict[str, Any] = {
        "schema_version": 2,
        "purpose": "pre-fix full-frame baseline for the five legacy battle actors",
        "targets": {},
    }
    for spec in TARGETS:
        sheet, anim = load_actor(spec)
        payload["targets"][spec.native_id] = {
            "champion": spec.label,
            "audit": full_actor_metrics(spec, sheet, anim),
        }
    QA_DIR.mkdir(parents=True, exist_ok=True)
    BEFORE_AUDIT_PATH.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return BEFORE_AUDIT_PATH


def contract_signature(anim: dict[str, Any]) -> dict[str, list[float]]:
    return {
        tag: [round(float(row["duration"]), 8) for row in value["frames"]]
        for tag, value in anim["anims"].items()
    }


def find_bundle_path() -> Path:
    for path in (MOD_ROOT.parents[2] / "bundle.game_data", MOD_ROOT.parents[1] / "bundle.game_data"):
        if path.is_file():
            return path
    raise FileNotFoundError("bundle.game_data not found from lol_mod tree")


def load_official_assets(native_ids: set[str]) -> dict[str, tuple[Image.Image, dict[str, Any]]]:
    keys = {
        f"asset/base/aseprite_resources/champions/{native_id}#{kind}": (native_id, kind)
        for native_id in native_ids
        for kind in ("sheet", "anim")
    }
    payloads: dict[tuple[str, str], bytes] = {}
    bundle = find_bundle_path()
    with bundle.open("rb") as handle:
        entry_count = struct.unpack("<I", handle.read(4))[0]
        for _ in range(entry_count):
            type_length = struct.unpack("<I", handle.read(4))[0]
            handle.seek(type_length, 1)
            key_length = struct.unpack("<I", handle.read(4))[0]
            key = handle.read(key_length).decode("utf-8")
            data_length = struct.unpack("<I", handle.read(4))[0]
            if key not in keys:
                handle.seek(data_length, 1)
                continue
            payloads[keys[key]] = handle.read(data_length)
            if len(payloads) == len(keys):
                break
    missing = sorted(set(keys.values()) - set(payloads))
    if missing:
        raise KeyError(f"official actor assets missing from bundle: {missing}")
    result: dict[str, tuple[Image.Image, dict[str, Any]]] = {}
    for native_id in native_ids:
        with Image.open(io.BytesIO(payloads[native_id, "sheet"])) as opened:
            image = opened.convert("RGBA")
        document = json.loads(payloads[native_id, "anim"].decode("utf-8"))
        result[native_id] = image, document
    return result


def maximum_core_size(actions: dict[str, Any]) -> list[int]:
    return [
        max(record["visible_width_range"][1] for record in actions.values()),
        max(record["visible_height_range"][1] for record in actions.values()),
    ]


def _action_before_after(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    if set(before["actions"]) != set(after["actions"]):
        raise ValueError("actor action keys changed during the scale-stability pass")
    comparisons: dict[str, Any] = {}
    for tag, after_action in after["actions"].items():
        before_action = before["actions"][tag]
        if before_action["declared_frame_count"] != after_action["declared_frame_count"]:
            raise ValueError(f"{tag} frame count changed during the scale-stability pass")
        comparisons[tag] = {
            "classification": after_action["classification"],
            "frame_count": after_action["declared_frame_count"],
            "visible_width_range_before": before_action["visible_width_range"],
            "visible_width_range_after": after_action["visible_width_range"],
            "visible_height_range_before": before_action["visible_height_range"],
            "visible_height_range_after": after_action["visible_height_range"],
            "silhouette_scale_range_before": before_action[
                "silhouette_scale_vs_idle_range"
            ],
            "silhouette_scale_range_after": after_action[
                "silhouette_scale_vs_idle_range"
            ],
            "max_adjacent_height_jump_before_px": before_action[
                "max_adjacent_visible_height_jump_px"
            ],
            "max_adjacent_height_jump_after_px": after_action[
                "max_adjacent_visible_height_jump_px"
            ],
            "max_adjacent_scale_jump_before_percent": before_action[
                "max_adjacent_scale_jump_percent"
            ],
            "max_adjacent_scale_jump_after_percent": after_action[
                "max_adjacent_scale_jump_percent"
            ],
        }
    return comparisons


def build_stability_contact() -> Path:
    """Render representative worst-height frames on their exact 64px canvases."""

    selected_tags = {
        "lol_shen": ("idle", "run", "attack", "skill", "skill2", "ult", "hit", "dead"),
        "archer": (
            "idle",
            "run",
            "attack_right",
            "attack_double",
            "skill",
            "skill2",
            "ult",
            "hit",
        ),
        "barrier_magician": (
            "idle",
            "run",
            "attack",
            "skill1",
            "skill2",
            "ult",
            "hit",
            "dead",
        ),
        "berserker": (
            "idle",
            "berserk_idle",
            "run",
            "attack2",
            "skill1",
            "skill2",
            "ult",
            "hit",
        ),
        "boomerang_hunter": (
            "idle",
            "run",
            "attack",
            "skill",
            "skill2",
            "ult",
            "hit",
            "dead",
        ),
    }
    cell_width = 160
    cell_height = 176
    contact = Image.new(
        "RGBA", (8 * cell_width, len(TARGETS) * cell_height), (18, 18, 26, 255)
    )
    draw = ImageDraw.Draw(contact)
    for row_index, spec in enumerate(TARGETS):
        sheet, anim = load_actor(spec)
        for column_index, tag in enumerate(selected_tags[spec.native_id]):
            rows = anim["anims"][tag]["frames"]
            frames = frame_images(sheet, anim, tag)
            visible = [
                (index, frame.getchannel("A").getbbox())
                for index, frame in enumerate(frames)
                if frame.getchannel("A").getbbox() is not None
            ]
            chosen_index = min(
                visible,
                key=lambda item: (item[1][3] - item[1][1], item[0]),
            )[0]
            frame = frames[chosen_index]
            bbox = frame.getchannel("A").getbbox()
            zoom = frame.resize((128, 128), Image.Resampling.NEAREST)
            x = column_index * cell_width + 16
            y = row_index * cell_height + 8
            contact.alpha_composite(zoom, (x, y))
            if bbox is not None:
                draw.rectangle(
                    (
                        x + bbox[0] * 2,
                        y + bbox[1] * 2,
                        x + bbox[2] * 2 - 1,
                        y + bbox[3] * 2 - 1,
                    ),
                    outline=(80, 235, 160, 255),
                    width=1,
                )
                draw.line(
                    (
                        x,
                        y + int(spec.foot_baseline or 0) * 2,
                        x + 127,
                        y + int(spec.foot_baseline or 0) * 2,
                    ),
                    fill=(235, 90, 110, 255),
                    width=1,
                )
                size_label = f"{bbox[2] - bbox[0]}x{bbox[3] - bbox[1]}"
            else:
                size_label = "empty"
            draw.text(
                (column_index * cell_width + 4, row_index * cell_height + 140),
                f"{spec.label} {tag}[{chosen_index}]",
                fill=(245, 245, 248, 255),
            )
            draw.text(
                (column_index * cell_width + 4, row_index * cell_height + 156),
                f"bbox {size_label}",
                fill=(150, 230, 195, 255),
            )
    output = QA_DIR / "legacy_battle_actor_state_stability_contact.png"
    contact.save(output)
    return output


def build_reference_scale_contact(
    reference_specs: tuple[ActorSpec, ...],
) -> Path:
    """Align target idles with every accepted reference present in this branch."""

    specs = (*reference_specs, *TARGETS)
    cell_width = 160
    cell_height = 176
    baseline_y = 128
    contact = Image.new(
        "RGBA", (len(specs) * cell_width, cell_height), (18, 18, 26, 255)
    )
    draw = ImageDraw.Draw(contact)
    draw.line((0, baseline_y, contact.width, baseline_y), fill=(235, 90, 110, 255))
    for index, spec in enumerate(specs):
        sheet, anim = load_actor(spec)
        frame = frame_images(sheet, anim, "idle")[0]
        bbox = frame.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"{spec.label} reference idle is empty")
        zoom = frame.resize((128, 128), Image.Resampling.NEAREST)
        x = index * cell_width + 16
        y = baseline_y - bbox[3] * 2
        contact.alpha_composite(zoom, (x, y))
        draw.rectangle(
            (
                x + bbox[0] * 2,
                y + bbox[1] * 2,
                x + bbox[2] * 2 - 1,
                y + bbox[3] * 2 - 1,
            ),
            outline=(80, 235, 160, 255),
        )
        draw.text(
            (index * cell_width + 4, 140),
            f"{spec.label} {bbox[2] - bbox[0]}x{bbox[3] - bbox[1]}",
            fill=(245, 245, 248, 255),
        )
    output = QA_DIR / "legacy_battle_actor_reference_scale_contact.png"
    contact.save(output)
    return output


def build_all() -> list[Path]:
    if not BEFORE_AUDIT_PATH.is_file():
        raise FileNotFoundError(
            "full-frame before baseline is missing; run with --capture-before first"
        )
    before_payload = json.loads(BEFORE_AUDIT_PATH.read_text(encoding="utf-8"))
    # Keep generated QA text canonical on Windows without recapturing metrics.
    BEFORE_AUDIT_PATH.write_bytes(
        (json.dumps(before_payload, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    native_ids = {spec.official_native_id for spec in TARGETS if spec.official_native_id}
    official = load_official_assets({native_id for native_id in native_ids if native_id})

    available_references = tuple(
        spec
        for spec in REFERENCES
        if (ACTOR_DIR / f"{spec.prefix}#sheet.png").is_file()
        and (ACTOR_DIR / f"{spec.prefix}#anim.fanim").is_file()
    )
    if not available_references:
        raise FileNotFoundError("no accepted battle-scale reference actor is available")

    references: dict[str, Any] = {}
    reference_idle_heights: list[int] = []
    for spec in available_references:
        sheet, anim = load_actor(spec)
        actions = action_metrics(sheet, anim, spec.tags)
        idle_range = actions["idle"]["visible_height_range"]
        reference_idle_heights.extend(idle_range)
        references[spec.native_id] = {
            "champion": spec.label,
            "sheet": f"aseprite_resources/champions/{spec.prefix}#sheet.png",
            "idle_height_range": idle_range,
            "observed_core_max_size": maximum_core_size(actions),
            "core_actions": actions,
        }

    targets: dict[str, Any] = {}
    for spec in TARGETS:
        sheet, anim = load_actor(spec)
        actions = action_metrics(sheet, anim, spec.tags)
        full_audit = full_actor_metrics(spec, sheet, anim)
        before_audit = before_payload["targets"][spec.native_id]["audit"]
        action_comparison = _action_before_after(before_audit, full_audit)
        if full_audit["live_body_failure_count"]:
            raise ValueError(
                f"{spec.label} still has live body scale failures: "
                f"{full_audit['live_body_failures']}"
            )
        idle_range = actions["idle"]["visible_height_range"]
        current_idle = idle_range[1]
        if current_idle != spec.idle_height_target:
            raise ValueError(
                f"{spec.label} idle is {current_idle}px, expected {spec.idle_height_target}px"
            )
        observed_max = maximum_core_size(actions)
        terrain_pass = bool(
            spec.terrain_cap
            and observed_max[0] <= spec.terrain_cap[0]
            and observed_max[1] <= spec.terrain_cap[1]
        )
        baseline_pass = all(
            record["bottom_range"][1] <= int(spec.foot_baseline or 0)
            for record in actions.values()
        )
        native_record: dict[str, Any] | None = None
        if spec.official_native_id:
            native_sheet, native_anim = official[spec.official_native_id]
            native_actions = action_metrics(native_sheet, native_anim, ("idle", "run"))
            native_record = {
                "asset_key": f"asset/base/aseprite_resources/champions/{spec.official_native_id}",
                "idle_height_range": native_actions["idle"]["visible_height_range"],
                "run_height_range": native_actions["run"]["visible_height_range"],
                "animation_contract_exact": contract_signature(anim)
                == contract_signature(native_anim),
            }
            # Lucian intentionally owns a project-specific action table for
            # Lightslinger/E/Q/R. The battle-scale pass must keep that table
            # byte-identical, while Orianna/Briar/Sivir remain exact native
            # tag/count/duration replacements.
            if (
                spec.native_id != "archer"
                and not native_record["animation_contract_exact"]
            ):
                raise ValueError(f"{spec.label} no longer preserves the official animation contract")
        anim_path = ACTOR_DIR / f"{spec.prefix}#anim.fanim"
        expected_anim_sha = PRESERVED_ANIMATION_SHA256[spec.prefix]
        actual_anim_sha = sha256(anim_path)
        if actual_anim_sha != expected_anim_sha:
            raise ValueError(
                f"{spec.label} battle-scale pass changed animation geometry/timing: "
                f"{actual_anim_sha} != {expected_anim_sha}"
            )
        if not terrain_pass or not baseline_pass:
            raise ValueError(
                f"{spec.label} battle footprint failed: max={observed_max}, "
                f"cap={spec.terrain_cap}, baseline={spec.foot_baseline}"
            )
        targets[spec.native_id] = {
            "champion": spec.label,
            "sheet": f"aseprite_resources/champions/{spec.prefix}#sheet.png",
            "idle_height_before_px": spec.idle_height_before,
            "idle_height_after_px": current_idle,
            "height_reduction_px": int(spec.idle_height_before or 0) - current_idle,
            "height_reduction_percent": round(
                100 * (int(spec.idle_height_before or 0) - current_idle)
                / int(spec.idle_height_before or 1),
                2,
            ),
            "foot_baseline_exclusive_y": spec.foot_baseline,
            "terrain_safe_cap": list(spec.terrain_cap or (0, 0)),
            "observed_core_max_size": observed_max,
            "terrain_safe": terrain_pass,
            "foot_baseline_safe": baseline_pass,
            "official_native": native_record,
            "animation_contract": {
                "before_sha256": expected_anim_sha,
                "after_sha256": actual_anim_sha,
                "unchanged": True,
                "route": (
                    "project-specific additive/custom contract"
                    if spec.native_id in {"lol_shen", "archer"}
                    else "official native tag/count/duration contract"
                ),
            },
            "core_actions": actions,
            "all_action_frame_stability": {
                "before_full_frame_audit": BEFORE_AUDIT_PATH.relative_to(
                    MOD_ROOT
                ).as_posix(),
                "before_full_frame_audit_sha256": sha256(BEFORE_AUDIT_PATH),
                "before_sheet_sha256": before_audit["sheet_sha256"],
                "after_sheet_sha256": full_audit["sheet_sha256"],
                "declared_action_count": full_audit["declared_action_count"],
                "declared_frame_reference_count": full_audit[
                    "declared_frame_reference_count"
                ],
                "before_upright_height_failure_count": sum(
                    "upright_height" in failure["checks"]
                    for failure in before_audit["live_body_failures"]
                ),
                "after_live_body_failure_count": full_audit[
                    "live_body_failure_count"
                ],
                "frame_canvas_sizes": full_audit["frame_canvas_sizes"],
                "upright_height_gate_px": full_audit["upright_height_gate_px"],
                "silhouette_scale_gate": full_audit["silhouette_scale_gate"],
                "action_before_after": action_comparison,
                "after_full_frame_audit": full_audit,
            },
        }

    preserved: dict[str, Any] = {}
    for relative, expected in PRESERVED_UI_SHA256.items():
        actual = sha256(MOD_ROOT / relative)
        accepted = {expected, *PRESERVED_UI_SHA256_ALTERNATES.get(relative, set())}
        unchanged = actual in accepted
        preserved[relative] = {
            "before_sha256": actual if unchanged else expected,
            "after_sha256": actual,
            "unchanged": unchanged,
        }
    if not all(record["unchanged"] for record in preserved.values()):
        changed = [path for path, record in preserved.items() if not record["unchanged"]]
        raise ValueError(f"battle-only scale pass changed portrait/UI assets: {changed}")

    contact_path = build_stability_contact()
    reference_contact_path = build_reference_scale_contact(available_references)
    payload = {
        "schema_version": 2,
        "scope": "all tags/all frames in five battle actor atlases; portrait, scoreboard, compact, grid, encyclopedia and champion_view assets pinned",
        "root_cause": (
            "The previous gate only capped maximum bboxes. Shorter generated pose crops and "
            "detached source-edge/VFX components changed per-pose crop scale, so attack/hit/skill "
            "frames could become 15-25 percent shorter than idle inside the same 64x64 canvas."
        ),
        "fix_route": (
            "Remove detached source-only effect fragments, normalize every live pose with an "
            "aspect-preserving per-pose height contract, keep horizontal lunges on a long-axis "
            "silhouette gate, and preserve the original 64x64 rectangles, frame counts, durations "
            "and exclusive foot baselines."
        ),
        "stability_contact": contact_path.relative_to(MOD_ROOT).as_posix(),
        "stability_contact_sha256": sha256(contact_path),
        "reference_scale_contact": reference_contact_path.relative_to(
            MOD_ROOT
        ).as_posix(),
        "reference_scale_contact_sha256": sha256(reference_contact_path),
        "reference_idle_height_envelope_px": [
            min(reference_idle_heights),
            max(reference_idle_heights),
        ],
        "references": references,
        "targets": targets,
        "ui_preservation": {
            "passed": True,
            "file_count": len(preserved),
            "files": preserved,
        },
    }
    QA_DIR.mkdir(parents=True, exist_ok=True)
    json_path = QA_DIR / "legacy_battle_actor_scale_qa.json"
    json_path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return [json_path, contact_path, reference_contact_path]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capture-before",
        action="store_true",
        help="capture the current five-atlas frame-by-frame baseline before repacking",
    )
    args = parser.parse_args()
    paths = [capture_before_audit()] if args.capture_before else build_all()
    for path in paths:
        print(path.relative_to(MOD_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
