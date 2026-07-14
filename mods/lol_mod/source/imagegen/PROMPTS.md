# Shen image-gen prompts

The original Shen source set was generated with the built-in `image_gen` path on 2026-07-10. On 2026-07-14 the second active slot was rebuilt from W into E, so the W icon/VFX sources below became inactive provenance and two new E sources replaced them. Every active Shen chroma source uses the installed imagegen background-removal helper before packing.

## Actor model contact sheet

Use case: stylized-concept. Asset type: final-scale 2D pixel-art game character sprite source sheet for Teamfight Manager 2. Create one consistent 4x3 sheet of Shen, the masked twilight ninja protector, with exactly twelve full-body poses: two idle poses, three run poses, three basic sword attack poses, Q/W/R cast poses, and one hit/death pose. Keep the same compact chibi masked ninja in every cell, facing screen-right in 3/4 side view, with indigo/charcoal armor, violet sash, steel mask, blue eye slit, small sword, and a teal-violet spectral spirit blade. Refined hand-painted pixel art; hard pixel clusters; restrained palette; crisp opaque edges; full head, body, legs and feet; stable scale; generous padding. Perfectly flat `#ff00ff` chroma background. No labels, grid lines, text, logos, watermark, shadows, floor, gradients, cropping, oversized weapon, different model, soft transparency, or UI frame.

## Nine-frame run-cycle refinement

Create a NEW exact 3 columns x 3 rows contact sheet containing NINE UNIQUE sequential run-cycle frames for the exact same Shen character shown in the attached actor references. No drawn grid and no labels. This must be one coherent loop, read left-to-right then top-to-bottom: 1 near/left heel contact forward, 2 near-leg loading, 3 near-leg midstance with far leg swinging, 4 clear passing pose with lower legs/ankles visibly crossing beneath the pelvis, 5 far/right heel contact forward, 6 far-leg loading, 7 far-leg midstance with near leg swinging, 8 opposite clear passing/cross step, 9 toe-off/recovery that flows into frame 1 but is visibly different from frame 1. Keep all nine poses screen-right in identical 3/4 side view. Preserve the exact approved compact chibi masked twilight ninja model in every cell: same indigo/charcoal armor, violet sash, steel mask and cyan eye slit, small waist sword, teal-violet floating spirit blade, exact head/body proportions and palette. Make the alternating legs, bent knees, planted feet, and two cross-step silhouettes very obvious at 36-pixel final actor height. Keep pelvis centered, one stable body scale, one stable foot baseline, full body and feet, generous equal cell padding. Crisp hand-painted pixel clusters and hard opaque edges. Perfectly flat `#ff00ff` chroma background. No text, numbers, labels, arrows, borders, grid lines, duplicate frames, mirrored whole character, left-facing pose, model redesign, inconsistent sword or spirit blade, motion blur, speed streaks, shadows, floor, cropping, soft transparency, logo, or watermark.

## Q icon

Use case: stylized-concept. Square 64x64-style pixel-art UI icon for Twilight Assault: a teal-violet spectral spirit blade pulled through a dark indigo enemy silhouette with a diagonal slash and three energized strike marks. Centered emblem, limited palette, hard pixel clusters, strong outline, readable at 32x32, generous padding, flat `#ff00ff` chroma background. No text, frame, logo, watermark, portrait, 3D rendering, blur, or circular shield motif.

## Superseded W icon (inactive)

Use case: stylized-concept. Square 64x64-style pixel-art UI icon for Spirit's Refuge: a circular teal-violet spirit field in slight top-down perspective protecting two allied silhouettes beneath a segmented dome while enemy weapon strikes stop at the rim. Centered protection emblem, limited palette, hard pixel clusters, strong outline, readable at 32x32, flat `#ff00ff` chroma background. No text, frame, logo, watermark, detailed portrait, sword as main motif, teleport columns, 3D rendering, or blur.

## E icon (active)

- Execution ID: `exec-50b58747-dec1-41d1-9494-f321d174200f`.
- Imported target: `source/imagegen/shen_e_icon_source.png`; accepted alpha source: `source/processed/shen_e_icon_source_alpha.png`.
- Prompt contract: a new square hard-edged pixel-art Shadow Dash icon using the accepted Shen model and Q/W/R palette references; the compact masked indigo ninja lunges horizontally with a cyan-violet spectral wake and a sharp taunt-impact ripple. Flat `#ff00ff`; no shield dome, refuge field, text, letters, UI border, duplicate body, logo, or watermark.

## R icon

Use case: stylized-concept. Square 64x64-style pixel-art UI icon for Stand United: an endangered ally inside a huge teal-violet shield while a masked twilight ninja teleports toward them through three spirit-light columns; a balanced eye rune joins both figures. Centered unified emblem, limited palette, hard pixel clusters, strong outline, readable at 32x32, flat `#ff00ff` chroma background. No text, frame, logo, watermark, detailed portrait, weapon motif, blocking dome, 3D rendering, or blur.

## Q VFX

Use case: stylized-concept. Exact 4x2 source sheet of eight sequential final-scale pixel-art phases for Twilight Assault: a compact spectral spirit blade/crescent traveling screen-right through materialize, brighten, launch, elongate, pulse, pass-through flare, taper, and dissipate. Teal/cyan/violet/white, crisp hard pixels, dark-violet edge, stable 64x64-cell footprint, flat `#ff00ff` chroma background. No character, text, labels, grid, logo, watermark, floor, shadow, generic fireball, realistic sword, huge explosion, or soft transparency.

## Superseded W VFX (inactive)

Use case: stylized-concept. Exact 3x2 source sheet of six sequential final-scale pixel-art phases for Spirit's Refuge: a slight top-down elliptical ground ring progressing from faint rune to growing ring, locked spectral blade segments, stable field, interception sparks, and fade. Teal/cyan/violet/white, crisp hard pixels, stable 112x64-cell footprint with empty center, flat `#ff00ff` chroma background. No character, text, labels, grid, logo, watermark, opaque dome, teleport columns, generic circle, or soft transparency.

## E Shadow Dash VFX (active)

- Execution ID: `exec-7537fd9a-649e-4628-b972-8cabb7ea6505`.
- Imported target: `source/imagegen/shen_e_vfx_contact.png`; accepted alpha source: `source/processed/shen_e_vfx_contact_alpha.png`.
- Prompt contract: exact 3x2 effect-only contact sheet; frames 1-3 build a compact horizontal cyan-violet dash wake and frames 4-6 flash, fracture, then fade a small taunt impact. The six cells keep one scale/baseline and generous padding on flat `#ff00ff`; no actor, shield/refuge field, large ground ring, projectile arrow, labels, grid, logo, or watermark.

## R VFX

Use case: stylized-concept. Exact 4x2 source sheet of eight sequential final-scale pixel-art phases for Stand United: small eye rune, circular shield outline, protective lotus silhouette, forming teleport columns, intense columns, masked-eye flash, expanding arrival ring, and dissolving afterglow. Teal/cyan/violet/white, crisp hard pixels, stable 112x112-cell footprint, flat `#ff00ff` chroma background. No character, text, labels, grid, logo, watermark, fire, generic explosion, angel wings, floor plane, or soft transparency.

## Lucian master actor model v3 (active)

Use the accepted Shen actor sheet only as the scale, compact silhouette, pixel density, chibi head/body ratio, upright posture, cell occupancy and foot-baseline reference; do not copy Shen's costume, mask, sword, spirit blade, colors or identity. Create a completely new exact 4x3 production pixel-art sprite sheet for base-skin Lucian, consistently facing screen-right. Keep one athletic dark-skinned adult male gunslinger with short braided black hair, readable eyes, a compact white/navy coat ending above the knees, restrained cyan trim, strong compact legs, silver knees, complete boots and two matching compact silver/cyan relic pistols. Pose order: idle A/B, right/left shots; balanced passive double shot, upright Q brace, compact E anticipation/travel; R start/fire, upright hit, defeated. Preserve the exact face, anatomy, costume, pistol design, palette, body scale and foot baseline across all cells. Refined hard-edged hand-painted pixel art, dark outlines, controlled palette, crisp clusters and generous padding on a perfectly flat `#ff00ff` background. No horizontal flying, extreme lean, giant split, missing/fused limbs, extra arms/guns, cyclops/blank face, model drift, oversized head, large VFX, shadow, gradient, floor, labels, grid, watermark or transparency.

V3 precise edit: preserve the v2 sheet exactly except row 3 columns 3 and 4. Redraw only those hit/dead cells so the fall sequence has no duplicated, floating, detached or visually competing second pistol. The hit pose keeps one pistol securely gripped close to the lowered hand/body while the second is holstered or occluded; the defeated pose shows at most one compact pistol next to or in the front hand while the second is hidden. Preserve the exact 4x3 canvas, first ten cells, identity, anatomy, costume, palette, scale, direction, padding and flat `#ff00ff` background. No raised extra pistol, loose gun, purple hit sparks, extra arm/hand, disconnected wrist, gun through torso, muzzle flash, blood, crop, shadow, floor, labels, grid, text, watermark, transparency or blur.

## Lucian master nine-frame run cycle v2 (active)

Use actor master v2 as the exact Lucian face, anatomy, costume, weapon, palette and rendering reference; use Shen's run sheet only as a compact scale, upright gait, modest-stride, pixel-density and body-occupancy reference. Create an exact 3x3 screen-right loop: left contact/loading/passing; right contact/loading/opposite passing; low transition/recovery/loop return. Show clear alternating legs, modest counter-motion, tiny vertical bounce and at most 15 degrees of torso lean. Keep both pistols controlled near the body, coat motion restrained, all nine bodies the same height/head size, and every grounded frame on one baseline. Each silhouette stays within 1.30x idle width. Refined hard-edged pixel art on perfectly flat `#ff00ff`; no horizontal flying, crouch crawl, giant split, duplicated pose, missing/merged boots, extra limbs/guns, muzzle flash, model drift, shadow, floor, labels, grid, watermark or transparency.

## Lucian Q icon

Square full-bleed pixel-art icon for Piercing Light: paired silver relic pistols aligned into one concentrated cyan-white piercing beam, dark navy background, bold high-contrast motif readable at 32x32. No frame, text, logo, UI, transparency or magenta.

## Lucian E icon

