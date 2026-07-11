# League system audio QA

## Runtime coverage

- BP music: the audited local Riot `mus_client_pregameui_default` source is decoded to `sound/bgm/lol_banpick.wav`. The native `banpick`, `banpick2`, and `banpick_match5_lastgame` keys all remap to this one track.
- Match music: the official loop body of one resolved Summoner's Rift Map11 layered event cycle is decoded to `sound/bgm/lol_match.wav`. Native `match` through `match6` all remap to it.
- Management, title, tutorial, new-game, and result-screen music are intentionally untouched.
- Both tracks are stereo 44.1 kHz PCM16. A fixed +4 dB runtime gain and the Map11 event's own Wwise loop-marker bounds are the only edits; the pinned outputs contain no clipped samples. The end-to-start boundary deltas are -70.31 dBFS for BP and -32.16 dBFS for Map11, below the focused QA gate and without an arbitrary crossfade/remix.

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

This local League installation contains `Map11.en_US.wad.client` but no `Map11.zh_CN.wad.client` or `Map11.zh_MY.wad.client`; the installed `Global.zh_MY` WAD contains no Female1 announcer chunks. EN-US is therefore the only installed official announcer source. Exact WAD, chunk, event, container, WEM, decoded WAV, and tool hashes are pinned in `league_music_source_qa.json` and `league_announcer_source_qa.json`.

Run the focused contract suite with:

```text
python -m pytest tests/test_league_system_audio.py -q
```
