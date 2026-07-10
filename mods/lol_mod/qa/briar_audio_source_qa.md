# Briar official audio source QA

All nine runtime clips are decoded without remixing from the local League of Legends base Briar SFX bank in Game/DATA/FINAL/Champions/Briar.wad.client.

The mapping is not based on filename or media-ID guesses. The base-skin registry supplies the Riot event names, lowercase FNV-1 supplies their Wwise event IDs, and the paired event bank resolves those IDs to media pools. briar_official_audio_sources.json pins the WAD, registry, event bank, audio bank, tools, event IDs, media IDs, source WEM hashes, decoded WAV hashes, formats, and durations. extract_briar_audio.py independently verifies the WAD and embedded audio-bank fingerprints before invoking vgmstream-cli.

Action mapping:

- Basic attack: BriarBasicAttack_OnCast and the character-impact layer of BriarBasicAttack_OnHit.
- Frenzy attack: BriarBasicAttackFrenzy_OnCast and BriarBasicAttackFrenzy_OnHit.
- Q slot / Blood Frenzy: BriarW_cast_foley_jump. The mod intentionally places Blood Frenzy / Snack in its first Q-labelled skill slot, so the official League event retains its W name in provenance.
- E / Chilling Scream: BriarEMisStrong_missilelaunch_charged and BriarEMisStrong_OnHit.
- R / Certain Death: BriarR_OnCast and BriarR_OnHit.

The basic-attack hit event also layers a material-switch impact. At full volume, the selected character layer plus the first Flesh material variant exceeds PCM full scale, so the fixed mod event uses only Briar's character-impact layer. This preserves the champion-specific sound and avoids clipping.

The exact Snack self event, BriarWAttackSpell_buffactivate_self (event 3856742472, media 509331730), resolves correctly but decodes as a 3.015-second stereo clip. It is excluded because spatial combat clips in this mod are mono and including it would require a remix. The mod uses the verified BriarBasicAttackFrenzy_OnHit media as the Snack contact proxy instead. No independent Briar bleed-tick event is registered in the base-skin event table; repeated bleed ticks therefore do not dispatch a guessed or rapidly repeating sound.

Every sound_info play uses volume 1.0. Runtime integration must remap each lol_briar_* event and every briar_*_clip asset independently in mod.override_info.

Repository scope is deliberately small: the nine decoded WAVs total 872,588 bytes. The Riot WAD, Wwise banks, source WEMs, hashtable, wadtools, wwiser, and vgmstream executables remain external and are not committed.
