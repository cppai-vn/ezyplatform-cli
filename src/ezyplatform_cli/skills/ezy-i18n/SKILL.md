---
name: ezy-i18n
description: Manage EzySupport i18n messages (web/admin UI strings in messages*.properties) for an EzyPlatform site — diff local vs server per language and push only changed keys. Use when adding or renaming menu labels, header/footer strings or other shared UI text, when a label shows the raw key or the wrong language, or when adding a new site language.
---

# ezy-i18n

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Two kinds of multilingual content exist on EzyPlatform:

| Kind | Lives in | Owner skill |
|---|---|---|
| Page/fragment content per language | `content.<lang>.html`, `meta.<lang>.json` | `ezy-author` + `ezy-publish` |
| Shared UI strings (menu labels, buttons) | `web|admin/messages/messages[_<lang>].properties` | **this skill** |

## Commands

```bash
S=${CLAUDE_SKILL_DIR}/scripts/ezy_messages.py
python3 $S diff web                 # default messages.properties
python3 $S diff web --lang en
python3 $S push web --lang en                          # dry run, changed keys only
python3 $S push web --lang en --keys cppai_nav_team --yes
```

## Rules

- Push only changed keys (the script never sends the full map); the server holds hundreds of keys owned by plugins and the admin UI.
- A new key must exist in **default, and every site language** before markup or a menu label uses it.
- Prefix site keys (`<site>_<area>_<name>`, e.g. `cppai_nav_about`) so templates can tell keys from literal labels.
- Menu items keep one URL list; translate labels through keys instead of duplicating menus per language.
- After pushing, the platform may cache messages briefly — reload the live page before concluding it failed.
- Adding a site language also needs **Settings → Website Languages** in the admin (no skill script yet).

## Finish

Report keys pushed per language and verification, then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
