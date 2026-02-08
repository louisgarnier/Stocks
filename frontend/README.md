# Frontend

Next.js frontend application.

⚠️ **Before making changes, read: `docs/workflow/BEST_PRACTICES.md`**

## Setup

1. Install dependencies:
```bash
npm install
```

2. Configure environment:
```bash
# Copy .env.example to .env.local (if exists)
# Or set NEXT_PUBLIC_API_URL in your environment
```

## Running

```bash
# Development server
npm run dev

# Production build
npm run build
npm start
```

The frontend will be available at: http://localhost:3000

## Testing

```bash
# Run tests
npm test

# Run tests in watch mode
npm test -- --watch
```

## Project Structure

```
frontend/
├── app/              # Next.js app router
│   ├── layout.tsx    # Root layout
│   ├── page.tsx      # Home page
│   └── globals.css   # Global styles
├── src/
│   ├── api/          # API client
│   ├── components/   # React components
│   └── types/        # TypeScript types
└── __tests__/        # Test files
```

## Best Practices

- Always check `docs/workflow/BEST_PRACTICES.md` before making changes
- Propose tests after developing new code
- Get user approval before committing changes




