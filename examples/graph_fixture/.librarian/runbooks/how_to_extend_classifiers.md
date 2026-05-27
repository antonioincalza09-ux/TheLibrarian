# How To Extend Classifiers

1. Update offline heuristics in `src/librarian/classifiers.py`.
2. Add or refine code analyzers in `src/librarian/code_analyzers/`.
3. Re-run:
   - `librarian scan <path>`
   - `librarian mark <path>`
   - `librarian dev index <path>`
4. Check `.librarian/notes/` and `manifest.json` for expected changes.
