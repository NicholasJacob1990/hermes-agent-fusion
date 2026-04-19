# Vanilla Sync — Conflict Resolution Prompt

You are resolving a `git merge vanilla/main` on the **Hermes pessoal backend
fusion** fork (`NicholasJacob1990/hermes-agent-fusion`). Vanilla upstream is
`NousResearch/hermes-agent`.

This repo is a "fusion" of vanilla NousResearch features + 42 enhanced
patches + voice features + skills_categories fix. Goal: keep absorbing
vanilla upstream while preserving the enhanced layer.

## Your role

The merge has been started by the workflow. Conflicts (if any) are unstaged
in the working tree. Your job:

1. Read `.github/upstream-sync-memory.md` for prior decisions.
2. Inspect each conflict via `git diff --name-only --diff-filter=U` and `git diff <file>`.
3. Resolve each conflict using the rules below. Stage with `git add`.
4. When all resolved, commit with structured message documenting decisions.
5. Append new decisions to `.github/upstream-sync-memory.md`.
6. The workflow handles push and PR creation after you exit.

## Hard limits — DO NOT proceed if exceeded

- More than 30 conflicted files
- More than 500 changed lines in a single file
- A conflict touches a file you cannot classify per the rules below

If any limit hits: leave conflict markers, write
`.github/last-sync-triage.md` with per-conflict triage, and exit. The
workflow will open a draft PR with `needs-human-review` label.

## Resolution rules (Hermes pessoal fusion context)

### Rule 1: pure cosmetic conflict → accept upstream
Whitespace, quote style, line wrapping, formatter changes — accept vanilla
(`git checkout --theirs`). Reduces drift, eases future merges.

### Rule 2: vanilla refactor with no enhanced customization → accept vanilla
HEAD has stock code, vanilla introduces refactor (extracted helper,
simplified flow) → accept vanilla.

### Rule 3: HEAD has enhanced layer customization → keep ours, integrate
**Enhanced features to preserve** (from prior fusion work):
- Voice features: `tools/voice_*`, `tools/tts_*`, anything under
  `agent/voice_*`, voice-related entries in `pyproject.toml` extras
- Skills enhancements: PR #4 `feat/api-skills-enrichment` and any
  follow-ups touching `agent/skills*`, `tools/skills_*`
- skills_categories fix (committed in fusion HEAD `3c00918b` era) — if
  vanilla touches the same area, keep our fix and integrate vanilla
  changes around it
- Any `enhanced-source` (outsourc-e/hermes-agent) backports already merged
- Localized polish: error messages, debug instrumentation we added

For files where the enhanced layer added meaningful logic, prefer ours
(HEAD) and integrate vanilla deltas via Edit (not blanket `--theirs`).

### Rule 4: feature removed in vanilla → accept removal, document loss
If vanilla intentionally removed a feature (PR ref in commit message,
"X owns its own state", deprecation note), accept the removal. Note in
memory which enhanced behaviors might depend on it.

### Rule 5: signature change → adopt new, update callers
Function signature changed in vanilla → adopt new signature, grep for
callers, update each. Common: rename + new optional param.

### Rule 6: structural file (pyproject.toml, setup.cfg, requirements*) → manual merge
Combine: enhanced extras (voice deps, mistral, etc.) + vanilla additions
(new packages, version bumps, new extras). Never blanket --ours/--theirs
on these.

### Rule 7: shim files (hermes_cli, etc.) → defer to vanilla
This repo (unlike Vorbium) does NOT have a hermes_cli rebrand shim.
Imports `from hermes_cli.X` are direct. Accept vanilla's import paths.

### Rule 8: tests
- `tests/hermes_cli/`, `tests/test_*.py` upstream additions → accept vanilla
- Tests we added for enhanced features → keep ours
- Tests upstream removed (e.g., for removed features per Rule 4) →
  accept removal

## After resolving

1. Sanity check: `git diff --check` empty AND no markers:
   `! grep -rE '^(<<<<<<<|>>>>>>>) ' --include='*.py' --include='*.json' --include='*.toml' --include='*.md' --include='*.yml' .`
2. Stage all: `git add -A`
3. Commit (template below)
4. Append memory entry

### Commit template
```
fusion: merge vanilla NousResearch (<N> commits, <date>)

Auto-resolved by GitHub Actions + Claude.

Conflicts (<count>):
- <file>: <rule applied> — <one-line decision>
- ...

Notes:
- <new pattern observed, if any>
```

### Memory append template
```
## <date> — sync from <vanilla HEAD short>

Decisions:
- <file or pattern>: <rule + rationale>

New rules learned:
- <if any>
```

## Tools available

`Read`, `Edit`, `Write`, `Grep`, `Glob`, `Bash(git:*)`, plus standard
read-only shell. No package installs, no CI config edits.
