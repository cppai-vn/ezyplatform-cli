---
name: ezy-publish
description: Publish local EzyArticle pages and page fragments to the live EzyPlatform site (local → server) with a dry-run plan, automatic backup, per-language updates, post-write verification and one-command rollback. Use when the user asks to deploy, publish, push or go live with site changes, or to roll back a publish.
---

# ezy-publish

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Local → server. This changes what visitors see. Read `ezy-guide` (safety rules, gotchas 2–6, 13–14) first.

## Workflow

1. **Drift check** — `ezy-sync status` for the targets. If the server differs from what you started from, stop and tell the human (someone else edited it).
2. **Preview** — `ezy-verify preview` for affected pages; fix layout issues before publishing.
3. **Plan (dry run)**
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_publish.py plan fragment:cppai/theme page:home
   ```
   Shows per target and language which fields change. Fragments are ordered before pages automatically.
4. **Ask the human** — show the plan and get explicit approval for this publish.
5. **Apply**
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_publish.py apply fragment:cppai/theme page:home --yes
   ```
   Backs up each live post to `.artifacts/backups/<timestamp>/`, PUTs only changed fields, re-reads and verifies, prints the rollback command. Stops at the first failure.
6. **Verify live** — `ezy-verify live` (both languages, expected texts), plus a visual check if layout changed.
7. **Rollback if needed** (also needs approval)
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_publish.py restore .artifacts/backups/<timestamp> --yes
   ```

## Remove (move to Trash)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_publish.py remove page:old-landing fragment:legacy/header post:sample-post    # dry run
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_publish.py remove page:old-landing fragment:legacy/header post:sample-post --yes
python3 ${CLAUDE_SKILL_DIR}/scripts/ezy_publish.py restore .artifacts/backups/<timestamp>-remove --yes                  # undo
```

- The server moves removed posts to the admin Trash (gotcha 13); say "moved to Trash", never "permanently deleted". Emptying the Trash is a manual admin action for the human.
- Refuses a fragment that local HTML still includes with `ezy:replace` (`--force` overrides). Check that the active theme does not use it either: theme-seeded fragments (`account/*`, `support/*`, …) belong to the theme.
- Backs up every site language first, then verifies each post is `TRASH` and gone from the post list. A removed page's URL then shows the theme's "not found" page with HTTP 200 (gotcha 14).
- After removing, delete the matching local folders so `ezy-sync status` does not report them as missing.

## Rules

- Only existing server posts are updated. A brand-new page/fragment must be created once with the VS Code extension (`EzyArticle: Publish Content To Server`), then managed here. If this keeps coming up, propose adding create support.
- Live `status`, `slug`, `postType`, `contentType` and menu link are preserved; the script warns when `meta.json` status disagrees.
- Media referenced by the new markup must already exist (`ezy-media status`); UI strings must already be pushed (`ezy-i18n`) before markup that uses new keys goes live.
- Publish order for shared changes: theme/CSS fragments → header/footer → pages.
- Do not commit or push git as part of publishing unless the human asks.

## Finish

Report what went live (targets × languages), the backup path, verification results, then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
