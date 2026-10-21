---
name: ezy-media
description: Manage files in the EzyPlatform media library (images, logos, CSS, JS under api/v1/media) — check what exists on the server, upload or replace files, toggle public/private, and produce cache-busted URLs. Use when a site change adds or replaces an image or static file, when media URLs return 404, or when moving embedded data-URL images to the media library.
---

# ezy-media

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Read `ezy-guide` first. Uploads and visibility changes write to the server: dry run, then human approval.

## Commands

```bash
S=${CLAUDE_SKILL_DIR}/scripts/ezy_media.py
python3 $S status                         # every local api/v1/media file vs server
python3 $S status cppai-logo.webp
python3 $S upload api/v1/media/hero.webp                 # dry run: add or replace
python3 $S upload api/v1/media/hero.webp --yes           # after approval
python3 $S public hero.webp --yes | python3 $S unpublic hero.webp --yes
python3 $S url hero.webp                  # https://<site>/api/v1/media/hero.webp?v=<mtime>
```

## Rules

- Names: `^[a-zA-Z0-9_-]+(.[a-zA-Z0-9_-]+)*$` — no spaces or accents; prefer `<site>-<purpose>.<ext>` (e.g. `cppai-partner-egany.webp`).
- Empty files or `{"token":"invalid"}` placeholders are refused by the platform; the script stops on them.
- Reference images as `/api/v1/media/<name>?v=<timestamp>`; CSS/JS with `<link ezy:mhref="/api/v1/media/x.css">` / `<script ezy:msrc="/api/v1/media/x.js">` so the platform appends the version.
- Upload media **before** publishing markup that references it, then confirm with `status` (gotcha 8).
- Optimise first: WebP, sized to display (≈2× CSS size), keep logos small.
- Saving a file under `api/v1/media` in VS Code with the extension active also uploads it — tell the human when that matters.

## Finish

Report uploaded/replaced files and their URLs, then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
