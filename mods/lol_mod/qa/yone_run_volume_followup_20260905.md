# Yone run volume follow-up — 0.12.19

## REJECTED — DO NOT INSTALL

The user rejected revision 2 after inspecting the three-row comparison.
Wider clusters did not solve the underlying anatomical/pose problems: knees
read as lumps, thigh-to-shin transitions remain unnatural and leg support is
not consistently readable. Volume measurements and passing tests cannot
override this rejection. Installation of 0.12.19 was stopped. The installed
game remains 0.12.18 (also visually rejected); no rollback is claimed.
The current working-tree assets are rejected candidates, not release-ready.

0.12.18 is **visually rejected by the user**: its 4–5px leg strips lost the
baggy trousers and substantial boots of the original model. Automated passing
tests did not establish visual quality. Do not reuse that thin-leg revision.

Revision 2 keeps the same model, protected upper body/swords, native dimensions,
eight frames and 80ms timing. It restores the two original upper-thigh/waist
rows verbatim, uses 7–8px near-leg / 6–7px far-leg thigh clusters, rounded knee
folds, 5px boot shafts and 6px soles. It does not increase stride or rescale the
actor. Far-leg cloth uses readable existing navy shades rather than vanishing
against the background.

New regression gate: actual five-row thigh area retains at least 70% of the
original source's occupied pixels during crossing, source waist rows are exact,
authored thighs are at least 6px wide, boot shafts at least 5px. These are volume
safety checks, **not** proof of natural motion or anatomical correctness.

Offline comparison was rendered from the installed rejected atlas and revised
pixels, at equal native boxes/floor anchors. Evidence outside the shipped mod:
`output/yone_leg_edit_v2/comparison.png`, `comparison.gif`, `contact.png`, `run.gif`.
Original source, rejected installed result and new candidate are separated in
the comparison. Live battle acceptance is pending; no game/save was opened.

Encyclopedia, BP, Xayah and skill mechanics are unchanged by this Yone-only pass.
