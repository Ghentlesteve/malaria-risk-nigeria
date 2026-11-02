# Development workflow

Keep the current repository and Git history when moving the checkout. Verify `git remote -v` in the new folder; do not initialise a replacement repository.

## Before committing

1. Make one coherent change and update the relevant documentation.
2. Run `python -m unittest discover -s tests -v` for ingestion/validation changes and `git diff --check`.
3. Review `git status --short`. Stage explicit code, test, template and documentation paths, then inspect `git diff --cached --stat` and the staged diff.
4. Commit with a message describing the completed change. Push completed milestones regularly to the existing remote. If the remote has moved, inspect and reconcile its commits before pushing; do not force-push over work.

## Public repository contents

Publish source code, tests using invented test records, empty input templates, methods and reproducibility instructions. The initial test suite uses only the Python standard library.

Keep routine health exports, derived health tables, source-cell lineage, local validation reports, climate downloads, model artifacts and credentials out of commits. The data and models directories are ignored except for their `.gitkeep` placeholders. Editor/session files, personal document outputs and the supplied training deck also remain local. Review notebook outputs before publishing any notebook containing routine health data.

Changing repository visibility does not publish ignored local files. However, `.gitignore` does not remove a file already committed in history. Check tracked files and historical contents before publishing new data. Obtain appropriate data-owner permission before sharing health-data outputs.

Repository visibility is managed by the owner. Do not infer a visibility change from a successful push.
