---
description: Execute a development phase from the consolidated plan with mandatory code review and testing
argument-hint: <phase-number> e.g. 0, 1, 1.5, 2, 2.5, 3, 4, 5
---

# Dev Pipeline: Phase Execution

Execute one phase from `docs/consolidated_dev_plan.md` with enforced review+test cycle.

## Instructions

Given argument `$ARGUMENTS` as the phase number, execute the following workflow:

### Step 1: Pre-flight (Redundancy Resolution)

1. Read `docs/consolidated_dev_plan.md`
2. Locate the section for the specified phase
3. Read every file mentioned in the "冗余代码裁定" table
4. For each entry, physically verify the current state matches the audit:
   - Files marked **删除**: confirm they exist and are not imported elsewhere
   - Files marked **修改**: confirm the current code matches the audit description
   - Files marked **保留**: confirm they should indeed be kept
5. Output a summary: "冗余裁定确认完毕，N 个删除，M 个修改，K 个保留"

### Step 2: Code (Implementation)

1. For each file in the "修改文件" table:
   - If DELETE: remove the file
   - If MODIFY: read the file, apply changes per "具体改动" section
   - If NEW: create the file with the specified content
2. Do NOT touch files listed in "不改什么"
3. After all changes, run a quick import check:
   ```bash
   cd backend && python -c "import app.main; print('imports OK')"
   ```

### Step 3: Review (Code Review)

Run through the "代码审查清单" for this phase. For each checklist item:
- If PASS: mark [x]
- If FAIL: fix the issue immediately, then re-check

Additional review checks (universal, apply to every phase):
- [ ] No `np.random` or `random.random()` in embedding/reranking code
- [ ] No hardcoded absolute paths (`D:\`, `/home/`, etc.)
- [ ] No circular imports introduced
- [ ] No unused imports added
- [ ] No debug `print()` statements left in production code
- [ ] All new functions have proper type annotations (Python)

### Step 4: Test (Verification)

Run the "验证" section commands for this phase. All must pass.
If any verification fails:
1. Identify the root cause
2. Fix the issue
3. Re-run verification
4. If fix requires changing a file in "不改什么" list, STOP and report to user

### Step 5: Commit

```bash
git add <specific changed files>
git commit -m "feat(phase-N): description"
```

Do NOT commit if any review or test step failed.

### Error Handling

- If pre-flight finds discrepancy with audit: STOP, report findings
- If code changes cause import errors: fix before proceeding to review
- If review finds issues: fix before proceeding to test
- If test fails after 2 fix attempts: STOP, report to user with diagnosis
