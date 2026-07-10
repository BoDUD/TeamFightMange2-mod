# Lucian official audio source QA

All eight runtime clips are decoded without remixing from the local League of Legends base Lucian SFX bank in `Game/DATA/FINAL/Champions/Lucian.wad.client`.

The machine-verifiable event name, media ID, WEM hash, WAV hash, channel count, sample rate, and duration records live in `lucian_official_audio_sources.json`. `extract_lucian_audio.py` pins the WAD and internal bank fingerprints before invoking `vgmstream-cli`.

Action wiring:

- Basic attack: `LucianBasicAttack_OnMissileLaunch` and `LucianBasicAttack_OnHit`.
- Lightslinger: `LucianPassiveAttack_OnMissileLaunch` and `LucianPassiveAttack_OnHit`.
- Q: `LucianQ_OnCast`.
- E: `LucianE_OnCast`.
- R: `LucianR_OnCast` plus `LucianR_OnBuffActivate` for the channel gunfire.

All `.sound_info` volumes are `1.0`; every event and clip has an explicit `mod.override_info` remap.
