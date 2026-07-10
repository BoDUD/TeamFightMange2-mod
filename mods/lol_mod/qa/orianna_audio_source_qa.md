# Orianna official audio source QA

All nine runtime clips are decoded without remixing from the local League of Legends base Orianna SFX bank in `Game/DATA/FINAL/Champions/Orianna.wad.client`.

The event mapping is not based on filename guesses. The base-skin registry supplies the exact Riot event names, and the paired Wwise event bank resolves each event to its media pool. The WAD, registry, audio bank, event bank, tools, event IDs, media IDs, source WEM hashes, decoded WAV hashes, formats, and durations are pinned in `orianna_official_audio_sources.json`. `extract_orianna_audio.py` independently verifies the WAD and embedded audio-bank fingerprints before invoking `vgmstream-cli`.

Action mapping:

- Basic attack: the cast event layers Riot's `OriannaBasicAttack_OnCast` mechanical windup at delay 0.00 with `OriannaBasicAttack_OnMissileLaunch` at delay 0.04, then the Flesh branch of `OriannaBasicAttack_OnHit` plays on contact. This restores all three official attack stages instead of exposing only the quieter launch/hit pair.
- Q / Command: Attack (`OrianaIzunaCommand`): command cast and `OriannaIzuna_hit`.
- E / Command: Protect (`OrianaRedactCommand`): command cast and `OrianaRedactShield_OnBuffActivate` at shield arrival. Riot's base event registry has no separate Redact hit event, so the target-side shield activation is deliberately exposed as the mod's `e_hit` event.
- R / Command: Shockwave (`OrianaDetonateCommand`): command cast and `OriannaDetonateCommand_hit`.

Q and E cast both route to the same four-variant Riot random pool. The fixed mod events select different official variants from that pool so the two skills do not become identical. Both basic-attack cast layers and every other `.sound_info` play use volume `1.0`.

Runtime integration remaps the eight `lol_orianna_*` events plus all nine clip assets. `lol_orianna_attack_cast` owns the two-layer windup/launch `sound_info`; the champion attack still dispatches one cast event and one target-side hit event.

Offline PCM mix QA at the configured 0.04-second launch delay measures the two-layer cast at approximately -17.84 dBFS RMS and -1.74 dBFS peak with zero samples above 0 dBFS. This places the cast feedback in the same audible class as the accepted Shen/Lucian attacks without clipping.
