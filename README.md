# Project Template

⚠️ **IMPORTANT: Before making any changes, read `docs/workflow/BEST_PRACTICES.md`**

This is a template project for quickly starting new full-stack applications with:
- **Backend**: FastAPI (Python)
- **Frontend**: Next.js (TypeScript/React)
- **Database**: SQLite (configurable)
- **Testing**: Pytest (backend) + Jest (frontend)

## 🚀 Quick Start

1. **Read the setup checklist**: `SETUP_CHECKLIST.md`
2. **Review best practices**: `docs/workflow/BEST_PRACTICES.md`
3. **Follow the setup script**: `./scripts/setup.sh`

## 📁 Project Structure

```
template_project/
├── backend/              # FastAPI backend
│   ├── api/             # API routes and models
│   ├── database/        # Database connection and migrations
│   └── tests/           # Backend tests
├── frontend/            # Next.js frontend
│   ├── app/            # Next.js app router
│   ├── src/            # Source code
│   └── __tests__/      # Frontend tests
├── docs/                # Documentation
│   ├── workflow/       # Best practices and git workflow
│   ├── project/        # Project-specific documentation
│   └── guides/         # User guides
└── scripts/            # Utility scripts
```

## ⚙️ Configuration

### Backend
- **Port**: 8000 (default)
- **Database**: `backend/database/app.db` (SQLite)
- **Environment**: Copy `.env.example` to `.env`

### Frontend
- **Port**: 3000 (default)
- **API URL**: `http://localhost:8000` (configured in `src/api/client.ts`)

## 📚 Documentation

- **[BEST_PRACTICES.md](docs/workflow/BEST_PRACTICES.md)** - ⚠️ **READ THIS FIRST**
- **[GIT_WORKFLOW.md](docs/workflow/GIT_WORKFLOW.md)** - Git workflow guidelines
- **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)** - Setup checklist

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 🔧 Development

### Start Backend
```bash
cd backend
python3 -m uvicorn api.main:app --reload --port 8000
```

### Start Frontend
```bash
cd frontend
npm run dev
```

## � Troubleshooting

### Frontend Won't Start

**Check for running processes:**
```bash
# Check if port 3000 is in use
lsof -ti:3000

# Check for any Next.js processes
lsof -ti:3000 | xargs kill -9
```

**Kill running processes:**
```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Kill all Node processes (use with caution)
killall node

# Kill specific process by PID
kill -9 <PID>
```

**Clear Next.js cache and restart:**
```bash
cd frontend
rm -rf .next
npm run dev
```

**If you see "Unable to acquire lock" error:**
```bash
cd frontend
rm -rf .next
lsof -ti:3000,3001 | xargs kill -9
npm run dev
```



### Backend Won't Start

**Check for running processes:**
```bash
# Check if port 8000 is in use
lsof -ti:8000

# Check for any uvicorn processes
ps aux | grep uvicorn
```

**Kill running processes:**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill all Python processes (use with caution)
killall python3

# Kill specific process by PID
kill -9 <PID>
```

### Common Issues

**Port already in use:**
- Another instance is running
- Previous process didn't terminate cleanly
- Use `lsof -ti:<PORT>` to find and kill the process

**Lock file errors (Next.js):**
- Delete `.next` directory: `rm -rf frontend/.next`
- Kill all node processes: `killall node`
- Restart dev server

**iCloud Drive sync issues:**
- Project is in iCloud Drive which can cause file lock issues
- Consider moving project to local directory for development
- Or exclude `.next` and `node_modules` from iCloud sync

### Clean Restart (Nuclear Option)

**Frontend:**
```bash
cd frontend
rm -rf .next node_modules
npm install
npm run dev
```

**Backend:**
```bash
cd backend
rm -rf __pycache__ **/__pycache__
python3 -m uvicorn api.main:app --reload --port 8000
```

**Both:**
```bash
# Kill all processes
lsof -ti:3000,8000 | xargs kill -9
killall node
killall python3

# Clean and restart
cd frontend && rm -rf .next && npm run dev &
cd backend && python3 -m uvicorn api.main:app --reload --port 8000
```

## �📝 Notes

- **Always check `docs/workflow/BEST_PRACTICES.md` before making code changes**
- **Always propose tests after developing new code**
- **Always get user approval before committing or pushing**
- **If dev servers hang, check for stale processes and lock files**




