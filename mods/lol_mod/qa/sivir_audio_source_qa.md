# Sivir official audio source QA

All seven runtime clips are decoded without remixing from the local League of Legends base Sivir SFX bank in `Game/DATA/FINAL/Champions/Sivir.wad.client`.

`sivir_official_audio_sources.json` pins the WAD and embedded bank hashes, Riot event names and IDs, media pools, selected media IDs, source WEM hashes, decoded WAV hashes, formats, durations, and runtime volumes. `extract_sivir_audio.py` verifies the pinned WAD and audio-bank fingerprints before decoding through `vgmstream-cli`.

Action mapping:

- Basic attack uses the champion-specific MissileLaunch event plus one hit event. The separate OnCast layer is intentionally omitted to prevent full-volume clipping.
- Q uses separate outbound, return, and hit events. The return event is dispatched exactly once from the outbound projectile's `end_effects` before the nested return projectile is created.
- E uses the official Spell Shield buff-activation event. A deactivate event is not packaged because the public data runtime cannot guarantee one exact consume/deactivate trigger.
- R uses one top-level OnCast event. It is deliberately outside the per-ally `RangeEffect`, preventing the command sound from playing once per affected ally.

All clips are mono, 16-bit PCM, 44.1 kHz. The Riot WAD, Wwise banks, source WEMs, path hash tables, and extraction executables remain external and are not committed.

## Same-ID native audio isolation

The native `boomerang_hunter` action layer automatically dispatches its original attack/Q/E/R audio in addition to the explicit replacement effects. All eight discovered native event keys and all 18 original Boomerang Hunter clip keys are therefore remapped to `sivir_native_silence` / `sivir_native_silence_clip`.

The silence target is a valid 50 ms mono PCM16 44.1 kHz WAV containing 2205 all-zero frames. It avoids an empty-play-list fallback while ensuring that only the seven explicit League Sivir clips remain audible. `sivir_official_audio_sources.json`, the static validator and unit tests pin the complete isolation list, format and hash.
