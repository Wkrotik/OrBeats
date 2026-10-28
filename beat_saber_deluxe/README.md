# OrBeats implementation

See the [project README](../README.md) for installation, compatibility and credits.
The source directory retains its upstream name to avoid breaking tooling.

- `src/main.cpp`, `include/additive_*.h`: the single GoldHEN plugin.
- `tools/additive_companion.py`, `tools/additive_library.py`: independent-song
  import, bounded library format and closed-title publication.
- `webapp/`: local FastAPI companion, discovery and installed-map management.
- `development/scripts/`: validated development converters and offline probes;
  the current companion reuses these rather than duplicating conversion code.
- `tests/`: host, actual native ABI mocks, sanitizer and API regressions.

The old replacement pipeline and its tests remain as legacy reference, not as
the new UI's normal installation path. Historical documentation is archived in
[`docs/legacy`](../docs/legacy/). Do not follow its slot-replacement/deploy-all
commands for an additive library.

See the [additive companion notes](../docs/additive-companion.md) and component
changelogs for protocol, recovery, versions and known limitations.
