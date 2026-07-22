from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw


MOD_ROOT = Path(__file__).resolve().parents[1]
FRAME_MANIFEST = MOD_ROOT / "source/native/yone_v7/frames.json"
GENERATION_QA = MOD_ROOT / "source/native/yone_v7/generation_qa.json"
ACTOR_ATLAS = MOD_ROOT / "aseprite_resources/champions/yone#sheet.png"
ACTOR_ANIM = MOD_ROOT / "aseprite_resources/champions/yone#anim.fanim"
RELEASE_MANIFEST = MOD_ROOT / "build_manifest.json"

EXPECTED_ATLAS_SIZE = (4262, 88)
EXPECTED_NATIVE_ATLAS_SIZE = (3502, 88)
EXPECTED_ROUTE = "dual-sword-v7"
EXPECTED_SCHEMA_VERSION = 7
EXPECTED_BODY_FRAME_COUNT = 67
CARD_PREVIEW_SIZE = (141, 138)
CARD_STAGE_HEIGHT = 121
CARD_SCALE = 2.2
CARD_DIVIDER_Y = 96
CARD_DIVIDER_CLEARANCE = 6
CARD_UI_ICON_SAFE_RECT = (98, 70, 141, 100)
CARD_OUTER_FILL = (15, 17, 26, 255)
CARD_INNER_FILL = (20, 21, 31, 255)
CARD_BORDER_COLOR = (66, 70, 83, 255)
CARD_DIVIDER_COLOR = (43, 46, 57, 255)
MAX_OPAQUE_PALETTE_COLORS = 48
EXPECTED_WEAPON_PALETTE_ROLES = {
    "steel": {
        "dark": ["source_06", "source_07"],
        "mid": ["source_04"],
        "highlight": ["source_03"],
    },
    "azakana": {
        "dark": ["mask_03", "mask_04"],
        "red": ["mask_00", "mask_02"],
        "highlight": ["mask_01"],
    },
}

PRIMARY_IDLE_KEY = ("idle", 0)
IDLE_FACE_MIN_SIZE = (5, 5)
IDLE_CONNECTED_SKIN_MIN = 8
IDLE_CARD_SKIN_MIN = 32
EXPECTED_SOURCE_HASHES = {
    "motion": "ab2bfe217a397384fc6738647b2a8c6a561e942e78ee4e3509ceb99eb217cb71",
    "attack_q": "81642ff3780139b966c4646060882aa33c416d56fd5f4dfcea3a86e556a60cd1",
    "w": "5cfa46346cb29e728a7195dbdd98b4b9ff84c3c32e4cd887c1fd1dcec53967c0",
    "ult": "588a38ec088a84fc899abf8f0fb86c85719f58b7b624a6bbb2fdd008027959e4",
}
SOURCE_PATHS = {
    "motion": MOD_ROOT / "source/imagegen/yone_v7_motion_contact.png",
    "attack_q": MOD_ROOT / "source/imagegen/yone_v7_attack_q_contact.png",
    "w": MOD_ROOT / "source/imagegen/yone_v7_w_contact.png",
    "ult": MOD_ROOT / "source/imagegen/yone_v7_ult_contact.png",
}

# V3 through V6 actor/body sources are retired by the final V7 route.  The
# accepted Q/W/R effect sources are independent and intentionally not listed.
# Prefix matching is used for the V4 native tree so a stale frame cannot evade
# this gate merely by being renamed.
RETIRED_BODY_PATHS = {
    "source/imagegen/yone_core_contact.png",
    "source/imagegen/yone_run_contact.png",
    "source/imagegen/yone_wr_body_contact.png",
    "source/imagegen/yone_defeat_contact.png",
    "source/processed/yone_core_contact_alpha.png",
    "source/processed/yone_run_contact_alpha.png",
    "source/processed/yone_wr_body_contact_alpha.png",
    "source/processed/yone_defeat_contact_alpha.png",
    "source/processed/yone_native_body_master.png",
    "source/imagegen/yone_v4_action_contact.png",
    "source/imagegen/yone_v4_idle_candidate_43x55.png",
    "source/imagegen/yone_v5_idle_golden_43x55.png",
    "source/imagegen/yone_v5_idle_source.png",
    "source/imagegen/yone_v5_motion_contact.png",
    "source/imagegen/yone_v5_attack_q_w_contact.png",
    "source/imagegen/yone_v5_q5_contact.png",
    "source/imagegen/yone_v5_ult_contact.png",
    "source/imagegen/yone_v6_motion_contact.png",
    "source/imagegen/yone_v6_attack_q_w_contact.png",
    "source/imagegen/yone_v6_w_contact.png",
    "source/imagegen/yone_v6_ult_contact.png",
}
RETIRED_BODY_PREFIXES = (
    "source/native/yone_v4/",
    "source/native/yone_v5/",
    "source/native/yone_v6/",
)

BODY_ACTION_COUNTS = {
    "skill2": 1,
    "hit": 1,
    "attack": 6,
    "skill2_dash": 1,
    "ult": 13,
    "run": 8,
    "skill2_attack": 5,
    "idle": 4,
    # The native ninth dead frame is a transparent terminal and is not a body
    # source frame.
    "dead": 8,
    "skill": 7,
    # These two sequences occupy the V7 atlas extension.  The other three
    # runtime aliases below intentionally point at immutable native-prefix
    # rectangles and therefore do not duplicate source-frame rows.
    "attack_azakana": 6,
    "skill_q3": 7,
}
NATIVE_TAG_PREFIX = (
    "skill2",
    "hit",
    "attack",
    "skill2_dash",
    "ult",
    "run",
    "ult_hit_effect",
    "skill2_attack",
    "idle",
    "hit_effect_area",
    "dead",
    "skill_projectile",
    "skill",
)
V7_EXTENSION_TAGS = (
    "attack_steel",
    "attack_azakana",
    "skill_q12",
    "skill_q3",
    "skill_w_azakana",
)
EXPECTED_TAG_ORDER = NATIVE_TAG_PREFIX + V7_EXTENSION_TAGS
EXPECTED_WEAPON_CONTRACT = {
    "version": 1,
    "weapons": ["steel", "azakana"],
    "always_dual_actions": ["idle", "run"],
    "semantic_animation_tags": {
        "attack_steel": "steel",
        "attack_azakana": "azakana",
        "skill_q12": "steel",
        "skill_q3": "steel",
        "skill_w_azakana": "azakana",
        "ult": "dual",
    },
    "long_blade_overlay_policy": (
        "caster-follow effects extend the active blade outside the compact actor frame"
    ),
}
ACTIVE_WEAPON_BY_ACTION = {
    "skill2": "azakana",
    "hit": "dual",
    "attack": "steel",
    "skill2_dash": "dual",
    "ult": "dual",
    "run": "dual",
    "skill2_attack": "azakana",
    "idle": "dual",
    "dead": "dual",
    "skill": "steel",
    "attack_azakana": "azakana",
    "skill_q3": "steel",
}
FRONT_FACE_ACTIONS = {"idle"}
FACE_VISIBILITY_VALUES = {"front", "profile", "hidden"}
FOOT_REQUIRED_ACTIONS = {
    "idle",
    "hit",
    "attack",
    "skill2",
    "skill2_dash",
    "skill2_attack",
    "run",
    "skill",
    "attack_azakana",
    "skill_q3",
}