Square full-bleed pixel-art icon for Relentless Pursuit: centered Lucian silhouette lunging screen-right with two cyan afterimages trailing left and a sharp speed streak, dark navy background, readable at 32x32. No frame, text, logo, UI, transparency or magenta.

## Lucian R icon

Square full-bleed pixel-art icon for The Culling: two relic pistols driving a symmetric storm of discrete cyan-white bullets toward screen-right, dark navy background, readable at 32x32. No frame, text, logo, UI, transparency or magenta.

## Lucian Q VFX

Exact 4x2 contact sheet of eight sequential Piercing Light phases: a thin horizontal cyan-white lance ignites, sharpens, reaches a fixed bright core, sparks and cleanly dissipates. Effect only, fixed origin and footprint, about 55% cell width. Flat `#ff00ff`; no character, weapon, labels, grid, blur or transparency.

The cyan Q route was rejected after live-read review because it was too close to the cyan basic-attack bolt.

## Lucian Q v2 gold muzzle beam

Preserve the exact 4x2 eight-phase Piercing Light layout and long fixed lance, but replace the cyan identity with a white-hot ivory center, saturated golden-yellow body/edges, amber sparks and a restrained pale-violet shadow outline. Cyan/blue must not be dominant. The packed 192x64 direction-aware line canvas uses x=96 as its rotation pivot and starts visible pixels at x=116, so either facing direction flashes the forward beam from the Q pose's pistol muzzle instead of placing it behind the actor. Runtime damage is a one-tick frozen `LineRangeProjectile`; visibility uses a separate damage-free `LinearProjectile` carrier with speed 1 and range 12, so it stays at the launch direction for 12 ticks without following the target. Flat `#ff00ff`; effect only, no projectile-shaped blue bolt, character, labels, grid or extra beams.

This v2 moving-carrier route was rejected after live review because the renderer could move, reverse or remove the visual independently of the fixed damage line. The v3 artwork remains useful, but its actor-embedded runtime route was later rejected too.

## Lucian R VFX

Exact 4x2 contact sheet of eight looping single-projectile phases for The Culling: one compact horizontal cyan-white diamond bullet with a short tail and controlled side sparks, fixed center and footprint. Flat `#ff00ff`; no beam, projectile cluster, labels, grid, blur or transparency.

## Lucian v2 readable actor model

Edit the supplied Lucian actor into an exact 4x3 production sprite sheet with the same dark-skinned dual-pistol identity, navy coat, silver shoulders and cyan relic pistols. Use simplified final-scale chibi pixel art: head about one quarter of standing height, larger warm-brown face, separated black hairline and bright eye pixels that remain readable at a 36-37px full-body height. Pose order: idle A/B, right/left shots; wide/forward double shots, dash start/travel; R start/fire, hit, dead. Flat `#ff00ff`; no labels, grid, shadows, extra characters, cropping or oversized skill VFX.

## Lucian v3 complete-leg actor correction

Edit the accepted v2 4x3 actor while preserving identity, face, hair, navy-and-silver coat, two cyan pistols, pose order, scale and chroma background. Correct every lower body so hips, distinct knees, calves and complete boots are readable; separate both trouser legs with negative space or highlights, open/shorten coat tails so they do not merge with the thighs, and keep every boot inside its cell. Standing poses use slightly longer chibi legs while preserving overall height by compacting the torso rather than enlarging the model. No crop, ground, shadow, extra limb, grid, label or model drift.

The v3 source contained complete geometry, but its dark long coat still merged with the thighs after packing to 24x33px and was rejected by live draft review.

## Lucian v4 final-scale leg-silhouette correction

Edit v3 while preserving Lucian's face, identity, pistols, pose order and overall height. Shorten and open the coat decisively so it ends at mid-thigh, make the legs roughly 40% of standing height, put both knees below the hem, separate trousers with a 2-3 source-pixel negative-space channel, and add restrained silver knee-guard and boot-rim highlights. Compact the torso rather than enlarging the model. Every thigh, knee, calf and boot must survive a 24x33px reduction; no crop, ground, shadow, grid, extra limb or model drift.

This route was rejected in live draft review because its high-detail face still collapsed when the whole body was reduced to 24x33px.

## Lucian v5 final-pixel idle face layer

Edit only the head/face rendering over v4 while locking the body, short coat, long legs, pistols, pose order and scale. Design the standing face specifically for a 7-9px-tall game head: solid swept-black hair with 2-3 highlight clusters, three warm-brown skin tones, two separated high-contrast eye pixels, a single-pixel nose/cheek highlight and one-pixel mouth shadow. Each logical face pixel is a large crisp source cluster; no realistic gradients, micro-detail, mask, skull, cyclops or featureless brown block. Only the first two uncropped idle heads are used as the 12x12 runtime face overlay; all body geometry remains v4.

The generated standing heads read as right-facing 3/4 profiles. The final palette restoration therefore keeps one right-side eye, brow, projecting nose and jaw shadow; applying the requested two-eye front layout to this profile was rejected as mask-like.

This overlay route was also rejected: mixing a separately packed face with the v4 body still looked pasted-on and inconsistent at card scale. Neither v4 nor v5 remains in the active source set.

## Lucian v6 native 24x33 model redraw

Create a completely new 4x3 Lucian sheet rather than editing v4/v5. Author each standing sprite as only 24 logical pixels wide by 33 logical pixels tall, displayed enlarged with hard square blocks; use roughly 160-230 visible logical pixels and a 16-20 color palette with no antialiasing or micro-detail. The right-facing 3/4 head is about 9x9 logical pixels and the face about 6x5, with one ivory eye, brow, nose-tip pixel and jaw shadow. Keep a short navy/silver coat, distinct long legs, silver knees, complete boots and compact cyan pistols. Pose order remains idle A/B, right/left shot; double shot, Q, E start/travel; R start/fire, hit, defeated. Flat `#ff00ff`; no grid, labels, crop, shadow, extra limbs, huge VFX or high-resolution illustration route. Runtime packing uses nearest-neighbor plus a 32-color cap, and stable UI idle uses frame 0 only.

## Lucian v2 distinct run cycle

Edit the supplied Lucian run source into an exact 3x3 nine-frame screen-right gunslinger sprint, visibly unlike Shen's upright ninja walk. Use a low forward torso, pistols held low and back, trailing coat, alternating contacts, two obvious cross/passing phases, airborne stride, heel kick and small vertical bounce. Preserve the v2 face, costume, scale and foot baseline in all cells. Flat `#ff00ff`; no duplicate pose, muzzle flash, labels, grid, cropping or model drift.

This first v2 sprint route was rejected after measuring the official Archer frames: its long airborne splits packed to as much as 58px wide, versus the official run's 23-24px visible width.

## Lucian v3 official-footprint run correction

Edit the v2 run sheet while locking the v2 actor identity. Keep nine screen-right gunslinger phases with modest forward lean, low pistols, alternating contacts and two passing/cross steps, but keep both legs mostly under the torso, coat tails close, no full split or long airborne jump, and a silhouette width no more than 90% of its height. Flat `#ff00ff`; preserve the face, costume, scale and foot baseline; no labels, grid, projectiles, cropping or model drift. This compact route is packed to the official 002 run envelope of at most 31px tall and 30px wide.

## Lucian basic attack / passive projectile VFX

Create an exact 4x2 eight-frame pixel-art contact sheet for one relic-pistol light bolt traveling screen-right: narrow diamond/needle white-hot core, cyan-blue shell, tiny electric particles and a short tapered tail, progressing from ignition through stable bolt and flare to dissipation. It must remain readable at about 32x16px and look like magical gunfire, not an arrow, casing, beam, rocket or projectile cluster. Flat `#ff00ff`; no character, gun, hand, labels, grid, scenery or watermark.

## Lucian v7 unified 21-frame replacement

Create a completely new exact 7x3 contact sheet containing all 21 Lucian poses in one generation: two idles; nine sequential right-facing run phases with alternating contacts and two passing/cross steps; right shot, left shot and passive double shot; Q cast, E start, E travel, R start, R fire, hit and dead. Use one consistent dark-skinned adult male gunslinger with short black hair, exactly two separated ivory eyes in front/three-quarter faces, white/navy long coat with cyan trim, black trousers, full boots and two matching silver relic pistols. Lock one head size, body scale, baseline, costume and palette across the complete sheet. Flat `#ff00ff`; no labels, grid, crop, shadows, extra limbs or body parts crossing cell boundaries.

The first v7 result established the accepted unified body and face, but its double-shot pistols fused into a forked weapon. It was not packed.

## Lucian v8 weapon and arm correction

Edit the unified sheet while preserving the 7x3 layout, identity, body, face, costume and poses. Across all cells, make each relic pistol one consistent independent object with one straight barrel, one grip and one trigger guard. In double-shot and R-fire cells, separate the two pistols vertically and connect each to exactly one continuous shoulder-elbow-wrist-hand chain. No forked barrel, fused forearm, floating wrist, third hand or gun emerging from the torso.

The first weapon correction fixed the guns but left the passive-double forearms visually fused. The accepted arm correction gives the near shoulder one horizontal firing arm and the far shoulder one lower, clearly separated firing arm, with one hand on each grip.

## Lucian v9 no-effect E cleanup (superseded body base)

Edit only E start and E travel while preserving the other 19 unified poses, especially the corrected passive-double arms. Remove every detached gold/cyan spark, speed line, glow trail and particle from the two E cells; retain only Lucian's physical body, coat tails, two arms, two hands, two separate pistols, legs and boots in the leaning dash poses. The resulting single v9 sheet supplies idle, the complete nine-frame run, attacks and every Q/E/R body pose; no separately generated Lucian run model remains active.

The v9 body/animation layout was accepted, but its small high-resolution eyes disappeared during 33px nearest-neighbor packing and the runtime face became a blank brown block.

## Lucian v10 final-scale two-eye face (rejected actor source)

Edit the head and face in all 21 v9 cells while locking the unified body, corrected passive-double arms, separate pistols, E-without-VFX poses, legs, boots, grid and baseline. Redesign the head for final-scale packing: near-front/mild three-quarter face, two large separated ivory source clusters on one row, separate brows, centered nose and short mouth; no profile, visor, cyclops, blank face or collar pixels in the eye row. The accepted runtime pack uses nearest-neighbor at 35px standing height. Both idle frames are mechanically checked for exactly two same-row bright eye pixels at x=30 and x=34; 33px lost the eyes, while 36px was unnecessary. A later attempt to shrink the source eye blocks again was rejected because image-gen reduced them below the stable sampling width.

