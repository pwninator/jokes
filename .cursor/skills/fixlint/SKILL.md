---
name: fixlint
description: Fix lint warnings and errors for user-specified files by selecting the correct linter per file type. Use when the user asks to fix lint issues in Python or Dart files, including pylint/basedpyright for Python and flutter analyze for Dart.
---

# Fix Lint

## When To Use

Use this skill when the user asks to fix lint warnings/errors for one or more files and the lint tool should be chosen by file type.

## Inputs

Require explicit target file path(s). Do not expand scope to other files unless the user asks.

Choose tools by file type:
- Python (`.py`): `pylint` and `basedpyright`
- Dart (`.dart`): `flutter analyze`

## Workflow

Copy this checklist and keep it updated:

```text
Fixlint Progress:
- [ ] Confirm target files from user input
- [ ] Run lint tools for target files only
- [ ] Apply safe automatic fixes first
- [ ] Re-run lint tools for target files
- [ ] Make minimal manual edits for remaining issues
- [ ] Re-run lint tools and tests relevant to changed behavior
- [ ] Report what was fixed and what remains
```

1. Validate target files:
   - If no file paths are provided, ask for file paths.
   - Operate only on those files.

2. Run lint checks on those files only:
   - Python targets: run `pylint` and `basedpyright`.
   - Dart targets: run `flutter analyze` scoped as narrowly as possible.
   - If project has additional lint checks for that file type, run them only if requested.

3. Apply safe auto-fixes first:
   - Use formatter/import organizers already used by the repo on target files only.
   - Dart targets: run `dart format` on the target `.dart` file(s) before re-running `flutter analyze`.
   - Do not introduce behavior changes while fixing style/type lint.

4. Handle remaining findings manually:
   - Prefer reusing existing helpers/patterns in the codebase.
   - Keep edits minimal and local.
   - Do not refactor unrelated code.

5. Verify:
   - Re-run the file-type-appropriate lint command(s) for target files.
   - Run focused tests only where behavior changed.
   - If no behavior changed, avoid broad test runs unless user asks.

## Command Patterns

Run from repo root and keep paths explicit.

```bash
# Python: pylint for specific files
python -m pylint --rcfile=py_quill/.pylintrc py_quill/path/to/file_a.py py_quill/path/to/file_b.py

# Python: basedpyright (file-scoped when supported by project config)
basedpyright py_quill/path/to/file_a.py py_quill/path/to/file_b.py

# Python: safe formatting used by this repo
python -m yapf -i py_quill/path/to/file_a.py py_quill/path/to/file_b.py

# Dart: flutter analyze (prefer narrow scope)
flutter analyze lib/src/path/to/file_a.dart test/path/to/file_a_test.dart

# Dart: safe formatting for target files
dart format lib/src/path/to/file_a.dart test/path/to/file_a_test.dart
```

If the project toolchain requires directory-level type checks, run the narrowest supported scope and clearly state that constraint.

## Guardrails

- Only make changes requested by the user.
- Never modify unrelated files.
- Prefer existing project patterns over new abstractions.
- Do not silence warnings by disabling rules unless user explicitly requests that approach.
- If a lint issue is ambiguous or risky, ask before changing behavior.

## Output Format

Provide:

1. Files fixed
2. Commands run
3. Remaining issues (if any)
4. Any assumptions or constraints