class V7ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Palette:
    colors: frozenset[tuple[int, int, int, int]]
    by_role: dict[str, frozenset[tuple[int, int, int, int]]]

    def semantic_colors(self, semantic: str) -> frozenset[tuple[int, int, int, int]]:
        """Return colors using semantic role boundaries, never substrings.

        In particular, eye colors are an explicit allow-list.  A role such as
        ``skin_shadow_eye`` remains a skin role and can never satisfy an eye
        annotation.
        """

        if semantic == "eye":
            accepted_roles = {"eye_outline", "eye_highlight"}
            return frozenset(
                color
                for role, colors in self.by_role.items()
                if role in accepted_roles
                for color in colors
            )
        if semantic not in {"skin", "mask"}:
            raise ValueError(f"unsupported palette semantic: {semantic}")
        prefix = semantic + "_"
        return frozenset(
            color
            for role, colors in self.by_role.items()
            if role == semantic or role.startswith(prefix)
            for color in colors
        )

    def exact_role(self, role: str) -> frozenset[tuple[int, int, int, int]]:
        return self.by_role.get(role, frozenset())


def _fail(message: str) -> None:
    raise V7ValidationError(message)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        _fail(f"missing required V7 file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(f"invalid JSON at {path}: {error}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        _fail(f"cannot hash V7 source {path}: {error}")
    return digest.hexdigest()


def _validate_generation_qa(mod_root: Path) -> dict[str, Any]:
    qa_path = mod_root / GENERATION_QA.relative_to(MOD_ROOT)
    payload = _read_json(qa_path)
    if not isinstance(payload, dict):
        _fail("V7 generation_qa.json must be an object")
    if (
        payload.get("schema_version") != EXPECTED_SCHEMA_VERSION
        or payload.get("route") != EXPECTED_ROUTE
    ):
        _fail("generation_qa.json must declare schema_version=7 and dual-sword-v7")
    if payload.get("failures") != []:
        _fail(f"generation_qa.json contains failures: {payload.get('failures')!r}")
    if payload.get("source_hashes") != EXPECTED_SOURCE_HASHES:
        _fail("generation_qa.json source_hashes do not match the accepted V7 sources")
    if payload.get("source_to_native_resampling") != "LANCZOS":
        _fail("V7 source-to-native route must declare LANCZOS resampling")
    if payload.get("opaque_palette_size") not in range(1, MAX_OPAQUE_PALETTE_COLORS + 1):
        _fail("generation_qa.json opaque_palette_size is outside 1..48")
    actual_hashes: dict[str, str] = {}
    for label, canonical_path in SOURCE_PATHS.items():
        path = mod_root / canonical_path.relative_to(MOD_ROOT)
        if not path.is_file():
            _fail(f"missing hash-locked V7 source: {path}")
        actual_hashes[label] = _sha256(path)
    if actual_hashes != EXPECTED_SOURCE_HASHES:
        _fail(f"hash-locked V7 source changed: {actual_hashes}")
    return {
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "source_hashes": actual_hashes,
        "source_to_native_resampling": "LANCZOS",
        "opaque_palette_size": payload["opaque_palette_size"],
        "quality_failures": [],
    }


def _safe_relative_file(base: Path, raw: object, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        _fail(f"{label} must be a non-empty POSIX relative path")
    relative = Path(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        _fail(f"{label} escapes the V7 source root: {raw!r}")
    resolved = (base / relative).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        _fail(f"{label} escapes the V7 source root: {raw!r}")
    if not resolved.is_file():
        _fail(f"{label} does not exist: {resolved}")
    return resolved


def _rect(value: object, *, label: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(type(component) is not int for component in value)
    ):
        _fail(f"{label} must be [x,y,w,h] integers")
    x, y, width, height = value
    if width <= 0 or height <= 0:
        _fail(f"{label} must have positive width and height: {value}")
    if x < 0 or y < 0 or x + width > size[0] or y + height > size[1]:
        _fail(f"{label} is outside {size}: {value}")
    return x, y, width, height


def _bbox_to_pillow(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, width, height = rect
    return x, y, x + width, y + height


def _rgba_pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    if image.mode != "RGBA":
        _fail(f"V7 source must be RGBA, got {image.mode}")
    getter = getattr(image, "get_flattened_data", None)
    return list(getter() if getter is not None else image.getdata())


def _pixels(image: Image.Image) -> Any:
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter is not None else image.getdata()


def _luminance(color: tuple[int, int, int, int]) -> float:
    red, green, blue, _alpha = color
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def load_palette(path: Path) -> Palette:
    if path.suffix.lower() != ".json":
        _fail(f"palette_file must end in .json: {path}")
    payload = _read_json(path)
    if not isinstance(payload, dict):
        _fail("palette.json must be an object")
    if (
        payload.get("schema_version") != EXPECTED_SCHEMA_VERSION
        or payload.get("route") != EXPECTED_ROUTE
    ):
        _fail("palette.json must declare schema_version=7 and dual-sword-v7")
    rows = payload.get("colors")
    if not isinstance(rows, list) or not rows:
        _fail("palette.json colors must be a non-empty list")

    rgba_seen: set[tuple[int, int, int, int]] = set()
    by_role: dict[str, set[tuple[int, int, int, int]]] = {}
    transparent_rows = 0
    opaque_rows = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"palette colors[{index}] must be an object")
        role = row.get("role")
        rgba = row.get("rgba")
        if not isinstance(role, str) or not role.strip():
            _fail(f"palette colors[{index}].role must be non-empty")
        if (
            not isinstance(rgba, list)
            or len(rgba) != 4
            or any(type(channel) is not int or not 0 <= channel <= 255 for channel in rgba)
        ):
            _fail(f"palette colors[{index}].rgba must contain four bytes")
        color = tuple(rgba)
        if color in rgba_seen:
            _fail(f"palette RGBA is duplicated: {rgba}")
        rgba_seen.add(color)
        normalized_role = role.strip().lower()
        by_role.setdefault(normalized_role, set()).add(color)
        if color[3] == 0:
            transparent_rows += 1
            if color != (0, 0, 0, 0):
                _fail("transparent palette color must clear RGB to [0,0,0,0]")
        elif color[3] == 255:
            opaque_rows += 1
        else:
            _fail(f"palette alpha must be hard 0/255, got {rgba}")

    if transparent_rows != 1:
        _fail(f"palette must contain exactly one transparent RGBA, got {transparent_rows}")
    if opaque_rows > MAX_OPAQUE_PALETTE_COLORS:
        _fail(
            f"palette has {opaque_rows} opaque colors; maximum is "
            f"{MAX_OPAQUE_PALETTE_COLORS}"
        )

    weapon_roles = payload.get("weapon_roles")
    if weapon_roles != EXPECTED_WEAPON_PALETTE_ROLES:
        _fail("palette.json weapon_roles must declare distinct steel and Azakana ramps")
    referenced_roles = {
        role
        for weapon in EXPECTED_WEAPON_PALETTE_ROLES.values()
        for roles in weapon.values()
        for role in roles
    }
    missing_weapon_roles = sorted(referenced_roles - set(by_role))
    if missing_weapon_roles:
        _fail(f"palette.json weapon_roles reference missing roles: {missing_weapon_roles}")
    steel_roles = {
        role
        for roles in EXPECTED_WEAPON_PALETTE_ROLES["steel"].values()
        for role in roles
    }
    azakana_roles = {
        role
        for roles in EXPECTED_WEAPON_PALETTE_ROLES["azakana"].values()
        for role in roles
    }
    if steel_roles & azakana_roles:
        _fail("steel and Azakana weapon palette roles must be disjoint")

    palette = Palette(
        frozenset(rgba_seen),
        {role: frozenset(colors) for role, colors in by_role.items()},
    )
    if not palette.semantic_colors("skin"):
        _fail("palette must include an exact skin or skin_* role")
    if not palette.semantic_colors("mask"):
        _fail("palette must include an exact mask or mask_* role")
    if not palette.exact_role("eye_outline"):
        _fail("palette must include the exact role 'eye_outline'")
    if any(_luminance(color) > 90 for color in palette.exact_role("eye_outline")):
        _fail("eye_outline must be a dark eye-frame color (luminance <= 90)")

    eye_colors = palette.semantic_colors("eye")
    skin_or_mask = palette.semantic_colors("skin") | palette.semantic_colors("mask")
    if eye_colors & skin_or_mask:
        _fail("eye colors must not overlap skin or mask semantic colors")
    return palette


def _frame_rects(animation: object, *, tag: str) -> list[list[int]]:
    if not isinstance(animation, dict):
        _fail(f"Yone actor animation {tag!r} is missing")
    frames = animation.get("frames")
    if not isinstance(frames, list):
        _fail(f"Yone actor animation {tag!r} has no frames")
    rects: list[list[int]] = []
    for index, frame in enumerate(frames):
        data = frame.get("data") if isinstance(frame, dict) else None
        if not isinstance(data, dict):
            _fail(f"Yone actor {tag}[{index}] has no data rect")
        rects.append([data.get("x"), data.get("y"), data.get("w"), data.get("h")])
    return rects


def _validate_animation_contract(anim_payload: dict[str, Any]) -> dict[str, Any]:
    anims = anim_payload.get("anims")
    if not isinstance(anims, dict):
        _fail("Yone actor anim is missing anims")
    tag_order = tuple(anims)
    if tag_order != EXPECTED_TAG_ORDER:
        _fail(
            "Yone V7 tag order must retain the immutable 13-tag native prefix "
            f"then the five dual-sword extensions: {tag_order!r}"
        )

    rects = {tag: _frame_rects(anims[tag], tag=tag) for tag in EXPECTED_TAG_ORDER}
    expected_counts = {
        "attack_steel": 6,
        "attack_azakana": 6,
        "skill_q12": 7,
        "skill_q3": 7,
        "skill_w_azakana": 5,
    }
    for tag, count in expected_counts.items():
        if len(rects[tag]) != count:
            _fail(f"Yone V7 {tag} must contain exactly {count} frames")

    aliases = {
        "attack_steel": "attack",
        "skill_q12": "skill",
        "skill_w_azakana": "skill2_attack",
    }
    for alias, native in aliases.items():
        if rects[alias] != rects[native]:
            _fail(f"Yone V7 {alias} must alias immutable native tag {native}")

    distinct = {
        "attack_steel_vs_azakana": rects["attack_steel"] != rects["attack_azakana"],
        "q12_vs_q3": rects["skill_q12"] != rects["skill_q3"],
    }
    if not all(distinct.values()):
        _fail("Yone V7 steel/Azakana attacks and Q12/Q3 must use distinct rectangles")
    if any(rect[0] < EXPECTED_NATIVE_ATLAS_SIZE[0] for rect in rects["attack_azakana"]):
        _fail("Yone V7 attack_azakana must be physically packed in the atlas extension")
    if any(rect[0] < EXPECTED_NATIVE_ATLAS_SIZE[0] for rect in rects["skill_q3"]):
        _fail("Yone V7 skill_q3 must be physically packed in the atlas extension")

    return {
        "native_tag_prefix": list(NATIVE_TAG_PREFIX),
        "extension_tags": list(V7_EXTENSION_TAGS),
        "aliases": aliases,
        "distinct_sequences": distinct,
    }


def _expected_actor_frames(anim_payload: dict[str, Any]) -> dict[tuple[str, int], list[int]]:
    anims = anim_payload.get("anims")
    if not isinstance(anims, dict):
        _fail("Yone actor anim is missing anims")
    expected: dict[tuple[str, int], list[int]] = {}
    for action, count in BODY_ACTION_COUNTS.items():
        frames = anims.get(action, {}).get("frames")
        if not isinstance(frames, list) or len(frames) < count:
            _fail(f"Yone native action {action!r} has fewer than {count} body frames")
        for index in range(count):
            frame = frames[index]
            data = frame.get("data") if isinstance(frame, dict) else None
            if not isinstance(data, dict):
                _fail(f"Yone native {action}[{index}] has no data rect")
            expected[(action, index)] = [
                data.get("x"),
                data.get("y"),
                data.get("w"),
                data.get("h"),
            ]
    if len(expected) != EXPECTED_BODY_FRAME_COUNT:
        _fail(
            f"internal body frame contract is {len(expected)}, "
            f"expected {EXPECTED_BODY_FRAME_COUNT}"
        )
    return expected


def _validate_binary_palette(
    image: Image.Image,
    palette: Palette,
    *,
    label: str,
    bright_pixel_floor: int = 8,
    dark_pixel_floor: int = 12,
) -> dict[str, Any]:
    pixels = _rgba_pixels(image)
    unknown = set(pixels) - set(palette.colors)
    if unknown:
        _fail(f"{label} contains RGBA outside fixed palette: {sorted(unknown)[:5]}")
    alpha_values = {color[3] for color in pixels}
    if not alpha_values <= {0, 255}:
        _fail(f"{label} contains soft alpha values: {sorted(alpha_values)}")
    contaminated = {color for color in pixels if color[3] == 0 and color[:3] != (0, 0, 0)}
    if contaminated:
        _fail(f"{label} has RGB under transparent pixels: {sorted(contaminated)[:5]}")
    visible = [color for color in pixels if color[3] == 255]
    if not visible:
        _fail(f"{label} is empty")
    bright_pixels = sum(_luminance(color) >= 150 for color in visible)
    dark_pixels = sum(_luminance(color) <= 60 for color in visible)
    if bright_pixels < bright_pixel_floor:
        _fail(
            f"{label} has only {bright_pixels} bright pixels; "
            f"minimum is {bright_pixel_floor}"
        )
    if dark_pixels < dark_pixel_floor:
        _fail(
            f"{label} has only {dark_pixels} dark pixels; "
            f"minimum is {dark_pixel_floor}"
        )
    return {
        "visible_pixels": len(visible),
        "bright_pixels": bright_pixels,
        "dark_pixels": dark_pixels,
        "bright_pixel_floor": bright_pixel_floor,
        "dark_pixel_floor": dark_pixel_floor,
        "opaque_palette_colors": len(set(visible)),
    }


def _validate_v7_quality(image: Image.Image, *, action: str, index: int) -> dict[str, Any]:
    label = f"{action}[{index}]"
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        _fail(f"{label} is empty")
    visible = [color for color in _rgba_pixels(image) if color[3] == 255]
    lumas = sorted(_luminance(color) for color in visible)
    low = lumas[len(lumas) // 10]
    high = lumas[min(len(lumas) - 1, (len(lumas) * 9) // 10)]
    contrast = high - low
    dark_ratio = sum(luma <= 60 for luma in lumas) / len(lumas)
    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    density = len(visible) / max(1, area)
    alpha = image.getchannel("A")
    core_top = bbox[1] + (bbox[3] - bbox[1]) // 4
    core_bottom = bbox[1] + ((bbox[3] - bbox[1]) * 3) // 4
    row_widths: list[int] = []
    for y in range(core_top, max(core_top + 1, core_bottom)):
        xs = [x for x in range(bbox[0], bbox[2]) if alpha.getpixel((x, y))]
        if xs:
            row_widths.append(max(xs) - min(xs) + 1)
    row_widths.sort()
    core_width = row_widths[len(row_widths) // 2] if row_widths else 0
    if contrast < 58:
        _fail(f"{label} V7 luminance contrast is too low: {contrast:.2f}")
    if not 0.06 <= dark_ratio <= 0.84:
        _fail(f"{label} V7 dark ratio is outside 0.06..0.84: {dark_ratio:.4f}")
    if density < 0.10:
        _fail(f"{label} V7 body density is too low: {density:.4f}")
    if action in {"idle", "run", "hit", "skill2", "skill2_dash", "skill2_attack"}:
        if bbox[2] - bbox[0] < 13:
            _fail(f"{label} has an abnormally narrow body bbox: {bbox}")
        if core_width < 8:
            _fail(f"{label} has an abnormally narrow central body: {core_width}px")
    return {
        "alpha_bbox": list(bbox),
        "body_density": round(density, 4),
        "luminance_contrast_p80": round(contrast, 2),
        "dark_ratio": round(dark_ratio, 4),
        "core_width_p50": core_width,
    }


def _validate_zero_clip(image: Image.Image, *, label: str) -> None:
    alpha = image.getchannel("A")
    edge = Counter()
    for x in range(image.width):
        edge["top"] += alpha.getpixel((x, 0)) != 0
        edge["bottom"] += alpha.getpixel((x, image.height - 1)) != 0
    for y in range(image.height):
        edge["left"] += alpha.getpixel((0, y)) != 0
        edge["right"] += alpha.getpixel((image.width - 1, y)) != 0
    if any(edge.values()):
        _fail(f"{label} touches a native frame edge (clip risk): {dict(edge)}")


def _pixels_in_rect(
    image: Image.Image,
    rect: tuple[int, int, int, int],
) -> Iterable[tuple[int, int, tuple[int, int, int, int]]]:
    x, y, width, height = rect
    for local_y in range(y, y + height):
        for local_x in range(x, x + width):
            yield local_x, local_y, image.getpixel((local_x, local_y))


def _largest_connected_component(
    points: set[tuple[int, int]],
) -> tuple[int, tuple[int, int, int, int] | None]:
    remaining = set(points)
    largest: set[tuple[int, int]] = set()
    while remaining:
        start = remaining.pop()
        component = {start}
        queue: deque[tuple[int, int]] = deque([start])
        while queue:
            x, y = queue.popleft()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        if len(component) > len(largest):
            largest = component
    if not largest:
        return 0, None
    xs = [point[0] for point in largest]
    ys = [point[1] for point in largest]
    return len(largest), (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def validate_frame_annotations(
    row: dict[str, Any],
    image: Image.Image,
    palette: Palette,
    *,
    label: str,
) -> dict[str, Any]:
    """Validate explicit V7 coordinates and the readable front-idle face."""

    action = row["action"]
    index = row["index"]
    face_raw = row.get("face_bbox")
    mask_raw = row.get("mask_bbox")
    eyes_raw = row.get("eye_pixels")
    feet_raw = row.get("foot_zones")
    face_visibility = row.get("face_visibility")
    if face_visibility is not None and face_visibility not in FACE_VISIBILITY_VALUES:
        _fail(
            f"{label}.face_visibility must be one of "
            f"{sorted(FACE_VISIBILITY_VALUES)}, got {face_visibility!r}"
        )
    if not isinstance(eyes_raw, list):
        _fail(f"{label}.eye_pixels must be a list")
    if not isinstance(feet_raw, list):
        _fail(f"{label}.foot_zones must be a list")

    face_required = action in FRONT_FACE_ACTIONS
    if face_visibility == "hidden" and (
        face_raw is not None or mask_raw is not None or eyes_raw
    ):
        _fail(f"{label} hidden face cannot carry face/eye/mask annotations")
    if face_required and (face_raw is None or mask_raw is None or not eyes_raw):
        _fail(f"{label} needs dynamically detected face/eye/mask annotations")
    if face_raw is None:
        if eyes_raw:
            _fail(f"{label} cannot declare eye pixels without a face_bbox")
        if mask_raw is not None:
            _fail(f"{label} cannot declare mask_bbox without a face_bbox")
        face_stats: dict[str, Any] = {
            "face_skin_pixels": 0,
            "connected_skin_pixels": 0,
            "eye_pixels": 0,
            "eye_outline_pixels": 0,
            "mask_pixels": 0,
        }
    else:
        face = _rect(face_raw, label=f"{label}.face_bbox", size=image.size)
        minimum_size = IDLE_FACE_MIN_SIZE if face_required else (3, 4)
        if face_required and (face[2] < minimum_size[0] or face[3] < minimum_size[1]):
            _fail(
                f"{label}.face_bbox must be at least {minimum_size[0]}x{minimum_size[1]}: "
                f"{face_raw}"
            )

        skin_colors = palette.semantic_colors("skin")
        skin_points = {
            (x, y)
            for x, y, color in _pixels_in_rect(image, face)
            if color in skin_colors
        }
        minimum_skin = IDLE_CONNECTED_SKIN_MIN if face_required else 3
        if len(skin_points) < minimum_skin:
            _fail(
                f"{label}.face_bbox contains {len(skin_points)} explicit skin-role pixels; "
                f"minimum is {minimum_skin}"
            )
        connected_skin, connected_bbox = _largest_connected_component(skin_points)
        if face_required and connected_skin < IDLE_CONNECTED_SKIN_MIN:
            _fail(
                f"{label} largest real connected skin block is {connected_skin}px; "
                f"minimum is {IDLE_CONNECTED_SKIN_MIN}px"
            )
        skin_pixels = [image.getpixel(point) for point in skin_points]
        mean_skin_luma = sum(_luminance(color) for color in skin_pixels) / len(skin_pixels)
        # Front-facing card/readability poses keep the strong 120 floor.  A
        # fast profile swing can legitimately expose only the authored shadow
        # side of the face, but must still remain visibly separated from hair.
        face_luminance_floor = 120 if face_visibility == "front" else 96
        if mean_skin_luma < face_luminance_floor:
            _fail(
                f"{label} face is too dark: mean skin luminance="
                f"{mean_skin_luma:.1f}, minimum={face_luminance_floor}"
            )

        eye_colors = frozenset(
            color
            for color in palette.colors
            if color[3] == 255 and _luminance(color) <= 52
        )
        eye_outline_colors = eye_colors
        eye_points: list[tuple[int, int]] = []
        for eye_index, point in enumerate(eyes_raw):
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(type(value) is not int for value in point)
            ):
                _fail(f"{label}.eye_pixels[{eye_index}] must be [x,y]")
            x, y = point
            if not (0 <= x < image.width and 0 <= y < image.height):
                _fail(f"{label}.eye_pixels[{eye_index}] is out of bounds: {point}")
            if not (face[0] <= x < face[0] + face[2] and face[1] <= y < face[1] + face[3]):
                _fail(f"{label}.eye_pixels[{eye_index}] is outside face_bbox: {point}")
            if image.getpixel((x, y)) not in eye_colors:
                _fail(
                    f"{label}.eye_pixels[{eye_index}] must point to a real dark "
                    "final-scale pixel (luminance <= 52)"
                )
            eye_points.append((x, y))
        if face_required and not set(eye_points):
            _fail(f"{label} needs at least one explicit readable eye pixel")

        outline_points = {
            (x, y)
            for x, y, color in _pixels_in_rect(image, face)
            if color in eye_outline_colors
        }
        if face_required and not outline_points:
            _fail(f"{label} needs at least one real dark eye cue inside face_bbox")
        if face_required:
            framed_eye = any(
                point in outline_points
                or any(
                    (point[0] + dx, point[1] + dy) in outline_points
                    for dx in (-1, 0, 1)
                    for dy in (-1, 0, 1)
                    if dx or dy
                )
                for point in set(eye_points)
            )
            if not framed_eye:
                _fail(f"{label} explicit eye has no adjacent dark eye_outline frame")
            # A hair/forehead outline on the outer edge of face_bbox is not a
            # readable eye.  At least one annotated eye must sit inside the
            # upper/middle face and touch real skin locally.  One good profile
            # eye is sufficient; V7 deliberately does not demand two dots.
            inner_eye_bottom = face[1] + max(2, (face[3] * 2) // 3)
            clear_eye_points = {
                point
                for point in set(eye_points)
                if face[0] + 1 <= point[0] < face[0] + face[2] - 1
                and face[1] + 1 <= point[1] < inner_eye_bottom
                and any(
                    (point[0] + dx, point[1] + dy) in skin_points
                    for dx in (-1, 0, 1)
                    for dy in (-1, 0, 1)
                    if dx or dy
                )
            }
            if not clear_eye_points:
                _fail(
                    f"{label} needs one clear interior eye point beside real skin; "
                    "outer hair/face-box border pixels do not count"
                )
        else:
            clear_eye_points = set()

        mask_pixels = 0
        if mask_raw is not None:
            mask = _rect(mask_raw, label=f"{label}.mask_bbox", size=image.size)
            mask_colors = palette.semantic_colors("mask")
            mask_pixels = sum(
                color in mask_colors for _x, _y, color in _pixels_in_rect(image, mask)
            )
            if mask_pixels < (4 if face_required else 1):
                _fail(f"{label}.mask_bbox does not contain enough exact mask-role pixels")
            intersection_width = max(
                0, min(face[0] + face[2], mask[0] + mask[2]) - max(face[0], mask[0])
            )
            intersection_height = max(
                0, min(face[1] + face[3], mask[1] + mask[3]) - max(face[1], mask[1])
            )
            if face_required and intersection_width * intersection_height > face[2] * face[3] // 3:
                _fail(f"{label} mask covers more than one third of the readable face box")

        face_stats = {
            "face_skin_pixels": len(skin_points),
            "connected_skin_pixels": connected_skin,
            "connected_skin_bbox": list(connected_bbox) if connected_bbox else None,
            "face_mean_luminance": round(mean_skin_luma, 2),
            "eye_pixels": len(set(eye_points)),
            "eye_outline_pixels": len(outline_points),
            "clear_interior_eye_pixels": len(clear_eye_points),
            "mask_pixels": mask_pixels,
        }

    foot_zones: list[tuple[int, int, int, int]] = []
    for zone_index, zone_raw in enumerate(feet_raw):
        zone = _rect(zone_raw, label=f"{label}.foot_zones[{zone_index}]", size=image.size)
        if zone[1] < image.height // 2:
            _fail(f"{label}.foot_zones[{zone_index}] is above the lower body")
        if not any(color[3] for _x, _y, color in _pixels_in_rect(image, zone)):
            _fail(f"{label}.foot_zones[{zone_index}] contains no actor pixels")
        foot_zones.append(zone)
    if action in FOOT_REQUIRED_ACTIONS and not foot_zones:
        _fail(f"{label} needs at least one explicit foot zone")

    return {
        **face_stats,
        "face_visibility": face_visibility,
        "foot_zone_count": len(foot_zones),
    }


def _validate_card_preview(
    preview_path: Path,
    idle_source: Image.Image,
    idle_row: dict[str, Any],
    palette: Palette,
) -> dict[str, Any]:
    preview = Image.open(preview_path)
    if preview.format != "PNG" or preview.mode != "RGBA" or preview.size != CARD_PREVIEW_SIZE:
        _fail(
            f"V7 body_preview must be RGBA {CARD_PREVIEW_SIZE}, got "
            f"{preview.format} {preview.mode} {preview.size}"
        )

    rendered = idle_source.resize(
        (
            round(idle_source.width * CARD_SCALE),
            round(idle_source.height * CARD_SCALE),
        ),
        Image.Resampling.NEAREST,
    )
    x = (CARD_PREVIEW_SIZE[0] - rendered.width) // 2
    y = (CARD_STAGE_HEIGHT - rendered.height) // 2
    if y < 0:
        _fail(f"idle[0] scaled height {rendered.height} exceeds the {CARD_STAGE_HEIGHT}px card stage")

    if set(_pixels(preview.getchannel("A"))) != {255}:
        _fail("V7 body_preview must be the complete opaque 141x138 card surface")

    # Rebuild the generator's real card QA surface independently.  Comparing
    # all bytes proves both the exact actor route and the rounded card chrome,
    # divider and right-side UI placeholders used during visual review.
    expected = Image.new("RGBA", CARD_PREVIEW_SIZE, CARD_OUTER_FILL)
    draw = ImageDraw.Draw(expected)
    draw.rounded_rectangle(
        (4, 4, 137, 136),
        radius=11,
        fill=CARD_INNER_FILL,
        outline=CARD_BORDER_COLOR,
        width=1,
    )
    draw.line(
        (5, CARD_DIVIDER_Y, 136, CARD_DIVIDER_Y),
        fill=CARD_DIVIDER_COLOR,
        width=1,
    )
    expected.alpha_composite(rendered, (x, y))
    draw.arc((99, 72, 112, 88), 290, 70, fill=(236, 238, 242, 255), width=2)
    draw.rectangle((119, 76, 130, 87), outline=(217, 220, 228, 255), width=2)
    draw.rectangle((122, 79, 127, 84), fill=(104, 110, 125, 255))
    if preview.tobytes() != expected.tobytes():
        _fail(
            "V7 body_preview is not the exact complete 141x138 card route "
            "(rounded chrome + divider + UI + idle[0] 2.2x NEAREST)"
        )

    actor_mask = Image.new("L", CARD_PREVIEW_SIZE, 0)
    actor_mask.paste(rendered.getchannel("A"), (x, y))
    actor_bbox = actor_mask.getbbox()
    if actor_bbox is None:
        _fail("V7 card actor route is empty")

    divider_clearance = CARD_DIVIDER_Y - actor_bbox[3]
    if divider_clearance < CARD_DIVIDER_CLEARANCE:
        _fail(
            f"V7 actor feet/weapon approach the card divider: clearance={divider_clearance}px"
        )
    # V7 is the battle-actor contract.  Its authored off-hand blade may enter
    # the old native card icon zone; live BP/management portraits are supplied
    # by separate UI-only textures and validated by their own route tests.
    ui_icon_overlap = actor_mask.crop(CARD_UI_ICON_SAFE_RECT).getbbox() is not None
    if actor_mask.crop((0, CARD_DIVIDER_Y, 141, 138)).getbbox() is not None:
        _fail("V7 actor enters the divider/name band")

    face = _rect(idle_row["face_bbox"], label="idle[0].face_bbox", size=idle_source.size)
    skin_colors = palette.semantic_colors("skin")
    rendered_skin = sum(
        color in skin_colors
        for _x, _y, color in _pixels_in_rect(rendered, (0, 0, *rendered.size))
    )
    if rendered_skin < IDLE_CARD_SKIN_MIN:
        _fail(
            f"V7 real card actor has only {rendered_skin} scaled skin pixels; "
            f"minimum is {IDLE_CARD_SKIN_MIN}"
        )
    rendered_face = (
        x + round(face[0] * CARD_SCALE),
        y + round(face[1] * CARD_SCALE),
        max(1, round(face[2] * CARD_SCALE)),
        max(1, round(face[3] * CARD_SCALE)),
    )
    _rect(list(rendered_face), label="body_preview rendered face", size=preview.size)
    return {
        "size": list(preview.size),
        "fully_opaque_complete_card": True,
        "actor_alpha_bbox": list(actor_bbox),
        "actor_origin": [x, y],
        "actor_scaled_size": list(rendered.size),
        "actor_route": "idle[0] -> 2.2x NEAREST -> complete 141x138 card chrome",
        "actor_pixels_exact": True,
        "card_pixels_exact": True,
        "divider_clearance": divider_clearance,
        "ui_icon_safe_rect": list(CARD_UI_ICON_SAFE_RECT),
        "ui_icon_overlap_allowed_for_battle_actor": ui_icon_overlap,
        "ui_portrait_route_is_separate": True,
        "rendered_skin_pixels": rendered_skin,
        "rendered_face_bbox": list(rendered_face),
    }


def _is_retired_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in RETIRED_BODY_PATHS or any(
        normalized.startswith(prefix) for prefix in RETIRED_BODY_PREFIXES
    )


def _validate_retired_paths(mod_root: Path) -> None:
    existing = sorted(path for path in RETIRED_BODY_PATHS if (mod_root / path).exists())
    for prefix in RETIRED_BODY_PREFIXES:
        prefix_path = mod_root / prefix.rstrip("/")
        if prefix_path.exists():
            existing.extend(
                str(path.relative_to(mod_root)).replace("\\", "/")
                for path in prefix_path.rglob("*")
                if path.is_file()
            )
    if existing:
        _fail("retired V3-V6 body paths still exist:\n" + "\n".join(sorted(set(existing))))

    manifest = _read_json(mod_root / RELEASE_MANIFEST.relative_to(MOD_ROOT))
    rows = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(rows, list):
        _fail("release build_manifest.json has no files list")
    manifest_paths = {
        row.get("path").replace("\\", "/")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    leaked = sorted(path for path in manifest_paths if _is_retired_path(path))
    if leaked:
        _fail("retired V3-V6 body paths entered release manifest:\n" + "\n".join(leaked))


def _validate_dual_sword_cues(
    sources: dict[tuple[str, int], Image.Image],
    palette: Palette,
    rows_by_key: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    """Prove the final 1x pixels carry both weapon families and action weight.

    The final palette is deliberately fixed.  The cold near-white
    ``source_03``/``source_04`` roles carry the wind-steel edge, while the exact
    ``mask_*`` family supplies the Azakana-red edge.  Distance is measured from
    the annotated face center so a face mask, collar or sash cannot by itself
    satisfy a long-blade cue.  These checks read the final native PNGs; the
    manifest's ``weapons_present`` declaration is never accepted as evidence.
    """

    steel_colors = palette.exact_role("source_03") | palette.exact_role("source_04")
    azakana_colors = palette.semantic_colors("mask")
    if not steel_colors or not azakana_colors:
        _fail("V7 palette is missing steel-white or Azakana-red cue colors")

    def cue_stats(
        key: tuple[str, int],
        colors: frozenset[tuple[int, int, int, int]],
    ) -> dict[str, float | int]:
        image = sources[key]
        row = rows_by_key[key]
        face = row.get("face_bbox")
        if (
            not isinstance(face, list)
            or len(face) != 4
            or any(type(value) is not int for value in face)
        ):
            bbox = image.getchannel("A").getbbox()
            assert bbox is not None
            center_x = (bbox[0] + bbox[2] - 1) / 2
            center_y = (bbox[1] + bbox[3] - 1) / 2
        else:
            center_x = face[0] + (face[2] - 1) / 2
            center_y = face[1] + (face[3] - 1) / 2
        points = [
            (x, y)
            for y in range(image.height)
            for x in range(image.width)
            if image.getpixel((x, y)) in colors
        ]
        farthest = max(
            (((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5 for x, y in points),
            default=0.0,
        )
        return {"pixels": len(points), "farthest_from_face": round(farthest, 3)}

    action_reports: dict[str, list[dict[str, Any]]] = {}

    def validate_each(
        action: str,
        *,
        steel_pixels: int = 0,
        steel_distance: float = 0.0,
        azakana_pixels: int = 0,
        azakana_distance: float = 0.0,
    ) -> None:
        action_reports[action] = []
        for index in range(BODY_ACTION_COUNTS[action]):
            key = (action, index)
            steel = cue_stats(key, steel_colors)
            azakana = cue_stats(key, azakana_colors)
            if (
                steel["pixels"] < steel_pixels
                or steel["farthest_from_face"] < steel_distance
            ):
                _fail(
                    f"{action}[{index}] lost its final-pixel steel cue: "
                    f"pixels={steel['pixels']} distance={steel['farthest_from_face']}"
                )
            if (
                azakana["pixels"] < azakana_pixels
                or azakana["farthest_from_face"] < azakana_distance
            ):
                _fail(
                    f"{action}[{index}] lost its final-pixel Azakana cue: "
                    f"pixels={azakana['pixels']} distance={azakana['farthest_from_face']}"
                )
            action_reports[action].append(
                {"index": index, "steel": steel, "azakana": azakana}
            )

    idle_reports: dict[str, dict[str, int]] = {}
    for index in range(BODY_ACTION_COUNTS["idle"]):
        image = sources[("idle", index)]
        steel_pixels = sum(
            image.getpixel((x, y)) in steel_colors
            for y in range(image.height // 2, image.height)
            for x in range(0, min(15, image.width))
        )
        red_pixels = sum(
            image.getpixel((x, y)) in azakana_colors
            for y in range(image.height // 3, image.height)
            for x in range((image.width * 2) // 3, image.width)
        )
        if steel_pixels < 1 or red_pixels < 4:
            _fail(
                f"idle[{index}] must retain opposing steel/red weapon cues; "
                f"got steel={steel_pixels}, red={red_pixels}"
            )
        idle_reports[f"idle[{index}]"] = {
            "steel_lower_left_pixels": steel_pixels,
            "azakana_lower_right_pixels": red_pixels,
        }

    # Every neutral frame must show two distinct weapon families.  Active
    # attacks are stricter about their leading blade; wind-up frames may keep
    # the off-hand blade compact, while their sequence still has to expose it.
    validate_each("idle", steel_pixels=6, steel_distance=26.0, azakana_distance=23.0)
    validate_each("run", steel_pixels=5, steel_distance=25.0, azakana_distance=17.0)
    validate_each("attack", steel_pixels=5, steel_distance=17.0, azakana_distance=17.0)
    validate_each("attack_azakana", azakana_pixels=20, azakana_distance=13.5)
    validate_each("skill", azakana_distance=22.0)
    validate_each("skill_q3", azakana_distance=22.5)
    validate_each("skill2_attack", azakana_pixels=50, azakana_distance=22.0)
    validate_each("ult", azakana_pixels=30)

    def count_extended(action: str, weapon: str, distance: float) -> int:
        return sum(
            report[weapon]["farthest_from_face"] >= distance
            for report in action_reports[action]
        )

    sequence_requirements = {
        "attack_azakana_offhand_steel_frames": (
            sum(report["steel"]["pixels"] >= 1 for report in action_reports["attack_azakana"]),
            4,
        ),
        "q12_extended_steel_frames": (count_extended("skill", "steel", 20.0), 4),
        "q3_extended_steel_frames": (count_extended("skill_q3", "steel", 20.0), 6),
        "w_offhand_steel_frames": (
            sum(report["steel"]["pixels"] >= 1 for report in action_reports["skill2_attack"]),
            3,
        ),
        "r_extended_steel_frames": (count_extended("ult", "steel", 25.0), 8),
        "r_extended_azakana_frames": (count_extended("ult", "azakana", 25.0), 7),
    }
    for label, (actual, minimum) in sequence_requirements.items():
        if actual < minimum:
            _fail(f"{label} regressed: {actual} < {minimum}")

    def sequence_digest(action: str) -> str:
        digest = hashlib.sha256()
        for index in range(BODY_ACTION_COUNTS[action]):
            image = sources[(action, index)]
            digest.update(image.width.to_bytes(2, "little"))
            digest.update(image.height.to_bytes(2, "little"))
            digest.update(image.tobytes())
        return digest.hexdigest()

    sequence_digests = {
        action: sequence_digest(action)
        for action in ("attack", "attack_azakana", "skill", "skill_q3")
    }
    if sequence_digests["attack"] == sequence_digests["attack_azakana"]:
        _fail("steel and Azakana basic attacks resolve to identical source pixels")
    if sequence_digests["skill"] == sequence_digests["skill_q3"]:
        _fail("Q1/Q2 and Q3 resolve to identical source pixels")

    return {
        "idle": idle_reports,
        "actions": action_reports,
        "sequence_requirements": {
            label: {"actual": actual, "minimum": minimum}
            for label, (actual, minimum) in sequence_requirements.items()
        },
        "sequence_sha256": sequence_digests,
        "distinct_attack_sequences": True,
        "distinct_q_sequences": True,
    }


def validate_v7(
    manifest_path: Path = FRAME_MANIFEST,
    *,
    mod_root: Path = MOD_ROOT,
    verify_runtime_atlas: bool = True,
    verify_retired_paths: bool = False,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    payload = _read_json(manifest_path)
    if not isinstance(payload, dict):
        _fail("frames.json must be an object")
    if (
        payload.get("schema_version") != EXPECTED_SCHEMA_VERSION
        or payload.get("route") != EXPECTED_ROUTE
    ):
        _fail("frames.json must declare schema_version=7 and dual-sword-v7")
    if payload.get("atlas_size") != list(EXPECTED_ATLAS_SIZE):
        _fail(f"frames.json atlas_size must be {list(EXPECTED_ATLAS_SIZE)}")
    if payload.get("weapon_contract") != EXPECTED_WEAPON_CONTRACT:
        _fail("frames.json weapon_contract does not match the V7 semantic contract")
    declared_visibility = payload.get("face_visibility_values")
    if declared_visibility is not None and (
        not isinstance(declared_visibility, list)
        or any(not isinstance(value, str) for value in declared_visibility)
        or set(declared_visibility) != FACE_VISIBILITY_VALUES
        or len(declared_visibility) != len(FACE_VISIBILITY_VALUES)
    ):
        _fail(
            "frames.json face_visibility_values must contain front/profile/hidden "
            "exactly once"
        )
    source_root = manifest_path.parent
    palette_path = _safe_relative_file(
        source_root, payload.get("palette_file"), label="palette_file"
    )
    palette = load_palette(palette_path)
    preview_path = _safe_relative_file(
        source_root, payload.get("body_preview"), label="body_preview"
    )
    if preview_path.suffix.lower() != ".png":
        _fail(f"body_preview must end in .png: {preview_path}")

    anim_path = mod_root / ACTOR_ANIM.relative_to(MOD_ROOT)
    if not anim_path.is_file():
        _fail("V7 runtime actor anim is missing")
    anim_payload = _read_json(anim_path)
    animation_contract = _validate_animation_contract(anim_payload)
    expected = _expected_actor_frames(anim_payload)
    atlas: Image.Image | None = None
    if verify_runtime_atlas:
        atlas_path = mod_root / ACTOR_ATLAS.relative_to(MOD_ROOT)
        if not atlas_path.is_file():
            _fail("V7 runtime actor atlas is missing")
        atlas = Image.open(atlas_path)
        if atlas.format != "PNG" or atlas.mode != "RGBA" or atlas.size != EXPECTED_ATLAS_SIZE:
            _fail(
                f"V7 actor atlas must be RGBA {EXPECTED_ATLAS_SIZE}, got "
                f"{atlas.format} {atlas.mode} {atlas.size}"
            )
    rows = payload.get("frames")
    if not isinstance(rows, list) or len(rows) != EXPECTED_BODY_FRAME_COUNT:
        actual_count = len(rows) if isinstance(rows, list) else None
        _fail(
            f"frames.json must contain exactly {EXPECTED_BODY_FRAME_COUNT} "
            f"body frames, got {actual_count}"
        )

    seen_keys: set[tuple[str, int]] = set()
    seen_files: set[str] = set()
    reports: dict[str, Any] = {}
    sources: dict[tuple[str, int], Image.Image] = {}
    rows_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    used_opaque_colors: set[tuple[int, int, int, int]] = set()
    visibility_presence: list[bool] = []
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"frames[{position}] must be an object")
        required = {
            "action",
            "index",
            "file",
            "rect",
            "bottom_margin",
            "face_bbox",
            "eye_pixels",
            "mask_bbox",
            "foot_zones",
            "active_weapon",
            "weapons_present",
        }
        missing = required - set(row)
        if missing:
            _fail(f"frames[{position}] is missing fields: {sorted(missing)}")
        action = row.get("action")
        index = row.get("index")
        if not isinstance(action, str) or type(index) is not int:
            _fail(f"frames[{position}] action/index types are invalid")
        visibility_presence.append("face_visibility" in row)
        key = (action, index)
        label = f"{action}[{index}]"
        if key in seen_keys:
            _fail(f"duplicate V7 frame key: {label}")
        seen_keys.add(key)
        if key not in expected:
            _fail(f"unexpected V7 body frame: {label}")
        if row.get("active_weapon") != ACTIVE_WEAPON_BY_ACTION[action]:
            _fail(
                f"{label}.active_weapon must be "
                f"{ACTIVE_WEAPON_BY_ACTION[action]!r}, got {row.get('active_weapon')!r}"
            )
        if row.get("weapons_present") != ["steel", "azakana"]:
            _fail(
                f"{label}.weapons_present must preserve both steel and Azakana swords"
            )
        if row.get("rect") != expected[key]:
            _fail(f"{label}.rect {row.get('rect')} != native exact rect {expected[key]}")
        atlas_rect = _rect(row["rect"], label=f"{label}.rect", size=EXPECTED_ATLAS_SIZE)

        file_raw = row.get("file")
        if not isinstance(file_raw, str):
            _fail(f"{label}.file must be a relative PNG path")
        if file_raw in seen_files:
            _fail(f"source frame path is reused: {file_raw}")
        seen_files.add(file_raw)
        source_path = _safe_relative_file(source_root, file_raw, label=f"{label}.file")
        if source_path.suffix.lower() != ".png":
            _fail(f"{label}.file must be PNG")
        source = Image.open(source_path)
        if (
            source.format != "PNG"
            or source.mode != "RGBA"
            or source.size != (atlas_rect[2], atlas_rect[3])
        ):
            _fail(
                f"{label} source must be exact RGBA native rect "
                f"{(atlas_rect[2], atlas_rect[3])}, got "
                f"{source.format} {source.mode} {source.size}"
            )
        # The collapsing terminal defeat silhouette is intentionally tiny and
        # face-hidden.  Keep the normal contrast floor on every playable pose,
        # including idle/card-critical frames, while allowing that one class
        # to retain its authored native silhouette without generator repaint.
        tiny_dead = action == "dead" and index >= 3
        bright_floor = 1 if tiny_dead else 8
        dark_floor = 2 if tiny_dead else 12
        source_stats = _validate_binary_palette(
            source,
            palette,
            label=label,
            bright_pixel_floor=bright_floor,
            dark_pixel_floor=dark_floor,
        )
        used_opaque_colors.update(
            color for color in _pixels(source) if color[3] == 255
        )
        _validate_zero_clip(source, label=label)
        alpha_bbox = source.getchannel("A").getbbox()
        assert alpha_bbox is not None
        bottom_margin = source.height - alpha_bbox[3]
        if type(row.get("bottom_margin")) is not int or row["bottom_margin"] != bottom_margin:
            _fail(f"{label}.bottom_margin {row.get('bottom_margin')} != exact {bottom_margin}")
        if action != "dead" and bottom_margin < 2:
            _fail(f"{label} has only {bottom_margin}px bottom safety margin")

        if atlas is not None:
            atlas_frame = atlas.crop(_bbox_to_pillow(atlas_rect))
            if atlas_frame.tobytes() != source.tobytes():
                _fail(
                    f"{label} source->atlas bytes differ (resample/quantize/clip is forbidden)"
                )
        annotation_stats = validate_frame_annotations(row, source, palette, label=label)
        quality_stats = _validate_v7_quality(source, action=action, index=index)
        reports[label] = {
            "file": file_raw,
            "rect": list(atlas_rect),
            "source_to_atlas_byte_identical": atlas is not None,
            "hard_alpha": True,
            "zero_resampling": True,
            "zero_quantize": True,
            "zero_clip": True,
            "bottom_margin": bottom_margin,
            **source_stats,
            **annotation_stats,
            **quality_stats,
        }
        sources[key] = source.copy()
        rows_by_key[key] = row

    if seen_keys != set(expected):
        _fail(
            "frames.json does not cover the exact 67-frame contract: "
            f"missing={sorted(set(expected) - seen_keys)}"
        )
    if any(visibility_presence) and not all(visibility_presence):
        _fail("face_visibility must be present on all 67 frames or omitted from all 67")
    if len(used_opaque_colors) > MAX_OPAQUE_PALETTE_COLORS:
        _fail(
            f"V7 body frames use {len(used_opaque_colors)} opaque colors; maximum is "
            f"{MAX_OPAQUE_PALETTE_COLORS}"
        )

    preview_report = _validate_card_preview(
        preview_path,
        sources[PRIMARY_IDLE_KEY],
        rows_by_key[PRIMARY_IDLE_KEY],
        palette,
    )
    generation_report = _validate_generation_qa(mod_root)
    dual_sword_report = _validate_dual_sword_cues(sources, palette, rows_by_key)
    if verify_retired_paths:
        _validate_retired_paths(mod_root)
    return {
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "route": EXPECTED_ROUTE,
        "atlas_size": list(EXPECTED_ATLAS_SIZE),
        "frame_count": len(reports),
        "palette_file": payload["palette_file"],
        "opaque_palette_limit": MAX_OPAQUE_PALETTE_COLORS,
        "opaque_palette_colors_used": len(used_opaque_colors),
        "eye_role_policy": ["eye_outline", "eye_highlight"],
        "body_transform": {
            "source_to_native_resampling": "LANCZOS",
            "native_to_atlas_resampling": "none" if atlas is not None else "not_checked",
            "quantize": "none",
            "clip": "none",
            "proof": (
                "exact per-frame RGBA byte identity"
                if atlas is not None
                else "source-only validation; runtime atlas check deferred"
            ),
        },
        "frames": reports,
        "body_preview": preview_report,
        "generation_qa": generation_report,
        "animation_contract": animation_contract,
        "weapon_contract": payload["weapon_contract"],
        "dual_sword": dual_sword_report,
        "runtime_atlas_verified": atlas is not None,
        "retired_v3_through_v6_body_paths_absent": verify_retired_paths,
    }


def main() -> int:
    try:
        report = validate_v7()
    except V7ValidationError as error:
        print(f"Yone V7 dual-sword validation FAILED: {error}", file=sys.stderr)
        return 1
    print(
        "Yone V7 dual-sword validation passed: "
        f"{report['frame_count']} frames, "
        f"{report['body_preview']['divider_clearance']}px card-divider clearance"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
