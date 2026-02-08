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

## Reminder

**This document serves as a permanent reminder. These rules must be followed EVERY TIME, without exception. If you find yourself checking [x] after creating code, STOP and follow the workflow above.**



