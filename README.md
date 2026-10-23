# ezyplatform-cli

`ezy` — set up [EzyPlatform](https://ezyplatform.com) / EzyArticle projects, install and manage coding-agent plugins and skills, and check your environment and site connection.

Use the [`ezyplatform` agent plugin](https://github.com/cppai-vn/agents-plugins/tree/main/ezyplatform) in your coding agent for content synchronization, publishing, media, translations, mail and previews. Agents without plugin support can receive the full skill set through `ezy skills install`. Pure Python standard library, Python 3.9+.

[Tiếng Việt ↓](#tiếng-việt)

## Install

One line, nothing else needed — the installer sets up [uv](https://docs.astral.sh/uv) and, when the machine has no Python 3.9+, Python itself.

**macOS / Linux**

```bash
curl -LsSf https://raw.githubusercontent.com/cppai-vn/ezyplatform-cli/main/install.sh | sh
```

**Windows** (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/cppai-vn/ezyplatform-cli/main/install.ps1 | iex"
```

Open a new terminal afterwards, then `ezy --version`. Upgrade: `ezy update` (from 0.1.2; older versions: run the install line again). Uninstall: `ezy uninstall` (from 0.1.3; older versions: `uv tool uninstall ezyplatform-cli`). Site projects are kept.

Already use uv or pipx? `uv tool install ezyplatform-cli` / `pipx install ezyplatform-cli` (once published on PyPI), or `uv tool install git+https://github.com/cppai-vn/ezyplatform-cli` for the latest `main`.

## Quick start

```bash
ezy init                        # once per computer: plugin into your coding agents, optional skills, doctor
ezy new my-site --admin-url https://admin.example.com
cd my-site
# open https://admin.example.com/admins/me, reveal "Access Token" and paste it into
# environment.json -> the "default": true entry -> "admin_access_token"
ezy check                       # validates the token, shows your roles and site URL
ezy whoami                      # confirms the selected environment and token owner roles
```

Open the project in your coding agent, start a new session to load the plugin,
then use `ezy-guide` to choose the skill for your site task. For example, ask the
agent to pull the site's content with `ezy-sync`, or prepare a publish with
`ezy-publish`.

## Commands

| Command | What it does | Skill |
|---|---|---|
| `ezy init [--yes] [--target …] [--skills\|--no-skills] [--dry-run]` | Set up this computer: find your coding agents, install the `ezyplatform` plugin into them, offer skill copies for agents without plugins, validate, then run `ezy doctor` | — |
| `ezy plugins status\|install\|update [--target all\|claude,codex,copilot,omp,cursor] [--dry-run]` | The plugin per agent, through each agent's own CLI (Cursor: UI steps) | — |
| `ezy skills status\|install\|verify\|remove [--target opencode] [--dir PATH] [--force]` | Skill copies for agents without plugins; refuses folders where a plugin already loads them | — |
| `ezy doctor` | ezy version, agents, plugin and skill copies, skills loaded twice, the project in this folder | — |
| `ezy new [dir] [--mode live\|local\|both] [--admin-url URL] [--yes] [--no-start] [--copy-skills]` | Create a site project (`environment.json`, `AGENTS.md`, `pages/`, `.gitignore` …). Asks where it runs when `--mode` is omitted — see [Local EzyPlatform](#local-ezyplatform) | ezy-new |
| `ezy token [admin_url]` | How to get the admin access token | ezy-new |
| `ezy check [dir]` | Validate `environment.json` and the connection | ezy-new |
| `ezy update [--cli-only]` · `ezy uninstall` | Latest ezy release, then update the plugin in your agents and ezy's skill copies · remove ezy (asks first, site projects are kept) | — |
| `ezy whoami` | Selected environment, admin URL and token owner's roles (JSON) | ezy-shared |

`ezy <command> --help` shows every option. Set `EZY_ENV=<name>` to use a non-default environment from `environment.json` for connection checks or plugin scripts.

Site operations are handled by the plugin's `ezy-sync`, `ezy-publish`, `ezy-media`,
`ezy-i18n`, `ezy-mail` and `ezy-verify` skills. The previous CLI routes `get`,
`sync`, `status`, `pull`, `pull-all`, `publish`, `media`, `i18n`, `mail` and `verify`
have been removed. Invoking one exits with code 2 and directs you to the matching
skill without running a site operation. Plugin scripts remain included for skill
installation and project skill copies.

`ezy plugins status` and `ezy doctor` show only completed results, one agent at a time, without “Checking…” progress lines. Plugin and marketplace list checks do not prompt for input and time out after 10 seconds per command, including checks during setup, updates and skill-copy validation. A failed or timed-out status check is reported as unknown, and the remaining checks continue. Release lookups use a 10-second network timeout per request (with one fallback). Installation and update operations keep their longer time budgets.

Status checks use a green `✓` for success, a red `✗` for a failed or missing result, and a neutral `?` for manual checks or informational results. This includes doctor, plugins, skills and site connection checks. Colors are disabled in redirected output, with `NO_COLOR=1`, or in a `TERM=dumb` terminal; symbols remain, with ASCII fallbacks when needed. Site API GET requests use a 10-second network timeout per request.

Your coding agent gets the site skills from the plugin (`ezy init`). Give each agent the skills one way only — plugin, a skill copy, or a project's `.claude/skills/` from `ezy new --copy-skills` — or it sees every skill twice; `ezy doctor` reports this.

## Local EzyPlatform

`ezy new my-site --mode local` (or `both`, or pick it when asked) runs EzyPlatform + MySQL for the project with Docker Compose, the same image and settings as [cppai-vn/ezyplatform-docker](https://github.com/cppai-vn/ezyplatform-docker):

1. Checks Docker and Docker Compose. When missing it offers to install them (`--yes` installs without asking): **macOS** OrbStack via Homebrew, **Linux** Docker Engine + Compose from get.docker.com (asks for your sudo password), **Windows** Docker Desktop via winget (start it and accept its terms). A stopped Docker is started.
2. Writes `docker-compose.yml` and a git-ignored `.env` with its own Docker project name (`ezy-<folder>-<random>`, so every new project gets separate containers, volumes and network, even with the same folder name), free local ports (admin from 9090, website from 8080) and random database passwords, then runs `docker compose up -d`. The first run downloads about 1 GB and takes a few minutes; on Apple silicon the amd64 image runs emulated.
3. Waits for the admin and the website, adds a `local` environment to `environment.json` and prints the next steps: open `http://127.0.0.1:9090/setup-admin`, create the first super admin, copy its access token from `/admins/me` into the `local` entry, run `ezy check`.

| Mode | `environment.json` |
|---|---|
| `live` | the live admin only (as before) |
| `local` | only `local` |
| `both` | `local` is the default; select `EZY_ENV=production` explicitly for live connection checks or plugin operations |

In the project folder: `docker compose stop` / `docker compose up -d` / `docker compose logs -f ezyplatform`; `docker compose down -v` deletes the local data.

The compose file fixes two problems of the image on an empty database: its entrypoint writes a `jdbc:mysql://` URL for the bundled MariaDB 3.x driver (every admin page answered 500), fixed with `DB_NAME=blog?permitMysqlScheme`; and the first boot needs longer than the 180 s startup limit. On the very first start the website answers 404 until the app restarts once, which `ezy new` does for you.

## Safety

- CLI connection checks are read-only. Project setup can create local files and start the local Docker stack.
- Site writes are handled by plugin skills, which retain their approval, dry-run and backup workflows.
- The admin token stays in `environment.json` (git-ignored, `chmod 600`) and is never printed.

## Maintainers

The skills in `src/ezyplatform_cli/skills/` are a copy of the plugin's `skills/` folder. Keep the full set: the CLI uses setup scripts and distributes complete skill copies to agents. To update them:

```bash
python3 scripts/vendor_skills.py ../cppai/agents-plugins/ezyplatform   # path to the plugin folder
python3 -m unittest discover -s tests
```

The script rewrites supported setup command hints, directs site work to agent skills, applies the status-output adaptations in `scripts/status_rewrites.py`, copies the shared renderer from `src/ezyplatform_cli/status_output.py`, and records the plugin version in `skills/VENDORED.json` (shown by `ezy --version`). Site scripts retain their Python invocation and rollback hints so they work independently of CLI routes. Rewrites fail when their expected upstream text changes, so review the adaptations when upgrading the plugin.

Release: bump `__version__` in `src/ezyplatform_cli/__init__.py`, commit, then `git tag vX.Y.Z && git push --tags`. The Release workflow builds and creates the GitHub release with the wheel (re-running it refreshes the files). PyPI publishing is off until the repository variable `PYPI_PUBLISH` is `true`: first add a trusted publisher on pypi.org (project `ezyplatform-cli`, workflow `release.yml`, environment `pypi`), then `gh variable set PYPI_PUBLISH --body true`.

## License

MIT — see [LICENSE](LICENSE). Bundled starter templates come from the EzyArticle VS Code extension by YoungMonkeys (MIT); see `src/ezyplatform_cli/skills/ezy-new/templates/NOTICE.md`.

---

## Tiếng Việt

`ezy` là công cụ dòng lệnh để khởi tạo dự án EzyPlatform / EzyArticle, quản lý plugin/skill cho coding agent và kiểm tra môi trường, cấu hình kết nối. Người dùng làm việc với nội dung, publish, media, bản dịch, mail và preview qua plugin `ezyplatform` trong coding agent. Agent không hỗ trợ plugin có thể dùng bản chép skill do `ezy skills install` cài đặt.

**Cài đặt** (một dòng, không cần cài gì trước — script tự cài uv và Python nếu máy chưa có):

```bash
# macOS / Linux
curl -LsSf https://raw.githubusercontent.com/cppai-vn/ezyplatform-cli/main/install.sh | sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/cppai-vn/ezyplatform-cli/main/install.ps1 | iex"
```

Cài xong mở terminal mới rồi gõ `ezy --version`. Cập nhật: `ezy update` (từ bản 0.1.2; bản cũ hơn thì chạy lại lệnh cài). Gỡ: `ezy uninstall` (từ bản 0.1.3; bản cũ hơn: `uv tool uninstall ezyplatform-cli`). Thư mục dự án site vẫn được giữ.

**Bắt đầu:**

1. `ezy init` (một lần cho mỗi máy): cài plugin `ezyplatform` vào các coding agent trên máy, hỏi có chép skill cho agent không hỗ trợ plugin không, kiểm tra rồi chạy `ezy doctor`.
2. `ezy new my-site` để tạo dự án site, rồi `cd my-site`. Lệnh hỏi dự án chạy ở đâu: **live** (nối với site thật, cần `--admin-url`), **local** (tự dựng EzyPlatform + MySQL bằng Docker trên máy; thiếu Docker thì đề nghị cài) hoặc **cả hai** (local là mặc định, site thật dùng `EZY_ENV=production`). Với local, mở `http://127.0.0.1:9090/setup-admin` tạo tài khoản super admin đầu tiên rồi lấy token ở `/admins/me`.
3. Vào `https://admin.example.com/admins/me`, bấm hiện **Access Token** (nhập mật khẩu), tự dán vào `environment.json` → mục `"default": true` → `admin_access_token`. Không gửi token cho ai.
4. `ezy check` để kiểm tra kết nối.
5. Mở dự án trong coding agent và bắt đầu phiên mới để nạp plugin. Dùng `ezy-guide` để chọn skill phù hợp; ví dụ yêu cầu agent kéo nội dung bằng `ezy-sync`, chỉnh sửa bằng `ezy-author` và chuẩn bị publish bằng `ezy-publish`.

CLI giữ các lệnh `init`, `new`, `token`, `check`, `whoami`, `plugins`, `skills`, `doctor`, `update` và `uninstall`. Các lệnh nghiệp vụ site trước đây đã được gỡ; khi gọi lại, CLI báo dùng skill tương ứng trong agent và trả mã thoát 2, không thực hiện thao tác trên site. Script nghiệp vụ vẫn được giữ trong bộ skill.

Kiểm tra kết nối từ CLI chỉ đọc dữ liệu. Các thao tác ghi lên site do skill thực hiện, với quy trình duyệt, chạy thử và sao lưu hiện có. Mỗi agent chỉ nên nhận skill theo một cách (plugin hoặc bản chép), nếu không sẽ thấy mỗi skill hai lần; `ezy doctor` sẽ báo. Xem tất cả lệnh: `ezy --help`.

`ezy plugins status` và `ezy doctor` chỉ hiển thị kết quả từng agent ngay khi kiểm tra xong, không hiện các dòng “Checking…”. Các lệnh kiểm tra danh sách plugin và marketplace không chờ nhập từ bàn phím, timeout 10 giây mỗi lệnh, kể cả khi setup, cập nhật hay kiểm tra trước khi chép skill. Nếu lỗi hoặc hết thời gian chờ, lệnh báo chưa đọc được trạng thái rồi tiếp tục kiểm tra các agent khác. Kiểm tra bản phát hành dùng timeout mạng 10 giây mỗi yêu cầu, có một lần thử qua địa chỉ dự phòng. Thao tác cài đặt và cập nhật vẫn giữ thời gian chờ dài hơn.

Các dòng trạng thái dùng `✓` xanh khi đạt, `✗` đỏ khi lỗi hoặc thiếu, và `?` trung tính cho thông tin hoặc mục cần kiểm tra thủ công. Áp dụng cho doctor, plugin, skill và kết nối site. Khi xuất ra file, đặt `NO_COLOR=1` hoặc dùng terminal `TERM=dumb`, lệnh giữ ký hiệu và bỏ màu; terminal không hỗ trợ Unicode dùng ký hiệu ASCII. Các yêu cầu GET tới API site có timeout mạng 10 giây mỗi yêu cầu.
