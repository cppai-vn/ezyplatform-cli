# HTTP APIs used by this skill

Use these directly (curl, PowerShell `Invoke-RestMethod`) only when `scripts/ezyadmin.py` cannot run. `<admin>` is the admin address, `<token>` the admin access token. Never print the token.

## EzyLogin CLI login (admin side, EzyLogin 0.4.1+)

| Step | Request |
|---|---|
| Probe (no token) | `POST <admin>/ezylogin/api/v1/cli/me/token` body `{}` → `404` EzyLogin missing/inactive, `403 {"cliLogin":"notAllowed"}` admin CLI login disabled, `400` enabled |
| Approval page | open `<admin>/ezylogin/cli/authorize?client_name=<name>&redirect_uri=http://127.0.0.1:<port>/callback&state=<random>&code_challenge=<BASE64URL(SHA256(verifier)) without =>&code_challenge_method=S256` in the browser while a local HTTP server listens on `127.0.0.1:<port>` |
| Callback | the browser calls `http://127.0.0.1:<port>/callback?code=<code>&state=<state>`; compare `state`; the code is valid 2 minutes, once |
| Exchange | `POST <admin>/ezylogin/api/v1/cli/me/token` `{"code":"...","codeVerifier":"...","redirectUri":"http://127.0.0.1:<port>/callback"}` → `{"accessToken","accessTokenExpiredAt","accessTokenStatus"}` |

`code_verifier`: 43-128 chars of `A-Z a-z 0-9 - . _ ~`. The setting is **EzyLogin → Regular settings → Allow admins to sign in from the command line (CLI)** (`/ezylogin/settings/regular`, setting `ezylogin_allow_admin_cli_login`).

Then send `Authorization: Bearer <token>` with every request. `401` = token expired or signed out: log in again.

## Account

| Request | Result |
|---|---|
| `GET /api/v1/admins/me` | the signed-in admin (`401` when the token is invalid) |

## Plugins (permission "plugin management")

| Request | Result |
|---|---|
| `GET /api/v1/projects/<name>` | `{name, displayName, version}`; `404` not installed |
| `GET /api/v1/projects/<name>/module-types?active=true` | active module types, e.g. `["admin-plugin","web-plugin"]` |
| `GET /api/v1/projects/version-status` | `[{projectName, version, status: INSTALLED/INSTALLING}]` |
| `POST /api/v1/projects/<name>/<version>/install?marketUrl=https://ezyplatform.com` | downloads and installs (waits until done) |
| `POST /api/v1/projects/<name>/activate` `{"moduleTypes":["admin-plugin","web-plugin"],"restart":true}` | activates and restarts admin/web |
| `GET https://ezyplatform.com/api/v1/released-projects/<name>` (public) | `latestVersion.name`, `includeModuleTypes`, `price` |

## EzySupport admin code (EzySupport 0.6.2+, permission "support settings")

| Request | Result |
|---|---|
| `GET /ezysupport/api/v1/settings/admin-additional-codes` | `{"additionalHead": "...", "additionalFoot": "..."}` (`null` when empty) |
| `PUT /ezysupport/api/v1/settings/admin-additional-codes` `{"additionalHead":"...","additionalFoot":"..."}` | `204`; a blank value removes that part; each value ≤ 1,000,000 chars (`400 {"additionalHead":"overLength"}`) |

The PUT replaces both parts: always send both, and GET first to back up. Older EzySupport versions (before 0.6.2) answer `404`: upgrade EzySupport.

## Local EzyPlatform (files on this computer)

From the EzyPlatform folder (it contains `cli.sh` / `cli.bat`, `admin/`, `web/`, `settings/`), with Java 8 on `PATH`:

```
sh cli.sh "install ezylogin"            # cli.bat "install ezylogin" on Windows
sh cli.sh "activate admin-plugin ezylogin"
sh cli.sh "activate web-plugin ezylogin"
sh cli.sh "update-modules ezysupport"    # then: sh cli.sh run-update
sh cli.sh "restart admin"                # and "restart web"
```

The admin port is `server.port` in `admin/settings/config.properties` (default 9090). Logs: `logs/admin-server.log`.
