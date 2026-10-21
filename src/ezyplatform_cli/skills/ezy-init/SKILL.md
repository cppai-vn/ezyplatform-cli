---
name: ezy-init
description: Bootstrap a new EzyPlatform / EzyArticle project folder — the same starter structure and agent instructions as the VS Code extension's "Create Project" (environment.json, AGENTS.md, AGENTS_UPDATED.md, README.md, api/v1/media, example page, .gitignore) plus the ezy-* skills — then guide the human to get the admin access token and validate the connection. Use when starting work on a new EzyPlatform site, when a folder has no environment.json, when the token is missing/expired/rejected, or to re-check a project's setup.
---

# ezy-init

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Sets up a project so every other `ezy-*` skill works. Never ask the human to paste the token into chat; they paste it into `environment.json` themselves.

## 1. Create the structure

Ask for the admin URL if you do not have it (e.g. `https://admin.example.com`), then:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_init.py create <target-folder> --admin-url https://admin.example.com
```

The script lives in `${CLAUDE_SKILL_DIR}/scripts/` wherever the skills are installed; it prints its own absolute path in the next steps.

Creates only what is missing (safe to re-run):

| Item | Content |
|---|---|
| `environment.json` | extension template (`production` default + optional `beta`), admin URL filled in, token placeholder, `chmod 600` |
| `.gitignore` | `environment.json`, `.artifacts/`, `*.pyc` |
| `AGENTS.md` | ezy section (how to work with this site + skill-improvement rule) + the extension's full EzyArticle conventions |
| `AGENTS_UPDATED.md` | extension's updated instructions (always refreshed, like the extension) |
| `README.md` | extension user guide; add site notes there later |
| `api/v1/media/`, `pages/example-page/` | starter folders, example page as `DRAFT` (`--no-example` to skip) |
| `.claude/skills/ezy-*` | only with `--copy-skills` (agents without plugin support, or to pin a version); `--update-skills` refreshes a vendored copy |

Starter texts come from the newest installed EzyArticle extension (via `node`), else from `templates/` (extension 0.2.8, MIT — see `templates/NOTICE.md`). If `AGENTS.md` already existed without the ezy section, the script says so; prepend `templates/ezy-section.md` only after the human agrees.

## 2. Guide the human to the token

Relay these steps (the script prints them with the real URL; `token-help <admin_url>` reprints them):

1. Open `<admin_url>/admins/me` and sign in as an admin.
2. Find **Access Token**, click to reveal it, confirm with the admin password.
3. Paste it into `environment.json` → entry with `"default": true` → `"admin_access_token"`; check `"admin_url"`; delete the `beta` entry if unused.
4. Tell the agent when done — do not send the token in chat.

Explain the risk once: the token carries the full rights of that admin account (often `super_admin`). Recommend a dedicated admin account with only content/media rights for day-to-day work, and regenerating the token if it leaks.

## 3. Validate

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_init.py check <target-folder>
```

Checks JSON shape, one default environment, real URL, token no longer the placeholder, `.gitignore` protection, file permissions; then calls the API: roles, public site URL, number of fragment groups on the server. HTTP 401 → token wrong/expired (copy again); 403 → wrong URL or not an admin token.

## 4. Hand over

- First content pull: `python3 ${CLAUDE_SKILL_DIR}/../ezy-sync/scripts/ezy_sync.py pull-all --langs <site languages>` (dry run, then `--write`; `--skip-placeholders` to leave out empty theme fragments, `--only <group>` to limit groups), which also pulls every page the server lists (Trash excluded); `discover-pages --write` is only needed to pull a linked subset.
- Record the site structure in `README.md` as you learn it (theme/header/footer fragments, menus, languages).
- Continue with `ezy-guide`.

## Finish

Report what was created, the `check` result (roles, site URL — never the token), next steps, then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
