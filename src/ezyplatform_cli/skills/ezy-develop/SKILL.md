---
name: ezy-develop
description: Build an EzyPlatform theme or plugin (website pages, APIs, admin screens, realtime socket) for a non-technical user, end to end - checks that EzyPlatform is installed (installs it with the ezyplatform-install skill if not), installs JDK 8, Maven, the EzyPlatform SDK and its development libraries, sets the environment variables, creates the project with the SDK, finds the plugins that fit the business on the ezyplatform.com market (API), installs and links them, syncs their versions (ezy sdv), reuses their tables and classes (decompiles jars when needed), builds, exports, activates and restarts so the user can see the result. Use when the user asks to build / code / lập trình / làm website, theme, plugin, module, feature, admin page or API on EzyPlatform, to add a market plugin to their project, or when an EzyPlatform project does not build, link or show up.
---

# Develop EzyPlatform themes and plugins for a vibe coder

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md).

The user is usually a "vibe coder": they describe what they want in plain words and do not know Java, Maven, ports, JDBC or EzyPlatform internals. You do every technical step yourself, ask only business questions and confirmations, and explain results in simple words in the user's language.

The skill ships:

| File | Use |
|---|---|
| `${CLAUDE_SKILL_DIR}/scripts/ezydev.sh` | macOS, Linux, WSL: `bash ${CLAUDE_SKILL_DIR}/scripts/ezydev.sh <command> [args] [options]` |
| `${CLAUDE_SKILL_DIR}/scripts/ezydev.ps1` | Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_SKILL_DIR}\scripts\ezydev.ps1" <command> [args] [options]` |
| `${CLAUDE_SKILL_DIR}/references/plugins.md` | business need → plugin, tables to reuse, core tables and services |

Below, `ezydev <command>` means the right one of these two. Bash options are `--dir`, `--home`, `--modules`...; PowerShell options are `-Dir`, `-EzyHome`, `-Modules`... (PascalCase; link types are `-m` in bash and `-Types` in PowerShell). Run `ezydev help` for all of them. On Windows, pass a command line to `run` as one quoted string: `ezydev run "mvn -v"`.

Commands: `check`, `setup`, `env` (bash), `run`, `create`, `link`, `sync-versions`, `export`, `market search|info|docs|doc`, `install-plugin`, `activate`, `restart`, `status`, `tables`, `find-class`, `decompile`. Every command prints `RESULT_*` lines on success. Exit code `3` prints `NEED <code>: ...` (see "When a command prints NEED"), `1` is an error with the reason and a log path.

## Rules

- Ask the user only about the business (what the site or feature does, who uses it, what they see), choices with a cost (paid plugin, replacing their active theme, deleting data) and confirmations. Never ask them to edit files, run commands, pick ports or read stack traces.
- Development needs a **native** EzyPlatform (files on disk). A Docker-only install cannot be used for development: install a native one next to it (see step 1).
- Never print secrets: `settings/setup.properties`, `settings/encryption-keys.txt`, `.ezy/*` of the install, `.env`, and `target/classes/setup.properties` of a built project (the test profile copies it there). Never commit them.
- Never edit files of installed plugins or of the platform (`$EZYPLATFORM_HOME/*/plugins/*`, `*/themes/*`, `lib/*.jar`). Extend them from the project (subclass, override hooks, own templates). Installed module files are treated as immutable; changes are lost on upgrade or flagged as tampering.
- Reuse before creating: plugin features, then core tables, then plugin tables, then new tables (step 5).
- Long steps (setup 5-15 min the first time, export 1-5 min, restart 1-3 min): run them with a long timeout or in the background, tell the user what is happening ("đang tải bộ công cụ lập trình, khoảng 5 phút").
- Installing or activating plugins and replacing the active theme changes the user's local site. Say what you are going to install (names, free/paid) before doing it. A paid plugin always needs the user's explicit "yes".
- The global `ezy.sh`/`ezy.bat`, `mvn`, `java` the user may have can be other versions. Always go through `ezydev` (it sets JDK 8, Maven, SDK, `EZYPLATFORM_HOME`), or `ezydev run <command>` for anything else (`ezydev run mvn -q -pl my-shop-admin-plugin test`).

