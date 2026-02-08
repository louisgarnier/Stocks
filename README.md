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

## 📝 Notes

- **Always check `docs/workflow/BEST_PRACTICES.md` before making code changes**
- **Always propose tests after developing new code**
- **Always get user approval before committing or pushing**




