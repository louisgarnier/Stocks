# Best Practices & Workflow Guidelines

## ⚠️⚠️⚠️ CRITICAL RULES - MUST BE FOLLOWED ALWAYS ⚠️⚠️⚠️

**These rules are NON-NEGOTIABLE. They must be followed EVERY TIME, without exception.**

### Before Any Code Changes
- ✅ **ALWAYS check with the user before:**
  - Writing or modifying code
  - Creating new files (except documentation)
  - Pushing to GitHub
  - Running commands that modify the codebase

### After Code is Developed - MANDATORY WORKFLOW

**⚠️ YOU MUST FOLLOW THIS EXACT SEQUENCE - NO EXCEPTIONS ⚠️**

1. **NEVER check [x] in feature MD files immediately after creating code**
   - ❌ DO NOT check [x] just because code was written
   - ❌ DO NOT check [x] before tests are created
   - ❌ DO NOT check [x] before tests are executed
   - ❌ DO NOT check [x] before user confirms

2. **ALWAYS create a test script (`.py` file) after writing code**
   - ✅ Test script must be executable: `python path/to/test_script.py`
   - ✅ Test script must display logs in terminal
   - ✅ Test script must verify the code works correctly
   - ✅ Test script must be in a clear location (e.g., `backend/tests/test_feature_name.py`)

3. **ALWAYS propose the test script to the user**
   - ✅ Show what the test script does
   - ✅ Explain how to run it
   - ✅ Wait for user approval before executing

4. **ONLY check [x] after ALL of these are true:**
   - ✅ Test script has been created
   - ✅ Test script has been executed (by user or AI)
   - ✅ Test results show the code works correctly
   - ✅ User explicitly confirms the step is complete
   - ✅ All acceptance criteria are met

5. **When updating MD files:**
   - ✅ Update tasks to [x] ONLY after tests pass
   - ✅ Update acceptance criteria to [x] ONLY after validation
   - ✅ Update step status to "COMPLETED" ONLY after user confirmation

### Before Pushing to GitHub
- ✅ **ALWAYS confirm with the user before:**
  - Committing changes
  - Pushing to any branch
  - Creating new branches (unless explicitly requested)

## Workflow - EXACT SEQUENCE TO FOLLOW

**Follow this sequence EXACTLY - do not skip steps:**

1. **Understand the requirement** - Ask clarifying questions if needed
2. **Propose the approach** - Explain what you'll do
3. **Wait for approval** - Get explicit confirmation before proceeding
4. **Implement** - Only after approval
5. **Create test script** - ALWAYS create a `.py` test file that can be executed
   - Test script must be in `backend/tests/` or appropriate location
   - Test script must be executable with `python path/to/test_script.py`
   - Test script must display logs when run
6. **Propose test execution** - Show the test script and propose running it
   - Explain what the test will verify
   - Show the command to run it
   - Wait for user approval
7. **Execute and verify** - Run tests and verify they pass
   - Execute test script (if user approved)
   - Check test results
   - Verify all functionality works
8. **Get user confirmation** - Wait for user to confirm step is complete
   - DO NOT update MD files until user confirms
9. **Update MD files** - ONLY after user confirms:
   - Check [x] in tasks
   - Check [x] in acceptance criteria
   - Update step status to "COMPLETED"

## Documentation

- Documentation files (`.md` files in `docs/`) can be created/updated without explicit approval
- Code files require explicit approval before modification

## Communication

- Be clear about what you're planning to do
- Explain the "why" behind your approach
- Wait for confirmation before executing

## Common Mistakes to AVOID

❌ **DO NOT:**
- Check [x] immediately after creating code
- Skip creating test scripts
- Update MD files before tests are validated
- Assume code works without testing
- Check [x] before user confirms

✅ **ALWAYS:**
- Create test script after writing code
- Propose test execution to user
- Wait for test results before updating MD
- Get user confirmation before marking steps complete
- Follow the exact workflow sequence

## Architectural Guidelines

### Component Size Limits

**Frontend Components (React/Next.js)**:
- ✅ Single component file: **< 300 lines**
- ✅ Page component: **< 200 lines** (orchestration only)
- ✅ Reusable component: **< 150 lines**
- ⚠️ **REFACTORING TRIGGER**: If component exceeds 300 lines, STOP and propose refactoring

**Backend Modules (Python)**:
- ✅ Single module file: **< 500 lines**
- ✅ API route file: **< 300 lines**
- ✅ Utility/helper file: **< 200 lines**
- ⚠️ **REFACTORING TRIGGER**: If module exceeds 500 lines, STOP and propose refactoring

