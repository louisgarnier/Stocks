# Git Workflow

## Repository
**Remote**: Update this with your repository URL

## Workflow Process

### 1. Development Cycle
1. **Create/Update Code** → Make changes according to plan
2. **Test Changes** → Run tests, verify functionality
3. **User Validation** → User reviews and approves changes
4. **Commit** → Commit with descriptive message
5. **Push** → Push to GitHub repository

### 2. Commit Message Convention

Use clear, descriptive commit messages:

```
Format: [Component] Brief description

Examples:
[Backend] Add Finviz scraper for Gross Margin
[Backend] Implement RatioFetcher service
[Frontend] Create SummaryTable component
[Frontend] Add API integration with useApi composable
[Docs] Update backend plan with validation checkpoints
[Tests] Add unit tests for scrapers
```

### 3. When to Commit

**Commit after:**
- ✅ Completing a validated step from PLAN.md
- ✅ All tests pass
- ✅ User has validated the changes
- ✅ Code is working as expected

**Do NOT commit:**
- ❌ Broken code
- ❌ Untested changes
- ❌ Before user validation

### 4. Branch Strategy

**Main Branch**: `main` (or `master`)

For this project, we'll work directly on `main` branch unless:
- Working on experimental features
- Multiple features in parallel

If branching:
- Feature branch: `feature/description`
- Bug fix: `fix/description`

### 5. Push Process

**Before pushing:**
- [ ] All changes committed
- [ ] Tests passing
- [ ] User has validated
- [ ] No sensitive data (API keys, etc.) in code

**Push command:**
```bash
git push origin main
```

### 6. Initial Repository Setup

If repository is empty or needs initialization:

```bash
# Initialize git (if not already done)
git init

# Add remote
git remote add origin <YOUR_REPO_URL>

# Add all files
git add .

# Initial commit
git commit -m "Initial project setup with documentation"

# Push to main
git push -u origin main
```

### 7. Regular Workflow Example

```bash
# 1. Make changes to files
# 2. Test changes
npm test  # or pytest for backend

# 3. Stage changes
git add .

# 4. Commit with descriptive message
git commit -m "[Backend] Add Morningstar scraper for ROIC"

# 5. Push to GitHub
git push origin main
```

### 8. Handling Conflicts

If conflicts occur:
1. Pull latest changes: `git pull origin main`
2. Resolve conflicts manually
3. Test resolved code
4. Commit resolution
5. Push again

### 9. File Tracking

**Always tracked:**
- Source code files
- Configuration files
- Documentation (MD files)
- Test files

**Never tracked (in .gitignore):**
- `node_modules/`
- `venv/` or `.venv/`
- `.env` files (use `.env.example` instead)
- `__pycache__/`
- `.DS_Store`
- Build artifacts

### 10. Validation Checkpoints

Before each commit, ensure:
- [ ] Code follows project structure
- [ ] Tests are written and passing
- [ ] Documentation is updated if needed
- [ ] User has reviewed and approved
- [ ] No console errors or warnings
- [ ] Code is clean and readable

## Summary

**Workflow**: Code → Test → Validate → Commit → Push

**Frequency**: After each validated step from PLAN.md files

**Message**: Clear, descriptive commit messages with component prefix

**Branch**: Work on `main` unless branching is needed




