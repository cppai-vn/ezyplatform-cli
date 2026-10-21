---
name: ezy-verify
description: Preview EzyArticle pages locally with fragments inlined and check the live EzyPlatform site after a change (HTTP status, unrendered template markers, expected texts, both languages, light/dark, mobile). Use before asking approval to publish, right after publishing, or when the user reports the live site looks wrong.
---

# ezy-verify

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

## Local preview (before publish)

```bash
S=${CLAUDE_SKILL_DIR}/scripts/ezy_verify.py
python3 $S preview home              # .artifacts/preview/home.html
python3 $S preview home --lang en
python3 -m http.server 8765 --bind 127.0.0.1 --directory .artifacts/preview   # run in background, stop afterwards
```

Thymeleaf is not executed locally (server menus, `#messages` stay empty) — judge layout and style only. Open the page in the browser pane and check:

- desktop 1440 px and mobile 375 px (no horizontal scroll: `document.documentElement.scrollWidth === clientWidth`);
- light **and** dark (`localStorage['<site>-theme']` = `light`/`dark`, reload);
- every section by scrolling with `behavior:'instant'` (smooth scrolling makes screenshots lag);
- default language and each translation.

Stop the preview server when done (process-management rule).

## Live check (after publish)

```bash
python3 $S live / --expect "Put AI to" "Our partner network"
python3 $S live / --lang en --expect "..."
```

Fails on non-200, on raw `ezy:block`/`th:` markers (wrong `contentType`, gotcha 9) or on missing expected text. Then repeat the visual checklist on the live URL and confirm interactive parts: theme toggle, language switch, menu (desktop + mobile, Escape closes).

Reset browser state you changed (theme in `localStorage`, emulated viewport) afterwards.

## Finish

Report what was checked and anything that failed with evidence (screenshot or command output), then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