The user rejected v10 for low overall model quality and poor movement. Its source, processed source and live card were deleted. Exact eye-pixel checks and code-injected face pixels are not valid substitutes for a readable final-scale actor.

## Lucian Q v3 gold beam (active art, rebuilt runtime)

Create an exact 4x2 eight-phase contact sheet for Piercing Light on flat `#ff00ff`: compact gold-white muzzle ignition, rapid extension, three full-width stable phases, right-to-left breakup, thin fade and residual muzzle spark. Every phase shares one left-side muzzle origin and one perfectly horizontal baseline. Use an ivory-white core, saturated golden body, amber sparks and restrained pale-violet edge accents; no cyan identity, curve, homing arc, projectile ball, character, gun, labels or grid. Runtime deliberately excludes the isolated ignition/residual-spark endpoints and packs eight 60-80px beam phases on a 192x32 projectile canvas. The canvas rotation pivot is x=96 and every beam begins at x=104, so the same `lol_lucian_q_piercing_light` `LinearProjectile` starts at the forward pistol muzzle instead of Lucian's body. The actor remains body-only 64x64, and the retired actor-embedded beam plus one-tick `LineRangeProjectile` route must not return.

# Orianna image-gen prompts

All nine Orianna sources were generated with the built-in `image_gen` path on 2026-07-10. Eight use a removable magenta background; the v3 basic-attack source uses a removable green background so its violet trail survives chroma despill. Each source was converted into the matching `source/processed/orianna_*_alpha.png` before packing. The source set is original and does not reuse the official Barrier Mage, Workshop Reimu, or League client artwork.

## Orianna actor model contact sheet v2 (active)

Use case: stylized-concept. Create an exact 4x4 contact sheet of one consistent final-scale chibi clockwork automaton woman for Teamfight Manager 2: an enlarged, clean porcelain face plane, separated bright-cyan eye clusters, short dark-blue bob, compact brass-and-steel joints, navy/ivory gear dress and a small connected brass crown. Include readable idle, attack-command, defensive-command, shockwave-cast, hit, kneeling and defeated poses while locking the same face, proportions, palette and body scale. Every upright pose must show both complete boots with generous space below the soles; the runtime pack targets a 38px standing silhouette and an exclusive y=42 foot baseline (visible pixels end at y=41) so cards and compact rows cannot crop the feet. Simplify tiny facial ornament instead of blurring the porcelain/eye/hair contrast at final size. The Ball remains a separate gameplay/effect asset and is not baked into clean body frames. Flat `#ff00ff`; no text, labels, grid lines, scenery, floor, shadows, crop, extra limbs, muddy face, model drift, soft transparency, logo or watermark.

## Orianna nine-frame run cycle v2 (active)

Use case: stylized-concept. Create an exact 3x3 sequence of nine unique screen-right run frames using the v2 actor's exact face, crown, dress, joints and boot design. Show alternating mechanical leg contacts, two clear passing poses, modest forward energy and a small vertical bounce while preserving the enlarged readable face, separated cyan eyes and complete boots in every cell. Keep all frames in the same 38px runtime height class with their soles aligned to the exclusive y=42 baseline; vary the leg contact without shrinking the head/body or cutting either foot. Flat `#ff00ff`; no Ball, spell effects, labels, grid, duplicate frames, whole-character mirroring, crop, shadow, model redesign, fused/missing boots or soft transparency.

## Orianna basic-attack energy-dart VFX v3 (active)

Use case: precise-object-edit. Create an exact 4x2 pixel-art effect sheet: four unique screen-right travel phases of a large, high-contrast cyan/ivory mechanical energy dart with asymmetric brass clamps and a short violet trail, followed by four compact directional cyan/brass contact-spark and gear-shard fade phases. The travel silhouette must stay visibly elongated rather than circular and remain readable when packed at roughly 25-28px wide by 10-14px high inside a 32x32 game cell. This is normal attack energy fired independently of the mechanical Ball: no Ball, orb, circular gear sphere, shield, laser beam or miniature command orb. Preserve the exact 4x2 layout on a removable flat green chroma background so violet pixels are not lost during despill; effect only, no actor, text, labels, grid, scenery, oversized explosion or soft transparency.

## Orianna Q/E/R icons

Create three independent square pixel-art UI icons with full-bleed dark navy backgrounds and bold cyan/ivory/brass silhouettes readable at 24x24: Q shows the Ball driving toward a target point and releasing a control field; E shows the Ball wrapping an allied silhouette in a clockwork shield; R shows a circular ring contracting inward around the Ball. No text, UI frame, portrait, logo, watermark, magenta or copied League icon composition.

## Orianna Q VFX

Use case: stylized-concept. Create an exact 4x3 contact sheet for Command: Attack: four screen-right Ball travel phases, four arrival/activation phases and four fixed elliptical control-field phases. Preserve the same navy/ivory/brass Ball and cyan-violet energy language throughout. The field must read as a ground-area control effect rather than a persistent second actor. Flat `#ff00ff`; no character, labels, grid, scenery, opaque floor or soft transparency.

## Orianna E VFX

Use case: stylized-concept. Create an exact 4x3 contact sheet for Command: Protect: four fast Ball travel phases, four clockwork shield-ring phases and four shield brighten/fade phases. Keep a hollow center so an allied actor remains readable beneath the effect, with restrained cyan light and brass nodes. Flat `#ff00ff`; no character, text, labels, grid, solid dome, permanent Ball attachment or soft transparency.

## Orianna R VFX

Use case: stylized-concept. Create an exact 4x3 contact sheet for Command: Shockwave: a wide clockwork ring contracts through eight clear phases toward the Ball, then four cyan-violet inward-impact and dissolution phases. Directional arrows and ring motion must visibly pull toward the selected target point, never toward Orianna's body. Flat `#ff00ff`; no character, text, labels, grid, outward explosion, scenery or soft transparency.

# Briar image-gen prompts

All nine Briar sources were generated with the built-in `image_gen` mode on 2026-07-11. Actor and VFX sources use a removable flat green background and were converted with the installed chroma-key helper before packing. The three icons are independent full-bleed sources. The local, uncommitted generated-images batch is `019f4bd8-30d3-7b60-98fa-58403cf263c7`; accepted copies are stored below `source/imagegen`.

## Briar actor contact sheet

Use case: stylized-concept. Asset type: production 2D pixel-art character sprite source sheet for Teamfight Manager 2. Primary request: create an exact 4 columns x 4 rows contact sheet containing SIXTEEN full-body key poses of Briar, the pale vampiric young woman champion, consistently facing screen-right in a mild three-quarter view. Read left-to-right, top-to-bottom: 1 restrained idle A, 2 restrained idle B, 3 basic claw-attack windup, 4 basic claw-attack strike; 5 forward snack/bite lunge, 6 bite impact recoil, 7 Q restraint core cracking open, 8 Q blood-frenzy combat stance; 9 E deep breath/charge, 10 E forward scream release, 11 R bloodstone throw, 12 R low predatory chase; 13 hit recoil, 14 falling defeat, 15 grounded defeat, 16 quiet final defeated pose. Character invariants: one identical compact chibi adult female model in all sixteen cells; porcelain-pale readable face plane; two separated crimson eye clusters; messy shoulder-length white hair with restrained dark-red tips; compact dark burgundy and charcoal combat outfit; a single unmistakable heavy black-iron pillory/restraint encircling both forearms with a dark-red glowing central core; clawed hands when the restraint opens; slim strong legs; both complete bare feet and toes visible. Keep the restraint symmetric and attached to the same arms, never duplicate it. Style/medium: refined hand-painted pixel art, hard square pixel clusters, dark outline, controlled 24-color burgundy/black/ivory palette, crisp opaque edges, deliberately simplified final-scale face. Designed to remain readable when each full standing body is reduced to 36-38 pixels tall. Composition/framing: exact equal 4x4 cells with invisible boundaries; one centered full-body pose per cell; identical head size and body scale; generous equal padding; no body part crosses a cell; all upright soles share one foot baseline; full hair, restraint, legs, feet and toes inside every cell. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background across the entire canvas. Constraints: no text, numbers, labels, arrows, visible grid lines, borders, UI frame, scenery, floor, cast shadow, gradient, lighting variation in the background, soft transparency, antialiased haze, motion blur, blood gore, extra character, extra restraint, extra arm, extra hand, missing/fused feet, shoes, cropped hair or feet, model drift, different costume, oversized head, giant VFX, logo, trademark text, or watermark. Do not use green anywhere inside the character.

Accepted source: `briar_actor_contact.png` (default generated original `exec-82f11845-5a7a-46ec-b9a1-362dce86e7d1.png`).

## Briar nine-frame run cycle

Image 1 is the exact identity, costume, face, palette, pillory/restraint, pixel density and scale reference; generate a NEW run-cycle source and do not alter Image 1. Use case: stylized-concept. Asset type: exact 3 columns x 3 rows production pixel-art run-cycle contact sheet for Teamfight Manager 2. Primary request: create NINE UNIQUE sequential screen-right running phases for the exact same Briar model from Image 1, read left-to-right then top-to-bottom: 1 left-foot contact, 2 left-leg loading, 3 first passing pose with ankles clearly crossing under the pelvis, 4 push-off, 5 right-foot contact, 6 right-leg loading, 7 opposite passing pose, 8 toe-off recovery, 9 loop-return anticipation visibly different from frame 1. Character invariants: preserve the same porcelain-pale face, two crimson eye clusters, white hair with dark-red tips, compact burgundy/charcoal outfit, one symmetric black-iron forearm pillory with red core, slim strong legs and complete bare feet. Keep the restraint closed while running and controlled in front of the torso; exactly two arms, two legs and two feet in every cell. Motion: predatory but compact claw-like gait, modest forward lean no more than 18 degrees, clear alternating planted feet, bent knees, two unmistakable passing/cross-step silhouettes, small vertical bounce, restrained hair motion. Every silhouette must remain within 1.25 times the idle width so the reduced sprite does not become a horizontal leap. Style/medium: refined hard-edged hand-painted pixel art matching Image 1 exactly; stable head size, stable body scale, stable palette, crisp opaque clusters; designed for a 36-38 pixel standing-height runtime sprite. Composition/framing: equal invisible 3x3 cells, one centered full-body pose per cell, generous equal padding, no body part crosses a cell, all planted soles share one baseline, full hair and every toe inside its cell. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: no text, labels, numbers, arrows, borders, visible grid lines, scenery, floor, shadow, gradient, green inside the character, duplicate frame, mirrored whole character, left-facing pose, horizontal flying, giant split stride, crouch crawl, fused/missing feet, shoes, extra arms/legs/restraint, model redesign, spell effects, blood, soft transparency, blur, logo, or watermark.

