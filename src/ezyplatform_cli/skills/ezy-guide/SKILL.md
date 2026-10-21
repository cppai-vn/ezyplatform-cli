---
name: ezy-guide
description: Guide and index for the ezy-* skill set that manages EzyPlatform / EzyArticle sites from a local project (environment.json + pages/ + page-fragments/). Use first for any EzyPlatform site task to pick the right ezy-* skill and workflow, when unsure which skill applies, when checking which site and permissions the access token gives, and before any API call or publish (safety rules, verified platform gotchas, skill-improvement loop).
---

# ezy-guide

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Signpost for the `ezy-*` skills: which skill does what, in what order, under which rules. It does not change the site itself.

## 1. Orient (always)

1. Find the project root (folder with `environment.json`). No `environment.json`, placeholder token, or HTTP 401 → use `ezy-new` first. Never print `admin_access_token`; never put it in a URL, browser page or commit.
2. Read the project `AGENTS.md` (EzyArticle conventions from the VS Code extension) and `README.md` (site-specific notes). Skills point to them rather than copying them.
3. Check which site and role you are acting as (read-only):
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/../ezy-shared/ezy_client.py whoami
   ```
4. Before any API call or publish, load `references/platform-gotchas.md` — verified server behaviour that silently breaks naive scripts.

## 2. Which skill

| User intent | Skill |
|---|---|
| New project, no `environment.json`, token missing/expired, setup check | `ezy-new` |
| "Is local up to date?", pull server changes, before editing | `ezy-sync` |
| Build or change a page, fragment, theme, copy, content translation | `ezy-author` |
| Images, CSS/JS files, logos, anything under `api/v1/media` | `ezy-media` |
| Menu labels, shared UI strings, `messages*.properties` | `ezy-i18n` |
| Push changes live, roll back | `ezy-publish` |
| Remove a page, post or fragment (move to Trash), undo it | `ezy-publish remove` / `restore` |
| Mail not arriving, mail templates, contact form, any feature that sends email | `ezy-mail` |
| Preview locally, check the live site | `ezy-verify` |

## 3. Standard workflow for a site change

```
ezy-sync status → ezy-author (edit) → [ezy-media / ezy-i18n if needed] → ezy-verify preview
→ human approves → ezy-publish apply → ezy-verify live → improvement check
```

## 4. Project layout (EzyArticle extension 0.2.x)

| Path | Server object | Key |
|---|---|---|
| `pages/<slug>/` | page post | folder name = slug (no `id` in meta) |
| `page-fragments/<page>/<fragment>/` | fragment post | `page/fragment` path |
| `posts/<slug>/` | blog post | slug |
| `api/v1/media/<name>` | media library file | file name |
| `web/messages/`, `admin/messages/` | EzySupport i18n | `messages[_<lang>].properties` |
| `mail-templates/` | EzyMail templates (`ezy-mail`) | folder name = template name |
| `content-templates/`, `terms/` | EzySupport / taxonomy | folder names |
| `.artifacts/` (git-ignored) | backups, previews, evidence | — |

Each page/fragment: `content.html`, `head.html`, `foot.html`, `meta.json`, plus `<region>.<lang>.html` / `meta.<lang>.json` for translations.

## 5. Safety rules (all ezy-* skills)

- Every server write (publish, media upload/visibility, messages push, restore) runs as a dry run first and needs explicit human approval for that action.
- Back up before writing (`ezy-publish` stores backups in `.artifacts/backups/`).
- Never expose personal data from source documents (ID numbers, registration scans).
- If someone edited the site in the admin UI, pull before editing.

## 6. Shared code and references

- `${CLAUDE_SKILL_DIR}/../ezy-shared/` — Python library imported by every ezy-* script: `ezy_client.py` (token-safe API client, Cloudflare-safe User-Agent, payload rules) and `ezy_local.py` (local layout, localized fallback). Extend it instead of writing new HTTP code.
- `references/platform-gotchas.md` — verified platform behaviour with evidence.
- `references/api-endpoints.md` — admin API endpoints and their status.
- `references/skill-improvement.md` — how to propose skill changes.

## 7. Improvement check (end of every site operation)

After any operation on a site, follow `references/skill-improvement.md`: note friction, propose concrete skill changes to the human (or say "No skill suggestions"), and edit skills only after approval. Edited skills load only in a new session; the current one keeps the text it started with.
