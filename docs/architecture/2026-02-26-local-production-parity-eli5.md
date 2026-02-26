# Local vs Production Parity (ELI5)

## Why this exists
You asked for one simple rule:

> If it breaks in production, it should break locally first.

That is the right goal. This doc explains the mental model and the setup that gets you as close as possible.

## ELI5 mental model
Imagine you run a bakery:

- **Local** = your practice kitchen
- **Production** = the real bakery customers pay for

If the oven temperature, ingredients, or timer are different between the two, your practice cake can succeed while customer cakes fail.

Software parity means: make the practice kitchen and real bakery match as much as possible.

## The four things that must match
If these four match, most surprises disappear.

1. **Same code**  
   The exact same commit should be what you test and what you deploy.

2. **Same container/runtime**  
   Same Python version, same OS libs, same installed packages, same startup command.

3. **Same environment contract**  
   Required env vars and secrets must be present and valid in both places.

4. **Same external dependencies behavior**  
   Database, APIs, timeouts, and retries must be tested in production-like conditions.

## Why "100% identical" is hard
Even with great parity, external systems still add variance:

- LLM responses can vary.
- Network latency can spike.
- Cloud services can throttle or time out.

So the realistic target is:

> Not "no failures ever", but "failures are detected before merge/deploy and are traceable in minutes."

## What each safeguard does (and why)

### 1) Environment contract validation
**What:** App checks required env vars at startup and fails fast if missing.  
**Why:** Prevents hidden misconfiguration from showing up only at runtime.

### 2) Container parity test
**What:** Run contract tests inside the same Docker image used for Cloud Run.  
**Why:** Catches "works on my machine" Python/package/runtime drift.

### 3) Pre-deploy parity gate
**What:** CI blocks deploy unless parity tests pass.  
**Why:** Stops broken builds from reaching production.

### 4) Post-deploy smoke test
**What:** Hit live endpoint after deploy, assert response contract and DB effects.  
**Why:** Proves real production behavior is healthy, not just unit tests.

### 5) Request ID lineage
**What:** One `request_id` flows dashboard -> API -> DB -> logs.  
**Why:** Lets you trace one failure end-to-end quickly.

## Practical rulebook (copy to any project)

1. Build one immutable Docker image per commit.
2. Run tests in that image.
3. Enforce required env vars at app startup.
4. Run DB migrations before app code depends on new columns.
5. Add pre-deploy parity checks in CI.
6. Add post-deploy smoke checks against live endpoints.
7. Pass a request/correlation ID through all layers.
8. Store that ID in audit/history tables.
9. Block merge on required checks.
10. Keep one short runbook for debugging.

## Fast debugging flow (when something fails)

1. Capture `request_id` from response/log.
2. Query DB history by `request_id`.
3. Confirm API response contract fields are present.
4. Confirm expected DB writes happened exactly once.
5. Check Cloud Run logs for timeout/retry/error path.
6. Reproduce with same payload in parity environment.

## What this means for Allied FeedOps

- We already added core deterministic regeneration contracts and parity tests.
- We still need to continuously run live smoke checks after deploy.
- We should treat this doc as the baseline pattern for all future repos.

## Notion sync note
Notion MCP currently returns `Auth required` in this Codex session.  
When connector auth is stable, copy this page into PARA Resources and keep it as the canonical learning doc.