Accepted source: `briar_run_contact.png` (default generated original `exec-99d060f7-6a2f-43ad-81b0-fbfb18c643e6.png`).

## Briar Q icon

Use case: stylized-concept. Asset type: square full-bleed pixel-art game UI icon for Briar's Q slot, Blood Frenzy. Primary request: a single centered black-iron pillory core splitting open with a white-hot crimson diamond, two pale clawed hands breaking free on opposite sides, and three short dark-red pulse streaks suggesting attack-speed frenzy. The motif must read as restraint-breaking predatory empowerment, not a projectile or shield. Style/medium: bold hand-painted pixel art, hard square clusters, crisp dark outline, limited ivory/crimson/burgundy/black palette, high contrast readable at 24x24. Composition/framing: one symmetric emblem centered with generous safe padding; full-bleed deep charcoal-to-burgundy flat painted background; no UI frame. Constraints: no text, letters, numbers, character portrait, gore, realistic blood, extra hands, circular shield, projectile, scenery, magenta or green key background, transparency, blur, photorealism, logo, trademark text, or watermark.

Accepted source: `briar_q_icon_source.png` (default generated original `exec-72b80c20-37d6-44ff-a847-cd0633da0b86.png`).

## Briar E icon

Use case: stylized-concept. Asset type: square full-bleed pixel-art game UI icon for Briar's E, Chilling Scream. Primary request: a pale white-haired vampiric profile at the left draws breath and releases one forceful narrow crimson-black shockwave toward screen-right; the wave forms a sharp forward cone with three compressed rings and small dark ground-crack shards. The motif must read as charged scream, damage reduction and knockback, not fire or a generic laser. Style/medium: bold hand-painted pixel art, hard square clusters, crisp dark outline, limited ivory/crimson/burgundy/black palette, high contrast readable at 24x24. Composition/framing: one clear left-to-right action silhouette centered with generous safe padding; full-bleed deep charcoal-to-burgundy flat painted background; no UI frame. Constraints: no text, letters, numbers, full character portrait, gore, realistic blood, circular shield, projectile ball, music notes, scenery, magenta or green key background, transparency, blur, photorealism, logo, trademark text, or watermark.

Accepted source: `briar_e_icon_source.png` (default generated original `exec-5476ddd0-76b7-4d38-8346-e3c41e52b573.png`).

## Briar R icon

Use case: stylized-concept. Asset type: square full-bleed pixel-art game UI icon for Briar's R, Certain Death. Primary request: a faceted crimson bloodstone streaks from upper-left toward a marked enemy silhouette at lower-right while a low pale white-haired predator silhouette chases along the same line; behind the target, one compact circular dark-red arrival shockwave and two small fear-eye marks imply impact and fear. The motif must clearly read as long-range mark, relentless chase, arrival impact. Style/medium: bold hand-painted pixel art, hard square clusters, crisp dark outline, limited ivory/crimson/burgundy/black palette, high contrast readable at 24x24. Composition/framing: one strong diagonal trajectory and one focal impact, centered with generous safe padding; full-bleed deep charcoal-to-burgundy flat painted background; no UI frame. Constraints: no text, letters, numbers, detailed portrait, gore, realistic blood, multiple projectiles, outward explosion filling the icon, circular shield, scenery, magenta or green key background, transparency, blur, photorealism, logo, trademark text, or watermark.

Accepted source: `briar_r_icon_source.png` (default generated original `exec-613da3b4-2ff3-4976-b0ef-7111029b8262.png`).

## Briar Crimson Curse VFX

Use case: stylized-concept. Asset type: exact 4 columns x 2 rows production pixel-art VFX contact sheet for Briar's Crimson Curse bleed tick. Primary request: create EIGHT sequential effect-only phases, read left-to-right then top-to-bottom, of one compact dark-crimson triple-claw scratch appearing on a target: tiny first nick, three sharp slashes ignite, bright compact center, peak short pulse, restrained red droplets/particles, dim scratch, fragmented fade, almost-empty final spark. Stylized magical curse only, not realistic blood. Style/medium: crisp hard-edged pixel art, dark burgundy outline, crimson/red/ivory highlight clusters, no soft haze; readable inside a 32x32 final target footprint. Composition/framing: exact equal invisible 4x2 cells; one effect centered per cell; identical origin and footprint; generous padding; no effect crosses a cell. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: effect only; no character, weapon, text, labels, numbers, arrows, borders, visible grid, floor, shadow, scenery, gore, pool of blood, realistic wound, giant explosion, opaque rectangle, green inside the effect, gradient in background, soft transparency, blur, logo, or watermark.

Accepted source: `briar_bleed_vfx_contact.png` (default generated original `exec-1ee1b482-cdba-45ad-b0cd-8073c1e5a3be.png`).

## Briar Blood Frenzy VFX

Use case: stylized-concept. Asset type: exact 4 columns x 2 rows production pixel-art VFX contact sheet for Briar's Blood Frenzy buff. Primary request: create EIGHT sequential effect-only phases of a hollow actor-following restraint-break aura, read left-to-right then top-to-bottom: dim black-iron core outline, crimson diamond crack, two symmetric restraint fragments opening, compact inward pulse, stable low-opacity dark-red breathing ring, brighter predatory heartbeat, fragments retract/fade, residual small core sparks. Keep a large empty transparent center so a 36-38px actor remains completely readable beneath it; do not draw the character or solid pillory. Style/medium: crisp hard-edged pixel art, restrained dark burgundy/crimson/ivory highlights, compact particles, no haze; intended final footprint around 64x64. Composition/framing: exact equal invisible 4x2 cells, one symmetric hollow effect centered per cell, stable origin and footprint, generous padding, no effect crosses a cell. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: effect only; no character, face, hands, text, labels, numbers, arrows, borders, visible grid, floor, shadow, scenery, realistic blood, gore, permanent fog, opaque filled center, giant explosion, green inside effect, background gradient, soft transparency, blur, logo, or watermark.

Accepted source: `briar_frenzy_vfx_contact.png` (default generated original `exec-9fa74797-5191-4f8a-a878-2b646a9fba59.png`).

## Briar Q overhead hit VFX

Use case: stylized-concept. Asset type: production source contact sheet for a small top-down pixel-art game VFX. Primary request: create one coherent eight-frame animation sheet for Briar's Q overhead hit/stun marker. The marker is a brief, compact scarlet impact sigil that appears above the struck target's head, never around the body. Subject: a small blood-red diamond-shaped impact spark with three short claw/fang accents and a few crimson fragments; frames 1-2 snap into view and tighten, frames 3-5 deliver the brightest compact impact/stun read, frames 6-8 break into tiny fading shards. Style/medium: polished League-inspired fantasy pixel-art VFX, crisp hard pixel clusters, deep burgundy outline, scarlet/red/orange highlights, readable after reduction to about 28 by 18 pixels. Composition/framing: exact 4 columns by 2 rows, eight equal cells, one centered marker per cell, identical anchor, generous clean padding, no gutters or dividers drawn. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background for later removal; every cell uses the same uniform green with no texture, shadow, floor, or glow spill. Constraints: animation only; one subject per cell; no character, face, letters, numbers, watermark, circles, rings, halos, cages, borders, square outlines, rectangular frames, target reticles, ground decals, large explosions, smoke clouds, soft haze, black cell backgrounds, grid lines, or labels; do not use `#00ff00` in the effect.

Accepted source: `source/imagegen/champions/004_briar/briar_q_overhead_v1_source.png` (built-in ImageGen source supplied in the task workspace). The installed chroma-key helper produced `source/processed/champions/004_briar/briar_q_overhead_v1_alpha.png` with border auto-key, soft matte, thresholds 12/220, and despill. The generated contact contains white gutters at the 4x2 boundaries, so the packer discards an 18-pixel band inside every cell before alpha bounding; no separator pixels are allowed into the eight 64x64 runtime cells.

## Briar E VFX

Use case: stylized-concept. Asset type: exact 4 columns x 2 rows production pixel-art VFX contact sheet for Briar's E, Chilling Scream. Primary request: create EIGHT sequential effect-only phases of one narrow forward shockwave traveling screen-right, read left-to-right then top-to-bottom: compressed dark-red breath spark at a fixed left origin, small pointed cone, longer crimson-black pressure wedge, full narrow wave with ivory-hot core, peak wave with restrained ground-crack shards, thinning tail, broken pressure rings, clean dissipating fragments. It must look like a forceful scream/pressure blast that knocks targets screen-right, not a laser, fireball or circular explosion. Style/medium: crisp hard-edged pixel art, burgundy/crimson/black with small ivory highlights, no soft fog; readable in a final 112x64 directional effect cell. Composition/framing: exact equal invisible 4x2 cells; every phase points perfectly horizontal screen-right; fixed left-side origin and central baseline; stable footprint; generous padding; no effect crosses a cell. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: effect only; no character, face, mouth, weapon, text, labels, numbers, arrows as UI symbols, borders, visible grid, floor plane, shadow, scenery, realistic blood, gore, music notes, curved/backward wave, circular shield, giant opaque explosion, green inside effect, background gradient, soft transparency, motion blur, logo, or watermark.

Accepted source: `briar_e_vfx_contact.png` (default generated original `exec-2adfe059-4ff1-4957-9b9a-ffd6c9b4d97b.png`).

## Briar R VFX

