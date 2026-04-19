# Enhanced Sync — Decision Memory (Fusion)

Persistent notes from prior `outsourc-e/hermes-agent` (enhanced) syncs
into the **Hermes pessoal fusion** fork. Each section: date + enhanced
HEAD short + decisions. Appended at the END of each successful auto-sync.

---

## 2026-04-19 — baseline (enhanced absorbed into fusion bootstrap)

Initial state when `sync-enhanced.yml` was authored on fusion. The
fusion repo was created on 2026-04-19 with the explicit intent of
merging vanilla NousResearch + enhanced outsourc-e patches before the
Vorbium rebrand. At that moment, enhanced HEAD was `334e012c` and all
relevant enhanced-specific patches were hand-picked into the bootstrap
fusion commit (fusion HEAD `3c00918b` era, later superseded by
`29e07f4d`).

Expectation: the first `sync-enhanced.yml` cron run is expected to
**no-op** because fusion's current main already contains everything
enhanced has. New entries get appended here only when Eric lands
genuinely new commits on `outsourc-e/hermes-agent`.

**Enhanced patches already in fusion's baseline:**
- `PR #4 easyvibecoding/feat/api-skills-enrichment` — skills
  enrichment endpoint (direct absorption, no rebrand)
- Web dashboard scaffolding (as-is from Eric)
- OAuth provider variants not present in NousResearch
- The `skills_categories fix` that unblocked enhanced's schema

**Repo structure:**
- `origin` = `NicholasJacob1990/hermes-agent-fusion` (push here)
- `vanilla` = `NousResearch/hermes-agent` (added on-the-fly by
  `sync-upstream.yml`)
- `enhanced` = `outsourc-e/hermes-agent` (added on-the-fly by
  `sync-enhanced.yml`)
- Sibling fork: `NicholasJacob1990/vorbium-engine-runtime` (rebranded
  variant; separate pipeline, not this repo)

**Policy at setup time:**
- Cadence: weekly (both vanilla on Monday 10:00 UTC, enhanced on
  Monday 11:00 UTC with 1h offset)
- Auto-merge: **enabled** on both workflows. Clean merges squash-merge
  themselves after CI passes. Conflicts fall through to draft PRs
  with `needs-human-review` label.
- Hard limit: 20 conflicted files (tighter than vanilla's 30).

**Divergence from Vorbium sibling:**
The Vorbium fork runs the same two workflows on the same schedule, but
with **auto-merge disabled** — every Vorbium PR requires human review
regardless of conflict status. Reason: Vorbium's rebrand layer is
sensitive (VEM Core memory, rebrand strings, `vorbium_engine_cli`
package, `webapi/`) and auto-merging could silently break it.
