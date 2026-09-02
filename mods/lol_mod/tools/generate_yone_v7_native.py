from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, deque
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import build_yone


MOD_ROOT = Path(__file__).resolve().parents[1]
IMAGEGEN_ROOT = MOD_ROOT / "source/imagegen"
MOTION_SOURCE = IMAGEGEN_ROOT / "yone_v7_motion_contact.png"
ATTACK_SOURCE = IMAGEGEN_ROOT / "yone_v7_attack_q_contact.png"
W_SOURCE = IMAGEGEN_ROOT / "yone_v7_w_contact.png"
ULT_SOURCE = IMAGEGEN_ROOT / "yone_v7_ult_contact.png"

V7_ROOT = MOD_ROOT / "source/native/yone_v7"
FRAME_ROOT = V7_ROOT / "frames"
PREVIEW_ROOT = V7_ROOT / "preview"
FRAME_MANIFEST = V7_ROOT / "frames.json"
PALETTE_PATH = V7_ROOT / "palette.json"
QA_PATH = V7_ROOT / "generation_qa.json"
BODY_PREVIEW = PREVIEW_ROOT / "yone_v7_actor_card.png"
CONTACT_PREVIEW = PREVIEW_ROOT / "yone_v7_native_contact.png"
MOTION_ATTACK_PREVIEW = MOD_ROOT / "qa/yone_motion_attack_qa.png"

EXPECTED_SOURCE_SHA256 = {
    "motion": "548fd4b85265b6a00ca0f6c7e1c2368a77af261f2ac9a7002f68f63a86b9349b",
    "attack_q": "e919e5629c5a56c0a9aaed220ce5b001449b31d70abe43523c5b2086aad29e4d",
    "w": "2ff4d7ec7284071f66296acb1982b1a282a01f1d15237412db4f31b5d366b57b",
    "ult": "c820d8fcf6cf56e82f4eaa896d2f71bb602a2914f53313fc0db03b88748ad4a4",
}
SOURCE_PATHS = {
    "motion": MOTION_SOURCE,
    "attack_q": ATTACK_SOURCE,
    "w": W_SOURCE,
    "ult": ULT_SOURCE,
}

# The V7 palette is derived deterministically from the four hash-locked source
# sheets.  Eight body anchors preserve the face, eyes, mask and trim.  Six
# additional colors are weapon-exclusive: body quantization is never allowed
# to emit them, so clothing, the demon mask and the sash cannot satisfy the
# dual-sword contract.
PALETTE_ANCHORS: tuple[tuple[int, int, int, int], ...] = (
    (5, 7, 14, 255),
    (18, 22, 38, 255),
    (92, 48, 29, 255),
    (218, 132, 73, 255),
    (248, 190, 122, 255),
    (191, 27, 22, 255),
    (224, 157, 35, 255),
    (224, 238, 246, 255),
)
WEAPON_COLORS: dict[str, tuple[tuple[int, int, int, int], ...]] = {
    "steel": (
        (27, 49, 69, 255),
        (101, 174, 216, 255),
        (238, 250, 255, 255),
    ),
    "azakana": (
        (72, 9, 22, 255),
        (205, 27, 40, 255),
        (255, 98, 72, 255),
    ),
}
WEAPON_ROLE_ROWS: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("steel_dark", WEAPON_COLORS["steel"][0]),
    ("steel_mid", WEAPON_COLORS["steel"][1]),
    ("steel_highlight", WEAPON_COLORS["steel"][2]),
    ("azakana_dark", WEAPON_COLORS["azakana"][0]),
    ("azakana_red", WEAPON_COLORS["azakana"][1]),
    ("azakana_highlight", WEAPON_COLORS["azakana"][2]),
)
WEAPON_COLOR_SET = {color for _role, color in WEAPON_ROLE_ROWS}
PALETTE: tuple[tuple[int, int, int, int], ...] = PALETTE_ANCHORS
BODY_PALETTE: tuple[tuple[int, int, int, int], ...] = PALETTE_ANCHORS
PALETTE_ROWS: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("transparent", (0, 0, 0, 0)),
    *((f"anchor_{index:02d}", color) for index, color in enumerate(PALETTE_ANCHORS)),
    *WEAPON_ROLE_ROWS,
)
WEAPON_PALETTE_ROLES = {
    "steel": {
        "dark": ["steel_dark"],
        "mid": ["steel_mid"],
        "highlight": ["steel_highlight"],
    },
    "azakana": {
        "dark": ["azakana_dark"],
        "red": ["azakana_red"],
        "highlight": ["azakana_highlight"],
    },
}
ALLOWED_COLORS = {color for _role, color in PALETTE_ROWS}
SKIN_COLORS: set[tuple[int, int, int, int]] = set()
EYE_COLORS: set[tuple[int, int, int, int]] = set()
MASK_COLORS: set[tuple[int, int, int, int]] = set()

# Cell indices are zero-based.  The action map is intentionally explicit so
# no later contact-sheet reorder can silently change the model or motion.
ACTION_SOURCES: dict[str, tuple[tuple[str, int | None], ...]] = {
    "skill2": (("w", 5),),
    "hit": (("motion", 4),),
    # A complete steel-sword basic attack assembled only from the accepted
    # Yone model: upright guard, weight transfer, steel extension, crossed
    # contact, counter-rotation and recovery.  Cells 12..17 are deliberately
    # excluded because that entire source row is one near-identical low thrust
    # and therefore reads as a frozen actor with a blade overlay at native 1x.
    "attack": tuple(
        ("attack_q", index) for index in (0, 1, 3, 10, 11, 5)
    ),
    # The source's intermediate red-sword-only cells 7..9 hide the steel
    # blade, so use six distinct approved dual-sword poses for a readable
    # ready -> red extension -> torso turn -> crossed follow-through -> recover
    # sequence without inventing or overlaying a second weapon.
    "attack_azakana": tuple(
        ("attack_q", index) for index in (0, 1, 2, 10, 6, 5)
    ),
    "skill2_dash": (("attack_q", 22),),
    # Keep the two frames immediately before the real tick-35 rush at full
    # actor scale. The source ult cells 8/9 are dominated by their long blade
    # spans; fitting those complete cells into the native boxes shrank Yone's
    # body to roughly half size exactly where the launch should read. Reuse
    # two accepted, dual-sword V7 poses instead: a compact crossed crouch for
    # compression, then the authored forward dash for take-off.
    "ult": (
        ("ult", 0),
        ("ult", 2),
        ("ult", 5),
        ("ult", 6),
        ("ult", 7),
        ("attack_q", 10),
        ("attack_q", 22),
        ("ult", 10),
        ("ult", 11),
        ("ult", 12),
        ("ult", 13),
        ("ult", 14),
        ("ult", 2),
    ),
    # Eight derived upright guard/recovery poses are assembled below as one
    # coherent gait.  The source sequence deliberately avoids attack-contact
    # frames so the hands and both blades stay continuous through the loop.
    "run": tuple(("run_pose", index) for index in range(8)),
    # The first two official W boxes are only 31px wide. Start from the two
    # compact dual-sword poses, then use the wider boxes for the heavy sweep.
    "skill2_attack": tuple(("w", index) for index in (5, 0, 1, 2, 3)),
    "idle": tuple(("motion", index) for index in (0, 1, 3, 1)),
    "dead": tuple(("motion", index) for index in range(13, 20))
    + (("motion", 19),),
    "skill": tuple(("attack_q", index) for index in (12, 14, 15, 16, 15, 14, 12)),
    # Q3 stays a distinct lowered/dashing route while the human steel blade
    # remains forward and the red sword stays visible as a trailing counterweight.
    "skill_q3": tuple(("attack_q", index) for index in (18, 21, 22, 23, 22, 21, 18)),
}

# One native eight-frame gait cycle. Negative values close/cross the two feet,
# positive values open them into the opposite contact pose, and the zero
# phases are the authored passing steps. The sources form one restrained guard
# rhythm: one arm leads, both recover, then the opposite guard shifts back.
# No crouched motion-sheet sprint or attack-contact frame is reused.
RUN_STRIDE_PHASES: tuple[float, ...] = (
    1.0,
    0.65,
    0.0,
    -0.65,
    -1.0,
    -0.65,
    0.0,
    0.65,
)
RUN_POSE_SOURCES: tuple[tuple[str, int], ...] = (
    ("attack_q", 0),
    ("attack_q", 0),
    ("attack_q", 5),
    ("attack_q", 5),
    ("attack_q", 11),
    ("attack_q", 5),
    ("attack_q", 5),
    ("attack_q", 0),
)
RUN_PASSING_LEG_SIDES: tuple[int, ...] = (1, 1, 1, 1, -1, -1, -1, -1)
# Palette compatibility only: 0.12.8 sampled these eight derived guard frames
# when creating the shared 48-color body palette. Replaying that sampling set
# prevents an animation-only run change from recoloring every unrelated frame.
PALETTE_COMPAT_STRIDE_PHASES: tuple[float, ...] = (
    -1.0, -0.48, 0.34, 0.86, 1.0, 0.48, -0.34, -0.86
)
RUN_ATTACK_POSE_PHASES: dict[str, tuple[str, ...]] = {
    "attack": ("windup", "windup", "contact", "contact", "recovery", "recovery"),
    "attack_azakana": (
        "windup",
        "windup",
        "contact",
        "contact",
        "recovery",
        "recovery",
    ),
}

# Alpha geometry measured from the installed SilverBear Workshop package
# (item 3774304166).  This is a timing/pivot/pose-structure reference only;
# those source pixels are never opened by the build and never copied into V7.
WORKSHOP_YONE_MOTION_MEASUREMENTS: dict[str, Any] = {
    "workshop_item": "3774304166",
    "usage": "measurement-only; zero reference pixels copied",
    "run": {
        "frame_count": 5,
        "durations_seconds": [0.1] * 5,
        "ground_offset_from_rect_center_px": [9.5, 9.0, 9.5, 10.0, 9.5],
        "ground_offset_range_px": 1.0,
        "upper_minus_mid_centroid_x_px": [-0.67, -1.06, 0.34, 0.06, -1.74],
    },
    "attack": {
        "frame_count": 5,
        "durations_seconds": [0.1] * 5,
        "alpha_bottom_margin_px": [20] * 5,
        "upper_minus_mid_centroid_x_px": [-2.97, -4.86, 0.07, 1.2, -1.86],
        "pose_structure": ["windup", "body_turn", "contact", "follow_through", "recovery"],
    },
}