Use case: stylized-concept. Asset type: exact 4 columns x 3 rows production pixel-art VFX contact sheet for Briar's R, Certain Death. Primary request: create TWELVE effect-only key phases, read left-to-right then top-to-bottom. Row 1: four target-mark phases—small crimson diamond above an invisible target, dark eye-rune opens, four thin downward targeting prongs lock, compact marked pulse. Row 2: four horizontal screen-right chase-trail phases—short burgundy streak, longer claw-like afterimage, peak ivory/crimson speed slash, tapering fragments. Row 3: four centered arrival phases—small ground ring, strong circular crimson-black inward impact, two compact fear-eye wisps at the rim, clean dissolving afterglow. Keep target mark, chase trail, and arrival visually distinct. Style/medium: crisp hard-edged pixel art, dark burgundy/crimson/black with restrained ivory highlights, no soft haze; readable at final 64x64 mark, 96x48 trail, and 96x96 arrival footprints. Composition/framing: exact equal invisible 4x3 cells; effects centered and separated; fixed origin within each row; generous padding; no effect crosses a cell. Hollow centers where a target or actor must remain readable. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: effect only; no character, face portrait, weapon, text, labels, numbers, UI arrows, borders, visible grid, floor plane, shadow, scenery, realistic blood, gore, giant opaque explosion, shield dome, green inside effects, background gradient, soft transparency, motion blur, logo, or watermark.

Accepted source: `briar_r_vfx_contact.png` (default generated original `exec-17d08d83-9ca1-42e0-9bbc-50dce9b576b3.png`).

# Sivir image-gen prompts

All ten Sivir sources were generated with built-in `image_gen` mode on 2026-07-11. The official Sivir splash was used only as an appearance reference; Briar's accepted sources were used only for final-scale pixel density, outline, layout, and motion quality. Actor and VFX sources use removable flat `#00ff00` backgrounds and were converted with the installed chroma-key helper. The three icons are independent original full-bleed sources. Generated-images batch: `019f4bd8-30d3-7b60-98fa-58403cf263c7`.

## Sivir actor contact sheet

Use case: stylized-concept. Asset type: final-scale pixel-art game character contact sheet for Teamfight Manager 2. Input images: Image 1 is the official Sivir appearance reference; Image 2 is the accepted pixel-art scale, outline, pose-grid, and rendering-quality reference only. Primary request: Create one coherent 4 columns by 4 rows contact sheet of the same Sivir character model in 16 distinct full-body action poses, facing mostly toward screen-right. Preserve one exact character design and scale in every cell. Subject: Sivir, a confident Shuriman battle mistress with warm brown skin, long flowing dark brown hair, a small gold forehead diadem with teal jewel, teal-black cropped battle armor with gold trim, dark fitted leggings and sturdy boots, and one large symmetric four-bladed jeweled crossblade. Keep the crossblade compact and close behind or beside her torso in idle poses so it never dominates the silhouette. Exactly one crossblade per pose. Pose order, left to right, top to bottom: neutral idle A; neutral idle B; basic attack windup; basic attack crossblade release; Q Boomerang Blade windup; Q throw follow-through; E Spell Shield guarded stance with a small tight cyan-gold barrier hugging the body; R On The Hunt command pose raising the crossblade; hit recoil A; hit recoil B; crouched recovery; determined ready stance; falling backward with crossblade separated only as the same one dropped beside her; lying defeated; kneeling defeated; compact seated recovery. Style/medium: polished hand-authored 2D pixel art, crisp dark pixel outlines, readable face and eyes, restrained palette, compact chibi proportions matching Image 2, final-scale sprite quality rather than painted concept art. No anti-aliased painterly blur. Composition/framing: exact 4x4 evenly spaced grid on a 2048x2048 square canvas; each cell centered with generous empty padding; full head, torso, both legs and both feet visible; consistent approximately 1:1 character scale; do not crop hair, feet, weapon, or fallen poses. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: one Sivir only in each cell; exactly one crossblade per cell; same face, outfit, hair, weapon shape, body proportions and pixel scale throughout; all core body poses readable without large detached effects; crossblade never covers the face; no labels, no text, no numbers, no panel borders, no shadows, no floor, no gradients, no texture, no watermark; do not use `#00ff00` anywhere in the subject.

Accepted source: `sivir_actor_contact.png` (default generated original `exec-00a12b1c-626b-4a1a-b54d-dc23a8e7d166.png`).

## Sivir nine-frame run cycle

Use case: stylized-concept. Asset type: final-scale pixel-art run-cycle contact sheet for Teamfight Manager 2. Input images: Image 1 is the locked Sivir character model—preserve her exact face, warm brown skin, long dark hair, teal-black-gold outfit, boots, proportions, outline, palette, and four-bladed crossblade. Image 2 is the accepted 3x3 run-cycle layout, stride energy, scale, and pixel rendering reference only. Primary request: Create a coherent nine-frame run cycle of the exact same Sivir from Image 1, carrying exactly one compact four-bladed crossblade close behind her torso while sprinting toward screen-right. Subject: Sivir in nine sequential full-body running poses with alternating left and right foot contacts, two passing poses, two airborne/extension poses, small natural torso lean, restrained vertical bounce, hair and cloth lag, and a stable weapon grip. Her face remains readable and her weapon shape does not mutate. Style/medium: polished hand-authored 2D pixel art, crisp dark pixel outlines, restrained palette, final-scale chibi sprite quality matching Image 1; no painterly blur or enlarged concept-art detail. Composition/framing: exact 3 columns by 3 rows grid on a 2048x2048 square canvas, chronological order left-to-right then top-to-bottom; equal cell sizes and generous empty padding; same body height and foot baseline class in all cells; full head, hair, weapon, both legs, and both feet visible. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: exactly one Sivir and one crossblade per cell; no duplicated limbs; clear nine-frame stride variation; no crouched shuffle, no walking, no sliding, no attack or spell effects; no labels, text, numbers, panel borders, shadows, floor, gradients, texture, or watermark; do not use `#00ff00` anywhere in the subject.

Accepted source: `sivir_run_contact.png` (default generated original `exec-0b7361b7-673c-4966-97c2-ae82fc1f3253.png`).

## Sivir Q icon

Use case: stylized-concept. Asset type: original square game UI skill icon for Sivir Q. Input images: Image 1 establishes Sivir's Shuriman crossblade design and teal-gold-black palette; Image 2 establishes the mod's crisp pixel-art rendering. Use them only as visual references and create original icon art. Primary request: depict a single symmetric four-bladed jeweled crossblade spinning forward and then curving back, communicating an outbound-and-return boomerang path with two clean opposing gold-white motion crescents. Subject: one readable dark-metal and gold crossblade with teal center gem; no character portrait, no extra weapons. Style/medium: richly painted pixel-art game icon, crisp silhouettes and hard readable edges at 24x24 downscale, dark navy vignette background, luminous Shuriman gold and cool white trails with restrained teal accents. Composition/framing: centered weapon at a slight diagonal, generous safe margin, strong circular motion read, full-bleed square. Constraints: original artwork; no text, letters, numbers, UI frame, logo, watermark, hand, person, extra projectile, or photographic detail.

Accepted source: `sivir_q_icon_source.png` (default generated original `exec-bbed210f-ec8c-41c9-ae42-c694fdc55ce2.png`).

## Sivir E icon

Use case: stylized-concept. Asset type: original square game UI skill icon for Sivir E Spell Shield. Input images: Image 1 establishes the locked Sivir teal-gold-black palette, crossblade motif, and crisp pixel-art rendering. Use it only as visual reference. Primary request: depict a compact single-use magical barrier as a bright cyan-teal circular shield with a gold Shuriman rim and a small four-point crossblade emblem at its center. A single incoming violet spell bolt should visibly break and dissolve at the outer edge, clearly communicating one blocked enemy ability. Subject: one shield, one blocked spell spark, no character portrait. Style/medium: richly painted pixel-art game icon, crisp silhouettes and readable hard edges at 24x24 downscale, dark navy vignette background, luminous cyan center, warm gold rim, tiny controlled white impact flash. Composition/framing: centered round barrier, slight three-quarter angle, generous safe margin, full-bleed square. Constraints: original artwork; no text, letters, numbers, UI frame, logo, watermark, hands, face, extra shields, damage explosion, or photographic detail.

Accepted source: `sivir_e_icon_source.png` (default generated original `exec-b582865a-dbc0-4a6f-a64d-f6ee6173d9f5.png`).

## Sivir R icon

Use case: stylized-concept. Asset type: original square game UI skill icon for Sivir R On The Hunt. Input images: Image 1 establishes the locked Sivir teal-gold-black palette, crossblade motif, and crisp pixel-art rendering. Use it only as visual reference. Primary request: communicate a team-wide battle charge: one radiant golden four-bladed crossblade emblem above three clean forward-rushing speed silhouettes/trails, with an expanding sand-gold circular pulse and teal wind accents. Subject: one crossblade command emblem and three abstract allied speed streaks, no character portrait. Style/medium: richly painted pixel-art game icon, crisp silhouette and readable hard edges at 24x24 downscale, dark navy vignette background, luminous Shuriman gold, warm sand, white highlights, restrained teal accents. Composition/framing: emblem centered in upper-middle, speed trails sweeping outward and forward beneath it, generous safe margin, full-bleed square, immediate sense of acceleration without damage or explosion. Constraints: original artwork; no text, letters, numbers, UI frame, logo, watermark, faces, weapons beyond the single emblem, explosion, shield bubble, or photographic detail.

Accepted source: `sivir_r_icon_source.png` (default generated original `exec-3724e3d5-809d-42ab-843c-b19e24e7e822.png`).

## Sivir basic-attack VFX

Use case: stylized-concept. Asset type: pixel-art projectile VFX contact sheet for Sivir basic attack. Input images: Image 1 establishes the locked crossblade shape, teal-gold-black palette, outline, and pixel rendering. Primary request: create eight sequential animation frames of one small spinning four-bladed crossblade projectile traveling toward screen-right. The crossblade must visibly originate as a compact hand-thrown weapon, rotate through distinct orientations, carry a short restrained gold-white trail, and end with a tiny teal-gold hit spark. Frame order, left-to-right then top-to-bottom: launch glint; rotation 1; rotation 2; rotation 3; rotation 4; rotation 5; approach streak; compact hit spark. Style/medium: clean hand-authored 2D pixel-art game VFX with crisp hard alpha-ready edges, dark outline on the weapon, limited colors, readable when packed near 24x24. Composition/framing: exact 4 columns by 2 rows grid on a 2048x1024 canvas, evenly spaced cells, one centered effect per cell, generous empty padding, consistent weapon size. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: one projectile per frame; no character, hand, body, labels, text, numbers, panel borders, shadows, floor, gradients, texture, watermark, giant explosion, or duplicated weapon; no persistent aura; do not use `#00ff00` in the effect.