## Steps

### 1. Check the machine

Find the OS from your environment (`uname -s`: `Darwin`/`Linux`; Windows: `$env:OS` is `Windows_NT` or the shell is PowerShell/cmd/Git Bash; on Windows always use the PowerShell script, inside WSL the bash one). Then:

```
ezydev check
```

It prints `ezyplatform_home`, `install_dir`/`install_mode`, admin/web URLs and HTTP codes, `jdk8`, `maven`, `sdk` and `sdk_latest`, `dev_libs`, `platform_sdk_sources`, `env_file`/`user_env`.

- `ezyplatform_home=missing`: EzyPlatform is not installed (or not where expected).
  - If the user has one somewhere else, find its folder (it contains `cli.sh`/`cli.bat`, `admin/`, `web/`, `settings/`) and pass `--home <folder>` / `-EzyHome <folder>` to every command (or set `EZYPLATFORM_HOME`).
  - Otherwise install it with the skill **ezyplatform-install**. If that skill is not available to you, download it into a new empty temporary folder from `https://ezyplatform.com/api/v1/skill-library/skills/1627/download` (a zip with `SKILL.md` and `scripts/`), unzip it, read its `SKILL.md` and follow it with **native** mode (do not offer Docker for development). Then run `check` again.
- `install_mode=docker`: tell the user that programming needs EzyPlatform installed directly on the computer, and install a native one with ezyplatform-install `--dir ~/ezyplatform-dev-site` (Windows `-Dir C:\ezyplatform-dev-site`). It picks free ports, so it can run next to the Docker one (or stop the Docker one first if the user prefers). Then pass `--dir <that folder>` / `-Dir <that folder>` to every `ezydev` command.
- admin/web HTTP `000`: EzyPlatform is stopped. `ezydev restart` starts it (and its private MySQL when it was installed by ezyplatform-install).

### 2. Set up the development tools (once per machine)

When `jdk8`, `maven`, `sdk`, `dev_libs` or `platform_sdk_sources` is missing:

```
ezydev setup
```

It installs only what is missing, inside the dev folder (`<install dir>/dev`, or `~/ezyplatform-dev` / `%USERPROFILE%\ezyplatform-dev`):
- JDK 8: reuses the one of the EzyPlatform install or an existing JDK 8, else downloads Azul Zulu 8 (checksum verified).
- Maven 3.9 (latest, sha512 verified), unless a working `mvn` exists.
- EzyPlatform SDK (latest from `https://ezyplatform.com/api/v1/platform-sdks`, sha256 verified), unless `EZYPLATFORM_SDK` points to one.
- The development libraries the generated projects need and that are **not** on Maven Central: it downloads the public repository `youngmonkeys/ezyplatform-development` and runs `mvn install` for `ezyplatform-devtools`, `ezyplatform-parent` and `ezyplatform-sdk` (`ezyplatform-test-sdk` included) into `~/.m2`. The sources are kept in `<dev>/ezyplatform-development/ezyplatform-sdk`: read them to learn the core services (`SettingService`, `DataMappingService`, `UserService`, pagination, `Reactive`...) without decompiling.
- Environment variables for the user's own terminals and IDE: `EZYPLATFORM_HOME`, `EZYPLATFORM_SDK`, `PATH` (+ SDK `bin`, Maven `bin`); `JAVA_HOME` only when the user has none. macOS/Linux: a file `<dev>/ezy-dev-env.sh` sourced from `~/.zshrc`/`~/.bashrc`/`~/.bash_profile`/`~/.profile` in a `# >>> ezyplatform dev >>>` block. Windows: user environment variables. Use `--no-profile` / `-SkipProfile` when the user does not want that.

