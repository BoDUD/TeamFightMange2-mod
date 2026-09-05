"""Reproduce 0.5.8's stock encyclopedia UV crop, then the layout-only fit.

This is an offline renderer model, NOT live acceptance. Derived from bundled
game_view cgu.15 init_champion_list+0x84f..0x874 (85,93,2 arguments) and
cgu.01 set_entity_icon_center+0x233..0x312 (UV) / +0x379..0x43b (layout).
Unlike the retired 2.2x/121px stage guess, negative center.y subtracts from
the sampled atlas coordinate and therefore moves the visible actor DOWN.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

MOD = Path(__file__).resolve().parents[1]
ACTORS = MOD / "aseprite_resources/champions"
TARGETS = {"dual_blader": "yone_v7", "dancer": "xayah"}


def native_geometry(rect, center, *, layout_factor=1.0, bottom=93.0):
    """UV is in atlas pixels; layout is in logical UI pixels, not frame pixels."""
    w, h = rect["w"], rect["h"]
    crop_w, crop_h = min(w, 85 / 2), min(h, 93 / 2)
    uv_x = rect["x"] + max(0, (w - 85 / 2) / 2) + center["x"]
    uv_y = rect["y"] + max(0, (h - 93 / 2) / 2) + center["y"]
    draw_w, draw_h = crop_w * 2 * layout_factor, crop_h * 2 * layout_factor
    return {
        "uv": [uv_x, uv_y, crop_w, crop_h],
        "layout": [(119 - draw_w) / 2, bottom - draw_h, draw_w, draw_h],
        "pixel_scale": 2 * layout_factor,
    }


def actor_geometry(sheet, rect, center, *, fitted=False):
    geometry = native_geometry(rect, center, layout_factor=.75 if fitted else 1,
                               bottom=76 if fitted else 93)
    frame = sheet.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"]))
    bbox = frame.getchannel("A").getbbox()
    assert bbox
    ux, uy, uw, uh = geometry["uv"]
    lx, ly, _, _ = geometry["layout"]
    scale = geometry["pixel_scale"]
    absolute = [bbox[0] + rect["x"], bbox[1] + rect["y"],
                bbox[2] + rect["x"], bbox[3] + rect["y"]]
    visible = [lx + (absolute[0] - ux) * scale, ly + (absolute[1] - uy) * scale,
               lx + (absolute[2] - ux) * scale, ly + (absolute[3] - uy) * scale]
    clipped_pixels = sum(1 for y in range(frame.height) for x in range(frame.width)
                         if frame.getpixel((x, y))[3] and
                         not (ux <= x + rect["x"] and x + rect["x"] + 1 <= ux + uw
                              and uy <= y + rect["y"] and y + rect["y"] + 1 <= uy + uh))
    geometry.update(actor_bbox=visible, source_pixels_clipped=clipped_pixels,
                    tier_clearance=70-visible[3], fullbody_height=visible[3]-visible[1])
    return geometry


def card_preview(sheet, geometry, label):
    """Diagnostic UI rendering only. Never exports/replaces champion art."""
    scale = 4
    card = Image.new("RGBA", (119*scale, 130*scale), "#20232c")
    ux, uy, uw, uh = geometry["uv"]
    lx, ly, lw, lh = geometry["layout"]
    sample = sheet.transform((round(lw*scale), round(lh*scale)), Image.Transform.EXTENT,
                             (ux, uy, ux+uw, uy+uh), resample=Image.Resampling.NEAREST)
    card.alpha_composite(sample, (round(lx*scale), round(ly*scale)))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((0, 0, 118*scale, 129*scale), 8*scale, outline="#778091", width=scale)
    draw.rounded_rectangle((4*scale, 70*scale, 68*scale, 92*scale), 8*scale, fill="#1b1e27", outline="#4b4d58", width=scale)
    draw.text((9*scale, 77*scale), "Unranked", fill="white", font_size=10*scale)
    draw.rectangle((77*scale, 72*scale, 95*scale, 90*scale), outline="#d2d7e4", width=3*scale)
    draw.rectangle((98*scale, 72*scale, 116*scale, 90*scale), outline="#d2d7e4", width=3*scale)
    draw.text((59.5*scale, 104*scale), label, anchor="mt", fill="white", font_size=13*scale)
    return card


def audit(output: Path | None = None):
    styles = json.loads((MOD / "style/champion_view.champion_view").read_text())["entries"]
    report = {"proof": "offline native UV/layout reproduction; live acceptance pending", "champions": {}}
    previews = []
    for champion, prefix in TARGETS.items():
        sheet = Image.open(ACTORS / f"{prefix}#sheet.png").convert("RGBA")
        anim = json.loads((ACTORS / f"{prefix}#anim.fanim").read_text())
        # ChampionInfoUIRunner samples time=0, not the entire idle cycle.
        rect = anim["anims"]["idle"]["frames"][0]["data"]
        before = actor_geometry(sheet, rect, {"x": 0, "y": -16 if champion == "dual_blader" else -12})
        after = actor_geometry(sheet, rect, styles[champion]["center"], fitted=True)
        assert before["source_pixels_clipped"] > 0, (champion, "must reproduce rejected 0.12.14")
        assert after["source_pixels_clipped"] == 0, (champion, after)
        assert 56 <= after["fullbody_height"] <= 60, (champion, after)
        assert after["tier_clearance"] >= 4, (champion, after)
        assert after["actor_bbox"][1] >= 6, (champion, after)
        report["champions"][champion] = {"before": before, "after": after}
        if output:
            previews.extend((card_preview(sheet, before, f"{prefix} before"), card_preview(sheet, after, f"{prefix} after")))
    if output:
        output.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", (4*500, 580), "#0b1018")
        ImageDraw.Draw(canvas).text((15, 10), "OFFLINE native UV/layout simulation - not an in-game screenshot", fill="white", font_size=24)
        for index, card in enumerate(previews):
            canvas.alpha_composite(card, (index*500+12, 50))
        canvas.save(output / "encyclopedia_native_before_after.png")
        (output / "encyclopedia_geometry.json").write_text(json.dumps(report, indent=2)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.output), indent=2))