### Code Organization Patterns

**Frontend Structure**:
```
frontend/
├── app/
│   ├── page.tsx              # < 200 lines - tab orchestration only
│   └── [feature]/
│       └── page.tsx          # Feature-specific pages
├── src/
│   ├── components/           # Reusable components
│   │   ├── [Feature]Tab.tsx  # Tab components
│   │   └── [Feature]Card.tsx # Card components
│   ├── hooks/                # Custom React hooks
│   ├── api/                  # API client services
│   └── types/                # TypeScript types
```

**Backend Structure**:
```
backend/
├── api/
│   └── routes/               # API endpoints (< 300 lines each)
├── scripts/                  # Standalone scripts
├── utils/                    # Helper functions
├── services/                 # Business logic
└── database/                 # Database operations
```

### When to Extract Components/Modules

**Extract a new component when**:
- Component exceeds 300 lines
- Logic is repeated in multiple places
- Component has more than 3 distinct responsibilities
- Component manages more than 5 state variables
- Component has more than 10 props

**Extract a new module when**:
- Module exceeds 500 lines
- Functions are used across multiple files
- Module has more than 3 distinct responsibilities
- Module becomes difficult to test

### Refactoring Triggers - MANDATORY STOPS

**⚠️ STOP and propose refactoring when**:

1. **File Size Exceeded**:
   - Frontend component > 300 lines
   - Backend module > 500 lines
   - Page component > 200 lines

2. **Complexity Indicators**:
   - Function has > 50 lines
   - Nested conditionals > 3 levels deep
   - Cyclomatic complexity > 10
   - More than 5 function parameters

3. **Code Duplication**:
   - Same logic appears in 3+ places
   - Copy-paste code detected

4. **Performance Issues**:
   - Component re-renders excessively
   - Database queries are slow (> 1 second)
   - API responses are slow (> 2 seconds)
   - Page load time > 3 seconds

**Refactoring Workflow**:
1. **STOP** adding features to the file
2. **Propose** refactoring plan to user
3. **Wait** for approval
4. **Refactor** into smaller components/modules
5. **Test** that functionality still works
6. **Get confirmation** before continuing with new features

### Performance Requirements

**Frontend Performance**:
- ✅ Initial page load: **< 3 seconds**
- ✅ Tab switching: **< 500ms**
- ✅ API response rendering: **< 1 second**
- ✅ Table with 100 rows: **< 2 seconds**
- ✅ Table with 1,000 rows: Use virtualization

**Backend Performance**:
- ✅ Simple API endpoint: **< 100ms**
- ✅ Database query: **< 500ms**
- ✅ Complex calculation: **< 2 seconds**
- ✅ Batch processing (100 items): **< 10 seconds**
- ✅ Batch processing (1,000 items): **< 60 seconds**

**Database Performance**:
- ✅ All queries must use indexes
- ✅ No full table scans on tables > 10,000 rows
- ✅ Batch inserts for > 100 records
- ✅ Connection pooling for concurrent requests

### Scalability Considerations

**Before implementing a feature, consider**:

1. **Data Volume**:
   - Will this work with 10 records? 100? 1,000? 10,000?
   - What happens with 8,000 securities?
   - What happens with 2 years of daily data per security?

2. **Concurrent Users**:
   - Can this handle multiple users simultaneously?
   - Are there race conditions?
   - Is caching needed?

3. **API Rate Limits**:
   - External API rate limits
   - Retry logic and exponential backoff
   - Fallback data sources

4. **Memory Usage**:
   - Loading 8,000 securities into memory?
   - Streaming/pagination needed?
   - Garbage collection considerations?

### Code Quality Checklist

**Before proposing code, verify**:

- [ ] Component/module is < size limit
- [ ] No code duplication
- [ ] Functions have single responsibility
- [ ] Proper error handling
- [ ] Performance requirements met
- [ ] Scalability considered
- [ ] Tests included
- [ ] Documentation/comments for complex logic

### Architecture Review Triggers

**Propose architecture review when**:
- Adding a major new feature (new phase)
- File size limits repeatedly exceeded
- Performance issues detected
- Scalability concerns arise
- Technical debt accumulates

**Architecture Review Process**:
1. **Document current pain points**
2. **Propose architectural changes**
3. **Estimate refactoring effort**
4. **Get user approval**
5. **Create refactoring plan**
6. **Execute incrementally**

## Reminder

**This document serves as a permanent reminder. These rules must be followed EVERY TIME, without exception. If you find yourself checking [x] after creating code, STOP and follow the workflow above.**



