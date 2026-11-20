---
name: ezy-admin-customize
description: Change how the EzyPlatform admin looks and behaves for a non-technical user (colors, fonts, logo, layout, sidebar position, dark look, extra buttons, or a whole new experience such as turning the admin into a desktop with windows, a taskbar and a start menu) by writing a head fragment (CSS, fonts, meta) and a foot fragment (JavaScript) and saving them through the EzySupport API, then opening the admin in the browser to show the result. Checks the admin is reachable, signs in through EzyLogin CLI login (installs or enables EzyLogin when needed), checks that EzySupport is installed and up to date (installs or upgrades it), backs up the current code before every save, and can roll back. Use when the user asks to customize / restyle / redesign / đổi giao diện / tuỳ biến giao diện trang quản trị (admin) of EzyPlatform, add custom CSS or JS to the admin, make the admin look like a desktop app, or undo such a change.
---

# Customize the EzyPlatform admin look

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md).

The user is usually a "vibe coder": they say what they want in plain words ("make the admin purple", "sidebar on the right", "make it look like Windows") and do not know CSS, APIs or EzyPlatform internals. Talk to them in their language, in simple words.

How it works: EzySupport (an EzyPlatform plugin) adds two pieces of HTML to every admin page of a signed-in admin: the **head** fragment (end of `<head>`) and the **foot** fragment (end of `<body>`, after jQuery and `ezyadmin.js`). You write these two fragments as local files, save them with the EzySupport API, and the new look appears on the next page load. Nothing in the platform or plugins is modified, and the default look comes back with one command.

## Rules

