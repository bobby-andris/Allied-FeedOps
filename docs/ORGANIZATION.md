# Repository Organization Standards

**Last Updated:** 2026-02-10
**Purpose:** Maintain clean, organized, discoverable repository structure

## Canonical Generation Doc Set

Generation-related truth should live in the canonical doc stack below, not in scattered one-off investigations:

1. `AGENTS.md`
2. `docs/architecture/generation-runtime-truth.md`
3. `docs/architecture/generation-core-task-model.md`
4. `docs/architecture/generation-prompt-lineage-contract.md`
5. `docs/architecture/generation-pipeline-routing-reference.md`
6. `docs/experiments/2026-02-28-production-divergence-closure/report.md`
7. `docs/development/generation-change-checklist.md`
8. `docs/operations/deploy-and-certify-generation.md`

If a doc is older, narrower, or investigation-specific, it should either:

1. point to the canonical set at the top, or
2. be marked historical/reference-only.

## Directory Structure

```
Allied-FeedOps/
├── .agents/                 # Repo-local agent skills and workflows
│   └── skills/             # Specialized skills (for example generation certification)
├── .claude/                 # Legacy Claude Code config still in use where applicable
│   ├── hooks/              # Automatic enforcement hooks
│   ├── skills/             # Triggered workflow skills
│   ├── templates/          # Reusable patterns & templates
│   ├── prompts/            # Continuation prompts
│   └── checkpoints/        # Session state saves
├── dashboard/              # Next.js frontend application
│   ├── src/
│   │   ├── app/           # App router pages & API routes
│   │   ├── components/    # React components
│   │   └── lib/           # Utilities, integrations, helpers
│   └── public/            # Static assets
├── src/                    # Python pipeline (feedops package)
│   └── feedops/
│       ├── api/           # FastAPI endpoints
│       ├── pipeline/      # Core pipeline logic
│       ├── integrations/  # External service integrations
│       └── quality/       # Content quality scoring
├── tests/                  # All test files (pytest & jest)
│   ├── api/               # API endpoint tests
│   └── test_*.py          # Unit tests by module
├── scripts/                # Maintenance & utility scripts
│   └── README.md          # Script documentation
├── docs/                   # All documentation
│   ├── architecture/      # System design & how things work
│   ├── troubleshooting/   # Debug guides & known issues
│   ├── audit/             # Investigation & root cause analysis
│   ├── plans/             # Implementation plans & roadmaps
│   ├── database/          # Schema documentation
│   ├── prompts/           # Legacy/reference prompts
│   └── images/            # Screenshots, diagrams, mockups
├── supabase/              # Database migrations & functions
│   └── migrations/        # SQL migration files
└── archive/               # Archived files by date
    └── YYYY-MM/           # Monthly archive folders
```

## File Placement Rules

### Root Directory (Keep Minimal)

**✅ ALLOWED at root:**
- Essential docs: `README.md`, `LICENSE`, `CLAUDE.md`, `AGENTS.md`
- Build configs: `package.json`, `pyproject.toml`, `Dockerfile`
- Tool configs: `.gitignore`, `.env.example`, `tsconfig.json`, `eslint.config.js`
- CI/CD: `cloudbuild.yaml`, `vercel.json`

**❌ NOT ALLOWED at root:**
- Screenshots → Move to `docs/images/`
- Analysis documents → Move to `docs/audit/` or `docs/analysis/`
- Temporary test files → Delete or move to `docs/images/tests/`
- Archived content → Move to `archive/YYYY-MM/`
- Scripts → Move to `scripts/`
- One-off data files → Delete or move to appropriate directory

**Why:** Root directory is the project's "lobby" - only essential navigation and setup files belong there.

### Documentation (docs/)

**MUST have for each doc:**
- Clear filename: `descriptive-purpose-date.md` (e.g., `baseline-capture-fix-2026-02.md`)
- Date in filename OR front matter
- Purpose stated in first paragraph
- Linked from `CLAUDE.md` or `README.md` if important

**Directory-specific purposes:**

