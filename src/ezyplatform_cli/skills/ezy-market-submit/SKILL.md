---
name: ezy-market-submit
description: Submit an EzyPlatform plugin or theme (admin plugin, web plugin, theme, socket plugin... packaged as `<name>-<version>.zip`) to the ezyplatform.com marketplace through its API - log in with EzyLogin CLI login (browser approval, no password in the terminal), create the marketplace project (name, package, category, tags, price, description, icon 512x512, banner 1640x720), upload a version bundle with release notes, follow the review, publish (release) the approved version, upload source code and gallery screenshots. Use when the user asks to "submit/publish/upload my plugin or theme to ezyplatform.com", "put it on the EzyPlatform market", "đưa plugin/theme lên chợ ezyplatform", "tạo project trên chợ", "upload version mới", "release lên chợ", or asks how the marketplace API works.
---

# Submit a plugin or theme to the ezyplatform.com marketplace

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Run commands from the user's project root.

Always talk to the user in their own language. Script (Python 3 standard library only, no install needed):

```
python3 ${CLAUDE_SKILL_DIR}/scripts/ezymarket.py [--base-url https://ezyplatform.com] <command> [options]
```

## 1. Explain permissions BEFORE logging in

The script logs in with **EzyLogin CLI login** (OAuth 2.0 authorization code + PKCE, result sent back to `http://127.0.0.1:<random port>/callback`). Before running `login` for the first time, tell the user in plain words:

- **What happens**: the browser opens `https://ezyplatform.com/ezylogin/cli/authorize`. If they are not logged in, they log in there as usual (including 2FA). The terminal and the AI never see their password or 2FA code.
- **What they grant**: clicking **Approve** gives the tool an access token with **the same rights as their ezyplatform.com account** (create/edit/delete their projects, upload and publish versions, upload media). It is not limited to one project. Only approve if they themselves just ran the login command, the tool name shown is `ezymarket`, and the result address shown on the page is `http://127.0.0.1:<port>/callback` (the port printed in the terminal). If anything differs, click **Cancel**.
- **Where the token lives**: `~/.ezyplatform/credentials.json` (file mode 600, keyed by site URL; shared with other EzyPlatform CLI tools). It expires according to the site's token lifetime; there is no refresh token, the script simply asks to log in again.
- **How to take it back**: `ezymarket.py logout` deletes the local copy. If they think the token leaked, they should log out of all sessions / change the password on ezyplatform.com.

Then ask for their go-ahead and run `ezymarket.py login`. Wait while the user approves in the browser (up to 10 minutes). `whoami` checks whether the saved token still works.

Rules for the AI around the token:

- Never print, echo, log, paste into chat, commit or send the token anywhere except `Authorization: Bearer` requests to the same site. Do not `cat` the credentials file.
- Never ask the user for their password, 2FA code or token. If login fails, run `login --force` again.
- Ask before every write that others will see or that is hard to undo: `create`, `update`, `upload-version`, `release` (makes the version public and downloadable), `cancel`, `delete-newest`, `upload-source`. Reading (`projects`, `get`, `status`, `categories`) needs no confirmation.

### Team permissions (working on someone else's project)

Projects belong to the account that created them. A team member can manage the owner's project only after the **owner** opens `https://ezyplatform.com/account/members`, adds the member (username, phone or email) and gives a role that includes project management. Explain this to the user when:

- a call returns `403 {"permission":"denied"}`: the logged-in account is not the owner and has no member role for that action. Ask the owner to add/upgrade the role, or log in with the owner account (`login --force`, approve with the other account in the browser).
- the project does not appear in `projects`: it belongs to another account that has not added them.

Some actions are owner-only even for members: adding gallery media (`add-gallery`) and media uploads are attached to the uploader's account (`iconImageId`/`bannerImageId` must be media uploaded by the same account that saves the project).

Other refusals to explain: `403 {"cliLogin":"notAllowed"}` (CLI login is turned off on the site: contact the marketplace support), `403 {"projectType":"notAllowed"}` (the marketplace currently does not accept this project type from users).

