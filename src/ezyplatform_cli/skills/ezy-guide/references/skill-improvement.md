# Skill improvement loop

This project manages a real site **and** grows the `ezy-*` skill set. Every
operation on a site is also a test of the skills.

## When

At the end of any operation that touched an EzyPlatform site or its local files
(sync, author, media, i18n, publish, verify, debugging).

## What to look for

- A step done by hand that a script could do (repeated curl/python, manual diffing).
- A server behaviour that surprised you → candidate entry for `platform-gotchas.md`.
- An instruction that was wrong, stale, missing or ambiguous.
- A script error, confusing output, or missing guard (dry run, backup, verify).
- A recurring task with no owning skill → candidate new `ezy-<name>` skill.
- A user correction about design, copy or process that should become a rule.

## How to propose

Do **not** edit skills silently. End the report to the human with:

```
Skill suggestions (need approval):
1. [ezy-<skill>] <file> — update — <concrete change> — why: <evidence from this run> — verified: <site> | both — effort: S/M/L
2. [new: ezy-<name>] <files to create> — new — <purpose and commands> — why: <evidence, which owner is missing> — verified: <site> | both — effort: S/M/L
```

Each line must name the exact file (`ezy-<skill>/SKILL.md`, `ezy-<skill>/references/<file>.md`, `ezy-<skill>/scripts/<file>.py`, `ezy-shared/<file>.py`) and say whether it updates an existing skill or creates a new one. "Update the skills" without a file is not a suggestion.
Check the behaviour read-only on a second site before calling it a platform fact; otherwise mark it `verified: <site>` and phrase it as seen there.

Say "No skill suggestions" when nothing qualifies, so the check is visible.

## Where the change goes

- Skills installed as the `ezyplatform` plugin are a read-only cache: never edit them in place. Open an issue or pull request at the skills repository (see the plugin's README), including the evidence.
- Skills vendored in the project (`.claude/skills`, `.agents/skills`) or a local clone of the repository may be edited after approval; upstream the change afterwards so every EzyPlatform user gets it.

## After approval

1. Make the smallest change that fixes the observed friction (frontmatter, SKILL.md step, reference, or script).
2. Run the touched script in its read-only / dry-run mode against the live site.
3. Record new verified platform facts in `platform-gotchas.md` with an evidence line.
4. Release in one step from a clone of the marketplace repository (users only receive releases with a new version):
   ```bash
   python3 scripts/release_plugin.py ezyplatform patch -n "<what changed and why>" -m "fix(ezyplatform): <summary>"           # dry run
   python3 scripts/release_plugin.py ezyplatform patch -n "<what changed and why>" -m "fix(ezyplatform): <summary>" --push --install --yes
   ```
   It bumps `version`, writes the `CHANGELOG.md` entry, validates (`claude plugin validate --strict`, Python syntax), commits, pushes and refreshes the local install. Use `minor` for new features or behaviour changes.
5. Do not hand-edit `version`/`CHANGELOG.md` when using the script; it refuses duplicate versions.
6. **Changed skills are not reloaded in a running session.** A session keeps the skill text it loaded at start, so it still shows the old instructions after you edit them. Test script changes by running the scripts directly; to confirm the new SKILL.md text (or `${CLAUDE_SKILL_DIR}` substitution), start a new agent session. Claude Code runs a copy of the plugin cached per version (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`), even when the marketplace is a local folder: after bumping the version run `claude plugin marketplace update cppai` and `claude plugin update ezyplatform@cppai` (or `/plugin marketplace update cppai` in a session), then start a new session. Never edit the cached copy.
