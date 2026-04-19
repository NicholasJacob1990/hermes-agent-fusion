# Enhanced Sync — Conflict Resolution Prompt (Fusion)

You are resolving a `git merge enhanced/main` on the **Hermes pessoal
fusion** fork (`NicholasJacob1990/hermes-agent-fusion`). Enhanced is
`outsourc-e/hermes-agent` — a low-velocity Eric fork of
NousResearch/hermes-agent.

## Context

Fusion's lineage: vanilla NousResearch absorbed + 42 original enhanced
patches + voice features stack + skills_categories fix. Fusion is
**not** rebranded — it keeps "Hermes Agent" UI strings, the
`hermes_cli` package name, and the `HERMES_*` env var contracts. The
sibling repo `NicholasJacob1990/vorbium-engine-runtime` is the
rebranded variant; **do not** port rebrand-specific concepts here.

## Your role

Conflicts are unstaged in the working tree after the workflow attempted
the merge. Your job:

1. Read `.github/enhanced-sync-memory.md` for prior decisions and the
   list of enhanced patches already absorbed.
2. Inspect each conflict via `git diff --name-only --diff-filter=U`.
3. Resolve per the rules below. Stage with `git add`.
4. Commit with structured decisions, append memory, exit.

## Hard limits — DO NOT proceed if exceeded

- More than 20 conflicted files (enhanced is low-velocity; 20+ means
  Eric did something unusual and needs human review)
- More than 300 changed lines in a single file
- Conflict in a file you cannot classify per the rules below

If exceeded: leave markers, write `.github/last-enhanced-sync-triage.md`,
exit.

## Resolution rules (Fusion context)

### Rule E1: vanilla-overlapping change — prefer ours, accept Eric's delta
Enhanced sometimes ships a patch that vanilla already has in a slightly
different form. If HEAD has the vanilla version and enhanced has an
Eric-modified version, **keep ours** (vanilla is authoritative) UNLESS
Eric's version fixes a real bug that vanilla didn't catch. Document
which case applied.

### Rule E2: Eric-exclusive feature → keep enhanced
If the file/feature exists only on enhanced and not on vanilla, take
enhanced's version. Common paths:
- `web_dashboard/` or dashboard-related static assets (Eric has shipped
  dashboard UI that upstream NousResearch does not)
- OAuth provider variants not present in vanilla
- `api/skills_enrichment/` (PR #4 territory — already partially
  absorbed; new commits there are genuinely new)

### Rule E3: voice features / skills_categories fix → keep ours
Voice features (`tools/voice_*`, `tools/tts_*`, `agent/voice_*`) and
the skills_categories fix are fusion-specific. If enhanced touches
those paths, keep ours and integrate Eric's deltas around them. If
enhanced adds voice-adjacent features, evaluate case-by-case —
prefer integrating if they extend our stack, keep ours if they
conflict with our routing.

### Rule E4: HERMES_* env vars, hermes_cli package name → preserve
Unlike Vorbium, fusion keeps the original Hermes branding. Do NOT
introduce `VORBIUM_*` env vars or rename `hermes_cli/` here. Enhanced
commits might touch these areas — always keep the Hermes naming.

### Rule E5: tests → follow vanilla sync rules
Same as `.github/upstream-sync-prompt.md` Rule 9. Enhanced tests that
touch only enhanced-exclusive files: accept. Tests overlapping vanilla
or fusion paths: prefer ours.

### Rule E6: pyproject.toml / setup.cfg → structural merge
Keep `name = "hermes-agent"` (or whatever fusion's current name is;
check before modifying). If Eric adds a new dependency, add it. If
Eric removes a dep, check if fusion still uses it via `grep -r`
before removing.

### Rule E7: feature removed in vanilla but still in enhanced → usually accept removal
If vanilla removed X and enhanced still has X, prefer vanilla's
removal (upstream authoritative). Only keep enhanced's version if it
fixes an active bug we depend on.

## After resolving

1. Sanity: `git diff --check` empty AND no markers.
2. `git add -A`
3. Commit (template below).
4. Append memory entry.

### Commit template
```
fusion: merge enhanced outsourc-e (<N> commits, <date>)

Auto-resolved by GitHub Actions + Claude.

Conflicts (<count>):
- <file>: <rule applied> — <decision>

Notes:
- <pattern observed>
```

### Memory append
```
## <date> — sync from <enhanced HEAD short>

Decisions:
- <file>: <rule + rationale>

New patterns observed:
- <if any>
```

## Tools available

`Read`, `Edit`, `Write`, `Grep`, `Glob`, `Bash(git:*)`. No installs, no
CI edits.

## Relationship with vanilla sync

Vanilla workflow runs **Monday 10:00 UTC** (see
`.github/workflows/sync-upstream.yml`), enhanced runs **Monday 11:00 UTC**.
If both have commits to integrate in the same week, vanilla is merged
first. Enhanced merges on top of whatever main looks like at 11:00 — if
the vanilla PR from 10:00 is still open, enhanced proceeds on pre-vanilla
main. Human resolves PR order at merge time.

## Auto-merge note

This fusion repo has **auto-merge enabled** — if the merge is clean and
CI passes, the PR self-merges. Contrast with Vorbium sibling, which
requires human review on every PR due to the rebrand layer's
sensitivity.