#### docs/architecture/
- How systems work (data flow, component interaction)
- Design decisions and rationale
- Integration patterns
- Canonical generation docs belong here

#### docs/troubleshooting/
- When things break (debugging guides)
- Known issues and workarounds
- FAQ and common errors

#### docs/audit/
- Investigation records
- Root cause analyses
- "Why did X happen" deep dives
- Historical, not canonical, unless linked from the canonical generation set

#### docs/plans/
- Implementation plans
- Feature roadmaps
- Multi-phase project documents

#### docs/prompts/
- Legacy prompt references
- Prompt templates
- Historical prompt evolution
- Never treat this directory as runtime authority unless the canonical docs say otherwise

#### docs/images/
- `product/` - Product screenshots
- `architecture/` - System diagrams
- `design/` - UI mockups
- `tests/` - Test evidence (temporary)

**Archive if:**
- >1 year old AND not referenced anywhere
- References deleted/renamed code
- Superseded by newer documentation

### Scripts (scripts/)

**MUST have for each script:**
- Purpose comment at top
- Usage example
- Documented in `scripts/README.md`
- Parameterized (no hardcoded paths/credentials)
- Executable permissions (`chmod +x`)

**Naming convention:**
- Snake_case: `analyze_file_usage.py`
- Descriptive: Action + object (e.g., `cleanup_duplicate_media.py`)

**Delete if:**
- One-off migration >6 months old (archive first)
- Duplicate functionality exists elsewhere
- Dependencies no longer available
- Not documented and unclear purpose

### Images & Media Files

**Location by purpose:**
- Product screenshots → `docs/images/product/`
- Architecture diagrams → `docs/images/architecture/`
- UI mockups → `docs/images/design/`
- Test screenshots → `docs/images/tests/` OR delete after testing

**Naming convention:**
`descriptive-purpose-date.ext`

Examples:
- `variant-review-lifestyle-images-2026-02.png`
- `data-pipeline-flow-diagram-2026-01.svg`
- `mobile-navigation-mockup-2026-02.png`

**NEVER commit:**
- Personal test screenshots (delete after session)
- Temporary debug images (use dev tools instead)
- Duplicate images (deduplicate)

### Configuration Files

**Essential configs at root:**
- `tsconfig.json` (TypeScript)
- `eslint.config.js` (Linting)
- `pyproject.toml` (Python dependencies)
- `.env.example` (Environment template)

**Keep up to date:**
- `.env.example` matches actual required env vars
- Configs are consistent across environments
- No orphaned/unused config files

**Remove:**
- Old/deprecated config files (e.g., `tslint.json` if using ESLint)
- Duplicate configs in multiple places
- Configs for removed tools/dependencies

## Naming Conventions

### Files
- Markdown: `kebab-case-with-date.md`
- Python: `snake_case.py`
- TypeScript: `camelCase.ts` or `PascalCase.tsx` (components)
- Scripts: `snake_case_action.py`

### Directories
- Lowercase with hyphens: `multi-word-directory`
- OR snake_case for Python: `module_name`
- Descriptive, not abbreviated

### Dates in Filenames
- Format: `YYYY-MM-DD` or `YYYY-MM`
- Placement: End of filename (e.g., `analysis-2026-02-10.md`)

## Temporary Files Policy

**NEVER commit:**
- Files matching: `*test*.png`, `*temp*.txt`, `*tmp*`, `*.log`
- Personal notes or scratch files
- Debug outputs
- Build artifacts (already in `.gitignore`)

**Add to .gitignore if pattern emerges**

**Session end check:** Before ending any session, verify no temporary files at root

## Monthly Maintenance

**First Monday of each month:**

1. **Run audit:**
   ```bash
   python scripts/analyze_file_usage.py
   # OR use /repo-audit skill
   ```

2. **Review results:**
   - Root clutter (move or delete)
   - Old files >6 months (archive or update)
   - Unreferenced files (verify usage, then delete/archive)
   - Large files (compress or remove if possible)