When `sdk_version` is older than `sdk_latest`, update it: `ezydev run ezy.sh update` (Windows `ezydev run "ezy.bat update"`).

### 3. Understand the business and choose plugins

1. Ask the user, in one message, what they want to build: what the site or feature is for, who uses it (visitors, members, admins), the main things people do (browse, buy, book, post, chat...), and whether they want a new look (own theme) or only new functions on their current site. Use their answer; do not ask for technical details.
2. Read `${CLAUDE_SKILL_DIR}/references/plugins.md`, then check the live market:
   ```
   ezydev market search --limit 100          # whole catalog: name | display name | category | price | modules | version | description
   ezydev market search shop                 # keyword search matches names mostly, so prefer reading the whole catalog
   ezydev market info ecommerce              # price, modules, latest version, description
   ezydev market docs ecommerce --lang en    # docs list, then: ezydev market doc ecommerce <slug> --lang en
   ```
3. Pick the smallest set of plugins that covers the business. Prefer free ones. Dependencies are installed automatically (from each plugin's `module.properties` `dependencies=`).
4. If a ready-made theme or solution on the market already does what the user wants, say so: installing it may be all they need (`ezydev install-plugin <name> --activate-theme`), and a new project can still add to it.
5. Tell the user in plain words what you will install and why (one line each, "free"/"paid $x"). For a paid one get an explicit yes; buying happens on ezyplatform.com and the market account must be connected in the EzyPlatform admin.

### 4. Create the project

Decide the modules from the business:
- `theme`: the website pages (Thymeleaf templates, CSS, JS, page controllers). Only one theme is active on a site.
- `web-plugin`: public APIs and logic for the website, works with any theme (a feature added to an existing site is a web-plugin + admin-plugin, no theme).
- `admin-plugin`: admin screens, settings, and the SQL scripts that create the project's tables.
- `socket-plugin` / `socket-app`: realtime (chat, games, live updates). Leave them out unless needed.

```
ezydev create my-shop --group com.mycompany --modules theme,web-plugin,admin-plugin --out <workspace folder>
```

- Name: lowercase letters, digits, `-` (`my-shop`); it becomes the module folder name in EzyPlatform and the admin URL prefix (`/my-shop/...`). Group: a reversed domain of the user's business if they have one, else `com.mycompany`. Folder: where the user keeps projects (their current workspace), no spaces on Windows. With two modules or more the SDK adds a shared `<name>-sdk` module.
- Then read the generated `AGENTS.md` and `SKILL.md` at the project root **before writing code**. They are the coding rules of this project: layout, base controllers to reuse, layers (entity, repository, model, service, converter, request, response, validator, controller service, decorator, view/API controllers), SQL script rules, i18n, checkstyle. This skill does not repeat them.

### 5. Link the plugins, export once, then build

From the project root:

```
ezydev link ezyarticle ecommerce                       # all modules
ezydev link ezylogin -m web-plugin,theme               # only some module types (Windows: -Types web-plugin,theme)
```

`link` does, for each plugin: install it from the market with its dependencies if it is not installed and activate it (not its theme), `ezy.sh link` (versions, `system` dependencies to `$EZYPLATFORM_HOME`, test resources, startup test package scan), adds it to `dependencies=` of the matching `module.properties` (so EzyPlatform loads it first), then `ezy.sh sdv` to sync the versions with the installed jars.

Then export the empty project right away, before writing features:

```
ezydev export
```

`export` runs the project's export steps (`mvn clean install` of each module with the `export` profile, `ezy.sh package`, `ezy.sh export`), copies the modules into `$EZYPLATFORM_HOME`, activates them (the project's theme becomes the active theme, the previous one is deactivated), restarts admin and web, and prints the URLs. This first export registers the project in EzyPlatform: its admin menu appears in the admin, its SQL scripts run, and its `dependencies.xml`, resources and templates are where the startup tests and the linking expect them. Errors seen before it (IDE red marks, missing classes, an unknown menu) usually disappear after it: build again with `ezydev export`.