Accepted source: `sivir_attack_vfx_contact.png` (default generated original `exec-262d4827-cb5c-43ed-af9b-f24456556ed4.png`).

## Sivir Q VFX

Use case: stylized-concept. Asset type: pixel-art projectile VFX contact sheet for Sivir Q Boomerang Blade. Input images: Image 1 locks Sivir's exact crossblade shape and teal-gold-black palette. Image 2 establishes the outbound-and-return ability identity. Create original animation frames consistent with both. Primary request: create eight sequential frames of one large spinning four-bladed crossblade boomerang. Frames 1–4 are the outbound phase traveling screen-right with a cold white-gold tail; frames 5–8 are the brighter return phase traveling screen-left with a slightly stronger gold-teal return trail. Rotation angle must clearly advance in every frame. Frame order, left-to-right then top-to-bottom: outbound rotations 1,2,3,4; return rotations 1,2,3,4. Style/medium: clean hand-authored 2D pixel-art game VFX, crisp hard alpha-ready edges, compact dark outline, limited palette, readable around 32–48 pixels. Composition/framing: exact 4 columns by 2 rows grid on a 2048x1024 canvas, evenly spaced cells, one centered effect per cell, generous empty padding, stable weapon size. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: exactly one crossblade in each frame; same weapon model and size; no character, hand, labels, text, numbers, panel borders, shadows, floor, gradients, texture, watermark, extra projectile, giant explosion, or weapon mutation; outbound and return must be visibly distinct by direction and trail brightness; do not use `#00ff00` in the effect.

Accepted source: `sivir_q_vfx_contact.png` (default generated original `exec-8917bc63-464a-4582-b73a-e033e95844fc.png`).

## Sivir E VFX

Use case: stylized-concept. Asset type: pixel-art buff VFX contact sheet for Sivir E Spell Shield. Input images: Image 1 establishes the cyan-teal and gold single-use spell barrier identity. Image 2 establishes Sivir's final actor scale; the effect must remain a tight body-hugging aura and must not contain the character. Primary request: create eight sequential frames of a compact circular spell shield animation: two quick activation frames, four stable shimmering loop frames, and two removal/break frames. Use a thin cyan-teal translucent ring with small gold Shuriman diamonds and a restrained four-point glint; the middle stays mostly empty so the actor remains visible. Frame order, left-to-right then top-to-bottom: activation spark, ring forms, loop shimmer A, loop shimmer B, loop shimmer C, loop shimmer D, blocked-spell crack, clean dissolve. Style/medium: clean hand-authored 2D pixel-art game VFX, crisp alpha-ready edges, limited palette, readable around a 48x56 body envelope, no painted fog. Composition/framing: exact 4 columns by 2 rows grid on a 2048x1024 canvas, evenly spaced cells, one centered shield effect per cell, generous empty padding, identical outer diameter. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: effect only; no Sivir body, face, weapon, incoming projectile, text, labels, numbers, panel borders, floor, cast shadow, gradients in the background, watermark, giant opaque bubble, or explosion; center must stay transparent/readable; do not use `#00ff00` in the effect.

Accepted source: `sivir_e_vfx_contact.png` (default generated original `exec-9cd4b21a-7dee-4d69-8228-c3151b553f4e.png`).

## Sivir R cast VFX

Use case: stylized-concept. Asset type: pixel-art cast VFX contact sheet for Sivir R On The Hunt. Input images: Image 1 establishes the Shuriman gold, sand, teal-wind, and crossblade command motif. Create original effect frames without copying the icon layout. Primary request: create eight sequential frames of a ground-level battle-command pulse expanding outward from Sivir's feet: a small gold crossblade sigil ignites, a thin sand-gold circular ring rapidly expands, four directional rays flash, then the ring fades into teal-gold wind sparks. The effect must read as team acceleration, not damage. Frame order, left-to-right then top-to-bottom: ignition; small ring; medium ring; large ring; peak command rays; outward wind ripple; fading ring; sparse final sparks. Style/medium: clean hand-authored 2D pixel-art game VFX, crisp alpha-ready edges, restrained transparent-looking interior, limited gold/white/teal palette, readable when packed around 96x48. Composition/framing: exact 4 columns by 2 rows grid on a 2048x1024 canvas; one centered low elliptical/circular effect per cell; identical center point; generous padding; keep vertical height compact so it does not cover the actor. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: effect only; no character, face, body, weapon projectile, text, labels, numbers, panel borders, floor texture, cast shadow, explosion, damage spikes, large vertical light column, opaque disk, or watermark; no persistent pillar; do not use `#00ff00` in the effect.

Accepted source: `sivir_r_cast_vfx_contact.png` (default generated original `exec-2a1a76af-7a43-455c-b811-467839cf0060.png`).

## Sivir R ally-buff VFX

Use case: stylized-concept. Asset type: pixel-art ally movement-speed buff VFX contact sheet for Sivir R On The Hunt. Input images: Image 1 establishes the Shuriman gold and teal wind language of the cast pulse. Create a smaller persistent ally buff that belongs to the same ability. Primary request: create eight sequential frames of a low-profile speed aura that sits just behind and beneath an allied champion's feet: two activation frames, four looping wind-streak frames, and two clean fade frames. Use two thin backward-swept teal-gold speed arcs, tiny sand sparks, and a very small open ring segment; keep the center and foot area mostly empty. Frame order, left-to-right then top-to-bottom: activation streak; aura forms; loop A; loop B; loop C; loop D; fade A; fade B. Style/medium: clean hand-authored 2D pixel-art game VFX, crisp alpha-ready edges, limited teal/gold/white palette, subtle and readable around a 56x24 footprint. Composition/framing: exact 4 columns by 2 rows grid on a 2048x1024 canvas, evenly spaced cells, one centered low horizontal effect per cell, stable dimensions, generous empty padding. Scene/backdrop: perfectly flat solid `#00ff00` chroma-key background. Constraints: effect only; no character, feet, face, body, weapon, text, labels, numbers, panel borders, floor texture, cast shadow, explosion, vertical light column, opaque disk, or watermark; never cover the actor's foot center; no large circle; do not use `#00ff00` in the effect.

Accepted source: `sivir_hunt_buff_vfx_contact.png` (default generated original `exec-997d2847-f965-4c78-a9f0-5af86aa548d3.png`).

# Kled image-gen source records

All ten Kled sources were generated with the built-in `image_gen` tool on 2026-07-12. The actor, run, defeat, and effect contacts were requested as hard-edged pixel art on a perfectly flat `#00ff00` chroma-key background, with no text, labels, panel borders, logo, or watermark. Character contacts required the same always-mounted Kled/Skaarl model, complete head/body/mount legs and feet, and generous safe margins so native-frame packing would not crop the weapon or mount. Icons and the BP illustration are independent original art and do not use the chroma-key route. Generated-images batch: `019f4bd8-30d3-7b60-98fa-58403cf263c7`.

## Kled mounted actor contact sheet

- Execution ID: `exec-9d525097-f1a2-48af-a356-ae42c4e68297`.
- Imported target: `source/imagegen/kled_actor_contact.png`; accepted alpha source: `source/processed/kled_actor_contact_alpha.png`.
- Purpose: locked always-mounted Kled/Skaarl body model for idle, attack, skill, ult, and hit actions.
- Generation requirements: one coherent 4x4 action grid; crisp final-scale chibi pixel art; the same orange-haired yordle rider, compact axe/pistol silhouette, and purple reptilian mount in every cell; full head, mounted torso, Skaarl legs and feet visible; consistent body scale and foot baseline; generous cell padding; flat `#00ff00`; no unmounted variant, second rider/mount, large detached spell effect, text, grid lines, scenery, logo, or watermark.

## Kled mounted run contact sheet

- Execution ID: `exec-eb603299-95a9-420d-8540-3c32018b20ae`.
- Imported target: `source/imagegen/kled_run_contact.png`; accepted alpha source: `source/processed/kled_run_contact_alpha.png`.
- Purpose: distinct mounted gait phases for the native eight-frame run action.
- Generation requirements: exact 3x3 chronological run cycle of the locked actor; clear alternating Skaarl leg contacts, forward momentum, restrained vertical bounce, stable rider/weapon/mount proportions, full feet and tail inside safe margins; crisp pixel art on flat `#00ff00`; no walking-in-place clone, sliding, duplicated limbs, attack VFX, labels, borders, scenery, logo, or watermark.

## Rejected Kled Q/E composite VFX contact sheet

- Execution ID: `exec-14e0a1e1-38cc-4df3-962d-5a7566b67f01`.
- Status: rejected after live review because it visually and mechanically bundled E into Q; the active source and processed derivative were deleted.
- Purpose: independent dash, spear-hook, rope/trap, tether, and delayed-pull effects for the combined Q+E slot.
- Generation requirements: exact 4x2 sequential effect grid; compact bronze/red spear-hook and rope/trap silhouettes with hollow centers where the target remains readable; fixed origins, generous padding, crisp hard-edged pixel art, flat `#00ff00`; effect only, no Kled/Skaarl body, character portrait, text, UI frame, giant opaque explosion, green effect pixels, logo, or watermark.

## Rejected Kled W four-hit VFX contact sheet

- Execution ID: `exec-ad51b92f-1be0-48f5-bd29-0be2b161a7c1`.
- Status: rejected after the user confirmed the public skills must be Q/E/R; the active source and processed derivative were deleted.
- Purpose: W activation, the first three compact hit streaks, the stronger fourth-hit burst, loop, and cleanup phases.
- Generation requirements: exact 4x2 effect grid; escalating crimson/orange claw and axe-like slashes with a clearly stronger but still compact fourth impact; readable at native size, stable center, generous padding, crisp pixel art on flat `#00ff00`; no character body, text, numbers, borders, blood/gore, opaque screen-filling flash, logo, or watermark.

## Rejected Kled R charge/trail VFX contact sheet

- Execution ID: `exec-10d2b838-97f7-4cf7-aa16-383d8d18424d`.
- Status: rejected after live review because the effect footprint was too dominant; the active source and processed derivative were deleted.
- Purpose: R charge start, straight ground trail, allied speed aura, terminal collision, and clean fade phases.
- Generation requirements: exact 4x2 effect grid; gold/ivory charge arcs, directional chevrons, low dust and ground streaks with mostly hollow actor space; fixed ground origin and generous padding; hard-edged pixel art on flat `#00ff00`; effect only, no mounted body, words, numbers, UI border, tall beam, opaque disk, scenery, logo, or watermark.

