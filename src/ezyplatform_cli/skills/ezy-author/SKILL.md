---
name: ezy-author
description: Write or redesign EzyArticle pages, page fragments and themes (HTML/Thymeleaf/CSS/JS) in a local EzyPlatform project, including translated content files. Use when the user asks to build, restyle, redesign, add a section to, translate or fix the markup of a page, header, footer or theme on an EzyPlatform site.
---

# ezy-author

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Edits local files only. Publishing is `ezy-publish`; preview is `ezy-verify`.

## Before writing

1. `ezy-sync status` for the targets — never edit on top of stale files.
2. Read the project `AGENTS.md` sections for the object you touch (page types, `ezy:block`, regions, localized files, `ezyfunctions`). They are the contract with the platform.
3. Read the site `README.md` for site-specific structure (which fragments make the theme, header, footer; menu wiring).
4. Load `references/authoring-patterns.md` for patterns proven on live sites.

## Core rules

- **Page type decides where code goes.** `STANDALONE_PAGE`: full HTML in `content.html`, include fragment regions with `<ezy:block ezy:replace="~{page/fragment :: head|content|foot}" />` in the matching place. `PAGE`/`TEMPLATED_PAGE`: body in `content.html`, page CSS in `head.html`, page JS in `foot.html`.
- **`contentType: THYMELEAF`** whenever the file uses `ezy:*`, `th:*`, `ezyfunctions` or `#messages`.
- **Shared look lives in a theme fragment** (CSS variables for light/dark, base components). Pages carry markup, not duplicated stylesheets.
- **Translations:** every language file must stay structurally identical. Edit the default file, then mirror the change into `content.<lang>.html` in the same session; translate copy, keep IDs, classes and anchors. Generate both from one data source when a section is data-heavy.
- **UI strings shared across pages** (menu labels, buttons in header/footer) belong in i18n messages (`ezy-i18n`), not hard-coded per language.
- **Images/CSS/JS files** go to the media library (`ezy-media`) and are referenced as `/api/v1/media/<name>?v=` or via `ezy:mhref`/`ezy:msrc`; avoid data URLs except for tiny icons.
- **Real content only.** Take facts from the user's sources; mark illustrative examples as such in your report; never publish personal data (ID numbers, registration scans).
- Never add `id` to `meta.json`; never rename a page folder to "rename" a page (it creates a new one).

## Quality bar before handing to ezy-verify

- Works in light and dark (if the site has a theme toggle) and at 375 px width without horizontal scroll.
- Text contrast ≥ 4.5:1; no meaning carried by faded/grey text alone.
- Motion is CSS-only, readable when static, and disabled under `prefers-reduced-motion`.
- Anchors used by menus still exist (check menu `customLink`s via `python3 ${CLAUDE_SKILL_DIR}/../ezy-shared/ezy_client.py get /ezyarticle/api/v1/menus`).

## Finish

List changed files and what changed per language, hand off to `ezy-verify preview`, then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
