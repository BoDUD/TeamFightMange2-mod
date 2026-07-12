# League system audio QA

## Runtime coverage

- BP music: the source is now the actual League Client draft plug-in at `Plugins/rcp-fe-lol-champ-select/assets.wad`, not the unrelated in-game `mus_client_pregameui_default` event. The plug-in's pinned JavaScript proves the synchronized layer and volume rules. Because TFM2 exposes one BP loop instead of per-pick layer switching, `sound/bgm/lol_banpick.wav` uses the exact official completed-pick-count 6 stack: base `0.37`, intensity 1 `0.37`, intensity 2 `0.37`, intensity 3 `0.2775`, and intensity 4 `0.185`. The native `banpick`, `banpick2`, and `banpick_match5_lastgame` keys remain mapped to this one representative draft loop.
- Match music: the Map11 Wwise event is resolved at state `phase_01` (`2002117580`). `sound/bgm/lol_match.wav` uses that branch's official 300-second base/master gameplay WEM `54102751` by itself. The separate 105-second side intro and 60-second event accent layers are intentionally omitted because TFM2 has one static match BGM key and cannot reproduce Map11's runtime state machine. Native `match` through `match6` all remain mapped to it.
- Management, title, tutorial, new-game, and result-screen music are intentionally untouched.
- Both tracks are stereo 44.1 kHz PCM16 with a fixed +4 dB TFM2 playback gain. The pinned outputs contain no clipped samples. The end-to-start boundary deltas are -52.92 dBFS for BP and -35.42 dBFS for Map11, below the focused QA gate and without a crossfade, arbitrary timeline, or unrelated-source remix.

## Multikill announcements

The game already owns the visible `center_kill` lifetime and its `#text` plus `#kills/#icon1..#icon5` nodes. Its private `play_kill_count_sound` path dispatches these native keys, so the mod only replaces their audio assets:

| Count | Native key | Official Female1 event |
| --- | --- | --- |
| 2 | `dual_takedown` | `DoubleKillYouYourTeam` |
| 3 | `triple_takedown` | `TripleKillYouYourTeam` |
| 4 | `devastation` | `QuadraKillYouYourTeam` |
| 5 | `annihilation` | `PentaKillYouYourTeam` |

Each output is one deterministic take from Riot's equal-weight Random/Shuffle pool. There is no new UI overlay, polling loop, kill-window guess, or duplicate sound dispatch.

## First Blood boundary

The exact EN-US source is fully audited as `Play_vo_Announcer_Female1_FirstBloodYouYourTeam` (event `1941092771`, WEM `835992869`). It is not shipped as a dead runtime file because the base bundle and public mod API expose no proven global first-kill sound key. Adding a guessed callback would risk repeat playback, spectator desync, and conflicts with the native center-kill timer. This remains an explicit engine/API boundary rather than a falsely claimed feature.

## Locale and provenance

This local League installation contains `Map11.en_US.wad.client` but no `Map11.zh_CN.wad.client` or `Map11.zh_MY.wad.client`; the installed `Global.zh_MY` WAD contains no Female1 announcer chunks. EN-US is therefore the only installed official announcer source. Exact client plug-in WAD, JavaScript, OGG layer, Map11 bank/package/event, WEM, decoded WAV, and tool hashes are pinned in `league_music_source_qa.json` and `league_announcer_source_qa.json`.

Run the focused contract suite with:

```text
python -m pytest tests/test_league_system_audio.py -q
```
