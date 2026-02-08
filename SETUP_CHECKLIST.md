# Setup Checklist

⚠️ **Before starting any work on this project, complete this checklist:**

## Pre-Development Checklist

- [ ] **Read `docs/workflow/BEST_PRACTICES.md`** - ⚠️ **MANDATORY**
- [ ] **Read `docs/workflow/GIT_WORKFLOW.md`** - Understand git workflow
- [ ] **Review project structure** - Understand the architecture
- [ ] **Set up environment** - Copy `.env.example` to `.env` and configure
- [ ] **Install dependencies** - Run `./scripts/setup.sh` or manually install

## Initial Setup

### 1. Environment Setup
- [ ] Copy `.env.example` to `.env`
- [ ] Configure environment variables in `.env`
- [ ] Verify `.env` is in `.gitignore` (never commit `.env`)

### 2. Backend Setup
- [ ] Navigate to `backend/`
- [ ] Create virtual environment: `python3 -m venv venv`
- [ ] Activate virtual environment: `source venv/bin/activate` (macOS/Linux)
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Verify installation: `python3 -m uvicorn api.main:app --help`

### 3. Frontend Setup
- [ ] Navigate to `frontend/`
- [ ] Install dependencies: `npm install`
- [ ] Verify installation: `npm run dev` (should start without errors)

### 4. Database Setup
- [ ] Review `backend/database/schema.sql`
- [ ] Database will be auto-created on first API call (if using SQLite)
- [ ] Or run migrations manually if configured

### 5. Git Setup
- [ ] Initialize git: `git init` (if not already done)
- [ ] Review `.gitignore` - ensure sensitive files are excluded
- [ ] Set up remote repository (if applicable)
- [ ] **DO NOT commit yet** - Wait for user approval per BEST_PRACTICES.md

## Development Workflow Reminder

Before making any code changes:
1. ✅ Read `docs/workflow/BEST_PRACTICES.md`
2. ✅ Propose your approach to the user
3. ✅ Wait for explicit approval
4. ✅ Implement only after approval
5. ✅ Propose tests after implementation
6. ✅ Get user validation before committing

## Testing Setup

- [ ] Backend tests run: `cd backend && pytest`
- [ ] Frontend tests run: `cd frontend && npm test`
- [ ] All tests pass

## Verification

- [ ] Backend starts: `http://localhost:8000/health`
- [ ] Frontend starts: `http://localhost:3000`
- [ ] API connection works (frontend can reach backend)
- [ ] Database connection works

## Ready to Develop

Once all checkboxes are complete, you're ready to start development!

**Remember**: Always refer back to `docs/workflow/BEST_PRACTICES.md` before making changes.




