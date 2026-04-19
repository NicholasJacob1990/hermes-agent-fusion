# Vanilla Sync — Decision Memory

Persistent notes from prior `NousResearch/hermes-agent` (vanilla) syncs into
this fusion fork. Each section: date + vanilla HEAD short + decisions taken.
Appended at the END of each successful auto-sync.

---

## 2026-04-19 — baseline (manual setup)

Initial automation setup. Prior fusion state: HEAD `3c00918b`, includes:
- Vanilla NousResearch (latest at fusion time)
- 42 enhanced patches (from outsourc-e/hermes-agent and elsewhere)
- Voice features stack
- skills_categories fix
- Personal gateway running on :8642 with 59+ real sessions

**Repo structure note:**
- `origin` = `NicholasJacob1990/hermes-agent-fusion` (push here)
- `vanilla` = `NousResearch/hermes-agent` (sync FROM here via this workflow)
- `enhanced-source` = `outsourc-e/hermes-agent` (manual backports as needed)

**Sister Vorbium fork:** `NicholasJacob1990/vorbium-engine-runtime`
(separate repo, not pushed to from this checkout). The Vorbium variant has
its own `vorbium_engine_cli` package + rebrand layer. This repo does NOT.

**Workflow scope:**
- Daily auto-sync from `vanilla/main` only.
- Manual cherry-pick from `enhanced-source` when interesting features
  appear there.

**No prior auto-sync runs yet — first cron will populate this file.**
