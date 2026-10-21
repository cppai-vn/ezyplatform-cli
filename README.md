# ezyplatform-cli

`ezy` — manage an [EzyPlatform](https://ezyplatform.com) / EzyArticle site from a local project folder: create the project, pull content, publish with backup and rollback, manage media, translations and mail, verify the live site.

It packages the scripts of the [`ezyplatform` agent plugin](https://github.com/cppai-vn/agents-plugins/tree/main/ezyplatform) as one command, so people (and agents without plugin support) can use them without installing a plugin. Pure Python standard library, Python 3.9+.

[Tiếng Việt ↓](#tiếng-việt)

## Install

One line, nothing else needed — the installer sets up [uv](https://docs.astral.sh/uv) and, when the machine has no Python 3.9+, Python itself.

**macOS / Linux**

```bash
curl -LsSf https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.sh | sh
```

**Windows** (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.ps1 | iex"
```

Open a new terminal afterwards, then `ezy --version`. Upgrade: `ezy update` (from 0.1.2; older versions: run the install line again). Uninstall: `ezy uninstall` (from 0.1.3; older versions: `uv tool uninstall ezyplatform-cli`). Site projects are kept.

Already use uv or pipx? `uv tool install ezyplatform-cli` / `pipx install ezyplatform-cli` (once published on PyPI), or `uv tool install git+https://github.com/itsddvn/ezyplatform-cli` for the latest `main`.

## Quick start

```bash
ezy init my-site --admin-url https://admin.example.com
cd my-site
# open https://admin.example.com/admins/me, reveal "Access Token" and paste it into
# environment.json -> the "default": true entry -> "admin_access_token"
ezy check                       # validates the token, shows your roles and site URL
ezy pull-all --langs en,vi      # dry run; add --write to write files
ezy status                      # local vs server
ezy publish plan page:home      # what would change
ezy publish apply page:home --yes   # backup -> publish -> verify, prints the rollback command
```

## Commands

| Command | What it does | Skill |
|---|---|---|
| `ezy init [dir] [--admin-url URL] [--copy-skills]` | Create a project (`environment.json`, `AGENTS.md`, `pages/`, `.gitignore` …). `ezy new` is the same | ezy-init |
| `ezy token [admin_url]` | How to get the admin access token | ezy-init |
| `ezy check [dir]` | Validate `environment.json` and the connection | ezy-init |
| `ezy update` · `ezy uninstall` | Install the latest ezy release from GitHub · remove ezy (asks first, site projects are kept) | — |
| `ezy whoami` · `ezy get <api-path>` | Token owner's roles · redacted GET of an admin API path | ezy-shared |
| `ezy sync status\|pull\|pull-all\|discover-pages` | Compare and pull pages/fragments, incl. translations. Shortcuts: `ezy status`, `ezy pull`, `ezy pull-all` | ezy-sync |
| `ezy publish plan\|apply\|restore\|remove` | Dry-run plan → backup → publish per language → verify; rollback; move to Trash | ezy-publish |
| `ezy media status\|upload\|public\|unpublic\|url` | Media library files and visibility | ezy-media |
| `ezy i18n diff\|push <web\|admin>` | UI message translations, changed keys only | ezy-i18n |
| `ezy mail status\|templates\|pull\|push\|contact-settings\|test-contact` | EzyMail health, templates, Contact Us flow | ezy-mail |
| `ezy verify preview <slug>` · `ezy verify live [path]` | Local preview with fragments inlined · live page checks | ezy-verify |

`ezy <command> --help` shows every option. Targets are `page:<slug>` or `fragment:<page_name>/<fragment_name>`. Set `EZY_ENV=<name>` to use a non-default environment from `environment.json`.

Authoring (`ezy-author`) and routing (`ezy-guide`) are agent instructions, not commands: `ezy init --copy-skills` copies all skills into `.claude/skills/` so any coding agent can use them together with `ezy`.

## Safety

- Every write to the site (publish, restore, remove, media, i18n push, mail) is a dry run unless you pass `--yes`.
- Publishing only updates existing posts and stores a backup in `.artifacts/backups/` first.
- The admin token stays in `environment.json` (git-ignored, `chmod 600`) and is never printed.

## Maintainers

The skills in `src/ezyplatform_cli/skills/` are a copy of the plugin's `skills/` folder. To update them:

```bash
python3 scripts/vendor_skills.py ../cppai/agents-plugins/ezyplatform   # path to the plugin folder
python3 -m unittest discover -s tests
```

The script also rewrites the command hints the scripts print (`python3 ezy_publish.py restore …` → `ezy publish restore …`) and records the plugin version in `skills/VENDORED.json` (shown by `ezy --version`).

Release: bump `__version__` in `src/ezyplatform_cli/__init__.py`, commit, then `git tag vX.Y.Z && git push --tags`. The Release workflow builds and creates the GitHub release with the wheel (re-running it refreshes the files). PyPI publishing is off until the repository variable `PYPI_PUBLISH` is `true`: first add a trusted publisher on pypi.org (project `ezyplatform-cli`, workflow `release.yml`, environment `pypi`), then `gh variable set PYPI_PUBLISH --body true`.

## License

MIT — see [LICENSE](LICENSE). Bundled starter templates come from the EzyArticle VS Code extension by YoungMonkeys (MIT); see `src/ezyplatform_cli/skills/ezy-init/templates/NOTICE.md`.

---

## Tiếng Việt

`ezy` là công cụ dòng lệnh quản trị site EzyPlatform / EzyArticle từ thư mục dự án trên máy: khởi tạo dự án, kéo nội dung, publish có sao lưu và khôi phục, quản lý media, bản dịch, mail và kiểm tra site thật. Đây là bản đóng gói các script của plugin `ezyplatform` thành một lệnh duy nhất, không cần cài plugin cho agent.

**Cài đặt** (một dòng, không cần cài gì trước — script tự cài uv và Python nếu máy chưa có):

```bash
# macOS / Linux
curl -LsSf https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.sh | sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.ps1 | iex"
```

Cài xong mở terminal mới rồi gõ `ezy --version`. Cập nhật: `ezy update` (từ bản 0.1.2; bản cũ hơn thì chạy lại lệnh cài). Gỡ: `ezy uninstall` (từ bản 0.1.3; bản cũ hơn: `uv tool uninstall ezyplatform-cli`). Thư mục dự án site vẫn được giữ.

**Bắt đầu:**

1. `ezy init my-site --admin-url https://admin.example.com` rồi `cd my-site`.
2. Vào `https://admin.example.com/admins/me`, bấm hiện **Access Token** (nhập mật khẩu), tự dán vào `environment.json` → mục `"default": true` → `admin_access_token`. Không gửi token cho ai.
3. `ezy check` để kiểm tra kết nối.
4. `ezy pull-all --langs vi,en --write` để kéo nội dung về, sửa file, rồi `ezy publish plan page:<slug>` xem trước và `ezy publish apply page:<slug> --yes` để publish (có sao lưu, in sẵn lệnh khôi phục).

Mọi lệnh ghi lên site chỉ chạy thử nếu không có `--yes`. Xem tất cả lệnh: `ezy --help`.
