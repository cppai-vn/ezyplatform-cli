---
name: ezy-publish-skill
description: Publish the user's own AI skill (a folder with SKILL.md) to the skill library of the EzyPlatform marketplace (https://ezyplatform.com/ezyai/skill-library), free or for sale. Signs in to ezyplatform.com through EzyLogin CLI login (the user only clicks Approve in the browser, no password or token is copied), registers the account as a skill seller when the user agrees, scans the skill for secrets and personal data, packs a clean zip, picks a category, sets the price, uploads it for review, and later updates the package, title, description or price, cancels a pending update or removes the skill. Use when the user asks to publish / sell / upload / đăng / bán / đưa skill lên chợ EzyPlatform (ezyplatform.com), update a skill already on the marketplace, change its price, or check the review status of their skills.
---

# Publish an AI skill to the EzyPlatform marketplace

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md).

The marketplace at https://ezyplatform.com has a skill library where anyone can publish AI skills, free or paid, and earn a commission on every sale. The marketplace supports **EzyLogin CLI login**: instead of asking the user for a password or an access token, you start the sign-in, the browser opens an approval page on ezyplatform.com, the user clicks **Approve**, and you receive your own access token. Then you call the marketplace API directly. This is much faster and safer than driving the website.

The user may not be technical. Talk to them in their language, in simple words, and do the work yourself.

## Rules

- **You do the work.** Run every command, write every file, check every result. Ask the user only for: approving the sign-in in the browser, decisions that cost or commit them (becoming a seller, the price, publishing under their name, removing a skill), and facts only they know.
- **Never ask for the password or a token**, never print, log or paste the access token, never put it in a URL, a file of the skill, or a commit. The script stores it in `~/.ezyplatform/publish-skill.json` (owner-only).
- **Never publish what you have not read.** Read every file that goes into the zip. Publishing makes it public (paid skills are still visible to the reviewers and buyers).
- **Clean before packing.** Secrets, real passwords, private hosts, personal paths, emails and names of real people or customers must not go to the marketplace. Fix the skill's files (use placeholders like `<password>`, `<host>`), never just force past findings.
- **Never register the user as a seller, set a price, or trash a skill without the user saying yes.**
- Upload is only to the account the user approved. If a request fails, explain it in plain words, do not retry blindly.

## Tools

Requires Python 3.8+ (`python3 --version`; Windows: `py -3 --version`). If Python is missing, install it after telling the user (macOS: `xcode-select --install`; Windows: `winget install -e --id Python.Python.3.12`; Linux: the package manager), or call the API with `curl` / PowerShell following `references/api.md`.

```
python3 -I ${CLAUDE_SKILL_DIR}/scripts/ezyskill.py [--market-url URL] <command> [options]
```

