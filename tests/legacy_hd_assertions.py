"""Reusable visual acceptance gates for legacy champion HD upgrades.

These helpers deliberately validate runtime-sized outputs rather than large
source art.  They protect the common failure modes seen in the first legacy
champions: stretching a pose, enlarging a tiny battle frame for UI, covering
the BP name band, and routing one crop to every surface.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


def _open_rgba(path: Path) -> Image.Image:
    assert path.is_file(), f"missing HD asset: {path}"
    return Image.open(path).convert("RGBA")


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    assert bbox is not None, "HD asset is fully transparent"
    return bbox


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pixel_data(image: Image.Image):
    flattened = getattr(image, "get_flattened_data", None)
    return flattened() if flattened is not None else image.getdata()


def assert_legacy_hd_portrait_set(
    mod_root: Path,
    champion_id: str,
    *,
    side_card_relative: str | None = None,
) -> dict[str, tuple[int, int, int, int]]:
    """Validate independent encyclopedia, list, scoreboard and BP crops."""

    paths = {
        "encyclopedia": mod_root / "ui/champion_fullbody" / f"{champion_id}.png",
        "compact": mod_root / "ui/champion_portrait" / f"{champion_id}_compact.png",
        "scoreboard": mod_root
        / "ui/champion_portrait"
        / f"{champion_id}_scoreboard.png",
        "bp_grid": mod_root / "ui/champion_portrait" / f"{champion_id}_grid.png",
    }
    expected_sizes = {
        "encyclopedia": (64, 64),
        "compact": (64, 64),
        "scoreboard": (64, 64),
        "bp_grid": (90, 122),
    }
    bboxes: dict[str, tuple[int, int, int, int]] = {}
    hashes: dict[str, str] = {}
    for surface, path in paths.items():
        image = _open_rgba(path)
        assert image.size == expected_sizes[surface]
        bbox = alpha_bbox(image)
        bboxes[surface] = bbox
        hashes[surface] = file_sha256(path)
        # Source-direct portrait builders must emit hard, deterministic alpha
        # so transparent UI margins cannot turn into a dark halo in game.
        assert set(_pixel_data(image.getchannel("A"))).issubset({0, 255})

    for surface in ("encyclopedia", "compact", "scoreboard"):
        left, top, right, bottom = bboxes[surface]
        assert left >= 2 and right <= 62
        assert top >= 1 and bottom <= 61
    left, top, right, bottom = bboxes["bp_grid"]
    assert left >= 3 and right <= 87
    assert top >= 1
    assert bottom <= 86
    assert 96 - bottom >= 10, "BP hero pixels intrude into the y=96 name band"

    # Compact rows and tiny scoreboard squares require different face crops;
    # using one resized actor frame for both is a regression even at 64x64.
    assert hashes["compact"] != hashes["scoreboard"]
    assert hashes["encyclopedia"] != hashes["compact"]

    if side_card_relative is not None:
        side_card = mod_root / side_card_relative
        side_card_image = _open_rgba(side_card)
        alpha_bbox(side_card_image)
        assert file_sha256(side_card) not in set(hashes.values())
    return bboxes


def animation_frames(
    sheet_path: Path,
    anim_path: Path,
    tag: str,
) -> list[Image.Image]:
    sheet = _open_rgba(sheet_path)
    anims = json.loads(anim_path.read_text(encoding="utf-8"))["anims"]
    assert tag in anims
    frames: list[Image.Image] = []
    for row in anims[tag]["frames"]:
        data = row["data"]
        frames.append(
            sheet.crop(
                (
                    data["x"],
                    data["y"],
                    data["x"] + data["w"],
                    data["y"] + data["h"],
                )
            )
        )
    return frames


def assert_actor_tag_scale(
    sheet_path: Path,
    anim_path: Path,
    tag: str,
    *,
    min_height: int,
    max_height: int,
    baseline: int,
    min_unique_frames: int = 1,
) -> list[tuple[int, int, int, int]]:
    """Assert visible action frames share a stable 64px actor contract."""

    frames = animation_frames(sheet_path, anim_path, tag)
    bboxes = [alpha_bbox(frame) for frame in frames]
    for left, top, right, bottom in bboxes:
        assert min_height <= bottom - top <= max_height
        assert bottom == baseline
        assert left >= 2 and right <= 62
    hashes = {hashlib.sha256(frame.tobytes()).hexdigest() for frame in frames}
    assert len(hashes) >= min_unique_frames
    return bboxes


def assert_uniform_aspect_ratio(
    source_size: tuple[int, int],
    target_bbox: tuple[int, int, int, int],
    *,
    tolerance: float = 0.08,
) -> None:
    """Reject x-only/y-only scaling by comparing visible aspect ratios."""

    source_ratio = source_size[0] / source_size[1]
    target_ratio = (target_bbox[2] - target_bbox[0]) / (
        target_bbox[3] - target_bbox[1]
    )
    assert abs(target_ratio / source_ratio - 1.0) <= tolerance


def assert_readable_upper_detail(
    frame: Image.Image,
    *,
    min_opaque_pixels: int = 40,
    min_colors: int = 12,
) -> None:
    """Lightweight gate that catches a face/torso reduced to a color smudge."""

    left, top, right, bottom = alpha_bbox(frame)
    upper_bottom = top + max(1, round((bottom - top) * 0.55))
    upper = frame.crop((left, top, right, upper_bottom)).convert("RGBA")
    pixels = [pixel for pixel in _pixel_data(upper) if pixel[3] == 255]
    assert len(pixels) >= min_opaque_pixels
    assert len({pixel[:3] for pixel in pixels}) >= min_colors