## 2. Prepare the bundle

- The marketplace needs a ready bundle zip named exactly `<project-url-name>-<version>.zip`, e.g. `my-shop-0.1.0.zip`. `<project-url-name>` is the dash-case name the marketplace derives from the display name (`My Shop` -> `my-shop`); read it from `projects`/`status` after the project exists. Version format: `X.Y.Z`.
- Build it with the project's own packaging (e.g. the `export.sh` / Maven profile from the EzyPlatform project template, output usually in `target/project/`). Do not build it yourself unless the user asks; ask where the zip is.
- Max size is set by the marketplace (around 30 MB by default). The file must really be a zip.
- Plugin vs theme is read from the bundle itself during review; the project form is the same for both.

## 3. Create the marketplace project (first time only)

1. `categories` lists `id<TAB>name`. Pick the best match with the user.
2. Images (PNG or JPEG):
   - icon: ratio 1:1, recommended 512x512 -> `upload-media icon.png --kind icon`
   - banner: ratio 1640:720, recommended 1640x720 -> `upload-media banner.png --kind banner`
   Each prints `{"id": ..., "url": ...}`. If the user has no images, offer to draw simple ones (SVG -> PNG) but let them approve the look.
3. Write `project.json` (keep it in the project, e.g. `marketplace/project.json`):

```json
{
  "projectName": "My Shop",
  "packageName": "com.example.myshop",
  "categoryId": 3,
  "tags": ["shop", "payment"],
  "shortDescription": "Online shop for EzyPlatform",
  "descriptionFile": "description.html",
  "iconImageId": 101,
  "bannerImageId": 102,
  "introYouTubeVideoId": "",
  "price": 0,
  "originalPrice": 0
}
```

   Rules (checked locally first, then by the server; server errors come back as `{"field": "required|tooShort|overLength|invalid|duplicated"}`):
   - `projectName`: 2..60 chars, letters/digits/spaces only, unique on the market. Becomes the display name and, in dash-case, the URL name and the zip prefix.
   - `packageName`: 12..120 chars of `a-z 0-9 _ .`, unique (use the Java base package or a reverse domain).
   - `shortDescription`: 9..40 chars. `description`: 100..6000 chars, HTML allowed, no `<script>` (put it in `descriptionFile`, a file next to the JSON, or inline as `description`).
   - `tags`: optional, each 2..32 chars of `a-z 0-9 - space`.
   - `categoryId`: required.
   - `introYouTubeVideoId`: optional, the video id only (`dQw4w9WgXcQ`), not the URL.
   - `price` / `originalPrice`: `0` for free; otherwise in the marketplace default currency. Confirm the price with the user.
   - Without both `iconImageId` and `bannerImageId` the project stays `SETTING_UP` and no version can be uploaded.
4. Show the final JSON to the user, get approval, then `create --json marketplace/project.json`. The response has `projectId` and the project name.

To edit later: `get --name <url-name> --out marketplace/project.json` (full editable body), change it, then `update --name <url-name> --json marketplace/project.json`. `update` replaces every field, so always start from `get`.

## 4. Upload a version and get it reviewed

1. Release notes: plain text or simple HTML, written for the plugin's users (features, fixes), no `<script>`, max length set by the marketplace (about 3000 chars). Save to e.g. `marketplace/notes-<version>.txt`. Read `git log` since the previous version tag to draft it, then let the user edit.
2. `upload-version --name <url-name> --version 0.1.0 --zip target/project/<url-name>-0.1.0.zip --notes-file marketplace/notes-0.1.0.txt`.
3. The version goes to `REVIEWING`. A marketplace reviewer checks and signs the bundle; this is done by ezyplatform.com staff, not by the author, and can take some time. The author gets a notification/email.
4. `status --name <url-name>` shows the project status and the newest version state:

