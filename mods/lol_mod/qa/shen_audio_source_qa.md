# Shen official audio source QA

All seven runtime clips are decoded without remixing from the local League of Legends base Shen SFX bank in `Game/DATA/FINAL/Champions/Shen.wad.client`.

The machine-verifiable event, media ID, WEM hash, WAV hash, channel count, sample rate, and duration records live in `shen_official_audio_sources.json`. The extraction script validates the WAD and WEM fingerprints before invoking `vgmstream-cli`.

Action wiring:

- Basic attack: `ShenBasicAttack_OnCast` and `ShenBasicAttack_OnHit`.
- Q: `ShenQ_OnCast`.
- W: `ShenW_OnCast` plus `ShenW_hit_block` at the field impact timing.
- R: `ShenR_OnCast` plus `ShenR_foley` at the 48-tick teleport timing.

All `.sound_info` volumes are `1.0`; every event and clip has its own `mod.override_info` remap.
