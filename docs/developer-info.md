# Developer Information

This document contains technical details for developers working on the Beat Saber Deluxe pipeline and plugin.

## Release Process

We use a dynamic release body generation process to ensure GitHub Releases always contain accurate changelogs.

### Pre-Release Checklist
1. **Increment Version:** Bump version in `beat_saber_deluxe/VERSION` (pipeline) and `src/main.cpp` (plugin).
2. **Update Changelogs:** Add entries to `beat_saber_deluxe/CHANGELOG-PLUGIN.md` and `beat_saber_deluxe/CHANGELOG-PIPELINE.md`.
3. **Generate Release Body:** Run the release preparation script to update `beat_saber_deluxe/CI_RELEASE.md` automatically:
   ```bash
   python3 beat_saber_deluxe/tools/prepare_release.py
   ```
4. **Tag:** `git tag vX.YY`
5. **Push:** `git push origin vX.YY`

The CI/CD pipeline (`.github/workflows/plugin-build.yml`) will automatically build the artifacts and create the release body using `CI_RELEASE.md`.

## Automation Scripts
All pipeline automation scripts are located in `beat_saber_deluxe/tools/`.
- `full_custom_song_pipeline.py`: Main conversion tool.
- `hevag_encoder.py`: Audio format conversion.
- `prepare_release.py`: Automation for release body generation.