| Newest version | Meaning | Next step |
|---|---|---|
| `REVIEWING` | waiting for review | wait, or `cancel` to withdraw and fix |
| `REJECTED` | reviewer refused it | open the project page, read the review notes, fix, `upload-version` again with the same version |
| `RELEASABLE` | approved and signed | `release` (after the user confirms) |
| `RELEASED` | public | upload the next version when ready |

Only one unreleased "newest version" exists at a time. While it is `REVIEWING` a new upload is refused (`projectVersion: reviewing`); a released version number cannot be reused (`projectVersion: duplicated`). `delete-newest` removes an unreleased newest version.

## 5. Publish

`release --name <url-name>` publishes the approved newest version. It fails with `bundleSignature: missing` if the review is not approved yet. Then verify:

- `status` shows the project `RELEASED`.
- `https://ezyplatform.com/market/items/<url-name>` shows the new version; the public API `GET /api/v1/released-projects/<url-name>` returns it.

## 6. Optional extras

- Gallery screenshots (owner only, up to 12): `upload-media shot.png` then `add-gallery --name <url-name> --media-id <id>`.
- Source code for a released version (if the marketplace asks for it, e.g. for paid projects): zip named `<url-name>-<version>-sources.zip`, `upload-source --name <url-name> --version <v> --zip ... --notes-file ...`. It is reviewed like a bundle.
- Documentation pages for the project are managed at `https://ezyplatform.com/account/projects/<url-name>/docs`.

## API reference (all under `https://ezyplatform.com`, `Authorization: Bearer <token>`)

| Purpose | Method and path | Body |
|---|---|---|
| CLI login page (browser) | `GET /ezylogin/cli/authorize?client_name&redirect_uri&state&code_challenge&code_challenge_method=S256` | - |
| Exchange code for token | `POST /ezylogin/api/v1/cli/token` (no auth) | `{"code","codeVerifier","redirectUri"}` -> `{"accessToken","accessTokenExpiredAt","accessTokenStatus"}` |
| My projects | `GET /api/v1/account/projects?limit=&keyword=` | - |
| Project id/status | `GET /api/v1/account/projects/{urlName}/simple` | - |
| Project editable data | `GET /api/v1/account/projects/{urlName}` | - |
| Create project | `POST /api/v1/account/projects/create` | project JSON -> `{"projectId","projectName"}` |
| Update project | `PUT /api/v1/account/projects/{id}` | full project JSON |
| Change icon / banner only | `PUT /api/v1/account/projects/{id}/update-icon` / `update-banner` | `{"iconImageId"}` / `{"bannerImageId"}` |
| Delete project (no version yet) | `DELETE /api/v1/account/projects/{id}` | - |
| Upload media | `POST /api/v1/media/add` | multipart `file` -> media with `id`, `name` |
| Upload version | `POST /api/v1/account/projects/{id}/versions/newest/create-or-update` | multipart `projectVersion`, `releaseNotes`, `file` |
| Cancel review | `POST /api/v1/account/projects/{id}/versions/newest/cancel` | - |
| Delete unreleased version | `DELETE /api/v1/account/projects/{id}/versions/newest` | - |
| Publish | `POST /api/v1/account/projects/{id}/versions/newest/release` | - |
| Upload source code | `PUT /api/v1/account/projects/{id}/versions/{version}/source-code` | multipart `notes`, `file` |
| Add / remove gallery media | `PUT` / `DELETE /api/v1/account/projects/{id}/medias/{mediaId}` | - |
| Public project info | `GET /api/v1/released-projects/{urlName}` (no auth) | - |

Errors are JSON maps of `field -> code` with HTTP 400 (validation), 401 (token missing/expired: log in again), 403 (permission or feature switched off, see section 1), 404 (`project: notFound`, wrong name or not yours).

## Report back

Tell the user, in their language: what was created/changed (project URL name and id, version, status), links (`/account/projects/<url-name>`, `/market/items/<url-name>`), what is waiting on the marketplace review, and anything not verified.
