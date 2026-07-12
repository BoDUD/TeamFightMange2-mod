# Quality-upgrade imagegen record

Generation mode: Codex built-in `image_gen`. Each distinct deliverable was generated with one independent call. Original outputs remain under `C:/Users/OWNER/.codex/generated_images`; the files in this directory are preserved copies.

## Ban/pick splash illustrations

The five prompts used the same production contract: one original cinematic League-style fantasy splash illustration; a single fully visible champion matching the accepted in-mod Shen, Lucian, Orianna, Briar, or Sivir design; dynamic three-quarter action pose; strong readable silhouette; atmospheric Rift-like battleground; clean 284:172 composition with safe central framing; no text, logos, UI, border, watermark, duplicate character, or cropped head/feet. Runtime copies are 1420x860.

| Champion | Runtime id | Project source | Preserved generated original |
| --- | --- | --- | --- |
| Shen | `lol_shen` | `bp_splash/lol_shen.png` | `exec-ecb19f26-201a-4037-80d9-13a8f6794181.png` |
| Lucian | `archer` | `bp_splash/archer.png` | `exec-dba7b2f0-f2a5-4af7-bdbb-aa0b0e1a35f0.png` |
| Orianna | `barrier_magician` | `bp_splash/barrier_magician.png` | `exec-c136930b-0285-47ec-8eec-2f62354b4487.png` |
| Briar | `berserker` | `bp_splash/berserker.png` | `exec-5317dbff-923d-43a6-8cbb-844b97a51d84.png` |
| Sivir | `boomerang_hunter` | `bp_splash/boomerang_hunter.png` | `exec-373d9d4c-6117-47de-8c8c-0dd8b1c68e65.png` |

## Objective and jungle actor sheets

The actor prompts used this shared contract: one crisp handcrafted 32-bit pixel-art production contact sheet; strict top-down three-quarter game view facing screen-left; exactly a 4x4 grid on a perfectly solid `#FF00FF` chroma-key background; rows for idle, movement, attack, and hit/death progression; one consistent fully visible creature per cell; generous key-color padding; no text, labels, borders, UI, external shadows, crop, or extra creatures. The Baron target impact used a separate 4x2 contact sheet.

| Role | Project source | Preserved generated original |
| --- | --- | --- |
| Baron Nashor actor | `jungle/baron_action_contact.png` | `exec-398ed931-b72e-4bea-8efa-b01e06c9fa7b.png` |
| Baron target impact | `jungle/baron_target_impact_contact.png` | `exec-6559de0d-3971-4cb9-af5a-c3aced2bf9b6.png` |
| Infernal Drake | `jungle/dragon_infernal_action_contact.png` | `exec-598de639-3989-424f-8726-134ab49da429.png` |
| Ocean Drake | `jungle/dragon_ocean_action_contact.png` | `exec-a911fd89-42ee-4ed1-bf44-e1349b7ff913.png` |
| Mountain Drake | `jungle/dragon_mountain_action_contact.png` | `exec-5e696d79-55e1-4140-a10e-bf01f40e2121.png` |
| Cloud Drake | `jungle/dragon_cloud_action_contact.png` | `exec-46f3c318-74bf-4b8f-b6dc-3cc2f85dc2a8.png` |
| Hextech Drake | `jungle/dragon_hextech_action_contact.png` | `exec-a79db1a5-ed56-4762-ac02-bb7668abf144.png` |
| Elder Dragon | `jungle/dragon_elder_action_contact.png` | `exec-3764f71f-d614-4526-94f4-65587151aa0c.png` |
| Red Brambleback | `jungle/red_brambleback_action_contact.png` | `exec-9a3d6155-0c10-40fa-8e5d-9ef96b6aa79a.png` |
| Blue Sentinel | `jungle/blue_sentinel_action_contact.png` | `exec-05ba9743-19ee-40bb-bed0-d436d91f95c8.png` |
| Gromp | `jungle/gromp_action_contact.png` | `exec-ed7e4cf2-aa08-4abe-becb-8101b798f076.png` |
| Murk Wolf | `jungle/murk_wolf_action_contact.png` | `exec-f9f910b6-b66a-4b36-baf2-0d205c9f9191.png` |
| Crimson Raptor | `jungle/raptor_action_contact.png` | `exec-cf44f0e7-575b-4b8f-9486-1a727c0c8647.png` |
| Ancient Krug | `jungle/krug_action_contact.png` | `exec-6f6b7acc-4f5f-4653-b7ea-a8c83a642a4c.png` |

The Raptor prompt specified a crimson-orange hooked-beak predator with a ragged feather crest, dark red wing armor, ember accents, peck/slash attack, and collapse progression. The Krug prompt specified a squat layered tan-brown stone golem with amber cracks, thick fists, a heavy slam, and crumble progression.

## Defensive towers

The tower actor was generated as a 4x4 pixel-art contact sheet on solid `#FF00FF`: one tall grounded stone-and-dark-metal MOBA bastion with gold trim, a faceted cyan crown crystal, and a forward arcane cannon; eight fixed-baseline idle energy phases followed by six attack charge/release/recovery phases. The VFX was generated separately as a 4x3 contact sheet containing left-facing cyan projectiles and a tiny-spark-to-hex-ring impact progression. No tower shadow was painted into either source because the game owns a separate position-locked shadow layer.

| Role | Project source | Preserved generated original |
| --- | --- | --- |
| Tower actor | `jungle/tower_actor_contact.png` | `exec-82e6b9f5-c37a-44cc-8fa4-a54a3690dfa6.png` |
| Tower projectile and impact | `jungle/tower_vfx_contact.png` | `exec-04bbf05e-b551-42ec-9f7b-cee2986c53e7.png` |

Blue-team runtime art uses the generated cyan energy palette. Red-team art is a deterministic team-color derivation of the same generated geometry so both sides retain identical silhouette, size, frame anchors, and animation timing.

## Nexus / base crystals

The nexus source was generated with built-in imagegen as a strict 2x2 contact sheet on a perfectly flat green chroma-key background: blue nexus, red nexus, blue energy orb, and red energy orb. The prompt required a low sturdy circular dark-stone base, restrained gold trim, short protective pylons, one bold central crystal, identical blue/red geometry, orthographic three-quarter framing, and shapes readable after reduction to the native 57-pixel actor and 31-pixel orb frame widths. It explicitly excluded towers, aura rings, health bars, shadows, characters, text, UI, purple/magenta glow, and external particles.

| Role | Project source | Preserved generated original |
| --- | --- | --- |
| Nexus actors and orbs | `jungle/nexus_actor_orb_contact.png` | `exec-cfd890cf-325b-40dc-b63d-d605bc251155.png` |

The blue imagegen cells are the runtime geometry authority. Red-team runtime art is a deterministic hue derivation of the same pixel geometry so the two teams have byte-identical alpha masks and cannot flicker from silhouette drift. The native nexus shadow and destruction effects remain separate and unchanged.

## Equipment icons

All 30 item icons were generated independently as centered, fully visible, high-resolution fantasy inventory objects on a flat chroma-key background, with no text, logo, UI frame, cast shadow, detached particles, or exact copy of existing Riot artwork. The exact per-item prompts, generated paths, source hashes, and processed hashes are recorded in:

- `qa/quality_items_ad_as_armor_imagegen.json`
- `qa/quality_items_mr_ap_hp_imagegen.json`