- **You do the work.** Run every command, write every file, check every result yourself. When something cannot be done by you (missing permission, no access to the server, a step that only works in the admin UI), do it through the browser yourself if you have browser tools (Playwright, Claude in Chrome, computer use, a built-in browser). Only when that is impossible too, give the user short numbered steps with the exact address to open, the menu, the field and the button names (in the user's admin language), wait until they say it is done, then check again with `check`.
- Ask the user only about what they want to see, choices with a cost (installing plugins, restarting the admin, replacing their current custom code) and approvals in the browser. Never ask them to edit files, run commands or read logs.
- Never print, log or paste the access token. It is stored by the script in `~/.ezyplatform/admin-customize.json` (owner-only file). Never put it in a URL, a page or a commit.
- Always back up before saving (`push`, `restore` and `reset` do it automatically) and keep the user's existing custom code unless they want it replaced: `pull` first and build on it.
- The custom code runs in every admin page for every admin. Keep it safe: no external scripts from unknown sources, no tracking, no secrets, no code that sends data elsewhere. Fonts and libraries only from well-known CDNs (Google Fonts, cdnjs, jsDelivr, unpkg) with exact versions.
- Restarting the admin or installing plugins interrupts other admins for 1-3 minutes: say so before doing it.

## Tools

Requires Python 3.8+ (`python3 --version`; on Windows `py -3 --version` or `python --version`). If Python is missing, install it (macOS: it ships with the Command Line Tools, `xcode-select --install`; Windows: `winget install -e --id Python.Python.3.12`; Linux: the package manager) after telling the user, or follow `references/api.md` with `curl` / PowerShell instead.

```
python3 ${CLAUDE_SKILL_DIR}/scripts/ezyadmin.py <command> [--admin-url URL] [options]
```

| Command | What it does |
|---|---|
| `check` | admin reachable, EzyLogin CLI login state, saved token, EzySupport/EzyLogin versions, codes API; ends with `READY` or `NEED <code>` |
| `login` | EzyLogin CLI login: opens the approval page in the browser, waits for **Approve**, saves the admin token |
| `plugin-status [name]` | installed version, active module types, latest market version, `ACTION=install/upgrade/activate/none` |
| `plugin-install [name]` | install or upgrade from the market, activate, restart the admin and wait (`--no-restart`, `--version`) |
| `pull --dir D` | download the current head/foot into `D/head.html`, `D/foot.html` |
| `push --dir D` | back up the current code to `D/.backups/<time>/`, save `D/head.html` + `D/foot.html`, read back and compare |
| `restore --dir D [--backup P]` | save a backup again (the latest one by default) |
| `reset --dir D` | back up, then remove the custom code (default admin look) |
| `verify --path /p` | load admin pages with the token and check they contain the saved code |
| `open --path /p` | open an admin page in the user's default browser |
| `local-install <name> [--update] --home H` | EzyPlatform on this computer only: install/update and activate a plugin with `cli.sh`/`cli.bat` |
| `local-restart --home H [--targets admin web]` | EzyPlatform on this computer only: restart and wait for the admin |
| `logout` | forget the saved token |

Exit code `0` = done, `3` = prints `NEED <code>: <what to do>` (see the table in step 2), `1` = error with the reason. The admin address is remembered after the first `--admin-url`; it is also read from `EZY_ADMIN_URL` or guessed (`http://localhost:9090`, or the port of an EzyPlatform found on this computer).

## Steps

### 1. Find the admin

If the user gave the admin address use it, otherwise run `check` (it tries the local one). If it answers `NEED admin_url`, ask the user for the address of their admin (the page where they sign in to manage the site).

### 2. Run `check` and fix what it asks for, in this order

| NEED | What to do |
|---|---|
| `admin_down` | `local_home` is set (EzyPlatform on this computer): `local-restart --home <local_home>`. Installed by the `ezyplatform-install` skill: its control script `start`. Otherwise tell the user the admin does not answer and ask them to start it or check the address. |
| `ezylogin_missing` | EzyLogin (free plugin) is needed so you can sign in to the admin. Tell the user, then:<br>- `local_home` set: `local-install ezylogin --home <local_home>`, then `local-restart --home <local_home>`.<br>- Otherwise, through the browser (yourself, or guide the user): open `<admin>/modules/add` (menu **Modules → Add new / Market**; on older versions **Market**), search **EzyLogin**, click **Install**, wait until it is installed, then in **Modules** activate EzyLogin for **admin-plugin** and **web-plugin** with **Restart** ticked (or restart the admin from **Servers**). It takes 1-3 minutes. |
| `ezylogin_outdated` | Same as above but **Update** EzyLogin (needs 0.4.1 or newer): `local-install ezylogin --update --home <local_home>` + `local-restart`, or in the admin **Modules** click **Update** next to EzyLogin, then restart. |
| `admin_cli_login_disabled` | Command line sign-in for admins is off. Open `<admin>/ezylogin/settings/regular` (`open --path /ezylogin/settings/regular`; menu **EzyLogin → Regular settings**). Tick **Allow admins to sign in from the command line (CLI)** (Vietnamese admin: **Cho phép quản trị viên đăng nhập từ dòng lệnh (CLI)**), click **Save**. Only a super admin or an admin allowed to change EzyLogin settings can do it. Do it through the browser if you can, else guide the user. |
| `login` | Tell the user: "a browser page will open, sign in to the admin if asked, check that the tool name is *AI admin customization*, then click **Approve**". Run `login` (it waits up to 10 minutes; run it in the background or with a long timeout). If no browser opens (`BROWSER_OPENED=no`, remote machine, sandbox), give the user the `OPEN_URL` line to open on the **same computer** where you run (the approval redirects to `127.0.0.1`). |
| `plugin_permission`, `settings_permission` | The approved admin account cannot manage plugins or EzySupport settings. Ask the user to approve with a super admin account (`logout`, `login`), or to give that account the permissions. |
| `paid_plugin` | Never buy for the user. Explain the price and ask. |

Run `check` again after each fix until it prints `READY`.

### 3. EzySupport installed and up to date

```
python3 ${CLAUDE_SKILL_DIR}/scripts/ezyadmin.py plugin-status ezysupport
```

- `ACTION=install` or `ACTION=upgrade`: tell the user EzySupport (free) will be installed/updated and the admin restarts for 1-3 minutes, then `plugin-install ezysupport`. When the account cannot install plugins, or the install fails, do it in the admin (**Modules → Market → EzySupport → Install/Update**, then activate **admin-plugin** and **web-plugin** with **Restart**) yourself through the browser or by guiding the user. With EzyPlatform on this computer, `local-install ezysupport [--update]` + `local-restart` also works.
- `ACTION=activate`: `plugin-install ezysupport` (it only activates and restarts).
- Then `check` must show `ezysupport_codes_api=available` (EzySupport 0.6.2 or newer). If it still says `missing`, the market has no newer version yet: tell the user that customization needs EzySupport 0.6.2+, and stop.

### 4. Understand what the user wants

Ask in one message, with examples, only if the request is vague: colors (brand color, light/dark), font, logo/title, layout (sidebar left/right, fixed header, compact tables), extra elements (a banner, a clock, shortcuts), or a whole experience ("like a desktop", "like a mobile app"). Ask whether to **build on the current custom code** or **replace it** when `pull` shows existing code.

### 5. Write the fragments

1. Work in a folder of the user's project or workspace, by default `admin-customization/` (it holds `head.html`, `foot.html` and `.backups/`). `pull --dir admin-customization` first.
2. Read `references/admin-layout.md` (page structure, CSS classes, JS available, RTL, mobile, pitfalls) before writing code.
3. `head.html`: `<link>` for fonts/CSS, `<style id="...">` with CSS variables first, then rules. No `<script>` that needs jQuery or `ezyadmin` there (they are not loaded yet).
4. `foot.html`: `<script id="...">(function () { ... })();</script>`. jQuery, Bootstrap 4, AdminLTE 3 and `ezyadmin` are available. Guard every query (`if (!el) return;`), wrap `localStorage` in try/catch, escape text with `ezyadmin.escapeHtml(String(value))`.
5. Give each fragment a first line comment that names it, for example `<!-- admin-customization: purple brand v1 -->`: it shows up in backups and `verify`.
6. Make it work in left-to-right and right-to-left languages (`?lang=ar`), on mobile (≤ 768 px), and keep the page usable if your script fails. For big changes (a new layout or experience) provide a way back (a button that turns the mode off, remembered in `localStorage`).

### 6. Save, check, show

```
python3 ${CLAUDE_SKILL_DIR}/scripts/ezyadmin.py push --dir admin-customization
python3 ${CLAUDE_SKILL_DIR}/scripts/ezyadmin.py verify --path / --path /ezysupport/settings
python3 ${CLAUDE_SKILL_DIR}/scripts/ezyadmin.py open --path /
```

- `push` prints the backup folder: keep it for the report.
- `verify` checks the server really sends the code in the pages.
- Look at the result yourself if you have browser tools: screenshots of the dashboard and one list page, desktop and mobile width, in the admin language and with `?lang=ar` (right-to-left). Check the browser console for errors. Without browser tools, open the page for the user and ask them to look and tell you what they see (or send a screenshot).
- Iterate: edit the files, `push` again, reload the page.

### 7. If something goes wrong

- Admin looks broken or a page is unusable: `restore --dir admin-customization` (previous version) or `reset --dir admin-customization` (default look). Both use the API, which the custom code cannot break.
- Token expired (`NEED login`): run `login` again. The sign-in page of the admin is never changed by the custom code (EzySupport 0.6.1+ adds it only for signed-in admins), but the approval page is a normal admin page: if your code broke it, the user can still click **Approve**; if not even that works, ask the user to clear the fields in **EzySupport → Settings → Admin additional header/footer** and save, or, with database access on a local install, delete the rows `admin_additional_head` and `admin_additional_foot` of the table `ezy_settings`.
- Save fails with `additionalHead: overLength`: each fragment is limited to 1,000,000 characters; move big CSS/JS into files hosted on the site (media library) and reference them.

## Example: turn the admin into a desktop

`${CLAUDE_SKILL_DIR}/examples/desktop/` is a complete, tested customization: wallpaper, every menu as a desktop icon, pages opening in windows you can drag, resize, minimize and maximize, a taskbar with a start menu (Ctrl/Cmd + K to search), open windows kept between pages, a clock, English/Vietnamese texts, right-to-left support, mobile fallback, and an **Exit desktop mode** button.

```
mkdir -p admin-customization
cp ${CLAUDE_SKILL_DIR}/examples/desktop/head.html ${CLAUDE_SKILL_DIR}/examples/desktop/foot.html admin-customization/
python3 ${CLAUDE_SKILL_DIR}/scripts/ezyadmin.py push --dir admin-customization
python3 ${CLAUDE_SKILL_DIR}/scripts/ezyadmin.py open --path /
```

Read it as a model for large changes: CSS variables in head, everything scoped under a body class (`custom-desktop`), the original header/sidebar hidden instead of removed, menus read from the existing sidebar (`.main-sidebar .nav-sidebar`), admin pages loaded in iframes that detect they are embedded (`custom-desktop-embedded`) and hide their own chrome, state in `localStorage` guarded by try/catch, an exit switch. To adapt it (colors, wallpaper, texts, another language), change the CSS variables in `head.html` and the `texts` object at the top of `foot.html`.

## Report to the user

In their language, simply: what changed and where to see it (the admin address), that the previous version is backed up (folder) and can be restored any time ("bảo mình quay lại giao diện cũ"), which plugins were installed or updated, and what you can change next. Do not paste code, tokens or logs unless asked.