## Rejected Kled Q icon

- Execution ID: `exec-5a1ea3c6-19d0-4305-ac74-ef9c9fee7c04`.
- Status: superseded with the independently rebuilt Q projectile icon; the old active source was deleted.
- Purpose: original Q-slot icon communicating the spear-hook, rope, and trap latch.
- Generation requirements: square full-bleed game icon with a compact central silhouette, safe margin for 64x64 downscale, dark vignette and bronze/red highlights; crisp pixel-art finish; no character portrait, letter Q, words, numbers, external UI frame, logo, or watermark.

## Rejected Kled W-mapped second-slot icon

- Execution ID: `exec-e1a2db38-2650-40bb-913c-f278763198dc`.
- Status: rejected because the second slot is now true E Jousting; the old active source was deleted.
- Purpose: original second-slot icon for the mapped Violent Tendencies four-hit sequence.
- Generation requirements: square full-bleed icon with several escalating red-orange slashes and one bright final impact, strong silhouette at 64x64, safe border margin and crisp pixel-art edges; no face, letter W/E, words, numbers, external frame, logo, or watermark.

## Accepted Kled Q Bear Trap VFX v2

- Execution ID: `exec-c4124e03-bc88-494b-ac4a-fa5672a86289`.
- Imported target: `source/imagegen/kled_q_vfx_contact_v2.png`; accepted alpha source: `source/processed/kled_q_vfx_contact_v2_alpha.png`.
- Purpose: eight compact chronological Q-only frames: throw, projectile travel, first-target latch, thin tether, yank, and clean fade.
- Generation requirements: exact 4x2 grid, final-scale hard-edged pixel art, Noxian bronze/dark iron/muted red, a thin rope and hollow latch center, effect limited to the center 55% of each cell on flat `#00ff00`; no actor, dash, body aura, laser, giant jaw/ring, text, border, logo, or watermark.

## Accepted Kled E Jousting VFX

- Execution ID: `exec-73c43540-2fb5-4e49-9123-11079666a33c`.
- Imported target: `source/imagegen/kled_e_vfx_contact.png`; accepted alpha source: `source/processed/kled_e_vfx_contact_alpha.png`.
- Purpose: eight independent E-only dash, low dust, speed streak, pass-through impact, small mark, and fade frames.
- Generation requirements: exact 4x2 grid, compact low horizontal Noxian red/bronze/ivory pixel effects inside the center 55% of each cell on flat `#00ff00`; no actor, rope, trap, W claw sequence, large enclosing circle, text, border, logo, or watermark.

## Accepted Kled R charge/trail VFX v2

- Execution ID: `exec-cf0350b0-b032-4a79-bc1c-51b4545ecc64`.
- Imported target: `source/imagegen/kled_r_vfx_contact_v2.png`; accepted alpha source: `source/processed/kled_r_vfx_contact_v2_alpha.png`.
- Purpose: eight restrained R-only shield flare, ground chevrons, dust trail, open charge arc, collision, and fade frames.
- Generation requirements: exact 4x2 grid, low ground origin, open center, effect limited to the center 60% of each cell on flat `#00ff00`; no actor, giant opaque ring, tall beam, body-covering aura, text, border, logo, or watermark.

## Accepted Kled Q icon v2

- Execution ID: `exec-20aff087-3bab-4126-98ac-e9ccaca0f6cb`.
- Imported target: `source/imagegen/kled_q_icon_source_v2.png`.
- Purpose: Q-only thrown dark-iron bear trap with a thin trailing chain/rope and forward motion.
- Generation requirements: square full-bleed original MOBA icon, strong 64px silhouette, generous safe margin, bronze edge light and restrained red sparks; no face, Q letter, words, UI frame, logo, watermark, laser, or body aura.

## Accepted Kled E icon

- Execution ID: `exec-37cf68cb-8bfc-455c-93bc-126d997a2570`.
- Imported target: `source/imagegen/kled_e_icon_source.png`.
- Purpose: E-only red-gold lance-shaped speed streak and compact pass-through impact.
- Generation requirements: square full-bleed original MOBA icon readable at 64px, diagonal Noxian red/bronze motion with a 10% safe margin; no face, E/W letter, words, UI frame, rope, trap, four-hit slash sequence, logo, or watermark.

## Kled R icon

- Execution ID: `exec-1ac83133-29d1-4fe1-9e33-8d609c1edeb2`.
- Imported target: `source/imagegen/kled_r_icon_source.png`.
- Purpose: original ultimate icon communicating a fast straight mounted charge and collision.
- Generation requirements: square full-bleed icon with gold directional chevrons, dust, and a compact mounted-charge silhouette; safe margins and immediate readability at 64x64; crisp pixel-art finish; no letter R, words, numbers, external UI frame, logo, or watermark.

## Kled BP illustration

- Execution ID: `exec-45370931-aff3-4094-bf76-d6411fc38df8`.
- Imported target: `source/imagegen/bp_splash/cavalry_knight.png`.
- Purpose: Kled-only ban/pick side-card illustration, normalized to the runtime 284:172 card composition.
- Generation requirements: polished original League-like fantasy illustration of the locked mounted Kled/Skaarl identity in a dynamic charge; complete rider, mount head/body, and weapon kept inside generous crop-safe margins; a readable focal subject under wide-card cropping; no text, champion name, UI panel, official logo, watermark, duplicated rider/mount, or severed/cropped feet.

## Kled mounted defeat contact sheet

- Execution ID: `exec-094d104e-d2a7-4509-986c-04265cf98424`.
- Imported target: `source/imagegen/kled_defeat_contact.png`; accepted alpha source: `source/processed/kled_defeat_contact_alpha.png`.
- Purpose: mounted fall, settle, and defeated poses for the native `dead` and `fire_dead` frame counts.
- Generation requirements: exact 2x2 chronological contact sheet using the same locked Kled/Skaarl model and scale; full rider, mount, weapon, and fallen silhouette within large safe margins; crisp pixel art on flat `#00ff00`; no dismount/remount transformation, duplicate body or weapon, gore, spell explosion, text, borders, scenery, logo, or watermark.

# Quality-map surface microdetail v4

These three sources were generated with the built-in `image_gen` tool on 2026-07-12. They are texture references only. The v4 packer removes low-frequency structure with a Gaussian blur, converts the residual to neutral high-frequency luminance, applies it at no more than 8-10% soft-light strength, and composites it back only through the official native alpha. The generated spatial layout, silhouettes, paths, water, collision, map settings, and dynamic minimap markers are never copied.

## Rift exterior cliff microdetail v4

- Execution ID: `exec-314b7938-4a24-46ba-aea4-fb476c3c8329`.
- Imported target: `source/imagegen/map/rift_cliff_microdetail_v4_source.png`.
- Runtime use: high-frequency-luminance-only detail, capped at 0.10, only on official `wall_5v5` alpha where `x < 192` or `x >= 1088` and `y >= 160`.
- Generation requirements: seamless orthographic top-down dark slate rift cliff texture; layered rock microfacets, thin roots, restrained moss, and tiny cyan mineral glints; original hand-painted MOBA environment feel; no lanes, roads, rivers, pools, pits, walls as map geometry, buildings, camps, landmarks, symbols, text, logo, watermark, lighting gradient, or perspective scene.

## Rift wall masonry microdetail v3

- Execution ID: `exec-b126d077-ca6f-4580-845c-85e54c299ad7`.
- Imported target: `source/imagegen/map/rift_wall_masonry_v3_source.png`.
- Runtime use: high-frequency-luminance-only detail, capped at 0.08, on the general official `wall_5v5` alpha and the entire official `wall_5v5_front` alpha.
- Generation requirements: seamless orthographic top-down blue-gray rift masonry texture; varied small slate blocks, fine cracks, restrained moss, tiny roots, and sparse cyan mineral details; original hand-painted MOBA environment feel; no map layout, lanes, water, pits, buildings, camps, landmarks, symbols, text, logo, watermark, lighting gradient, or perspective scene.

## Rift bush microdetail v3

- Execution ID: `exec-d8c82ac3-7568-41bb-973a-304bb910f23b`.
- Imported target: `source/imagegen/map/rift_bush_microdetail_v3_source.png`.
- Runtime use: high-frequency-luminance-only detail, capped at 0.08, only through the official `bush_5v5` alpha.
- Generation requirements: seamless orthographic top-down dense dark emerald rift brush texture; fine leaves, ferns, thin vines, and sparse blue-violet flowers; original hand-painted MOBA environment feel; no paths, clearings, water, stone walls, terrain layout, buildings, camps, landmarks, symbols, text, logo, watermark, lighting gradient, or perspective scene.

# Xayah image-gen prompts

All Xayah sources were generated with the built-in `image_gen` tool on 2026-07-12 in batch `019f4bd8-30d3-7b60-98fa-58403cf263c7`. Character and VFX contacts use a flat `#00ff00` chroma-key background for the local alpha-removal workflow. Icons and the BP splash are opaque original illustrations. Every prompt required original art with no text, letters, numbers, logo, watermark, panel border, or unrelated character.

## Xayah actor contact

- Execution ID: `exec-7701ed50-84bb-4c42-bc50-f2cf2f86072b`.
- Imported target: `source/imagegen/xayah_actor_contact.png`; accepted alpha source: `source/processed/xayah_actor_contact_alpha.png`.
- Key prompt: exact 4x3 pixel-art action contact sheet of one consistent full-body Xayah model; magenta hair, violet feather hood/cape, dark plum armor, gold trim and crystal feather daggers; four idle/ready poses, four attack/throw poses, then four Q/E/R/hit-safe cast poses; stable body proportions, clear head, torso, legs and clawed feet, compact weapons and generous padding on perfectly flat `#00ff00`; no scenery, detached giant VFX, duplicate body, cropped feet, grid lines, text, logo, or watermark.

## Xayah run contact

- Execution ID: `exec-de545759-00d3-4e35-942e-44c3b3e41912`.
- Imported target: `source/imagegen/xayah_run_contact.png`; accepted alpha source: `source/processed/xayah_run_contact_alpha.png`.
- Key prompt: exact 4x2 chronological eight-frame side-running cycle using the locked actor identity and scale; alternating leg contacts, restrained cape bounce and forward momentum, complete feet and hood in every cell, stable baseline and compact silhouette on flat `#00ff00`; no sliding clone, extra limbs, attack effect, labels, border, scenery, logo, or watermark.

