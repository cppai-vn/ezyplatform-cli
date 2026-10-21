# Working With This Project

This is an EzyPlatform / EzyArticle site project (site: {{SITE}}). Content lives
in local files and is synchronized with the EzyPlatform admin server configured in
`environment.json` (git-ignored, holds the admin access token — never print,
commit or paste it anywhere).

## ezy-* skills

The `ezy-*` agent skills manage this site. Install them once as the Claude Code plugin
`ezyplatform` from the CPPAI marketplace (https://github.com/{{REPO}}), or copy its `skills/` folder into
`.claude/skills/` / `.agents/skills/` for other agents:

* Start every site task with `ezy-guide` (routing, safety rules, verified platform gotchas). It routes to `ezy-new`, `ezy-sync`, `ezy-author`, `ezy-media`, `ezy-i18n`, `ezy-publish`, `ezy-verify`.
* `ezy-new check` re-validates `environment.json` and the token at any time.
* Prefer the skill scripts over ad-hoc HTTP calls; shared code is in the `ezy-shared` folder next to the skills.
* Every write to the server (publish, media upload/visibility, messages push, restore) runs as a dry run first and needs explicit human approval.

## Skill improvement rule

After every operation on the site, check whether an ezy-* skill could be improved or a new one is needed (manual steps a script could do, surprising server behaviour, wrong or missing instructions, script errors). Suggest changes to the human at the end of the report (format: `references/skill-improvement.md` of the `ezy-guide` skill) or state "No skill suggestions". Approved changes go upstream as an issue or pull request to the skills repository; never edit a plugin's installed copy.

## Site notes

Record site-specific structure and decisions in `README.md` (which fragments form the theme, header and footer; menu wiring; languages; publishing notes).

---

