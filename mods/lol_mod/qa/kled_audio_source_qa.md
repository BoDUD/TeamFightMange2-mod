# Kled official audio source QA

All 14 runtime clips are decoded without remixing from the local League of Legends Base Kled SFX bank in `Game/DATA/FINAL/Champions/Kled.wad.client`.

`kled_official_audio_sources.json` pins the local WAD, Base skin registry, audio and event banks, path hashes, extraction tools, exact Riot event names, lowercase FNV-1 event IDs, wwiser media pools, selected media IDs, source WEM hashes, decoded WAV hashes, formats, durations, runtime volumes, and native-audio isolation contract. `extract_kled_audio.py` verifies every pinned fingerprint, proves that each event resolves to the recorded media pool through wwiser, and only then decodes through `vgmstream-cli`.

## Runtime mapping

- Basic attack uses one official `KledBasicAttack_OnCast` variant and the first variant in the event's default non-Metal/Stone/Wood hit switch.
- Q uses the official Bear Trap missile-launch one-shot, the Q mark activation when the tether attaches, and the Q mark deactivation only when the delayed pull resolves.
- E uses the official `KledEDash` cast and hit one-shots. These are separate from Q so the public three-active-slot contract remains Q/E/R.
- W remains folded into the basic-attack state machine, not exposed as a fourth active skill. It uses one short `KledW_buffactivate` event and the four ordered `KledWAttack1..4_OnHit` events. The 5.365-second `KledWActive_OnBuffActivate` pool is deliberately excluded because it can outlive or overlap the four-hit window.
- R uses the deterministic mono `KledRDash_cast` and `KledRDash_hit` one-shots. `KledR_cast` is a 3.2-3.8-second stereo sequence, while `KledR_spell4_cycle` and the other charge layers are continuous; none are packaged because the data runtime has no proven matching stop event.

Cast sounds belong in top-level `Sfx` effects. Damage/mark sounds belong in `TargetSfx` after the corresponding successful effect. In particular, E hit and R impact must dispatch once, Q pull must only dispatch from the delayed pull, and W stage sounds must only advance after a committed hit.

Every `.sound_info` play has volume `1.0`. All outputs are mono, 16-bit PCM, 44.1 kHz. Every `lol_kled_*` event and every `kled_*_clip` has an explicit `mod.override_info` remap.

## Same-ID native audio isolation

Official champion 006 is `cavalry_knight`. Its native action layer can automatically dispatch original Cavalry audio in addition to the explicit Kled effects. The following event keys are remapped to `kled_native_silence`:

- `cavalry_knight_attack`
- `cavalry_knight_skill1`
- `cavalry_knight_skill2`
- `cavalry_knight_ult`

The following native clip keys are independently remapped to `kled_native_silence_clip`:

- `cavalry_knight_attack_resource`
- `cavalry_knight_skill_resource`
- `cavalry_knight_skill2_resource`
- `cavalry_knight_ult_resource`

The silence target is a valid 50 ms mono PCM16 44.1 kHz WAV containing 2,205 all-zero frames. It avoids missing/empty play-list fallbacks while guaranteeing that only the explicit Kled events remain audible.

## Reproduction

Run from the repository root:

```powershell
$env:PYTHONIOENCODING='utf-8'
python .\mods\lol_mod\tools\extract_kled_audio.py
```

The Riot WAD, extracted banks, Base registry, WEM intermediates, hashtable, wadtools, wwiser, and vgmstream executables remain external and are not committed. Only the decoded runtime WAVs and their machine-verifiable provenance are committed.