3. **Archive old content:**
   ```bash
   mkdir -p archive/$(date +%Y-%m)
   # Move files >1 year old, not recently accessed
   ```

4. **Update documentation:**
   - Review `CLAUDE.md` for accuracy
   - Update this `ORGANIZATION.md` if structure changed
   - Check links in `README.md`

5. **Commit cleanup:**
   ```bash
   git add -A
   git commit -m "chore: Monthly repository cleanup $(date +%Y-%m)"
   git push origin codex/<cleanup-topic>-$(date +%Y%m%d)
   ```

## Automated Enforcement

**Hooks prevent clutter automatically:**

See `.claude/hooks/config.json` and `.claude/templates/repo-cleanup-automation.json`

**Warnings you'll see:**
- Creating file at repository root → Suggests proper location
- Moving images → Reminds about `docs/images/`
- New documentation → Reminds to link from `CLAUDE.md`
- New scripts → Reminds to document in `scripts/README.md`
- Session end → Warns about temporary files

## Tools & Skills

### `/repo-audit` Skill
Comprehensive repository audit:
- Scans for organizational issues
- Categorizes files (delete/relocate/archive/update)
- Generates action plan
- Executes approved changes

**Usage:** `/repo-audit` in Claude Code

### `analyze_file_usage.py` Script
Python script for file usage analysis:
- Finds unreferenced files
- Identifies old files (>6 months)
- Locates large files (>1MB)
- Detects root clutter
- Generates cleanup script

**Usage:**
```bash
python scripts/analyze_file_usage.py
python scripts/analyze_file_usage.py --aggressive  # Include reference checking
python scripts/analyze_file_usage.py --generate-script  # Create cleanup.sh
```

### Automation Hooks
See `.claude/templates/repo-cleanup-automation.json` for preventive hooks

## Archive Strategy

**When to archive:**
- Files >1 year old not recently accessed
- Completed migration scripts >6 months old
- Superseded documentation
- Historical data no longer actively used

**Archive structure:**
```
archive/
  2026-01/
    old-migration-script.py
    superseded-architecture-doc.md
  2026-02/
    [files archived this month]
```

**Archive process:**
1. Create monthly directory: `mkdir -p archive/YYYY-MM`
2. Move files with clear naming: `mv old-file.py archive/YYYY-MM/old-file-archived-YYYY-MM-DD.py`
3. Update any references to archived files
4. Commit with clear message: `chore: Archive [description] to YYYY-MM`

## Best Practices

### Before Creating New Files
1. **Check if already exists** - Search for similar functionality/docs
2. **Determine proper location** - Use directory structure above
3. **Follow naming convention** - See conventions above
4. **Plan for maintenance** - How will this stay current?

### During Development
1. **Keep commits atomic** - One logical change per commit
2. **Update docs with code** - Don't let them drift
3. **Clean as you go** - Delete temporary files immediately
4. **Use descriptive names** - Future-you will thank you

### Session End Checklist
1. **Delete temp files** - No test screenshots, debug logs, etc.
2. **Move misplaced files** - Check for root clutter
3. **Update CLAUDE.md** - Add learnings
4. **Link new docs** - From README or CLAUDE.md if important

## Red Flags

**Signs repository needs cleanup:**
- 🚩 >5 files at root that aren't essential configs/docs
- 🚩 Files with names like `test1.png`, `temp.txt`, `old_backup.py`
- 🚩 Documentation >1 year old with no updates
- 🚩 Scripts without documentation
- 🚩 Images at root or in wrong directories
- 🚩 Duplicate files (same functionality, different names)

**When you see these, run `/repo-audit` immediately**

## Evolution of This Document

This document itself should evolve:
- Add discovered patterns as sections
- Update structure when directory layout changes
- Remove deprecated guidelines
- Add automation as it's implemented

**Last review:** Check date at top of document
**Next review:** First Monday of next month

## Questions?

- Repository organization questions → Review this document
- Cleanup tools → See `/repo-audit` skill or `analyze_file_usage.py`
- Automation → See `.claude/hooks/config.json`
- Monthly maintenance → Follow checklist above