| Command | What it does |
|---|---|
| `check` | marketplace reachable, saved sign-in still valid; ends with `READY` or `NEED login` |
| `login [--no-browser] [--timeout 600]` | EzyLogin CLI login: prints `OPEN_URL`, opens the browser, waits for **Approve**, saves the token |
| `logout` | forget the saved token |
| `scan <dir>` | files that will be packed + findings (secrets, personal data, structure); exit 1 when there are findings |
| `pack <dir> --out <zip> [--force]` | scan, then write a clean zip (`<name>/...`); refuses while findings remain |
| `categories [--keyword K]` | existing skill categories |
| `currency` | the default currency of prices (prices are in this currency) |
| `list [--keyword K] [--status S]` | the user's skills: id, status, category, title |
| `show <id>` | details, price, package, pending update, public and manage links |
| `projects [--keyword K]` | the user's plugins/themes on the marketplace (id, name, released version) |
| `register-seller` | register the account as a skill seller (only after the user agrees) |
| `add --zip Z --title T --description D --category C [--price P --original-price O] [--project-id ID]` | add a new skill, sent to review |
| `update <id> [--zip Z] [--title] [--description] [--category] [--price P --original-price O / --free]` | change a skill; everything not passed is kept (title, description, category, price) |
| `cancel-update <id>` | cancel an update of a published skill that is still waiting for review |
| `trash <id>` | move the skill to trash (removes it from the marketplace) |
| `open [--path /p]` | open a marketplace page in the browser (default: the user's skill library) |

Exit code `0` = done, `3` = `NEED <code>: <what to do>`, `1` = error with the reason. `--market-url` (or `EZY_MARKET_URL`) is only for testing another EzyPlatform site; the default is `https://ezyplatform.com`.

## Steps

### 1. Sign in

Run `check`. On `NEED login`:

1. Tell the user: "A page of ezyplatform.com will open. Sign in (or create a free account) if asked, check that the tool name is **AI skill publisher**, then click **Approve**."
2. Run `login`. It waits up to 10 minutes: run it in the background or with a long timeout, and keep watching its output.
3. If `BROWSER_OPENED=no` (remote machine, sandbox, no desktop), give the user the `OPEN_URL` and tell them to open it in a browser **on the same computer** where you run, because the approval sends the result to `127.0.0.1`. If the user can only use another device, the CLI login cannot work: ask them to run the AI tool on their own computer.
4. `RESULT_LOGIN=ok` means signed in. Run `check` again: it must print `READY`.

The token lasts as long as the marketplace allows; when any command prints `NEED login`, sign in again the same way.

### 2. Find and read the skill

- The skill is a folder with `SKILL.md` (frontmatter `name` and `description`, then the instructions). A bundle of several skills is a folder whose direct sub-folders each have a `SKILL.md`; then add a `README.md` at the root, it becomes the text shown on the marketplace.
- If the user has no skill yet but describes what it should do, write it with them first (a clear `description` that says when to use it, short steps, scripts in `scripts/`, long details in `references/`).
- Read every file. `SKILL.md` at the root is shown as the skill content and must be at most 30,000 characters.

### 3. Scan and clean

```
python3 -I ${CLAUDE_SKILL_DIR}/scripts/ezyskill.py scan <skill folder>
```

The scan lists the files that will be packed (it skips `.git`, `node_modules`, `target`, `build`, `__pycache__`, `.DS_Store`, `*.pyc`, `*.class`...) and reports sensitive files (`.env`, keys, certificates, databases, logs), keys and tokens, real password assignments, credentials in URLs, home folder paths, real emails and the user's git email, and structure problems (missing frontmatter, too long, more than 100 files, symlinks). Values are partly masked.

Also look yourself for what a machine cannot catch: test accounts and passwords, internal host names, IPs, ports and database names, real customer or company names, names of people, private URLs. Edit the skill's files to remove or replace them, then scan again until it prints `findings: none`. Use `pack --force` only when every remaining finding is clearly a false positive (for example `user@example.com` style samples the regex still caught), and tell the user which ones and why.

### 4. Pack

```
python3 -I ${CLAUDE_SKILL_DIR}/scripts/ezyskill.py pack <skill folder> --out <temp folder>/<name>.zip
```

Write the zip in a temporary folder, never inside the skill folder or a git repo. Limits: zip 2 MB, 5 MB extracted, 100 files, paths up to 255 characters.

### 5. Seller account

Only sellers can add skills. Try the upload (step 7); when it answers `NEED seller`, explain to the user in one message: selling skills on EzyPlatform means their skills are reviewed before publishing, they appear under their account name, and they earn a commission on each sale (the rate and rules are on https://ezyplatform.com/account/seller-registration and in the terms of service https://ezyplatform.com/terms-of-service). Ask whether to register. On yes, run `register-seller` (`RESULT_SELLER=registered` or `already`), then retry the upload. On `NEED seller_registration_closed` or `NEED seller_removed`, tell the user to contact https://ezyplatform.com/contact-us and stop.

### 6. Title, description, category, price

Propose all four to the user in one short message and let them change anything:

- **Title**: short, Title Case, in English unless the user wants another language, unique on the whole marketplace (for example `Compose Email`, `Reset Admin Password`), at most 300 characters.
- **Description**: 1-2 plain sentences saying what the skill does and when to use it, taken from the `description` of `SKILL.md`.
- **Category**: run `categories` and reuse a matching one with its exact spelling. If none fits, propose a short new English name (for example `Email`, `Database`, `DevOps`, `Security`, `Content`, `Marketing`): the marketplace creates it automatically.
- **Price**: free by default. For a paid skill, run `currency` and give the price in that currency (`--price 9.99`). `--original-price` is the crossed-out price before a discount and must be greater than or equal to `--price`.
- **Project** (optional): if the skill belongs to one of the user's released plugins/themes on the marketplace, `projects` gives its id; pass `--project-id` so the skill shows on that project and its team can manage it.

### 7. Upload

Check that the skill is not already there: `list --keyword "<word of the title>"`.

- New skill:
  ```
  python3 -I ${CLAUDE_SKILL_DIR}/scripts/ezyskill.py add --zip <zip> --title "<title>" --description "<description>" --category "<category>" [--price P] [--original-price O] [--project-id ID]
  ```
  On `NEED title_duplicated`: if `list` shows it is the user's own skill, update it instead; otherwise choose another title with the user.
- Existing skill: `update <id> --zip <zip>` (add `--title`, `--description`, `--category`, `--price`/`--original-price` or `--free` only for what changes).

The new skill starts with status `REQUEST_APPROVAL`: the marketplace team reviews it, then it becomes `PUBLISHED` (public) or `REJECTED`. For a published skill, a new package or content goes to review as a pending update (`REVIEW_REQUIRED=yes`) while the published version stays online; title, description, category and price changes apply at once.

### 8. Report

Tell the user, in simple words: the title, the status and what happens next (review), the price, the category (new or existing), the list of files that were published, what the scan found and what you changed, and the links: `MANAGE_URL` (their skill library, where they can also edit everything by hand) and `PUBLIC_URL` once published. Delete the temporary zip unless the user wants to keep it.

Later, `list` or `show <id>` tells whether the review is done.

## Other requests

- **Change price / make it free**: `update <id> --price P` or `update <id> --free` (confirm with the user first).
- **Cancel an update waiting for review**: `cancel-update <id>`.
- **Remove a skill**: confirm with the user, then `trash <id>`.
- **See it in the browser**: `open` (skill library) or `open --path /ezyai/skill-library/<slug>`.
- **Sign out this tool**: `logout`; the user can also sign out the session from the list of signed-in devices of their ezyplatform.com account.

## Errors

| Message | Meaning and what to do |
|---|---|
| `NEED login` | not signed in or the session expired: step 1 |
| `NEED cli_login_disabled` | the marketplace has turned off signing in from tools: tell the user, they can still publish by hand at https://ezyplatform.com/account/ai-skill-library (offer to pack the zip for them) |
| `NEED seller` | not a seller yet: step 5 |
| `NEED title_duplicated` | step 7 |
| `NEED skill_not_found` | wrong id or not the user's skill: `list` |
| `NEED project_not_released` / `project_not_found` | the project must exist, belong to the user and have a released version; upload without `--project-id` or fix the id |
| `the server refused the package: file=...` | the message says which limit failed; fix the skill and pack again |
| `HTTP 400 {"currencyId": ...}`, `{"price": "invalid"}`, `{"originalPrice": "invalid"}` | price values are wrong: positive numbers, original price not lower than price |

The API is described in `references/api.md`.
