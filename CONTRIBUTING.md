# Contributing to Allied-FeedOps

Development workflow for any contributor — human, Claude Code, Codex, or any other tool.

## Git Workflow

**`master` is protected and auto-deploys.** All work happens on feature branches.

```
master (always deployable)
  └── feat/my-feature   ← work here
       └── squash-merge PR back to master
            └── delete branch after merge
```

**For Claude Code / GSD:** Use worktrees (`/worktree` or GSD phase branches) so master stays untouched while you work. Push feature branch, open PR, squash-merge.

**For Codex:** Codex auto-creates worktrees. Review the PR it creates before merging. Never auto-merge.

**For humans:** Standard feature branch workflow. `git checkout -b feat/name`, commit, push, PR.

**After any merge:**
```bash
git checkout master && git pull --rebase
```

## Living Documents

These documents **must stay current with the codebase**. When you change code that affects them, update them in the same PR.

| Document | What it tracks | Update when... |
|----------|---------------|----------------|
| `docs/database/SCHEMA.md` | Every table, column, type, constraint | Any migration or schema change |
| `CLAUDE.md` | Architecture, file locations, env vars, endpoints | Pipeline structure, new endpoints, env var changes |
| `.planning/ROADMAP.md` | Current milestone phases and status | Phase completes, milestone ships |
| `.planning/PROJECT.md` | What's built, what's validated, what's next | Milestone ships, requirements change |
| `CONTRIBUTING.md` | This file — workflow and decisions | New architectural decision or workflow change |

**The rule:** If your PR changes something a document describes, update that document in the same PR. Stale docs caused more confusion in this project than any bug.

## Pre-Merge Checklist

Every PR, regardless of who creates it:

- [ ] Dashboard builds: `cd dashboard && npm run build`
- [ ] Types clean: `npx tsc --noEmit`
- [ ] Lint passes: `npm run lint`
- [ ] Python tests pass (if pipeline changed): `pytest tests/ -v`
- [ ] Affected living documents updated (see table above)
- [ ] PR description shows real output (not just "tests pass")

## Post-Merge Verification

After merge to master:
- [ ] Cloud Build succeeded: `gcloud builds list --project=bobbys-project-346400 --limit=3`
- [ ] Pipeline health: `curl -s https://feedops-pipeline-3b43yg32oa-ue.a.run.app/health`
- [ ] Dashboard loads: check `https://allied-feed-ops.vercel.app`

## Architectural Decisions

Validated in production. Don't reverse without evidence and approval.

| Decision | Rationale |
|----------|-----------|
| Claude Sonnet 4.6 as primary LLM | 84% cheaper, 2x faster, higher quality than GPT-5.2 |
| Python pipeline as prompt authority | Single source of truth for content generation |
| `run_async_in_thread()` for background jobs | FastAPI BackgroundTasks die on Cloud Run scale-to-zero |
| Offer ID: lowercase in DB, uppercase at publish | GMC requires `shopify_US_`, DB stores `shopify_us_` |
| `variant_index` as entity hub | 72K rows linking GMC, Shopify, Google Ads, master SKUs |
| Content in Supabase only (not git) | candidate → approved (immutable) lifecycle |

## Technology Stack

- **Dashboard:** Next.js / TypeScript → Vercel (auto-deploy on push)
- **Pipeline:** Python / FastAPI → Cloud Run (auto-deploy via Cloud Build)
- **Database:** Supabase (PostgreSQL) — schema in `docs/database/SCHEMA.md`
- **Publishing:** Google Sheets supplemental feed + Shopify GraphQL API

Python for scripts/pipeline. TypeScript for dashboard. Don't mix without approval.

---

*Updated: 2026-03-04. Update this doc when workflow or architecture changes.*
