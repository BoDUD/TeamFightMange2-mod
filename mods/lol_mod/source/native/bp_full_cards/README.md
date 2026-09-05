# Portable native BP inputs

These are the 52 native (non-mod-owned) compact actor crops already used by
the BP full-card packer, extracted from the installed 0.5.8 bundle. They are
build inputs, not new hero models or the full game archive. The manifest
records the native roster, styles, crop identity and each PNG checksum.

Normal builds always use this snapshot and load mod-owned heroes directly
from their current local actor sheets. No CI game installation is required.
A changed native crop contract fails instead of silently using stale pixels.

Explicit regeneration, only from a matching local game installation:

```python
from build_bp_full_cards import export_native_sources
export_native_sources()
```

Review the changed portrait inputs before committing a regenerated snapshot.