X_SHIFTS: dict[str, tuple[int, ...]] = {
    "skill2": (0,),
    "hit": (-1,),
    "attack": (-1, 0, 1, 1, 0, -1),
    "attack_azakana": (-1, 0, 1, 1, 0, -1),
    "skill2_dash": (0,),
    "ult": (-1, 0, 1, 1, 1, 0, -1, -1, 0, 1, 1, 0, -1),
    # A stable torso/weapon pivot is more important than generic whole-actor
    # sway here.  The lower-body compositor already supplies locomotion.
    "run": (0, 0, 0, 0, 0, 0, 0, 0),
    "skill2_attack": (-1, 0, 1, 0, -1),
    "idle": (0, 0, 1, 0),
    "dead": (-1, 0, 1, 1, 0, -1, 0, 1),
    "skill": (-1, 0, 1, 1, 0, -1, 0),
    "skill_q3": (-1, 0, 1, 1, 0, -1, 0),
}
DEAD_TARGET_HEIGHTS = (34, 28, 24, 12, 12, 12, 12, 12)
DEAD_BOTTOM_MARGINS = (6, 6, 5, 4, 4, 4, 4, 4)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pixel_sha256(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


def pixels(image: Image.Image) -> Any:
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter is not None else image.getdata()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def save_png(path: Path, image: Image.Image) -> None:
    if image.mode != "RGBA":
        raise ValueError(f"V7 PNG must be RGBA: {path} {image.mode}")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("empty V7 image")
    return bbox


def keyed(source: Image.Image) -> Image.Image:
    """Clear the saturated-magenta field and harden all retained alpha."""

    rgba = source.convert("RGBA")
    result = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    output_pixels = result.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = source_pixels[x, y]
            is_magenta = (
                red > 155
                and blue > 115
                and green < 165
                and red - green > 55
                and blue - green > 35
            )
            if alpha < 24 or is_magenta:
                continue
            output_pixels[x, y] = (red, green, blue, 255)
    return result


def _material_components(image: Image.Image) -> list[set[tuple[int, int]]]:
    alpha = image.getchannel("A")
    remaining = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y)) != 0
    }
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        queue: deque[tuple[int, int]] = deque((start,))
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    point = (x + dx, y + dy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        components.append(component)
    if not components:
        raise ValueError("source has no actor component after chroma key")
    components.sort(key=len, reverse=True)
    return components


def _render_components(
    image: Image.Image, components: list[set[tuple[int, int]]]
) -> Image.Image:
    output = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_pixels = image.load()
    output_pixels = output.load()
    for component in components:
        for x, y in component:
            output_pixels[x, y] = source_pixels[x, y]
    return output


def _clean_actor_crop(raw_crop: Image.Image, *, preserve_detached: bool) -> Image.Image:
    """Return the actor representation used for body compositing.

    Weapon geometry is recovered separately from ``raw_crop``.  For live
    frames, keeping only the dominant body component prevents detached blade or
    trail fragments from surviving underneath the authoritative native weapon
    repaint.  Death poses intentionally contain separated dropped swords, so
    they retain only large authored components via an explicit exception.
    """

    components = _material_components(raw_crop)
    if preserve_detached:
        minimum = max(64, round(len(components[0]) * 0.05))
        retained = [component for component in components if len(component) >= minimum]
        if not 1 <= len(retained) <= 3:
            raise ValueError(
                "Yone death source detached-component contract changed: "
                f"{[len(component) for component in retained]}"
            )
    else:
        retained = components[:1]

    cleaned = _render_components(raw_crop, retained)
    cleaned_components = _material_components(cleaned)
    if preserve_detached:
        if len(cleaned_components) != len(retained):
            raise ValueError("Yone death component cleanup changed")
    elif len(cleaned_components) != 1:
        raise ValueError("Yone live actor cleanup retained detached source fragments")
    return cleaned


def split_cell_pair(
    sheet: Image.Image,
    columns: int,
    rows: int,
    index: int,
    *,
    preserve_detached: bool = False,
) -> tuple[Image.Image, Image.Image]:
    """Return aligned ``(actor_crop, raw_keyed_crop)`` representations."""

    if not 0 <= index < columns * rows:
        raise ValueError(f"cell index {index} outside {columns}x{rows}")
    row, column = divmod(index, columns)
    left = round(column * sheet.width / columns)
    right = round((column + 1) * sheet.width / columns)
    top = round(row * sheet.height / rows)
    bottom = round((row + 1) * sheet.height / rows)
    keyed_cell = keyed(sheet.crop((left, top, right, bottom)))
    crop_box = alpha_bbox(keyed_cell)
    raw_crop = keyed_cell.crop(crop_box)
    actor_crop = _clean_actor_crop(raw_crop, preserve_detached=preserve_detached)
    if actor_crop.size != raw_crop.size:
        raise ValueError("Yone actor/raw source crops lost coordinate alignment")
    return actor_crop, raw_crop


def split_cell(sheet: Image.Image, columns: int, rows: int, index: int) -> Image.Image:
    actor_crop, _raw_crop = split_cell_pair(sheet, columns, rows, index)
    return actor_crop


def _recompose_stride_pair(
    actor: Image.Image,
    raw_weapon_source: Image.Image,
    frame_index: int,
    *,
    stride_phases: tuple[float, ...] = RUN_STRIDE_PHASES,
    stride_ratio: float = 0.14,
    neutral_inset_ratio: float = 0.0,
    torso_sway_phases: tuple[float, ...] | None = None,
    drop_ratio: float = 0.045,
    lift_ratio: float = 0.035,
    torso_sway_ratio: float = 0.04,
    articulated_cycle: bool = False,
) -> tuple[Image.Image, Image.Image]:
    """Articulate two source leg identities without repainting the actor.

    Each frame starts from a distinct accepted V7 pose, so the head, hair,
    shoulders, hands and two attached swords retain their authored motion.
    This deterministic source-space pass only strengthens the existing
    lower-body step by moving the two hip-connected halves in opposite x
    directions and lifting the passing leg. No Workshop pixel and no newly
    painted limb enters the result.

    ``raw_weapon_source`` receives identical canvas padding/cropping but is not
    deformed. Its hand-to-tip vectors therefore remain authored and aligned
    with that frame's moving upper body, while the cleaned actor supplies the
    strengthened step. Native weapon proof is recovered from the raw sheet
    separately and never becomes a duplicated blade silhouette.
    """

    if actor.size != raw_weapon_source.size:
        raise ValueError("Yone articulated run actor/raw pair lost source alignment")
    if not 0 <= frame_index < len(stride_phases):
        raise ValueError(f"invalid Yone run frame index: {frame_index}")

    rgba = actor.convert("RGBA")
    raw_rgba = raw_weapon_source.convert("RGBA")
    left, top, right, bottom = alpha_bbox(rgba)
    body_height = bottom - top
    pelvis_x = core_center_x(rgba)
    hip_y = top + round(body_height * 0.57)
    phase = stride_phases[frame_index]

    # Source pixels are roughly five times native size.  These restrained
    # amplitudes become a visible 3-4px step at 1x without changing the native
    # action rectangle or touching the one-pixel transparent frame border.
    maximum_stride = max(8, round(body_height * stride_ratio))
    neutral_inset = round(maximum_stride * neutral_inset_ratio)
    maximum_drop = max(2, round(body_height * drop_ratio))
    maximum_lift = max(2, round(body_height * lift_ratio))
    maximum_torso_sway = max(2, round(body_height * torso_sway_ratio))
    leg_radius = max(16, round(body_height * 0.24))
    pad_x = round(
        maximum_stride
        * (max(abs(value) for value in stride_phases) + neutral_inset_ratio)
    ) + maximum_torso_sway + 3
    pad_top = 2
    pad_bottom = maximum_drop + 3
    canvas_size = (
        rgba.width + pad_x * 2,
        rgba.height + pad_top + pad_bottom,
    )
    recomposed = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    aligned_raw = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    raw_source_pixels = raw_rgba.load()
    target_pixels = recomposed.load()
    raw_target_pixels = aligned_raw.load()
    torso_phase = (
        torso_sway_phases[frame_index]
        if torso_sway_phases is not None
        else 0.0
    )

    for y in range(raw_rgba.height):
        upper_progress = min(
            1.0, max(0.0, (hip_y - y) / max(1, hip_y - top))
        )
        torso_shift = round(torso_phase * maximum_torso_sway * upper_progress)
        for x in range(raw_rgba.width):
            color = raw_source_pixels[x, y]
            if color[3] == 0:
                continue
            raw_target_pixels[x + pad_x + torso_shift, y + pad_top] = color

    # The leg crossing nearest the centre is drawn last so the advancing foot
    # reads in front at the two overlap phases, like the measured reference
    # gait, while still retaining both separated boot clusters at native 1x.
    x_order = tuple(range(rgba.width))
    if phase < 0:
        x_order = tuple(reversed(x_order))
    for y in range(rgba.height):
        for x in x_order:
            color = source_pixels[x, y]
            if color[3] == 0:
                continue
            upper_progress = min(
                1.0, max(0.0, (hip_y - y) / max(1, hip_y - top))
            )
            torso_shift = round(torso_phase * maximum_torso_sway * upper_progress)
            target_x = x + pad_x + torso_shift
            target_y = y + pad_top
            inside_leg_core = (
                y >= hip_y
                and abs(x - pelvis_x) <= leg_radius
                and not _source_weapon_candidate(color, "steel")
                and not _source_weapon_candidate(color, "azakana")
            )
            if inside_leg_core:
                progress = min(1.0, (y - hip_y) / max(1, bottom - hip_y))
                leg_side = -1 if x < pelvis_x else 1
                # A walking cycle has two wide contact poses (phase +/-1)
                # and two narrow passing poses (phase 0).  Using the signed
                # phase directly made only one half of the cycle open while
                # the other half collapsed past centre.  Keep the two source
                # leg identities, open them symmetrically at both contacts,
                # then alternate their draw/lift order from the phase sign so
                # a different leg visibly passes in front every half-cycle.
                if articulated_cycle:
                    phase_magnitude = abs(phase)
                    stride_position = (
                        phase_magnitude * maximum_stride
                        - (1.0 - phase_magnitude) * neutral_inset
                    )
                else:
                    # Retain the historical palette-sampling geometry.  The
                    # generated run passes opt into the symmetric contact
                    # cycle below, but changing this compatibility route would
                    # re-quantize every unrelated Yone action.
                    stride_position = phase * maximum_stride - neutral_inset
                target_x += round(leg_side * stride_position * progress)
                target_y += round(maximum_drop * progress)
                # The two zero-phase frames are different anatomical passes:
                # right leg in front during the first half-cycle, left leg in
                # front during the second.  Basing this only on ``phase < 0``
                # selected the same leg at both exact zero crossings.
                passing_side = (
                    RUN_PASSING_LEG_SIDES[frame_index]
                    if articulated_cycle
                    else (-1 if phase < 0 else 1)
                )
                if leg_side == passing_side:
                    passing_lift = max(0.0, 1.0 - abs(phase)) * maximum_lift
                    target_y -= round(passing_lift * progress)

            if not (0 <= target_x < recomposed.width and 0 <= target_y < recomposed.height):
                raise ValueError("Yone crossover stride escaped its padded canvas")
            target_pixels[target_x, target_y] = color
            # Vertical lengthening can skip a source row.  Reusing the same
            # approved pixel once fills that sub-native gap; hard-alpha and
            # palette validation below still prove that no new color appeared.
            if inside_leg_core and target_y > 0:
                if target_pixels[target_x, target_y - 1][3] == 0:
                    target_pixels[target_x, target_y - 1] = color

    actor_box = recomposed.getchannel("A").getbbox()
    raw_box = aligned_raw.getchannel("A").getbbox()
    if actor_box is None or raw_box is None:
        raise ValueError("Yone articulated stride removed actor or weapon source")
    union = (
        min(actor_box[0], raw_box[0]),
        min(actor_box[1], raw_box[1]),
        max(actor_box[2], raw_box[2]),
        max(actor_box[3], raw_box[3]),
    )
    actor_result = recomposed.crop(union)
    raw_result = aligned_raw.crop(union)
    if actor_result.size != raw_result.size:
        raise ValueError("Yone articulated stride crop lost source alignment")
    return actor_result, raw_result


def recompose_run_articulated_pair(
    actor: Image.Image,
    raw_weapon_source: Image.Image,
    frame_index: int,
) -> tuple[Image.Image, Image.Image]:
    """Build a smooth upright cycle from compatible accepted guard poses.

    The upper-body guard rhythm moves both sword hands without inserting a
    contact pose. The lower compositor keeps the original left/right pixel
    groups as identities, closes them at frames 2/6 and alternates which leg
    renders in front between the two passing steps. Keep source-space offsets
    modest: the previous 0.18/1.0 pass over-separated the legs and visibly
    deformed the tiny native actor during the crossover.
    """

    return _recompose_stride_pair(
        actor,
        raw_weapon_source,
        frame_index,
        stride_phases=RUN_STRIDE_PHASES,
        stride_ratio=0.105,
        neutral_inset_ratio=0.35,
        torso_sway_phases=(0.0, 0.3, 0.5, 0.3, 0.0, -0.3, -0.5, -0.3),
        drop_ratio=0.022,
        lift_ratio=0.018,
        torso_sway_ratio=0.025,
        articulated_cycle=True,
    )


def _source_weapon_candidate(
    color: tuple[int, int, int, int], weapon: str
) -> bool:
    """Recognize only the authored blade highlight used to recover geometry.

    These colors are not the final proof.  They are used once, on four
    hash-locked ImageGen sheets, to locate the long thin source component.
    Final proof comes from the weapon-exclusive colors painted from the chosen
    component after the exact native transform.
    """

    red, green, blue, alpha = color
    if alpha != 255:
        return False
    if weapon == "steel":
        return (
            blue >= 128
            and green >= 112
            and blue >= red - 12
            and green >= red - 32
            and max(red, green, blue) - min(red, green, blue) <= 150
        )
    if weapon == "azakana":
        return (
            red >= 96
            and red - green >= 44
            and red - blue >= 32
            and green <= 132
        )
    raise ValueError(f"unknown V7 weapon: {weapon}")


def _point_components(points: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(points)
    result: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        queue = deque((start,))
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    point = (x + dx, y + dy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        result.append(component)
    return result


def _principal_endpoints(
    component: set[tuple[int, int]],
) -> tuple[tuple[int, int], tuple[int, int], float, float]:
    """Return stable PCA endpoints plus axial span and perpendicular width."""

    mean_x = sum(x for x, _y in component) / len(component)
    mean_y = sum(y for _x, y in component) / len(component)
    cov_xx = sum((x - mean_x) ** 2 for x, _y in component) / len(component)
    cov_yy = sum((y - mean_y) ** 2 for _x, y in component) / len(component)
    cov_xy = sum(
        (x - mean_x) * (y - mean_y) for x, y in component
    ) / len(component)
    angle = 0.5 * math.atan2(2.0 * cov_xy, cov_xx - cov_yy)
    axis_x = math.cos(angle)
    axis_y = math.sin(angle)
    normal_x = -axis_y
    normal_y = axis_x

    def axial(point: tuple[int, int]) -> float:
        return (point[0] - mean_x) * axis_x + (point[1] - mean_y) * axis_y

    def normal(point: tuple[int, int]) -> float:
        return (point[0] - mean_x) * normal_x + (point[1] - mean_y) * normal_y

    first = min(component, key=axial)
    last = max(component, key=axial)
    axial_values = [axial(point) for point in component]
    normal_values = [normal(point) for point in component]
    return (
        first,
        last,
        max(axial_values) - min(axial_values),
        max(normal_values) - min(normal_values),
    )


def extract_source_weapon_trace(
    subject: Image.Image, weapon: str
) -> dict[str, Any]:
    """Locate one real elongated blade component in a hash-locked source cell."""

    candidates = {
        (x, y)
        for y in range(subject.height)
        for x in range(subject.width)
        if _source_weapon_candidate(subject.getpixel((x, y)), weapon)
    }
    components = _point_components(candidates)
    minimum_span = max(8.0, subject.height * (0.10 if weapon == "azakana" else 0.12))
    ranked: list[tuple[float, set[tuple[int, int]], tuple[int, int], tuple[int, int], float, float]] = []
    body_center = (core_center_x(subject), subject.height * 0.62)
    for component in components:
        if len(component) < 4:
            continue
        first, last, span, thickness = _principal_endpoints(component)
        if span < minimum_span:
            continue
        elongation = span / max(1.0, thickness)
        if elongation < 1.12:
            continue
        endpoint_reach = max(
            math.dist(first, body_center), math.dist(last, body_center)
        ) / max(1.0, subject.height)
        score = span * (1.0 + min(8.0, elongation)) * (1.0 + endpoint_reach * 0.25)
        ranked.append((score, component, first, last, span, thickness))
    if not ranked:
        raise ValueError(
            f"V7 source {subject.size} has no elongated {weapon} blade component"
        )
    _score, component, first, last, span, thickness = max(ranked, key=lambda row: row[0])
    if math.dist(first, body_center) <= math.dist(last, body_center):
        hand, tip = first, last
    else:
        hand, tip = last, first
    mask = Image.new("L", subject.size, 0)
    mask_pixels = mask.load()
    for point in component:
        mask_pixels[point] = 255
    left = min(x for x, _y in component)
    top = min(y for _x, y in component)
    right = max(x for x, _y in component) + 1
    bottom = max(y for _x, y in component) + 1
    return {
        "mask": mask,
        "hand": hand,
        "tip": tip,
        "source_bbox": [left, top, right - left, bottom - top],
        "source_pixel_count": len(component),
        "source_span": round(span, 3),
        "source_thickness": round(thickness, 3),
    }


def luminance(color: tuple[int, int, int, int]) -> float:
    return 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]


def is_skin_color(color: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = color
    return (
        alpha == 255
        and red >= 112
        and red - green >= 20
        and green - blue >= 12
        and blue * 4 >= green
        and blue <= 165
        and luminance(color) >= 82
    )


def is_eye_color(color: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = color
    return alpha == 255 and max(red, green, blue) <= 72 and luminance(color) <= 52


def is_mask_color(color: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = color
    return (
        alpha == 255
        and red >= 98
        and red - green >= 48
        and red - blue >= 28
        and green <= 112
    )


def install_source_palette(subjects: dict[tuple[str, int], Image.Image]) -> None:
    """Install one deterministic source-derived palette for every V7 frame."""

    global PALETTE, BODY_PALETTE, PALETTE_ROWS, ALLOWED_COLORS
    global SKIN_COLORS, EYE_COLORS, MASK_COLORS

    samples: list[tuple[int, int, int]] = []
    for key in sorted(subjects):
        subject = subjects[key]
        pixels = subject.load()
        # Sampling every fourth source pixel preserves the source distribution
        # while keeping median-cut deterministic and inexpensive.
        for y in range(0, subject.height, 4):
            for x in range(0, subject.width, 4):
                red, green, blue, alpha = pixels[x, y]
                if alpha == 255:
                    samples.append((red, green, blue))
    if len(samples) < 256:
        raise ValueError(f"too few V7 opaque source samples: {len(samples)}")

    width = 1024
    height = (len(samples) + width - 1) // width
    sample_image = Image.new("RGB", (width, height), samples[-1])
    sample_image.putdata(samples + [samples[-1]] * (width * height - len(samples)))
    quantized = sample_image.quantize(
        colors=34,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    raw_palette = quantized.getpalette() or []
    used_indices = sorted(index for _count, index in (quantized.getcolors() or []))
    derived = [
        (raw_palette[index * 3], raw_palette[index * 3 + 1], raw_palette[index * 3 + 2], 255)
        for index in used_indices
    ]
    opaque: list[tuple[int, int, int, int]] = []
    for color in (*PALETTE_ANCHORS, *derived):
        if color not in opaque and color not in WEAPON_COLOR_SET:
            opaque.append(color)
    body_opaque = opaque[:42]
    opaque = [*body_opaque, *(color for _role, color in WEAPON_ROLE_ROWS)]
    if not 22 <= len(opaque) <= 48:
        raise ValueError(f"unexpected V7 palette size: {len(opaque)}")

    PALETTE = tuple(opaque)
    BODY_PALETTE = tuple(body_opaque)
    semantic_counts = {"skin": 0, "mask": 0, "source": 0}
    rows: list[tuple[str, tuple[int, int, int, int]]] = [
        ("transparent", (0, 0, 0, 0))
    ]
    for index, color in enumerate(BODY_PALETTE):
        if color == PALETTE_ANCHORS[0]:
            role = "eye_outline"
        elif is_skin_color(color):
            role = f"skin_{semantic_counts['skin']:02d}"
            semantic_counts["skin"] += 1
        elif is_mask_color(color):
            role = f"mask_{semantic_counts['mask']:02d}"
            semantic_counts["mask"] += 1
        else:
            role = f"source_{semantic_counts['source']:02d}"
            semantic_counts["source"] += 1
        rows.append((role, color))
    rows.extend(WEAPON_ROLE_ROWS)
    PALETTE_ROWS = tuple(rows)
    ALLOWED_COLORS = {color for _role, color in PALETTE_ROWS}
    SKIN_COLORS = {color for color in BODY_PALETTE if is_skin_color(color)}
    EYE_COLORS = {color for color in BODY_PALETTE if is_eye_color(color)}
    MASK_COLORS = {color for color in BODY_PALETTE if is_mask_color(color)}
    if len(SKIN_COLORS) < 3 or not EYE_COLORS or len(MASK_COLORS) < 2:
        raise ValueError(
            "V7 semantic palette coverage failed: "
            f"skin={len(SKIN_COLORS)} eye={len(EYE_COLORS)} mask={len(MASK_COLORS)}"
        )


def palette_finish(image: Image.Image) -> Image.Image:
    result = image.convert("RGBA")
    pixels = result.load()
    for y in range(result.height):
        for x in range(result.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            pixels[x, y] = min(
                BODY_PALETTE,
                key=lambda color: (
                    2 * (red - color[0]) ** 2
                    + 3 * (green - color[1]) ** 2
                    + (blue - color[2]) ** 2
                ),
            )
    return result


def core_center_x(subject: Image.Image) -> float:
    """Estimate pelvis/root x without letting long sword tips steer packing."""

    bbox = alpha_bbox(subject)
    top = bbox[1] + round((bbox[3] - bbox[1]) * 0.38)
    bottom = bbox[1] + round((bbox[3] - bbox[1]) * 0.88)
    alpha = subject.getchannel("A")
    alpha_pixels = alpha.load()
    xs = [
        x
        for y in range(top, max(top + 1, bottom))
        for x in range(bbox[0], bbox[2])
        if alpha_pixels[x, y]
    ]
    if not xs:
        return (bbox[0] + bbox[2] - 1) / 2
    xs.sort()
    middle = len(xs) // 2
    if len(xs) % 2:
        return float(xs[middle])
    return (xs[middle - 1] + xs[middle]) / 2


def remove_detached_native_specks(image: Image.Image) -> Image.Image:
    """Drop only 1-2px fragments created when a long source tip is clipped."""

    alpha = image.getchannel("A")
    remaining = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y))
    }
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        queue = deque((start,))
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    point = (x + dx, y + dy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        components.append(component)
    if not components:
        return image
    retained = [component for component in components if len(component) >= 8]
    if not retained:
        retained = [max(components, key=len)]
    cleaned = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_pixels = image.load()
    output_pixels = cleaned.load()
    for component in retained:
        for x, y in component:
            output_pixels[x, y] = source_pixels[x, y]
    return cleaned


def _clamp_inner(
    point: tuple[float, float],
    size: tuple[int, int],
    *,
    max_y: int | None = None,
) -> tuple[int, int]:
    width, height = size
    y_limit = height - 4 if max_y is None else min(height - 4, max_y)
    return (
        min(width - 4, max(3, round(point[0]))),
        min(y_limit, max(3, round(point[1]))),
    )


def _transform_weapon_mask(
    source_mask: Image.Image,
    *,
    resize_size: tuple[int, int],
    fitted_bbox: tuple[int, int, int, int],
    viewport: tuple[int, int, int, int],
    paste_xy: tuple[int, int],
    bottom_delta: int,
    frame_size: tuple[int, int],
) -> tuple[Image.Image, float]:
    """Apply the exact body resize/crop/paste transform to one semantic mask."""

    scaled = source_mask.resize(resize_size, Image.Resampling.BOX)
    scaled = scaled.point(lambda value: 255 if value >= 20 else 0)
    scaled = scaled.crop(fitted_bbox)
    before = sum(1 for value in pixels(scaled) if value)
    source_left, source_top, source_right, source_bottom = viewport
    visible = scaled.crop((source_left, source_top, source_right, source_bottom))
    output = Image.new("L", frame_size, 0)
    output.paste(
        visible,
        (
            paste_xy[0] + source_left,
            paste_xy[1] + source_top + bottom_delta,
        ),
    )
    after = sum(1 for value in pixels(output) if value)
    crop_ratio = 1.0 - after / max(1, before)
    return output, round(min(1.0, max(0.0, crop_ratio)), 4)


def _weapon_points(image: Image.Image, weapon: str) -> set[tuple[int, int]]:
    colors = set(WEAPON_COLORS[weapon])
    return {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if image.getpixel((x, y)) in colors
    }


def _component_at_anchor(
    points: set[tuple[int, int]], anchor: tuple[int, int]
) -> tuple[set[tuple[int, int]], tuple[int, int]]:
    if not points:
        raise ValueError("empty native weapon mask")
    snapped = min(points, key=lambda point: (math.dist(point, anchor), point[1], point[0]))
    remaining = set(points)
    remaining.remove(snapped)
    component = {snapped}
    queue = deque((snapped,))
    while queue:
        x, y = queue.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                point = (x + dx, y + dy)
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    queue.append(point)
    return component, snapped


def _resolve_weapon_geometry(
    image: Image.Image,
    weapon: str,
    projected_hand: tuple[int, int],
    projected_tip: tuple[int, int],
    crop_ratio: float,
) -> dict[str, Any]:
    points = _weapon_points(image, weapon)
    component, hand = _component_at_anchor(points, projected_hand)
    vector = (
        projected_tip[0] - projected_hand[0],
        projected_tip[1] - projected_hand[1],
    )
    if vector == (0, 0):
        vector = (1, 0)
    tip = max(
        component,
        key=lambda point: (
            (point[0] - hand[0]) * vector[0]
            + (point[1] - hand[1]) * vector[1],
            math.dist(point, hand),
        ),
    )
    left = min(x for x, _y in component)
    top = min(y for _x, y in component)
    right = max(x for x, _y in component) + 1
    bottom = max(y for _x, y in component) + 1
    return {
        f"{weapon}_blade_bbox": [left, top, right - left, bottom - top],
        f"{weapon}_hand_anchor": list(hand),
        f"{weapon}_tip": list(tip),
        f"{weapon}_span_px": round(math.dist(hand, tip), 3),
        f"{weapon}_connectedness": round(len(component) / len(points), 4),
        f"{weapon}_pixel_count": len(points),
        f"{weapon}_crop_ratio": crop_ratio,
        # The source vector may be shortened by the native viewport, but the
        # deterministic 1x cleanup always recreates a concrete pointed tip.
        f"{weapon}_source_tip_survived": tip in points,
    }


def _paint_native_weapon(
    image: Image.Image,
    weapon: str,
    _transformed_mask: Image.Image,
    hand: tuple[int, int],
    tip: tuple[int, int],
) -> None:
    """Rebuild one continuous blade at final 1x using exclusive colors."""

    dark, mid, highlight = WEAPON_COLORS[weapon]
    image_pixels = image.load()
    draw = ImageDraw.Draw(image)
    draw.line((hand, tip), fill=dark, width=3)
    draw.line((hand, tip), fill=mid, width=2)
    draw.line((hand, tip), fill=highlight, width=1)
    # A single dark cap reads as the hilt at native size and keeps the blade
    # anchored even when LANCZOS would otherwise leave a one-pixel gap.
    hx, hy = hand
    for dx, dy in ((0, 0), (-1, 0), (0, 1)):
        x, y = hx + dx, hy + dy
        if 0 < x < image.width - 1 and 0 < y < image.height - 1:
            image_pixels[x, y] = dark


def _project_source_point(
    point: tuple[int, int],
    *,
    subject_size: tuple[int, int],
    resize_size: tuple[int, int],
    fitted_bbox: tuple[int, int, int, int],
    paste_xy: tuple[int, int],
    bottom_delta: int,
) -> tuple[float, float]:
    scaled_x = (point[0] + 0.5) * resize_size[0] / subject_size[0] - 0.5
    scaled_y = (point[1] + 0.5) * resize_size[1] / subject_size[1] - 0.5
    return (
        scaled_x - fitted_bbox[0] + paste_xy[0],
        scaled_y - fitted_bbox[1] + paste_xy[1] + bottom_delta,
    )


def fit_pose(
    subject: Image.Image,
    frame_size: tuple[int, int],
    *,
    visible_height: int,
    bottom_margin: int,
    x_shift: int,
    weapon_traces: dict[str, dict[str, Any]],
    active_weapon: str,
) -> tuple[Image.Image, dict[str, Any], dict[str, Any]]:
    """Smoothly reduce one high-resolution pose into its native frame."""

    frame_width, frame_height = frame_size
    if visible_height + bottom_margin >= frame_height:
        visible_height = frame_height - bottom_margin - 1
    if visible_height < 1:
        raise ValueError((frame_size, visible_height, bottom_margin))

    original_core_x = core_center_x(subject)
    target_width = max(1, round(subject.width * visible_height / subject.height))
    # Clear chroma RGB before this single source-to-native resize, then use
    # LANCZOS so facial features survive instead of becoming blocky mosaics.
    fitted = subject.resize(
        (target_width, visible_height), Image.Resampling.LANCZOS
    )
    fitted.putalpha(
        fitted.getchannel("A").point(lambda value: 255 if value >= 96 else 0)
    )
    fitted = palette_finish(fitted)
    fitted_bbox = alpha_bbox(fitted)
    left_trim = fitted_bbox[0]
    fitted = fitted.crop(fitted_bbox)
    scaled_core_x = original_core_x * target_width / subject.width - left_trim

    desired_core_x = (frame_width - 1) / 2 + x_shift
    paste_x = round(desired_core_x - scaled_core_x)
    paste_y = frame_height - bottom_margin - fitted.height
    if paste_y < 1:
        raise ValueError(
            f"V7 pose {fitted.size} cannot fit {frame_size} at bottom {bottom_margin}"
        )

    # Clip weapons to the transparent one-pixel inner viewport.  Cropping is
    # performed after the one direct resize and cannot shrink the actor body.
    source_left = max(0, 1 - paste_x)
    source_right = min(fitted.width, frame_width - 1 - paste_x)
    source_top = max(0, 1 - paste_y)
    source_bottom = min(fitted.height, frame_height - 1 - paste_y)
    if source_right <= source_left or source_bottom <= source_top:
        raise ValueError("V7 pose lies outside its native frame")
    visible = fitted.crop((source_left, source_top, source_right, source_bottom))
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    output.alpha_composite(
        visible, (paste_x + source_left, paste_y + source_top)
    )
    output = remove_detached_native_specks(output)
    bbox = alpha_bbox(output)
    bottom_delta = (frame_height - bottom_margin) - bbox[3]
    if bottom_delta:
        anchored = Image.new("RGBA", frame_size, (0, 0, 0, 0))
        anchored.alpha_composite(output, (0, bottom_delta))
        output = anchored
        bbox = alpha_bbox(output)

    viewport = (source_left, source_top, source_right, source_bottom)
    transformed_masks: dict[str, Image.Image] = {}
    crop_ratios: dict[str, float] = {}
    projected: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}
    weapon_max_y = frame_height - bottom_margin - 2
    for weapon in ("steel", "azakana"):
        trace = weapon_traces[weapon]
        transformed_masks[weapon], crop_ratios[weapon] = _transform_weapon_mask(
            trace["mask"],
            resize_size=(target_width, visible_height),
            fitted_bbox=fitted_bbox,
            viewport=viewport,
            paste_xy=(paste_x, paste_y),
            bottom_delta=bottom_delta,
            frame_size=frame_size,
        )
        raw_hand = _project_source_point(
            trace["hand"],
            subject_size=subject.size,
            resize_size=(target_width, visible_height),
            fitted_bbox=fitted_bbox,
            paste_xy=(paste_x, paste_y),
            bottom_delta=bottom_delta,
        )
        raw_tip = _project_source_point(
            trace["tip"],
            subject_size=subject.size,
            resize_size=(target_width, visible_height),
            fitted_bbox=fitted_bbox,
            paste_xy=(paste_x, paste_y),
            bottom_delta=bottom_delta,
        )
        hand = _clamp_inner(raw_hand, frame_size, max_y=weapon_max_y)
        tip = _clamp_inner(raw_tip, frame_size, max_y=weapon_max_y)
        if math.dist(hand, tip) < 4.0:
            dx = raw_tip[0] - raw_hand[0]
            dy = raw_tip[1] - raw_hand[1]
            length = max(1.0, math.hypot(dx, dy))
            unit = (dx / length, dy / length)
            candidates = [
                (hand, tip),
                (
                    hand,
                    _clamp_inner(
                        (hand[0] + unit[0] * 6.0, hand[1] + unit[1] * 6.0),
                        frame_size,
                        max_y=weapon_max_y,
                    ),
                ),
                (
                    _clamp_inner(
                        (tip[0] - unit[0] * 6.0, tip[1] - unit[1] * 6.0),
                        frame_size,
                        max_y=weapon_max_y,
                    ),
                    tip,
                ),
            ]
            hand, tip = max(
                candidates,
                key=lambda pair: (
                    math.dist(pair[0], pair[1]),
                    -math.dist(pair[0], raw_hand),
                ),
            )
        projected[weapon] = (hand, tip)

    # At extreme native reductions two grips can quantize onto one pixel.
    # Keep their source directions but separate the red grip by one native
    # pixel so the two-hand contract remains physically testable.
    if projected["steel"][0] == projected["azakana"][0]:
        red_hand, red_tip = projected["azakana"]
        red_hand = _clamp_inner(
            (red_hand[0] + 1, red_hand[1]), frame_size, max_y=weapon_max_y
        )
        projected["azakana"] = (red_hand, red_tip)

    order = ["steel", "azakana"]
    if active_weapon in {"steel", "azakana"}:
        order.remove(active_weapon)
        order.append(active_weapon)
    for weapon in order:
        hand, tip = projected[weapon]
        _paint_native_weapon(output, weapon, transformed_masks[weapon], hand, tip)

    weapon_geometry: dict[str, Any] = {}
    for weapon in ("steel", "azakana"):
        hand, tip = projected[weapon]
        weapon_geometry.update(
            _resolve_weapon_geometry(
                output, weapon, hand, tip, crop_ratios[weapon]
            )
        )
    bbox = alpha_bbox(output)

    return output, {
        "source_subject_size": list(subject.size),
        "direct_resize_size": [target_width, visible_height],
        "pelvis_center_x": round(original_core_x, 3),
        "paste_xy": [paste_x, paste_y],
        "horizontal_crop": source_left > 0 or source_right < fitted.width,
        "cropped_source_columns": source_left + fitted.width - source_right,
        "horizontal_crop_ratio": round(
            (source_left + fitted.width - source_right) / max(1, fitted.width), 4
        ),
        "alpha_bbox": list(bbox),
        "source_weapon_traces": {
            weapon: {
                key: value
                for key, value in trace.items()
                if key != "mask"
            }
            for weapon, trace in weapon_traces.items()
        },
    }, weapon_geometry


def _components_for_colors(
    image: Image.Image,
    colors: set[tuple[int, int, int, int]],
    search_box: tuple[int, int, int, int],
) -> list[set[tuple[int, int]]]:
    left, top, right, bottom = search_box
    remaining = {
        (x, y)
        for y in range(max(0, top), min(image.height, bottom))
        for x in range(max(0, left), min(image.width, right))
        if image.getpixel((x, y)) in colors
    }
    result: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        queue = deque((start,))
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    point = (x + dx, y + dy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        result.append(component)
    return result


def detect_face(
    image: Image.Image,
) -> tuple[str, tuple[int, int, int, int] | None, list[tuple[int, int]]]:
    body = alpha_bbox(image)
    body_height = body[3] - body[1]
    search = (body[0], body[1], body[2], body[1] + round(body_height * 0.62))
    components = _components_for_colors(image, SKIN_COLORS, search)
    if not components:
        return "hidden", None, []
    component = max(
        components,
        key=lambda points: (
            len(points) * 8
            - min(y for _x, y in points) * 2
            + round(sum(x for x, _y in points) / len(points))
        ),
    )
    left = min(x for x, _y in component)
    top = min(y for _x, y in component)
    right = max(x for x, _y in component) + 1
    bottom = max(y for _x, y in component) + 1
    face = (left, top, right - left, bottom - top)
    if len(component) < 6 or face[2] < 3 or face[3] < 4:
        return "hidden", None, []

    eye_candidates: list[tuple[int, int]] = []
    for y in range(top, bottom):
        for x in range(left, right):
            if image.getpixel((x, y)) not in EYE_COLORS:
                continue
            adjacent_skin = any(
                0 <= x + dx < image.width
                and 0 <= y + dy < image.height
                and image.getpixel((x + dx, y + dy)) in SKIN_COLORS
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if dx or dy
            )
            if adjacent_skin:
                eye_candidates.append((x, y))
    pair: list[tuple[int, int]] = []
    for first in eye_candidates:
        for second in eye_candidates:
            if abs(first[0] - second[0]) >= 2:
                pair = [first, second]
                break
        if pair:
            break
    if len(component) >= 14 and face[2] >= 6 and face[3] >= 7 and pair:
        return "front", face, pair
    return "profile", face, pair[:1]


def annotations_for_frame(
    image: Image.Image, action: str, index: int
) -> tuple[list[int] | None, list[list[int]], list[int] | None, str]:
    """Describe only facial pixels that really survived final-scale packing."""

    _coarse_visibility, face, _coarse_eyes = detect_face(image)
    if face is None:
        if action == "idle":
            raise ValueError(f"idle[{index}] lost its warm face at native scale")
        return None, [], None, "hidden"
    fx, fy, fw, fh = face
    skin_points = {
        (x, y)
        for y in range(fy, fy + fh)
        for x in range(fx, fx + fw)
        if image.getpixel((x, y)) in SKIN_COLORS
    }
    interior_bottom = fy + max(2, (fh * 2) // 3)
    eye_candidates = [
        (x, y)
        for y in range(fy, min(fy + fh, interior_bottom + 1))
        for x in range(fx, fx + fw)
        if image.getpixel((x, y)) in EYE_COLORS
        and any(
            (x + dx, y + dy) in skin_points
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            if dx or dy
        )
    ]
    # Prefer a same-row pair in the middle of the face.  A single surviving
    # cue is recorded honestly as profile; no coordinate or color is injected.
    eye_candidates.sort(key=lambda point: (abs(point[1] - (fy + fh * 0.42)), point[0]))
    eyes: list[tuple[int, int]] = []
    if eye_candidates:
        eyes = [eye_candidates[0]]
        compatible = [
            point
            for point in eye_candidates[1:]
            if abs(point[0] - eyes[0][0]) >= 2
            and abs(point[1] - eyes[0][1]) <= 1
        ]
        if compatible:
            compatible.sort(key=lambda point: (abs(point[1] - eyes[0][1]), point[0]))
            eyes.append(compatible[0])

    if action == "idle" and not eyes:
        raise ValueError(f"idle[{index}] has no real dark eye cue beside warm skin")
    search = (
        max(0, fx - 14),
        max(0, fy - 8),
        min(image.width, fx + max(2, fw // 3)),
        min(image.height, fy + fh + 1),
    )
    mask_points = [
        (x, y)
        for y in range(search[1], search[3])
        for x in range(search[0], search[2])
        if image.getpixel((x, y)) in MASK_COLORS
    ]
    mask: tuple[int, int, int, int] | None = None
    if mask_points:
        mask = (
            min(x for x, _y in mask_points),
            min(y for _x, y in mask_points),
            max(x for x, _y in mask_points) - min(x for x, _y in mask_points) + 1,
            max(y for _x, y in mask_points) - min(y for _x, y in mask_points) + 1,
        )
    visibility = "front" if len(eyes) >= 2 else "profile"
    return (
        list(face),
        [list(point) for point in eyes],
        list(mask) if mask is not None else None,
        visibility,
    )


def foot_zones(image: Image.Image, action: str) -> list[list[int]]:
    if action in {"dead", "ult"}:
        return []
    left, _top, right, bottom = alpha_bbox(image)
    zone_top = max(image.height // 2, bottom - 4)
    return [[left, zone_top, right - left, bottom - zone_top]]


def frame_quality(image: Image.Image) -> dict[str, float | int]:
    bbox = alpha_bbox(image)
    opaque = [color for color in pixels(image) if color[3] == 255]
    if not opaque:
        raise ValueError("V7 quality audit received an empty frame")
    lumas = sorted(luminance(color) for color in opaque)
    low = lumas[len(lumas) // 10]
    high = lumas[min(len(lumas) - 1, (len(lumas) * 9) // 10)]
    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    core_top = bbox[1] + (bbox[3] - bbox[1]) // 4
    core_bottom = bbox[1] + ((bbox[3] - bbox[1]) * 3) // 4
    alpha = image.getchannel("A")
    row_widths: list[int] = []
    for y in range(core_top, max(core_top + 1, core_bottom)):
        xs = [x for x in range(bbox[0], bbox[2]) if alpha.getpixel((x, y))]
        if xs:
            row_widths.append(max(xs) - min(xs) + 1)
    row_widths.sort()
    return {
        "opaque_pixels": len(opaque),
        "bbox_width": bbox[2] - bbox[0],
        "bbox_height": bbox[3] - bbox[1],
        "core_width_p50": row_widths[len(row_widths) // 2] if row_widths else 0,
        "body_density": round(len(opaque) / max(1, area), 4),
        "luminance_contrast_p80": round(high - low, 2),
        "dark_ratio": round(
            sum(luma <= 60 for luma in lumas) / len(lumas), 4
        ),
        "bright_ratio": round(
            sum(luma >= 160 for luma in lumas) / len(lumas), 4
        ),
    }


def motion_pose_metrics(
    image: Image.Image,
    action: str,
    index: int,
) -> dict[str, Any]:
    """Return pixel-derived gait and full-body attack semantics at native 1x."""

    body_only = Image.new("RGBA", image.size, (0, 0, 0, 0))
    body_pixels = body_only.load()
    body_points: list[tuple[int, int]] = []
    for y in range(image.height):
        for x in range(image.width):
            color = image.getpixel((x, y))
            if color[3] == 0 or color in WEAPON_COLOR_SET:
                continue
            body_pixels[x, y] = color
            body_points.append((x, y))
    if not body_points:
        raise ValueError(f"{action}[{index}] has no body pixels for motion QA")

    left = min(x for x, _y in body_points)
    top = min(y for _x, y in body_points)
    right = max(x for x, _y in body_points) + 1
    bottom = max(y for _x, y in body_points) + 1
    body_height = bottom - top
    upper_bottom = top + max(1, round(body_height * 0.40))
    mid_bottom = top + max(2, round(body_height * 0.68))
    upper = [(x, y) for x, y in body_points if y < upper_bottom]
    mid = [(x, y) for x, y in body_points if upper_bottom <= y < mid_bottom]
    if not upper or not mid:
        raise ValueError(f"{action}[{index}] has incomplete torso geometry")
    upper_x = sum(x for x, _y in upper) / len(upper)
    mid_x = sum(x for x, _y in mid) / len(mid)
    torso_y = sum(y for _x, y in (*upper, *mid)) / (len(upper) + len(mid))

    result: dict[str, Any] = {
        "body_pose_sha256": pixel_sha256(body_only),
        "body_alpha_bbox": [left, top, right, bottom],
        "body_visible_height_px": body_height,
        "ground_offset_from_rect_center_px": round(bottom - image.height / 2, 3),
        "torso_height_from_ground_px": round(bottom - torso_y, 3),
        "upper_minus_mid_centroid_x_px": round(upper_x - mid_x, 3),
    }
    if action in RUN_ATTACK_POSE_PHASES:
        result["attack_pose_phase"] = RUN_ATTACK_POSE_PHASES[action][index]

    if action != "run":
        return result

    lower_start = top + round(body_height * 0.66)
    pelvis_x = sum(x for x, y in body_points if y < lower_start) / max(
        1, sum(1 for _x, y in body_points if y < lower_start)
    )
    foot_points = [
        (x, y)
        for x, y in body_points
        if y >= lower_start and abs(x - pelvis_x) <= body_height * 0.46
    ]
    foot_xs = [x for x, _y in foot_points]
    if len(foot_xs) < 4 or max(foot_xs) - min(foot_xs) < 2:
        raise ValueError(f"run[{index}] lost its two-foot lower-body span")

    # One-dimensional k-means separates the two visible boot clusters. Do not
    # invent anatomical left/right identities from the scripted phase: the old
    # QA did that and could report a crossover even while the pixels stayed
    # frozen. The actual close/open span is the auditable gait signal here.
    centres = [float(min(foot_xs)), float(max(foot_xs))]
    clusters: list[list[int]] = [[], []]
    for _iteration in range(12):
        clusters = [[], []]
        for x in foot_xs:
            group = 0 if abs(x - centres[0]) <= abs(x - centres[1]) else 1
            clusters[group].append(x)
        if not all(clusters):
            raise ValueError(f"run[{index}] collapsed to one foot cluster")
        updated = [sum(group) / len(group) for group in clusters]
        if all(abs(updated[i] - centres[i]) < 0.001 for i in (0, 1)):
            centres = updated
            break
        centres = updated
    centres.sort()
    result.update(
        {
            "run_stride_phase": RUN_STRIDE_PHASES[index],
            "foot_centers_x": [round(value, 3) for value in centres],
            "foot_separation_px": round(centres[1] - centres[0], 3),
            "stride_pose": (
                "crossing"
                if centres[1] - centres[0] <= 8.0
                else "extended"
                if centres[1] - centres[0] >= 10.0
                else "passing"
            ),
        }
    )
    return result


def frame_rects() -> dict[tuple[str, int], tuple[int, int, int, int]]:
    result: dict[tuple[str, int], tuple[int, int, int, int]] = {}
    for action in build_yone.GENERATED_BODY_ACTIONS:
        contract = (
            build_yone.NATIVE_CONTRACT
            if action in build_yone.NATIVE_CONTRACT
            else build_yone.CUSTOM_ACTION_CONTRACT
        )
        rects = contract[action]["rects"]
        if action == "dead":
            rects = rects[:-1]
        for index, rect in enumerate(rects):
            result[(action, index)] = tuple(rect)
    if len(result) != build_yone.GENERATED_BODY_FRAME_COUNT:
        raise ValueError(
            "V7 body contract changed: "
            f"{len(result)}/{build_yone.GENERATED_BODY_FRAME_COUNT}"
        )
    return result


def load_subjects() -> tuple[
    dict[tuple[str, int], Image.Image],
    dict[tuple[str, int], dict[str, dict[str, Any]]],
    dict[str, str],
]:
    hashes: dict[str, str] = {}
    for label, path in SOURCE_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        hashes[label] = sha256(path)
        if hashes[label] != EXPECTED_SOURCE_SHA256[label]:
            raise ValueError(f"accepted Yone V7 source hash changed: {label}")

    motion = Image.open(MOTION_SOURCE).convert("RGBA")
    attack = Image.open(ATTACK_SOURCE).convert("RGBA")
    w_sheet = Image.open(W_SOURCE).convert("RGBA")
    ult = Image.open(ULT_SOURCE).convert("RGBA")
    subjects: dict[tuple[str, int], Image.Image] = {}
    raw_subjects: dict[tuple[str, int], Image.Image] = {}
    for index in range(20):
        key = ("motion", index)
        subjects[key], raw_subjects[key] = split_cell_pair(
            motion,
            5,
            4,
            index,
            preserve_detached=13 <= index <= 19,
        )
    for index in range(24):
        key = ("attack_q", index)
        subjects[key], raw_subjects[key] = split_cell_pair(attack, 6, 4, index)
    for index in range(6):
        key = ("w", index)
        subjects[key], raw_subjects[key] = split_cell_pair(w_sheet, 3, 2, index)
    for index in range(15):
        key = ("ult", index)
        subjects[key], raw_subjects[key] = split_cell_pair(ult, 5, 3, index)
    palette_subjects = dict(subjects)
    palette_guard_actor = subjects[("attack_q", 2)]
    palette_guard_raw = raw_subjects[("attack_q", 2)]
    for frame_index in range(len(PALETTE_COMPAT_STRIDE_PHASES)):
        palette_key = ("run_guard", frame_index)
        palette_subjects[palette_key], _palette_raw = _recompose_stride_pair(
            palette_guard_actor,
            palette_guard_raw,
            frame_index,
            stride_phases=PALETTE_COMPAT_STRIDE_PHASES,
            stride_ratio=0.105,
        )
    for frame_index, source_key in enumerate(RUN_POSE_SOURCES):
        key = ("run_pose", frame_index)
        subjects[key], raw_subjects[key] = recompose_run_articulated_pair(
            subjects[source_key], raw_subjects[source_key], frame_index
        )
    install_source_palette(palette_subjects)
    used_keys = {
        (source_kind, int(cell_index))
        for assignments in ACTION_SOURCES.values()
        for source_kind, cell_index in assignments
        if cell_index is not None
    }
    traces = {
        key: {
            weapon: extract_source_weapon_trace(raw_subjects[key], weapon)
            for weapon in ("steel", "azakana")
        }
        for key in sorted(used_keys)
    }
    if set(traces) != used_keys:
        raise ValueError("V7 source weapon trace coverage changed")
    return subjects, traces, hashes


def build_frames() -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, int], Image.Image],
    list[dict[str, Any]],
    dict[str, str],
]:
    subjects, source_weapon_traces, source_hashes = load_subjects()
    rects = frame_rects()
    rows: list[dict[str, Any]] = []
    frames: dict[tuple[str, int], Image.Image] = {}
    audits: list[dict[str, Any]] = []

    for action in build_yone.GENERATED_BODY_ACTIONS:
        assignments = ACTION_SOURCES[action]
        shifts = X_SHIFTS[action]
        expected_count = sum(1 for frame_action, _index in rects if frame_action == action)
        if len(assignments) != expected_count or len(shifts) != expected_count:
            raise ValueError(
                f"V7 {action} mapping mismatch: {len(assignments)}/{expected_count}"
            )
        for index, ((source_kind, cell_index), x_shift) in enumerate(
            zip(assignments, shifts, strict=True)
        ):
            x, y, width, height = rects[(action, index)]
            if action == "dead":
                target_height = DEAD_TARGET_HEIGHTS[index]
                bottom_margin = DEAD_BOTTOM_MARGINS[index]
            else:
                target_height = build_yone.BODY_TARGET_HEIGHTS[action][index]
                bottom_margin = build_yone.BODY_BOTTOM_MARGINS[action][index]
                minimum_height = build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[action][index]
                target_height = max(target_height, minimum_height)
                bottom_margin = min(bottom_margin, height - minimum_height - 1)

            subject_key = (source_kind, int(cell_index))
            subject = subjects[subject_key]
            active_weapon = build_yone.V7_FRAME_ACTIVE_WEAPON[action]
            image, fit_audit, weapon_geometry = fit_pose(
                subject,
                (width, height),
                visible_height=target_height,
                bottom_margin=bottom_margin,
                x_shift=x_shift,
                weapon_traces=source_weapon_traces[subject_key],
                active_weapon=active_weapon,
            )

            bbox = alpha_bbox(image)
            if any(
                image.getchannel("A").getpixel(point)
                for point in (
                    *((x_pos, 0) for x_pos in range(image.width)),
                    *((x_pos, image.height - 1) for x_pos in range(image.width)),
                    *((0, y_pos) for y_pos in range(image.height)),
                    *((image.width - 1, y_pos) for y_pos in range(image.height)),
                )
            ):
                raise ValueError(f"{action}[{index}] touches a native edge")
            if set(pixels(image)) - ALLOWED_COLORS:
                raise ValueError(f"{action}[{index}] escaped the V7 palette")
            if set(pixels(image.getchannel("A"))) - {0, 255}:
                raise ValueError(f"{action}[{index}] alpha is not hard")

            face, eyes, mask, visibility = annotations_for_frame(image, action, index)
            motion_metrics = motion_pose_metrics(image, action, index)

            relative = f"frames/{action}_{index:02d}.png"
            path = V7_ROOT / relative
            save_png(path, image)
            row = {
                "action": action,
                "index": index,
                "file": relative,
                "rect": [x, y, width, height],
                "bottom_margin": height - bbox[3],
                "face_bbox": face,
                "eye_pixels": eyes,
                "mask_bbox": mask,
                "foot_zones": foot_zones(image, action),
                "face_visibility": visibility,
                "active_weapon": active_weapon,
                "weapons_present": build_yone.V7_FRAME_WEAPONS_PRESENT[action],
                **weapon_geometry,
            }
            rows.append(row)
            frames[(action, index)] = image
            quality = frame_quality(image)
            audits.append(
                {
                    "action": action,
                    "index": index,
                    "source": source_kind,
                    "cell": cell_index,
                    "size": [width, height],
                    "visible_size": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
                    "bottom_margin": height - bbox[3],
                    "face_visibility": visibility,
                    "active_weapon": active_weapon,
                    "hard_alpha": True,
                    "transparent_edges": True,
                    "opaque_colors": len(
                        {color for color in pixels(image) if color[3] == 255}
                    ),
                    **weapon_geometry,
                    **quality,
                    **fit_audit,
                    **motion_metrics,
                }
            )

    if (
        len(rows) != build_yone.GENERATED_BODY_FRAME_COUNT
        or len(frames) != build_yone.GENERATED_BODY_FRAME_COUNT
    ):
        raise ValueError(
            f"generated {len(rows)}/{build_yone.GENERATED_BODY_FRAME_COUNT} V7 frames"
        )
    return rows, frames, audits, source_hashes


def build_card_preview(idle: Image.Image) -> Image.Image:
    rendered = idle.resize(
        (
            round(idle.width * build_yone.YONE_LIVE_CARD_SCALE),
            round(idle.height * build_yone.YONE_LIVE_CARD_SCALE),
        ),
        Image.Resampling.NEAREST,
    )
    # Reconstruct the complete opaque card surface.  The actor route itself is
    # still the exact engine route below: full 43x55 idle frame, 2.2x NEAREST,
    # centered at (23, 0), with divider y=96 and right icon region untouched.
    preview = Image.new("RGBA", (141, 138), (15, 17, 26, 255))
    draw = ImageDraw.Draw(preview)
    draw.rounded_rectangle(
        (4, 4, 137, 136), radius=11, fill=(20, 21, 31, 255),
        outline=(66, 70, 83, 255), width=1,
    )
    draw.line((5, 96, 136, 96), fill=(43, 46, 57, 255), width=1)
    stage_height = max(
        round(rect[3] * build_yone.YONE_LIVE_CARD_SCALE)
        for rect in build_yone.NATIVE_CONTRACT["idle"]["rects"]
    )
    actor_x = (preview.width - rendered.width) // 2
    actor_y = (stage_height - rendered.height) // 2
    preview.alpha_composite(rendered, (actor_x, actor_y))
    actor_mask = Image.new("L", preview.size, 0)
    actor_mask.paste(rendered.getchannel("A"), (actor_x, actor_y))
    actor_bbox = actor_mask.getbbox()
    if actor_bbox is None:
        raise ValueError("V7 card preview lost the actor")
    # V7's battle idle intentionally exposes both swords.  Management/BP and
    # compact UI surfaces use dedicated source-direct portraits, so the battle
    # frame is no longer forced into the old card's right-side icon exclusion.
    if 96 - actor_bbox[3] < 6:
        raise ValueError(f"V7 card divider clearance regressed: {96 - actor_bbox[3]}")
    # Compact neutral placeholders make the icon-safe area visible in review;
    # they are card chrome, never part of the actor alpha audit.
    draw.arc((99, 72, 112, 88), 290, 70, fill=(236, 238, 242, 255), width=2)
    draw.rectangle((119, 76, 130, 87), outline=(217, 220, 228, 255), width=2)
    draw.rectangle((122, 79, 127, 84), fill=(104, 110, 125, 255))
    return preview


def build_contact_preview(
    rows: list[dict[str, Any]], frames: dict[tuple[str, int], Image.Image]
) -> Image.Image:
    columns = 6
    scale = 3
    maximum_width = max(frame.width for frame in frames.values())
    maximum_height = max(frame.height for frame in frames.values())
    cell_width = maximum_width * scale + 10
    cell_height = maximum_height * scale + 26
    total_rows = (len(rows) + columns - 1) // columns
    preview = Image.new(
        "RGBA", (columns * cell_width, total_rows * cell_height), (8, 13, 23, 255)
    )
    draw = ImageDraw.Draw(preview)
    for order, row in enumerate(rows):
        column = order % columns
        contact_row = order // columns
        left = column * cell_width
        top = contact_row * cell_height
        frame = frames[(row["action"], row["index"])]
        rendered = frame.resize(
            (frame.width * scale, frame.height * scale), Image.Resampling.NEAREST
        )
        x = left + (cell_width - rendered.width) // 2
        y = top + 18 + (maximum_height * scale - rendered.height)
        preview.alpha_composite(rendered, (x, y))
        draw.text(
            (left + 2, top + 2),
            f"{row['action']}[{row['index']}] {row['face_visibility'][0]}",
            fill=(225, 230, 239, 255),
        )
    return preview


def build_motion_attack_preview(
    frames: dict[tuple[str, int], Image.Image],
) -> Image.Image:
    """Render run and both basic attacks large enough for semantic review."""

    scale = 4
    columns = 8
    cell_width = 260
    cell_height = 235
    rows = (
        ("RUN crossover", "run", 8),
        ("STEEL windup > contact > recovery", "attack", 6),
        ("AZAKANA windup > contact > recovery", "attack_azakana", 6),
    )
    preview = Image.new(
        "RGBA", (columns * cell_width, len(rows) * cell_height), (8, 13, 23, 255)
    )
    draw = ImageDraw.Draw(preview)
    for row_index, (title, action, count) in enumerate(rows):
        row_top = row_index * cell_height
        baseline = row_top + 205
        draw.text((8, row_top + 5), title, fill=(226, 231, 240, 255))
        draw.line((0, baseline, preview.width, baseline), fill=(54, 71, 91, 255))
        for index in range(count):
            frame = frames[(action, index)]
            rendered = frame.resize(
                (frame.width * scale, frame.height * scale),
                Image.Resampling.NEAREST,
            )
            cell_left = index * cell_width
            x = cell_left + (cell_width - rendered.width) // 2
            y = baseline - rendered.height
            preview.alpha_composite(rendered, (x, y))
            phase = (
                f"stride {RUN_STRIDE_PHASES[index]:+.2f}"
                if action == "run"
                else RUN_ATTACK_POSE_PHASES[action][index]
            )
            draw.text(
                (cell_left + 8, row_top + 24),
                f"{index}: {phase}",
                fill=(177, 204, 224, 255),
            )
    return preview


def main() -> int:
    FRAME_ROOT.mkdir(parents=True, exist_ok=True)
    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    for path in FRAME_ROOT.glob("*.png"):
        path.unlink()
    for path in (
        BODY_PREVIEW,
        CONTACT_PREVIEW,
        MOTION_ATTACK_PREVIEW,
        FRAME_MANIFEST,
        PALETTE_PATH,
        QA_PATH,
    ):
        if path.exists():
            path.unlink()

    rows, frames, audits, source_hashes = build_frames()
    card_preview = build_card_preview(frames[("idle", 0)])
    contact_preview = build_contact_preview(rows, frames)
    motion_attack_preview = build_motion_attack_preview(frames)
    save_png(BODY_PREVIEW, card_preview)
    save_png(CONTACT_PREVIEW, contact_preview)
    save_png(MOTION_ATTACK_PREVIEW, motion_attack_preview)
    write_json(
        PALETTE_PATH,
        {
            "schema_version": 7,
            "route": "dual-sword-v7",
            "weapon_roles": WEAPON_PALETTE_ROLES,
            "colors": [
                {"role": role, "rgba": list(color)} for role, color in PALETTE_ROWS
            ],
        },
    )
    write_json(
        FRAME_MANIFEST,
        {
            "schema_version": 7,
            "route": "dual-sword-v7",
            "atlas_size": list(build_yone.ACTOR_SHEET_SIZE),
            "palette_file": "palette.json",
            "body_preview": "preview/yone_v7_actor_card.png",
            "weapon_contract": build_yone.V7_WEAPON_CONTRACT,
            "frames": rows,
        },
    )
    failures: list[str] = []
    if len(rows) != build_yone.GENERATED_BODY_FRAME_COUNT:
        failures.append(f"frame_count={len(rows)}")
    if any(not audit["hard_alpha"] for audit in audits):
        failures.append("soft_alpha")
    if any(not audit["transparent_edges"] for audit in audits):
        failures.append("opaque_edge")
    if len(PALETTE) > 48 or any(audit["opaque_colors"] > 48 for audit in audits):
        failures.append("palette_over_48")
    for audit in audits:
        label = f"{audit['action']}[{audit['index']}]"
        if audit["luminance_contrast_p80"] < 58:
            failures.append(f"low_contrast:{label}")
        if not 0.06 <= audit["dark_ratio"] <= 0.84:
            failures.append(f"dark_ratio:{label}")
        if audit["body_density"] < 0.10:
            failures.append(f"low_density:{label}")
        core_frame = audit["action"] in {
            "idle", "run", "hit", "skill2", "skill2_dash", "skill2_attack"
        }
        if core_frame and audit["bbox_width"] < 13:
            failures.append(f"abnormally_narrow_bbox:{label}")
        if core_frame and audit["core_width_p50"] < 8:
            failures.append(f"abnormally_narrow_core:{label}")
        if core_frame and audit["horizontal_crop_ratio"] > 0.60:
            failures.append(f"excessive_horizontal_crop:{label}")
        minimum_span = 3.0 if audit["action"] == "dead" else 4.0
        for weapon in ("steel", "azakana"):
            if audit[f"{weapon}_span_px"] < minimum_span:
                failures.append(f"short_{weapon}_blade:{label}")
            if audit[f"{weapon}_connectedness"] < 0.85:
                failures.append(f"disconnected_{weapon}_blade:{label}")
            if audit[f"{weapon}_pixel_count"] < 8:
                failures.append(f"weak_{weapon}_blade:{label}")
        if audit["steel_hand_anchor"] == audit["azakana_hand_anchor"]:
            failures.append(f"shared_weapon_hand:{label}")
        if math.dist(audit["steel_tip"], audit["azakana_tip"]) < 3.0:
            failures.append(f"merged_weapon_tips:{label}")
    for row in rows:
        if row["action"] != "idle":
            continue
        label = f"idle[{row['index']}]"
        face = row["face_bbox"]
        if face is None or face[2] < 5 or face[3] < 5:
            failures.append(f"small_face:{label}")
            continue
        if not row["eye_pixels"]:
            failures.append(f"missing_eye:{label}")
        frame = frames[("idle", row["index"])]
        fx, fy, fw, fh = face
        warm_pixels = sum(
            frame.getpixel((x, y)) in SKIN_COLORS
            for y in range(fy, fy + fh)
            for x in range(fx, fx + fw)
        )
        if warm_pixels < 8:
            failures.append(f"weak_warm_face:{label}")

    run_audits = sorted(
        (audit for audit in audits if audit["action"] == "run"),
        key=lambda audit: audit["index"],
    )
    if len(run_audits) != len(RUN_STRIDE_PHASES):
        failures.append(f"run_motion_audit_count={len(run_audits)}")
    run_ground_offsets = [
        audit["ground_offset_from_rect_center_px"] for audit in run_audits
    ]
    run_torso_heights = [
        audit["torso_height_from_ground_px"] for audit in run_audits
    ]
    run_body_heights = [audit["body_visible_height_px"] for audit in run_audits]
    run_torso_leans = [
        audit["upper_minus_mid_centroid_x_px"] for audit in run_audits
    ]
    run_foot_separations = [audit["foot_separation_px"] for audit in run_audits]
    run_stride_pose_counts = Counter(audit["stride_pose"] for audit in run_audits)
    run_crossing_frame_indices = [
        audit["index"] for audit in run_audits if audit["stride_pose"] == "crossing"
    ]
    run_extended_frame_indices = [
        audit["index"] for audit in run_audits if audit["stride_pose"] == "extended"
    ]
    run_local_minimum_indices = [
        index
        for index, value in enumerate(run_foot_separations)
        if value < run_foot_separations[index - 1]
        and value < run_foot_separations[(index + 1) % len(run_foot_separations)]
    ]
    run_local_maximum_indices = [
        index
        for index, value in enumerate(run_foot_separations)
        if value > run_foot_separations[index - 1]
        and value > run_foot_separations[(index + 1) % len(run_foot_separations)]
    ]
    run_hand_ranges: dict[str, dict[str, float]] = {}
    hand_x_paths: dict[str, list[float]] = {}
    hand_paths: dict[str, list[tuple[float, float]]] = {}
    for weapon in ("steel", "azakana"):
        xs = [float(audit[f"{weapon}_hand_anchor"][0]) for audit in run_audits]
        ys = [float(audit[f"{weapon}_hand_anchor"][1]) for audit in run_audits]
        hand_x_paths[weapon] = xs
        hand_paths[weapon] = list(zip(xs, ys, strict=True))
        run_hand_ranges[weapon] = {
            "x": round(max(xs) - min(xs), 3),
            "y": round(max(ys) - min(ys), 3),
        }
    run_maximum_adjacent_hand_steps = {
        weapon: round(
            max(
                math.dist(path[index], path[(index + 1) % len(path)])
                for index in range(len(path))
            ),
            3,
        )
        for weapon, path in hand_paths.items()
    }
    steel_x = hand_x_paths["steel"]
    azakana_x = hand_x_paths["azakana"]
    steel_mean = sum(steel_x) / len(steel_x)
    azakana_mean = sum(azakana_x) / len(azakana_x)
    covariance = sum(
        (steel - steel_mean) * (azakana - azakana_mean)
        for steel, azakana in zip(steel_x, azakana_x, strict=True)
    )
    steel_variance = sum((value - steel_mean) ** 2 for value in steel_x)
    azakana_variance = sum((value - azakana_mean) ** 2 for value in azakana_x)
    run_hand_x_correlation = covariance / max(
        0.0001, math.sqrt(steel_variance * azakana_variance)
    )
    run_blade_angle_ranges: dict[str, float] = {}
    run_maximum_adjacent_blade_angle_steps: dict[str, float] = {}
    run_minimum_blade_pixel_ratios: dict[str, float] = {}
    run_maximum_adjacent_tip_steps: dict[str, float] = {}
    run_maximum_adjacent_blade_span_ratios: dict[str, float] = {}
    run_maximum_adjacent_blade_pixel_ratios: dict[str, float] = {}
    for weapon in ("steel", "azakana"):
        angles = []
        blade_pixel_counts = []
        blade_spans = []
        tip_path = []
        for audit in run_audits:
            hand_x, hand_y = audit[f"{weapon}_hand_anchor"]
            tip_x, tip_y = audit[f"{weapon}_tip"]
            tip_path.append((float(tip_x), float(tip_y)))
            angles.append(
                math.atan2(tip_y - hand_y, tip_x - hand_x) % (2 * math.pi)
            )
            blade_pixel_counts.append(int(audit[f"{weapon}_pixel_count"]))
            blade_spans.append(float(audit[f"{weapon}_span_px"]))
        run_maximum_adjacent_tip_steps[weapon] = round(
            max(
                math.dist(tip_path[index], tip_path[(index + 1) % len(tip_path)])
                for index in range(len(tip_path))
            ),
            3,
        )
        run_maximum_adjacent_blade_angle_steps[weapon] = round(
            max(
                abs(
                    (
                        angles[(index + 1) % len(angles)]
                        - angles[index]
                        + math.pi
                    )
                    % (2 * math.pi)
                    - math.pi
                )
                for index in range(len(angles))
            ),
            3,
        )
        run_minimum_blade_pixel_ratios[weapon] = round(
            min(blade_pixel_counts) / max(blade_pixel_counts), 3
        )
        run_maximum_adjacent_blade_span_ratios[weapon] = round(
            max(
                max(
                    blade_spans[index],
                    blade_spans[(index + 1) % len(blade_spans)],
                )
                / min(
                    blade_spans[index],
                    blade_spans[(index + 1) % len(blade_spans)],
                )
                for index in range(len(blade_spans))
            ),
            3,
        )
        run_maximum_adjacent_blade_pixel_ratios[weapon] = round(
            max(
                max(
                    blade_pixel_counts[index],
                    blade_pixel_counts[(index + 1) % len(blade_pixel_counts)],
                )
                / min(
                    blade_pixel_counts[index],
                    blade_pixel_counts[(index + 1) % len(blade_pixel_counts)],
                )
                for index in range(len(blade_pixel_counts))
            ),
            3,
        )
        angles = sorted(angles)
        circular_gaps = [
            second - first for first, second in zip(angles, angles[1:])
        ] + [angles[0] + 2 * math.pi - angles[-1]]
        run_blade_angle_ranges[weapon] = round(
            2 * math.pi - max(circular_gaps), 3
        )
    if run_stride_pose_counts["crossing"] < 2:
        failures.append(f"run_crossing_pose_count={run_stride_pose_counts['crossing']}")
    if run_stride_pose_counts["extended"] < 2:
        failures.append(f"run_extended_pose_count={run_stride_pose_counts['extended']}")
    # Calibrate the gait against finished combined-mod actors instead of
    # forcing an artificial deep crossover.  Measured with this same lower-
    # body clustering pass, Briar spans about 5.4..14.3px and Orianna about
    # 7.7..12.0px. Yone should stay near the latter: a readable narrow passing
    # step at frames 2/6, moderate contacts at 0/4, and no 15px+ split.
    if run_foot_separations and min(run_foot_separations) < 6.0:
        failures.append(
            f"run_foot_separation_min={min(run_foot_separations):.3f}"
        )
    if run_crossing_frame_indices != [2, 6] or run_local_minimum_indices != [2, 6]:
        failures.append(
            "run_passing_step_indices="
            f"{run_crossing_frame_indices}/{run_local_minimum_indices}"
        )
    if run_local_maximum_indices != [0, 4]:
        failures.append(f"run_contact_step_indices={run_local_maximum_indices}")
    if run_extended_frame_indices != [0, 4]:
        failures.append(f"run_extended_frame_indices={run_extended_frame_indices}")
    if any(not 6.5 <= run_foot_separations[index] <= 8.5 for index in (2, 6)):
        failures.append(f"run_crossing_foot_separations={run_foot_separations}")
    if any(not 10.0 <= run_foot_separations[index] <= 13.5 for index in (0, 4)):
        failures.append(f"run_contact_foot_separations={run_foot_separations}")
    if any(
        not 8.5 <= run_foot_separations[index] <= 10.5
        for index in (1, 3, 5, 7)
    ):
        failures.append(f"run_transition_foot_separations={run_foot_separations}")
    if abs(run_foot_separations[0] - run_foot_separations[4]) > 2.0:
        failures.append(f"run_contact_symmetry={run_foot_separations}")
    if abs(run_foot_separations[2] - run_foot_separations[6]) > 1.0:
        failures.append(f"run_crossing_symmetry={run_foot_separations}")
    if RUN_PASSING_LEG_SIDES[2] != -RUN_PASSING_LEG_SIDES[6]:
        failures.append(f"run_passing_leg_sides={RUN_PASSING_LEG_SIDES}")
    if run_ground_offsets and max(run_ground_offsets) - min(run_ground_offsets) > 3.0:
        failures.append(
            "run_ground_anchor_range="
            f"{max(run_ground_offsets) - min(run_ground_offsets):.3f}"
        )
    if run_torso_heights and max(run_torso_heights) - min(run_torso_heights) > 5.0:
        failures.append(
            "run_torso_height_range="
            f"{max(run_torso_heights) - min(run_torso_heights):.3f}"
        )
    if run_body_heights and max(run_body_heights) - min(run_body_heights) > 2:
        failures.append(
            "run_body_height_range="
            f"{max(run_body_heights) - min(run_body_heights)}"
        )
    if run_torso_leans and not 0.4 <= max(run_torso_leans) - min(run_torso_leans) <= 1.5:
        failures.append(
            "run_upper_guard_lean_range="
            f"{max(run_torso_leans) - min(run_torso_leans):.3f}"
        )
    if run_hand_ranges["steel"]["x"] < 3.0 or run_hand_ranges["steel"]["y"] < 1.5:
        failures.append(f"weak_steel_hand_motion={run_hand_ranges['steel']}")
    if run_hand_ranges["azakana"]["x"] < 2.5 or run_hand_ranges["azakana"]["y"] < 1.0:
        failures.append(f"weak_azakana_hand_motion={run_hand_ranges['azakana']}")
    if run_hand_x_correlation > -0.15:
        failures.append(f"run_hand_x_correlation={run_hand_x_correlation:.3f}")
    for weapon, adjacent_step in run_maximum_adjacent_hand_steps.items():
        if adjacent_step > 3.0:
            failures.append(f"run_{weapon}_hand_step={adjacent_step:.3f}")
    for weapon, angle_range in run_blade_angle_ranges.items():
        if angle_range > 3.0:
            failures.append(f"run_{weapon}_angle_range={angle_range:.3f}")
        adjacent_angle_step = run_maximum_adjacent_blade_angle_steps[weapon]
        if adjacent_angle_step > 0.45:
            failures.append(
                f"run_{weapon}_adjacent_angle_step={adjacent_angle_step:.3f}"
            )
        blade_pixel_ratio = run_minimum_blade_pixel_ratios[weapon]
        if blade_pixel_ratio < 0.65:
            failures.append(
                f"run_{weapon}_minimum_blade_pixel_ratio={blade_pixel_ratio:.3f}"
            )
        if run_maximum_adjacent_tip_steps[weapon] > 5.0:
            failures.append(
                f"run_{weapon}_tip_step={run_maximum_adjacent_tip_steps[weapon]:.3f}"
            )
        if run_maximum_adjacent_blade_span_ratios[weapon] > 1.2:
            failures.append(
                "run_"
                f"{weapon}_adjacent_span_ratio="
                f"{run_maximum_adjacent_blade_span_ratios[weapon]:.3f}"
            )
        if run_maximum_adjacent_blade_pixel_ratios[weapon] > 1.2:
            failures.append(
                "run_"
                f"{weapon}_adjacent_pixel_ratio="
                f"{run_maximum_adjacent_blade_pixel_ratios[weapon]:.3f}"
            )

    attack_motion_summary: dict[str, Any] = {}
    for attack_action in ("attack", "attack_azakana"):
        action_audits = sorted(
            (audit for audit in audits if audit["action"] == attack_action),
            key=lambda audit: audit["index"],
        )
        phase_hashes = {
            phase: {
                audit["body_pose_sha256"]
                for audit in action_audits
                if audit["attack_pose_phase"] == phase
            }
            for phase in ("windup", "contact", "recovery")
        }
        pose_hashes = {audit["body_pose_sha256"] for audit in action_audits}
        torso_leans = [
            audit["upper_minus_mid_centroid_x_px"] for audit in action_audits
        ]
        if any(not values for values in phase_hashes.values()):
            failures.append(f"missing_attack_pose_phase:{attack_action}")
        if len(pose_hashes) < 5:
            failures.append(
                f"repeated_attack_body_pose:{attack_action}:{len(pose_hashes)}"
            )
        if torso_leans and max(torso_leans) - min(torso_leans) < 1.25:
            failures.append(f"weak_attack_body_turn:{attack_action}")
        attack_motion_summary[attack_action] = {
            "source_cells": [
                int(cell) for source, cell in ACTION_SOURCES[attack_action]
                if source == "attack_q" and cell is not None
            ],
            "pose_phases": list(RUN_ATTACK_POSE_PHASES[attack_action]),
            "unique_body_pose_count": len(pose_hashes),
            "body_turn_span_px": round(max(torso_leans) - min(torso_leans), 3),
            "phase_unique_pose_counts": {
                phase: len(values) for phase, values in phase_hashes.items()
            },
        }

    motion_attack_contract = {
        "reference": WORKSHOP_YONE_MOTION_MEASUREMENTS,
        "native_contract_preserved": {
            "run_frames": len(build_yone.NATIVE_CONTRACT["run"]["rects"]),
            "run_durations_seconds": build_yone.NATIVE_CONTRACT["run"]["durations"],
            "attack_frames": len(build_yone.NATIVE_CONTRACT["attack"]["rects"]),
            "attack_durations_seconds": build_yone.NATIVE_CONTRACT["attack"]["durations"],
        },
        "run": {
            "source": "approved upright V7 guard poses; authored upper-body articulation plus moderate finished-hero-calibrated passing-step motion",
            "pose_sources": [list(source) for source in RUN_POSE_SOURCES],
            "stride_phases": list(RUN_STRIDE_PHASES),
            "passing_leg_sides": list(RUN_PASSING_LEG_SIDES),
            "foot_separations_px": run_foot_separations,
            "stride_pose_counts": dict(sorted(run_stride_pose_counts.items())),
            "crossing_frame_indices": run_crossing_frame_indices,
            "extended_frame_indices": run_extended_frame_indices,
            "local_minimum_frame_indices": run_local_minimum_indices,
            "local_maximum_frame_indices": run_local_maximum_indices,
            "minimum_foot_separation_px": round(min(run_foot_separations), 3),
            "maximum_foot_separation_px": round(max(run_foot_separations), 3),
            "ground_anchor_range_px": round(
                max(run_ground_offsets) - min(run_ground_offsets), 3
            ),
            "torso_height_range_px": round(
                max(run_torso_heights) - min(run_torso_heights), 3
            ),
            "body_visible_height_range_px": max(run_body_heights)
            - min(run_body_heights),
            "upper_guard_lean_range_px": round(
                max(run_torso_leans) - min(run_torso_leans), 3
            ),
            "hand_anchor_ranges_px": run_hand_ranges,
            "hand_x_correlation": round(run_hand_x_correlation, 3),
            "maximum_adjacent_hand_step_px": run_maximum_adjacent_hand_steps,
            "maximum_adjacent_tip_step_px": run_maximum_adjacent_tip_steps,
            "blade_angle_ranges_radians": run_blade_angle_ranges,
            "maximum_adjacent_blade_angle_step_radians": (
                run_maximum_adjacent_blade_angle_steps
            ),
            "minimum_blade_pixel_ratio": run_minimum_blade_pixel_ratios,
            "maximum_adjacent_blade_span_ratio": (
                run_maximum_adjacent_blade_span_ratios
            ),
            "maximum_adjacent_blade_pixel_ratio": (
                run_maximum_adjacent_blade_pixel_ratios
            ),
            "unique_body_pose_count": len(
                {audit["body_pose_sha256"] for audit in run_audits}
            ),
        },
        "attacks": attack_motion_summary,
    }
    write_json(
        QA_PATH,
        {
            "schema_version": 7,
            "route": "dual-sword-v7",
            "frame_count": len(rows),
            "contact_preview": "preview/yone_v7_native_contact.png",
            "motion_attack_preview": "../../../qa/yone_motion_attack_qa.png",
            "source_hashes": source_hashes,
            "source_layouts": {
                "motion": [5, 4],
                "attack_q": [6, 4],
                "w": [3, 2],
                "ult": [5, 3],
            },
            "source_to_native_resampling": "LANCZOS",
            "hard_alpha_threshold": 96,
            "opaque_palette_size": len(PALETTE),
            "face_visibility_values": ["front", "profile", "hidden"],
            "idle0_pixel_sha256": pixel_sha256(frames[("idle", 0)]),
            "card_alpha_bbox": list(alpha_bbox(card_preview)),
            "motion_attack_contract": motion_attack_contract,
            "failures": failures,
            "frames": audits,
        },
    )
    if failures:
        raise ValueError(f"V7 generation QA failed: {failures}")
    hidden = sum(row["face_visibility"] == "hidden" for row in rows)
    profile = sum(row["face_visibility"] == "profile" for row in rows)
    front = len(rows) - hidden - profile
    cropped = sum(audit["horizontal_crop"] for audit in audits)
    print(
        "generated Yone V7 dual-sword source: "
        f"{len(rows)} frames, face front/profile/hidden={front}/{profile}/{hidden}, "
        f"palette={len(PALETTE)}, horizontal_weapon_crops={cropped}, failures=0, "
        f"card_bbox={alpha_bbox(card_preview)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
