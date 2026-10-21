---
name: ezy-sync
description: Compare and pull EzyPlatform pages and page fragments from the live server into the local EzyArticle project (server → local, read-only for the site). Use before editing a site, when the user asks whether local files are up to date, after someone edited content in the admin UI, or to fetch a translated (`<lang>`) version of a page or fragment.
---

# ezy-sync

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Server → local. Never writes to the site. Read `ezy-guide` first if you have not.

## Check drift

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py status            # all local targets
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py status page:home fragment:cppai/header
```

- Compares `content`, `head`, `foot`, `title`, `summary` for the default language and every language that has localized files locally.
- Exit code 1 when anything differs — treat that as "someone changed the site" and pull before editing.
- A local page the server does not have is shown as `local only` when its `meta.json` status is `DRAFT` (or missing) and does not count as a difference; with any other status it is `MISSING on server` (deleted or renamed in the admin).
- Localized `summary` is skipped on purpose (the server keeps one summary; gotcha 5).

## Pull

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py pull fragment:cppai/header --lang en          # dry run
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py pull fragment:cppai/header --lang en --write
```

- Dry run by default; `--write` overwrites `content/head/foot[.<lang>].html`.
- `meta.json` / `meta.<lang>.json` is **created when missing** (extension format: title, summary, slug, pageType, contentType, status, priority, publishedAt, terms, metadata; localized meta = title only, skipped when the server has no translation). An existing meta is never rewritten (local-only fields survive); differing titles are reported for a manual edit.
- Pulling into a folder that does not exist yet creates it, so `pull` also brings a new page or fragment under local management.
- Localized fragments are read via `/posts/{id}?i18n_lang=` because the fragment endpoint ignores the language (gotcha 2).
- If local files have uncommitted edits, show `git diff` to the human before `--write`.

## Pull everything

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py pull-all --langs en                 # dry run: every fragment + local pages
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py pull-all --skip-placeholders --write      # first pull of a site
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py pull-all --only cppai --langs en --write
```

- Covers every fragment the server lists (`/pages/fragments`), every page the server lists (`GET /ezyarticle/api/v1/posts`, page types only, Trash excluded) and pages already present locally. With `--only`, server pages are skipped so only the chosen fragment groups and local pages are pulled.
- Local-only pages (not created on the server yet) are reported and skipped; they never stop the run.
- `--skip-placeholders` does not create folders for fragments whose content is only their own name (themes seed dozens of these, and the list grows as the site renders new page types). Fragments already local are always pulled.
- `--only <page_name ...>` limits fragments to some groups.
- Run `git status` first; with `--write` it overwrites local regions that differ.
- The dry-run count can be higher than the real write: localized regions are compared against default files that do not exist yet.

## Discover pages

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py discover-pages            # dry run
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_sync.py discover-pages --write
```

- Optional now that `pull-all` lists server pages: use it to pull only the pages the site actually links. Scans local page and fragment HTML for site-relative links (`href="/<slug>"`, `href="/pages/<slug>"`), checks each unknown slug against the server and pulls the ones that are pages. Slugs that are routes (or missing) are listed with the file that links them.
- Run it after the first `pull-all`, then again after pulling new pages (pages link to pages). Absolute links to the site's own domain and pages linked from nowhere are not found; pull those with `pull page:<slug>`.

## Not covered (use the VS Code extension for now)

Posts, terms, mail/content templates, media download. If you need one of these repeatedly, propose a script extension via the improvement check.

## Finish

Report which targets differed and what was pulled, then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
