---
name: precise-html-generation
description: Generate HTML only from the specific JSON file requested, never scanning other files
metadata:
  type: feedback
---

When the user asks to generate HTML from a specific JSON file (e.g., `shared/reading/cambridge-2/test-gt-a.json`), **only generate sections from that file**. Do NOT use `--all` without `--test` scope, as that scans all `test-*.json` files in the source directory and regenerates everything, overwriting any manual edits.

**Why:** The user may have manually edited existing HTML files. `--all --force` destroys those edits without warning.

**How to apply:**
- For one test: `--test gt-a --section N` (single section) or `--test gt-a --all` (all sections of that test only)
- Never use bare `--source X --all` unless explicitly told to regenerate everything
- Never use `--force` unless the user confirms they want to overwrite, or the files don't exist yet
