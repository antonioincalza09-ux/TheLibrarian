# File Organization Rules

## Default Categories

- `Documents/`: PDFs, Word documents, text notes, presentations.
- `Media/`: images, audio, video, design exports.
- `Code/`: source files, scripts, config files, development assets.
- `Archives/`: zip, rar, 7z, tar, gz, backups.
- `Data/`: CSV, Excel, JSON, XML, database exports.
- `Apps/`: installers, executables, packages.
- `Review/`: unknown, ambiguous, duplicate-risk, or low-confidence files.

## Decision Signals

Use multiple signals before deciding:

- file extension
- filename
- parent folder
- modified date
- lightweight content hints when safe
- related filename patterns
- project/client/topic naming

## Safety Behavior

- If source and destination conflict, do not overwrite automatically.
- If confidence is low, route to `Review/`.
- If a file appears to belong to multiple groups, choose the group that best preserves workflow convenience.
- Preserve relative grouping when files appear related.

