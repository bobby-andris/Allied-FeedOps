---
name: repo-audit
description: Audit repository for unused files, organizational issues, and outdated content
---

# Repository Audit & Cleanup

Systematically audits the repository for organizational issues, unused files, and stale content.

## When to Use

**Trigger `/repo-audit` when:**
- Repository feels cluttered or disorganized
- Before major milestones or releases
- Monthly/quarterly maintenance
- After completing large features
- Onboarding new team members (clean house first)

## What This Audits

### 1. Root-Level Files (Should Be Minimal)

**Check:** Files at repository root that might belong elsewhere

**Common issues:**
- Screenshots/images → Should be in `docs/images/` or deleted
- Audit/analysis docs → Should be in `docs/audit/` or `docs/analysis/`
- Temporary test files → Should be deleted
- Old config files → Should be in appropriate directory or deleted

**Process:**
```bash
# List non-standard root files
ls -1 | grep -v -E '(^\\.|README|LICENSE|CLAUDE|package|pyproject|tsconfig|Dockerfile|cloudbuild|\.gitignore|node_modules|\.venv)'
```

**Categorize each file:**
- ✅ **Keep at root** (essential config/docs)
- 📁 **Relocate** (move to appropriate directory)
- 🗑️ **Delete** (temporary/outdated)

### 2. Documentation Structure

**Check:** Documentation is organized and current

**Expected structure:**
```
docs/
  architecture/     # How systems work
  troubleshooting/  # When things break
  audit/            # Investigation records
  plans/            # Implementation plans
  prompts/          # Legacy/reference prompts
  database/         # Schema docs
  images/           # Screenshots, diagrams
```

**Audit each docs/ file:**
- **Current?** Still relevant to current codebase?
- **Accurate?** Information is correct?
- **Organized?** In right directory?
- **Referenced?** Linked from CLAUDE.md or README?

**Flag for review:**
- Files >6 months old with no updates
- Files referencing deleted/renamed code
- Orphaned files (not linked anywhere)

### 3. Scripts & Tools

**Check:** Scripts are used, working, and documented

```bash
# List all scripts
find scripts/ -type f -executable
```

**For each script, verify:**
- ✅ **Purpose documented** (comment at top or README)
- ✅ **Recently used** (check git log for last modification)
- ✅ **Dependencies exist** (imports/requires are installed)
- ✅ **Executable** (chmod +x if needed)

**Common issues:**
- One-off migration scripts no longer needed
- Duplicate functionality (consolidate)
- Hardcoded paths/credentials (parameterize)
- No error handling (improve)

### 4. Test Files & Test Data

**Check:** Test files are current and valuable

```bash
# Find test files
find tests/ -name "*.py" -o -name "*.ts"
```

**Audit:**
- Tests for deleted features (remove)
- Skipped tests (fix or delete)
- Outdated fixtures/mocks (update or delete)
- Test data files no longer used (remove)

### 5. Code Imports & Dependencies

**Check:** No unused imports or dependencies

**TypeScript/JavaScript:**
```bash
# Find potentially unused dependencies
npx depcheck dashboard/
```

**Python:**
```bash
# Find unused imports (requires pip-autoremove or similar)
cd src && python -m autoflake --check --remove-all-unused-imports -r .
```

**Review:**
- Packages in package.json/pyproject.toml but not imported
- Large dependencies used minimally (consider alternatives)
- Duplicate dependencies (consolidate)

### 6. Prompt Files & Templates

**Check:** Prompt files are current and organized

**Expected:**
- Active prompts in `docs/prompts/`
- Legacy/reference prompts clearly marked
- Continuation prompts in `.claude/prompts/` or `.claude/checkpoints/`

**Audit:**
- Outdated prompt files (mark as legacy or delete)
- Duplicate prompts (consolidate)
- Prompts referencing old architecture (update or delete)

### 7. Images & Media Files

**Check:** Images are used and organized

```bash
# Find all images
find . -type f \\( -name "*.png" -o -name "*.jpg" -o -name "*.gif" -o -name "*.svg" \\) | grep -v node_modules | grep -v .venv
```

**For each image:**
- **Referenced?** Grep codebase for filename
- **Purpose clear?** Filename is descriptive
- **Location appropriate?** In `docs/images/` or asset directory