Open the admin (`RESULT_ADMIN_URL`, then the project's menu entries under `/my-shop/...`) and the website (`RESULT_WEB_URL`) in the user's browser (`open`, `xdg-open`, `Start-Process`) so they see the starting point.

### 6. Design the data and reuse the code

Before writing a feature, look at what exists. Do not invent tables or classes that already exist.

| Question | How |
|---|---|
| Which tables does the platform / a plugin already have? | `ezydev tables core`, `ezydev tables ecommerce` (table → SQL file), then read the SQL file (`scripts_dir`) for columns and indexes |
| Which core services exist? | `<dev>/ezyplatform-development/ezyplatform-sdk` sources (`platform_sdk_sources` of `check`), and the table in `references/plugins.md` |
| Which class does X in a plugin, what can I extend? | `ezydev find-class WebCheckoutController` (prints `jar!path`), then `ezydev decompile org.youngmonkeys.ecommerce.web.controller.view.WebCheckoutController` (prints `RESULT_FILE`, the decompiled Java; the whole jar is in `RESULT_SOURCES`) |
| How does a plugin render a page, which fragments can I reuse? | its templates in `$EZYPLATFORM_HOME/web/plugins/<plugin>/resources/templates`, `.../web/themes/<theme>/resources/templates`, `.../admin/plugins/<plugin>/resources/templates`; its messages in `resources/messages` |
| How is a plugin used? | `ezydev market docs <plugin>` and `ezydev market doc <plugin> <slug>` |

Order of choice for data (details in the project's `SKILL.md`):
1. A plugin feature that already does it (ezyarticle posts with a custom `post_type`, ecommerce products and orders, ezycrm events...). Configure it, extend its base controllers, wrap its templates.
2. Core tables: `ezy_settings`, `ezy_data_meta`, `ezy_unique_data`, `ezy_data_mappings`, `ezy_data_i18n`, `ezy_user_meta`... with `data_type`/`mapping_name` prefixed by the project.
3. Plugin tables through the plugin's services and repositories (inject them; read the decompiled service to know the methods).
4. A new table (`<project>_...`, `CREATE TABLE IF NOT EXISTS`, indexes that match the queries) in `<name>-admin-plugin/src/main/resources/scripts/`, only when nothing above fits. A script runs once per file name; to change a released table add an `alter` file.

Decompiled code is for reading. Do not copy large parts of a plugin into the project: extend or call it.

### 7. Build, deploy and show

After each meaningful change:

```
ezydev export
```

- Build errors: the command prints the `[ERROR]` lines and the log path (`<dev>/logs/export-<project>.log`). Fix the cause and run it again. Checkstyle runs during the build (line length 100, imports, whitespace, empty line after the license header...): fix the reported lines, never disable checkstyle.
- After the restart, check the pages yourself first (`curl -s -o /dev/null -w '%{http_code}' <url>`, logs in `$EZYPLATFORM_HOME/logs/admin-server.log` and `web-server.log`), then open them for the user and explain what to try.
- Only messages, templates or static files changed: `export` is still the simple and safe way.
- `ezydev status` shows what runs and which modules are active. `ezydev restart` restarts admin and web.
- Faster loop for a developer who wants it: the project's `*StartupTest` classes start the theme (web) or admin plugin from the IDE with the current code; they use the same database and the same ports as the installed EzyPlatform, so stop it first and start it again after (`ezydev restart`).

### 8. Later changes

| User says | Do |
|---|---|
| add a feature / change a page | steps 6-7 in the existing project |
| use another market plugin | `ezydev link <plugin>` from the project root, then `ezydev export` |
| update plugins | update them in the admin (Modules), or from `$EZYPLATFORM_HOME` with `ezydev run sh cli.sh "update-modules all"` then `ezydev run sh cli.sh run-update` (Windows `ezydev run "cli.bat \"update-modules all\""`, `ezydev run "cli.bat run-update"`); then in the project `ezydev sync-versions` and `ezydev export` |
| plugin installed but not visible | `ezydev activate <name>` then `ezydev restart` |
| switch the site back to another theme | `ezydev activate <theme>` (deactivates the others) then `ezydev restart`; confirm first |
| give the project to someone / publish it | it is a normal Maven project; `ezy.sh package` (run by export) builds the zips in `target`. To publish on the marketplace, use the `ezy-market-submit` skill |

## When a command prints NEED

| Code | What to do |
|---|---|
| `ezyplatform_not_installed` | Step 1: install with ezyplatform-install (native), or pass `--home`. |
| `native_install` | Step 1: install a native EzyPlatform in another folder and pass `--dir`. |
| `jdk8`, `dev_setup` | Run `ezydev setup`. |
| `paid_plugin` | The plugin costs money. Ask the user: buy it on ezyplatform.com and connect the market account in the admin (Modules / Market), then run the command again; or choose a free plugin. |
| `curl`, `unzip` | Install the package with the system package manager after telling the user (`sudo apt-get install -y curl unzip`, `sudo dnf install -y curl unzip`, macOS has both). If `sudo -n true` fails, ask the user to paste that one command in a terminal. |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Could not find artifact org.youngmonkeys:ezyplatform-parent` or `ezyplatform-test-sdk` | Development libraries missing: `ezydev setup`. |
| `project <x> has no dependencies.xml file` (link) | The plugin is not installed: `ezydev link` installs it; for a manual `ezy.sh link` run `ezydev install-plugin <x>` first. |
| `systemPath ... .jar` not found, `package org.youngmonkeys.<plugin> does not exist` | The `<plugin>.version` in the root `pom.xml` does not match the installed jar: `ezydev sync-versions`. If the plugin is missing: `ezydev link <plugin>`. |
| `ezy.sh set-dependencies-version` says unknown command | The SDK command name has a typo in some versions; use `ezy.sh sdv` (or `ezydev sync-versions`). |
| `ezy.sh create` asks "Folder ... existed, do you want to override?" | Never answer yes; `ezydev create` refuses existing folders. Choose another name or folder. |
| Admin menu of the project missing | Not exported or not active: `ezydev export` (or `ezydev activate <project>` + `restart`). Hidden detail pages need a `~` line in `menus.properties`. |
| Website still shows the old theme | The project theme is not active: `ezydev activate <project>` + `restart`. |
| Admin stops at start after an export | Read `$EZYPLATFORM_HOME/logs/admin-server.log`: a bad SQL script (fix it in a **new** file if it was already run), a missing dependency in `module.properties`, a bean error in the project code. Fix, `ezydev export`. |
| Website answers 500 with `NullPointerException` at `java.util.Locale.<init>` / `RequestLocalFetcher.getLocal` | The site has no default web language yet (fresh install) and the theme reads messages per language. `ezydev setup` / `restart` set it for installs made by ezyplatform-install (the language chosen at install). Otherwise set one in the admin: Settings → Web languages, add a language and "set as default". |
| `Address already in use` | A startup test or another program holds the admin/web port: stop it, `ezydev restart`. |
| Windows: path errors | Keep projects in folders without spaces or accented characters. |
| Market unreachable | Proxy or offline: `curl` honours `HTTPS_PROXY`; Maven needs the proxy in `~/.m2/settings.xml`. |

## Report to the user

In their language, simply: what was built (pages, admin screens), which plugins were installed (and why), the admin and website addresses, what to click to try it, the project folder, and that you can continue ("bảo mình thêm tính năng X"). Do not paste logs, passwords or file contents unless asked.
