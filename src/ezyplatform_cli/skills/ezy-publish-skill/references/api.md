# EzyPlatform marketplace API for skills

Base URL: `https://ezyplatform.com`. Every account API needs the header `Authorization: Bearer <access token>` from the EzyLogin CLI login. Send a recognizable `User-Agent` (it is shown in the user's list of signed-in sessions). Errors are JSON objects `{"<field>": "<code>"}` with HTTP 400, 403 or 404; HTTP 401 means the token expired or was signed out.

## Sign in (EzyLogin CLI login, OAuth 2.0 authorization code + PKCE, loopback redirect)

1. Create `code_verifier` (43-128 chars of `A-Z a-z 0-9 - . _ ~`), `code_challenge = BASE64URL(SHA256(code_verifier))` without `=` (43 chars), and a random `state`.
2. Listen on `http://127.0.0.1:<random port>/callback` (`redirect_uri`).
3. Open in the browser: `GET /ezylogin/cli/authorize?client_name=<name>&redirect_uri=<redirect_uri>&state=<state>&code_challenge=<code_challenge>&code_challenge_method=S256`. The user signs in if needed and clicks **Approve**.
4. The browser comes back to `<redirect_uri>?code=<code>&state=<state>`. Check `state`. The code works once, for 2 minutes.
5. `POST /ezylogin/api/v1/cli/token` with JSON `{"code": "...", "codeVerifier": "...", "redirectUri": "..."}` returns `{"accessToken": "...", "accessTokenExpiredAt": <ms>, "accessTokenStatus": "ACTIVATED"}`. Errors: `403 {"cliLogin":"notAllowed"}`, `400 {"code":"invalid"}`, `400 {"owner":"invalid"}`.

There is no refresh token: sign in again when a call returns 401.

## Seller

| Call | Result |
|---|---|
| `POST /api/v1/account/seller-registration` | `204` registered; `400 {"seller":"registered"}` already a seller; `403 {"sellerRegistration":"disabled"}` registration closed; `403 {"seller":"removed"}` selling disabled for this account |

Adding or changing skills without being a seller returns `403 {"user":"notSkillSeller"}`.

## Skills of the signed-in account

| Call | Body | Result |
|---|---|---|
| `GET /api/v1/account/ai-skill-library?keyword=&status=&limit=12&nextPageToken=` | | `{"items": [skill...], ...}` (trashed skills excluded unless `status=TRASH`) |
| `GET /api/v1/account/ai-skill-library/{id}` | | skill |
| `POST /api/v1/account/ai-skill-library/add` | JSON data with `content` (markdown) | `{"createdId": <id>}` |
| `POST /api/v1/account/ai-skill-library/add-package` | multipart: `data` (JSON, `application/json`) + `file` (zip) | `{"createdId": <id>}` |
| `PUT /api/v1/account/ai-skill-library/{id}` | JSON data with `content` | `{"reviewRequired": true/false}` |
| `POST /api/v1/account/ai-skill-library/{id}/package` | multipart `data` + `file` | `{"reviewRequired": true}` |
| `DELETE /api/v1/account/ai-skill-library/{id}/revision` | | `204`, cancels the pending update of a published skill |
| `DELETE /api/v1/account/ai-skill-library/{id}` | | `204`, moves the skill to trash |

Data fields:

| Field | Rule |
|---|---|
| `title` | required, at most 300 characters, unique on the marketplace when adding (`title: duplicated`) |
| `description` | short text shown in lists |
| `categoryName` | at most 256 characters; a missing category is created automatically |
| `content` | markdown, required, at most 30000 characters; with a package it is taken from the package's root `SKILL.md` (or `README.md`, or a generated file list) |
| `currencyId` | `0` = default currency (`GET /api/v1/currencies/default`) |
| `price` | empty = free; must be >= 0 |
| `originalPrice` | optional crossed-out price, needs `price`, must be >= `price` |
| `forEntityType`, `forEntityId` | optional, `"project"` + the id of a released project of the account, only when adding |

**Every save replaces all fields**: a missing `price` removes the price, a missing `description` clears it. Read the skill first and send back what must be kept (the script does this).

Skill fields: `id`, `title`, `slug`, `description`, `content`, `categoryName`, `status` (`REQUEST_APPROVAL`, `PUBLISHED`, `REJECTED`, `DRAFT`, `TRASH`), `skillPackage` (`fileCount`, `scriptFileCount`, `skillCount`, `totalSize`), `prices` (`currencyId`, `price`, `originalPrice`, `formattedPriceIncludeIsoCode`...), `revision` (pending update: `content`, `status`, `skillPackage`), `createdAt`, `updatedAt`, `publishedAt`.

Package rules: zip, at most 2 MB and 5 MB extracted, at most 100 files, paths at most 255 characters without `..`, `\`, `:` or a leading `/`; `__MACOSX`, `.DS_Store` and `._*` are ignored; one common root folder is stripped. Errors are `400 {"file": "<code>"}`: `required`, `skillPackageTooLarge`, `tooMany`, `skillPackageEmpty`, `skillPackageInvalidPath`, `skillPackageDuplicatedPath`, `skillPackageMainFileEmpty`, `skillPackageMainFileOverLength`, `invalid`.

## Public data

| Call | Result |
|---|---|
| `GET /api/v1/skill-library/categories?keyword=&limit=100` | `{"items": [{"id", "name", "originalName", "slug"}...]}` |
| `GET /api/v1/skill-library/skills?keyword=&categoryId=&limit=` | published skills |
| `GET /api/v1/currencies/default` | default currency (`id`, `isoCode`...) |
| `GET /api/v1/account/projects?keyword=&limit=` (token) | the account's plugins/themes: `id`, `name`, `displayName`, `latestVersion` |

## Pages

- Skill library of the account: `/account/ai-skill-library`
- Seller registration: `/account/seller-registration`
- Published skill: `/ezyai/skill-library/<slug>`
