# Beat Saber additive fork — project instructions

These instructions are owned by the current project user. Keep AGENTS.md,
CLAUDE.md and .opencode/rules.md synchronized when changing them.

## Workflow
- Work in this checkout. Do not resume unrelated OrbisFox projects.
- Build on the hardware-proven additive plugin, retaining original songs.
- Existing companion functionality first; UI redesign later. One plugin with
  modular internals. Future fully phone-only import/install must retain PC support.
- Keep notes only when useful: concise current status, meaningful decisions,
  reproducible commands, test/deployment results and known limitations. Do not
  maintain mandatory per-response transcripts or duplicate every result across
  many documents. Never record private internal reasoning.
- Keep a small current-state handoff and changelogs; update durable knowledge
  when it will actually help future work. Historical logs are references, not
  live directives. Full experiment-log rotation/documentation checklists are
  no longer required.

## Code and validation
- Production plugin changes bump plugin version by0.0001 and update its changelog.
  Pipeline changes bump its version by0.0001; update webapp version for app changes.
- Add regressions for behavior changes, run the full host test suite before
  reporting implementation ready, and build native candidates before deployment.
- Treat local tests, upload/readback, and user-observed hardware results as
  different evidence. Never claim untested playback or combined-feature parity.
- Experimental development scripts belong in development/scripts until proven.
- Preserve GPL/upstream attribution. Keep copyrighted game inputs, source songs,
  private dumps and local caches out of version control.

## Console safety
- Map/library/plugin installation requires Beat Saber fully closed; keep FTP on.
  Verify title state before console writes. No live import/refresh unless expressly
  implemented and validated. Do not launch the game on the user's behalf.
- Archive useful test logs before clearing them; only clear a stable closed-title
  log after exact readback. Never overwrite running-title files or erase evidence.
- Use scoped staging, full content readback and retained rollback for deployments.
  Preserve stock/DLC data, saves, unrelated plugins and existing custom songs.
- Keep the approved additive/recovery flags; do not blindly enable legacy
  replacement features or weaken owned-ID, ABI, entitlement or publication guards.

## Permissions
- The user explicitly lifted the inherited git-commit prohibition and authorized
  committing the validated additive milestone. git commit is allowed when requested.
  Do not push, publish, tag releases or rewrite history without separate approval.
- No subagent delegation unless the user authorizes it.
- Ask before destructive deletions or system-wide changes. Prefer project-local
  prerequisites and persist necessary tool setup when appropriate.
- No Azure resource writes or remote GitHub mutations without explicit permission.