**Common issues:**
- Test screenshots at root (move to docs/images/ or delete)
- Unused mockup images (delete)
- Duplicate images (deduplicate)

### 8. Configuration Files

**Check:** Config files are necessary and current

**Audit:**
- `.env.example` up to date with actual env vars?
- Multiple similar configs (tsconfig, eslint) - can consolidate?
- Old/deprecated config files (remove)
- Config overrides in multiple places (consolidate)

## Execution Flow

### Phase 1: Quick Scan

Run automated checks:

```bash
# Root-level non-standard files
echo "=== Root-Level Files ===\"
ls -1 | grep -v -E '(^\\.|README|LICENSE|CLAUDE|package|pyproject|tsconfig|Dockerfile|cloudbuild|\\.gitignore)'

# Large files
echo -e "\\n=== Large Files (>1MB) ===\"
find . -type f -size +1M | grep -v node_modules | grep -v .venv | grep -v .git

# Old files (>6 months, not modified)
echo -e "\\n=== Old Files (>6 months since modification) ===\"
find . -type f -mtime +180 | grep -v node_modules | grep -v .venv | grep -v .git | head -20

# Potentially unused scripts
echo -e "\\n=== Scripts Not Modified in >3 Months ===\"
find scripts/ -type f -mtime +90 2>/dev/null || echo \"No old scripts found\"
```

### Phase 2: Categorize Findings

For each flagged file, determine:

1. **Essential** (keep as-is)
2. **Relocate** (move to proper location)
3. **Archive** (move to `archive/` directory with date)
4. **Delete** (no longer needed)
5. **Update** (content is stale)

### Phase 3: Create Action Plan

Generate cleanup plan:

```markdown
## Repository Cleanup Plan

**Generated:** [date]
**Files Audited:** [N]
**Issues Found:** [N]

### High Priority (Do Now)
- [ ] Delete: [file] - [reason]
- [ ] Relocate: [file] → [new-location] - [reason]
- [ ] Update: [file] - [what needs updating]

### Medium Priority (Do This Week)
- [ ] Consolidate: [files] → [single location]
- [ ] Document: [file] - [add purpose/usage]
- [ ] Archive: [file] → archive/YYYY-MM/ - [reason]

### Low Priority (Do Eventually)
- [ ] Review: [file] - [needs manual review]
- [ ] Consider: [file] - [potential improvement]

### Statistics
- Root-level clutter: [N files]
- Orphaned docs: [N files]
- Unused scripts: [N files]
- Old test files: [N files]
- Unreferenced images: [N files]
```

### Phase 4: Execute Cleanup (With Approval)

Present plan to user for approval, then execute:

```bash
# Create archive directory
mkdir -p archive/$(date +%Y-%m)

# Execute approved actions
# (move, delete, update files as approved)
```

### Phase 5: Update Organization Standards

After cleanup, document standards in new file: `docs/ORGANIZATION.md`

## Organization Standards Document

Create `docs/ORGANIZATION.md`:

```markdown
# Repository Organization Standards

**Last Updated:** [date]

## Directory Structure

```
Allied-FeedOps/
├── .claude/                  # Claude Code configuration
│   ├── hooks/               # Automatic enforcement
│   ├── skills/              # Triggered workflows
│   ├── templates/           # Reusable patterns
│   ├── prompts/             # Continuation prompts
│   └── checkpoints/         # Session state saves
├── dashboard/               # Next.js frontend
│   ├── src/
│   │   ├── app/            # App router pages
│   │   ├── components/     # React components
│   │   └── lib/            # Utilities, integrations
│   └── public/             # Static assets
├── src/                     # Python pipeline
│   └── feedops/
│       ├── api/            # FastAPI endpoints
│       ├── pipeline/       # Core pipeline logic
│       └── integrations/   # External services
├── tests/                   # All test files
│   ├── api/                # API tests
│   └── [module]_test.py    # Unit tests
├── scripts/                 # Maintenance scripts
│   └── README.md           # Script documentation
├── docs/                    # All documentation
│   ├── architecture/       # System design
│   ├── troubleshooting/    # Debug guides
│   ├── audit/              # Investigations
│   ├── plans/              # Implementation plans
│   ├── database/           # Schema docs
│   └── images/             # Screenshots, diagrams
├── supabase/               # Database migrations
└── archive/                # Archived files by date
    └── YYYY-MM/            # Monthly archives