## Xayah defeat contact

- Execution ID: `exec-23dae259-50cf-441f-b2f1-0e02644dc296`.
- Imported target: `source/imagegen/xayah_defeat_contact.png`; accepted alpha source: `source/processed/xayah_defeat_contact_alpha.png`.
- Key prompt: exact 3x3 chronological fall-and-defeat sheet of the same locked Xayah actor: stagger, fall, kneel, collapse, grounded and settled phases; intact non-gory body, cape and one compact dagger fully inside each cell on flat `#00ff00`; no revival, duplicate body, severed limbs, explosion, text, border, scenery, logo, or watermark.

## Xayah Q icon

- Execution ID: `exec-6b94dadd-7846-4d8d-b35e-1f5bde124d8c`.
- Imported target: `source/imagegen/xayah_q_icon_source.png`.
- Key prompt: square full-bleed original MOBA icon for Double Daggers, exactly two parallel violet-magenta crystal feather blades flying diagonally across a dark indigo background, bright readable edges and safe margin for 64x64 downscale; no face, hand, letter Q, text, external UI frame, logo, or watermark.

## Xayah E icon

- Execution ID: `exec-3f657323-3644-4485-980c-8729ea1c318f`.
- Imported target: `source/imagegen/xayah_e_icon_source.png`.
- Key prompt: square full-bleed original MOBA icon for Bladecaller, several violet-magenta feather blades converging toward one center with curved return trails, strong radial silhouette on dark indigo, readable at 64x64; no character portrait, letter E, text, frame, logo, or watermark.

## Xayah R icon

- Execution ID: `exec-496337cc-de5f-4d21-a34f-3cc68c1f7e02`.
- Imported target: `source/imagegen/xayah_r_icon_source.png`.
- Key prompt: square full-bleed original MOBA icon for Featherstorm, airborne dark feathered huntress silhouette above a broad magenta-violet fan of crystal feathers, moonlit indigo background and strong 64px silhouette; no letter R, text, external frame, logo, or watermark.

## Xayah basic-attack VFX

- Execution ID: `exec-2a5b5154-eb36-46f7-9b02-9af21f0ee3ad`.
- Imported target: `source/imagegen/xayah_attack_vfx_contact.png`; accepted alpha source: `source/processed/xayah_attack_vfx_contact_alpha.png`.
- Key prompt: exact 4x2 pixel-art effect contact: top row four phases of one compact violet feather projectile traveling right; bottom row four phases of its small star-shaped feather impact and clean dissolve; stable center, generous padding and flat `#00ff00`; effect only, no actor, second projectile, giant explosion, text, border, logo, or watermark.

## Xayah Q VFX

- Execution ID: `exec-7de3674c-1147-4f64-8995-b22ed24b39cb`.
- Imported target: `source/imagegen/xayah_q_vfx_contact.png`; accepted alpha source: `source/processed/xayah_q_vfx_contact_alpha.png`.
- Key prompt: exact 4x2 pixel-art Double Daggers contact: top row four travel phases of the paired long magenta crystal feathers, bottom row four sharp feather impacts and dissolve phases, fixed direction and size on flat `#00ff00`; effect only, no character, text, border, logo, or watermark. The runtime builder deliberately crops one feather from each top-row cell because gameplay launches two independently timed projectiles.

## Xayah E VFX

- Execution ID: `exec-46c0fb68-6656-43a6-89a6-dc4632134d2d`.
- Imported target: `source/imagegen/xayah_e_vfx_contact.png`; accepted alpha source: `source/processed/xayah_e_vfx_contact_alpha.png`.
- Key prompt: exact 4x2 pixel-art Bladecaller contact: top row four phases of three feathers curving back toward the caster; bottom row four crossed-feather root sigils with an open center, thin magenta ring and clean fade; stable anchor, generous padding and flat `#00ff00`; no actor, opaque body-covering disk, text, border, logo, or watermark.

## Xayah R VFX

- Execution ID: `exec-4766b1bd-0dc1-43f1-9359-ef27b0c17c48`.
- Imported target: `source/imagegen/xayah_r_vfx_contact.png`; accepted alpha source: `source/processed/xayah_r_vfx_contact_alpha.png`.
- Key prompt: exact 4x2 pixel-art Featherstorm contact: top row four phases of a broad five-feather fan opening outward; bottom row four landing/guard bursts with an open actor center and clean dissolve, vivid magenta-violet on flat `#00ff00`; effect only, no character, opaque screen-filling flash, text, border, logo, or watermark.

## Xayah BP splash

- Execution ID: `exec-6d731110-576e-4f43-8510-0d21c5d8382b`.
- Imported target: `source/imagegen/bp_splash/dancer.png`.
- Key prompt: polished original wide fantasy illustration of Xayah in a moonlit Ionian forest, complete dynamic full body, magenta hair, feather hood/cape and crystal feather daggers, readable subject with generous crop-safe margins for the 1420x860 ban/pick card; no text, champion name, UI panel, official logo, watermark, duplicate body, or cropped feet.

## Xayah final-scale corrective actor and VFX pass

The first 320-pixel-detail actor/run route above is retained only as rejected provenance: at native 007 size it produced a 41-44px-tall body with one-pixel bottom clearance, an unreadable face, and 9.6%-43.7% horizontal run compression. The active route is the built-in `image_gen` corrective batch `019f560d-2e11-70e1-a2b8-60cdebabc3ba`. Every body prompt locked one simplified 16-bit model with a 6x6-or-larger face opening, full feet, short knee-length cape, chunky logical pixels, flat `#00ff00`, no body VFX, no text, border, logo, watermark, shadow, or scenery.

- Removed/superseded Idle v2: execution `exec-1b62a431-bd0b-4183-b129-7a7526a69011`; former paths `source/imagegen/xayah_idle_contact_v2.png` -> `source/processed/xayah_idle_contact_v2_alpha.png`. Compact review showed that both eyes were not reliably readable, so both files were deleted; this line is the only retained provenance and the builder must not use the route for runtime actor or portrait art.
- Accepted Idle v3: execution `exec-14c8a307-6e2b-4821-859a-9f62c5e391ef`; `source/imagegen/xayah_idle_contact_v3.png` -> `source/processed/xayah_idle_contact_v3_alpha.png`. Four locked-model full-body idle silhouettes with two clearly separated visible eyes, readable magenta fringe, complete feather ears, cape, legs and feet, generous transparent margins, and no body VFX. This is the sole idle source and the high-resolution source for the dedicated compact, 90x122 BP-grid, and encyclopedia portraits.
- Core/attack/hit: execution `exec-64ff4089-db0a-4485-911a-04a03a593458`; `source/imagegen/xayah_core_body_contact_v2.png` -> `source/processed/xayah_core_body_contact_v2_alpha.png`. Exact 5x2 grid: idle references plus hit on row one, five body-only basic-attack phases on row two; active packing uses the hit and attack cells.
- Run 8: execution `exec-f6d84990-a38a-4f51-a8ac-15cd2e55623e`; `source/imagegen/xayah_run_contact_v2.png` -> `source/processed/xayah_run_contact_v2_alpha.png`. Exact 4x2 chronological compact sprint with alternating feet and narrow cape.
- Q body 5: execution `exec-fdca83ae-1972-4306-ab00-ae2dd1feac0c`; `source/imagegen/xayah_q_body_contact_v2.png` -> `source/processed/xayah_q_body_contact_v2_alpha.png`. Unique double-arm forward throw sequence with no released projectile.
- E body 3: execution `exec-a6dacdf5-c950-4e03-b8e5-206252eb08c8`; `source/imagegen/xayah_e_body_contact_v2.png` -> `source/processed/xayah_e_body_contact_v2_alpha.png`. Unique open-hands/pull-to-chest/recovery recall sequence.
- R body 5: execution `exec-2168dfce-962e-4ddb-8060-a7055fa1322e`; `source/imagegen/xayah_r_body_contact_v2.png` -> `source/processed/xayah_r_body_contact_v2_alpha.png`. Unique crouch/rise/apex/descent/landing sequence; no E pose reuse or giant wing VFX.
- Dead 9: execution `exec-4c5bbbf1-13f1-4ed7-bf51-32ea5f8e7ac4`; `source/imagegen/xayah_defeat_contact_v2.png` -> `source/processed/xayah_defeat_contact_v2_alpha.png`. Exact 3x3 non-gory continuous fall and settle.
- Q VFX v2: execution `exec-ecca4378-a2a9-4fa0-9632-6097fc623ff4`; `source/imagegen/xayah_q_vfx_contact_v2.png` -> `source/processed/xayah_q_vfx_contact_v2_alpha.png`. Exact 4x2; every projectile frame contains one and only one straight feather, so the two gameplay launches render two total feathers rather than four.
- E VFX v3: execution `exec-000f3867-e11d-49cf-ae52-c9e0d8649024`; `source/imagegen/xayah_e_vfx_contact_v3.png` -> `source/processed/xayah_e_vfx_contact_v3_alpha.png`. Exact 4x4 independent rows for one-feather return, two-feather return, three-feather cluster return, and triangular root; no attack/Q asset reuse.
- R VFX v2: execution `exec-bd5ad3d7-1657-4558-9bc0-597a46dc4aaf`; `source/imagegen/xayah_r_vfx_contact_v2.png` -> `source/processed/xayah_r_vfx_contact_v2_alpha.png`. Exact 4x3 rows for the five-feather fan, five-feather impact, and empty-center oval guard afterimage.
- Ground Feather VFX v1: execution `exec-178182ff-7735-4228-b339-62352f37295c`; `source/imagegen/xayah_ground_feather_contact_v1.png` -> `source/processed/xayah_ground_feather_contact_v1_alpha.png`. Exact 4x2 rows for one embedded Q Feather and one five-Feather R landing fan. Runtime packing reduces them to 48x40 / 72x48, plays once, and forces the fourth frame fully transparent so the fixed 180-tick data projectile cannot leave a permanently visible ghost.

All corrective chroma sources used the installed `remove_chroma_key.py` helper with border auto-key, soft matte, thresholds 12/220 and despill. Validation found transparent corners and zero visible green-dominant residue in every accepted output.
