# Project guidance

This file applies to the repository root. All paths below are relative to that root.

- Read [development/README.md](development/README.md) before changing the driver, tests, or build workflow.
- For changes under `src/firebird/driver/`, read the matching module note. Keep module-specific
  findings there rather than expanding this file:
  [__init__](development/__init__.md),
  [config](development/config.md),
  [core](development/core.md),
  [fbapi](development/fbapi.md),
  [hooks](development/hooks.md),
  [interfaces](development/interfaces.md), and
  [types](development/types.md).
- Keep developer information in `development/`. `docs/docs/` contains the Zensical documentation
  for driver users.
- Check `git status` before editing and preserve unrelated work. Verify changes with the focused
  tests and build commands described in the development README; report any Firebird-dependent
  checks that could not run.