```

## File Placement Rules

### Root Directory
**ALLOWED:**
- Essential docs: README.md, LICENSE, CLAUDE.md
- Build configs: package.json, pyproject.toml, Dockerfile
- Tool configs: .gitignore, .env.example, tsconfig.json
- CI/CD: cloudbuild.yaml, vercel.json

**NOT ALLOWED:**
- Screenshots (→ docs/images/)
- Analysis docs (→ docs/audit/ or docs/analysis/)
- Temporary files (→ delete)
- Archived content (→ archive/YYYY-MM/)

### Documentation (docs/)
**MUST have:**
- Clear filename: `problem-solution-date.md`
- Date in filename or front matter
- Purpose stated in first paragraph
- Linked from CLAUDE.md or README if important

**Archive if:**
- >1 year old AND not referenced
- References deleted/renamed code
- Superseded by newer doc

### Scripts (scripts/)
**MUST have:**
- Purpose comment at top
- Usage example in scripts/README.md
- Parameterized (no hardcoded paths/creds)
- Listed in scripts/README.md

**Delete if:**
- One-off migration >6 months old
- Duplicate functionality
- Dependencies no longer available

### Images & Media
**Location:**
- Product screenshots → docs/images/product/
- Architecture diagrams → docs/images/architecture/
- UI mockups → docs/images/design/
- Test screenshots → docs/images/tests/ OR delete after testing

**Naming:** `descriptive-purpose-date.png`

### Temporary Files
**Never commit:**
- Local test outputs
- Debug screenshots (unless documenting a bug)
- Personal notes
- `.DS_Store`, `Thumbs.db`, etc.

Add to .gitignore if needed.

## Monthly Maintenance

**First Monday of each month:**
1. Run `/repo-audit`
2. Review and execute cleanup plan
3. Archive files >1 year old not recently accessed
4. Update docs/ORGANIZATION.md if structure changed

## Automated Cleanup

See `.claude/templates/repo-cleanup-hook.json` for automated checks.
```

## Automation: Monthly Audit Reminder

Add to `.claude/hooks/config.json`:

```json
{
  "sessionStart": {
    "command": "bash -c 'LAST_AUDIT=$(find .claude/ -name \"*repo-audit*\" -type f -mtime -30 | wc -l); if [ \"$LAST_AUDIT\" -eq 0 ]; then echo \"💡 Repository audit overdue. Consider running /repo-audit\"; fi'"
  }
}
```

## Integration with /wrapup

Add to `/wrapup` skill:

```markdown
## Step X: Check for Repository Clutter

If files were added/created in this session:
- Are they in the right location?
- Do they follow naming conventions?
- Should any be temporary (deleted)?
```

## Output Format

```markdown
## Repository Audit Results

**Date:** [timestamp]
**Files Scanned:** [N]
**Issues Found:** [N]

### Summary
- 🗑️ [N] files recommended for deletion
- 📁 [N] files should be relocated
- 📝 [N] files need updates
- 📦 [N] files should be archived

### Detailed Findings

#### Root-Level Clutter
- `sticky-tabs-test.png` → 🗑️ Delete (test screenshot, no longer needed)
- `prompt-scoring-audit-FINAL.md` → 📁 Move to docs/audit/
- `package-lock.json` (root) → 🗑️ Delete (duplicate, dashboard has own)

#### Documentation Issues
- `docs/prompts/old-prompt.md` → 📦 Archive (references deleted features)
- `docs/architecture/outdated.md` → 📝 Update (describes old architecture)

#### Unused Scripts
- `scripts/one_time_migration.py` → 📦 Archive (migration complete, >6 months old)

[Continue for each category...]

### Recommended Actions

**Immediate (Do Now):**
```bash
# Delete temporary/test files
rm sticky-tabs-test.png sticky-tabs-scrolled.png

# Move misplaced files
mv prompt-scoring-audit-FINAL.md docs/audit/prompt-scoring-audit-2026-02.md

# Delete root package-lock.json (dashboard has own)
rm package-lock.json
```

**This Week:**
```bash
# Archive old migrations
mkdir -p archive/2026-02
mv scripts/one_time_migration.py archive/2026-02/
```

**Eventually:**
- Review and update docs/architecture/outdated.md
- Consolidate duplicate test fixtures

**Total cleanup impact:** [N] files, [Size] space

Proceed with cleanup?
```
