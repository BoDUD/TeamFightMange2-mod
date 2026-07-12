# Masked map landmark sources

This directory accepts nine independent, square ImageGen source images.  They
are optional for a safe build: when a file is absent, `pack_quality_map.py`
keeps the refined native landmark unchanged.  A source is never tiled or
copied outside its audited native mask.

Recommended source size is `1024x1024` RGBA.  RGB is accepted when the unused
area is one uniform deep-rift green (`#18382f`).  Art must be orthographic
top-down terrain only: no champion, monster, tower, nexus, river, road, wall,
brush, UI, text, logo, or perspective lighting.

| File | Packed canvas | Use |
| --- | ---: | --- |
| `baron_pit_source.png` | 192x192 | northwest Baron pit |
| `dragon_pit_source.png` | 192x192 | southeast Dragon pit |
| `jungle_camp_large_source.png` | 96x96 | four large neutral-camp pads |
| `jungle_camp_small_source.png` | 64x64 | four small neutral-camp pads |
| `tower_pad_source.png` | 96x96 | sixteen neutral tower foundations |
| `blue_nexus_pad_source.png` | 64x64 | blue nexus foundation only |
| `red_nexus_pad_source.png` | 64x64 | red nexus foundation only |
| `blue_spawn_platform_source.png` | 160x160 | blue official L-shaped spawn platform |
| `red_spawn_platform_source.png` | 160x160 | red official L-shaped spawn platform |

The exact half-open map coordinates, rotations, polygon/ellipse contours,
inward feather, wall/brush exclusions, and per-mask hashes are generated in
`qa/quality_map_imagegen_pack.json`.  The compositor retains a two-pixel native
rim and preserves `background_5v5` dimensions and alpha byte-for-byte.
