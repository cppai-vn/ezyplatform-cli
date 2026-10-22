"""A local EzyPlatform for a site project: EzyPlatform app + MySQL in Docker Compose.

Follows cppai-vn/ezyplatform-docker (same image, MySQL 8.0 with
mysql_native_password, the app volume at /app/ezyplatform) with two fixes
found when starting it on an empty database:
- the image's entrypoint always writes a jdbc:mysql:// URL while the bundled
  driver is MariaDB Connector/J 3.x, which ignores that scheme unless
  `permitMysqlScheme` is set: without it every repository fails and the admin
  answers 500 on every page. DB_NAME carries the option into the URL.
- the first boot takes longer than the entrypoint's 180s startup limit, which
  made the container exit and restart once; the limit is raised.
- MySQL's healthcheck pings over TCP; a socket ping passes while the first-run
  init server is still offline, so the app started before MySQL listened.
Passwords are random and live in the project's git-ignored .env.
"""
import os
import re
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request

IMAGE = os.environ.get('EZY_LOCAL_IMAGE', 'vutadev/ezyplatform-app:1.5.0')
COMPOSE_FILE = 'docker-compose.yml'
ENV_FILE = '.env'
START_TIMEOUT = 600  # first run pulls ~1 GB of images and runs the amd64 image emulated on Apple silicon

COMPOSE = """# Local EzyPlatform for this site project, created by `ezy new`.
# Start: docker compose up -d   Stop: docker compose stop   Logs: docker compose logs -f ezyplatform
# Admin: http://127.0.0.1:${EZY_ADMIN_PORT}   Website: http://127.0.0.1:${EZY_WEB_PORT}
# Settings and passwords are in .env (git-ignored). Data stays in the Docker volumes until `docker compose down -v`.
name: ${COMPOSE_PROJECT_NAME}
services:
  mysql:
    image: mysql:8.0
    restart: unless-stopped
    command: --default-authentication-plugin=mysql_native_password
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql-data:/var/lib/mysql
    healthcheck:
      # TCP, not the socket: the first-run init server answers socket pings before MySQL listens
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1"]
      interval: 5s
      timeout: 20s
      retries: 60

  ezyplatform:
    image: ${EZY_IMAGE}
    platform: linux/amd64
    restart: unless-stopped
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      DB_HOST: mysql
      DB_PORT: "3306"
      # permitMysqlScheme: the image writes jdbc:mysql:// but ships the MariaDB 3.x driver
      DB_NAME: ${MYSQL_DATABASE}?permitMysqlScheme
      DB_USERNAME: ${MYSQL_USER}
      DB_PASSWORD: ${MYSQL_PASSWORD}
      DB_TABLES_CREATE_MANUALLY: "false"
      AUTO_START_WEB: "true"
      # the first boot on an empty database (emulated amd64 on Apple silicon) takes longer than the 180s default
      STARTUP_TIMEOUT_SECONDS: "600"
    ports:
      - "127.0.0.1:${EZY_ADMIN_PORT}:9090"
      - "127.0.0.1:${EZY_WEB_PORT}:8080"
    volumes:
      - ezyplatform-data:/app/ezyplatform

volumes:
  mysql-data: {}
  ezyplatform-data: {}
"""


def project_name(root):
    slug = re.sub(r'[^a-z0-9]+', '-', os.path.basename(os.path.abspath(root)).lower()).strip('-')
    return 'ezy-' + (slug or 'site')


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            return False
    return True


def free_port(start, taken=()):
    port = start
    while port in taken or not port_free(port):
        port += 1
    return port


def read_env(root):
    values = {}
    path = os.path.join(root, ENV_FILE)
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                key, sep, value = line.strip().partition('=')
                if sep and not key.startswith('#'):
                    values[key] = value
    return values


def write_files(root, report):
    """docker-compose.yml + .env; existing files are kept, so ports and passwords stay stable."""
    env = read_env(root)
    if not env:
        admin = free_port(9090)
        env = {
            'COMPOSE_PROJECT_NAME': project_name(root),
            'EZY_IMAGE': IMAGE,
            'EZY_ADMIN_PORT': str(admin),
            'EZY_WEB_PORT': str(free_port(8080, {admin})),
            'MYSQL_DATABASE': 'blog',
            'MYSQL_USER': 'ezyplatform',
            'MYSQL_PASSWORD': secrets.token_urlsafe(18),
            'MYSQL_ROOT_PASSWORD': secrets.token_urlsafe(18),
        }
        path = os.path.join(root, ENV_FILE)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# Local EzyPlatform settings for docker-compose.yml (git-ignored; keep it private)\n')
            fh.write(''.join(f'{k}={v}\n' for k, v in env.items()))
        os.chmod(path, 0o600)
        report.append(f'  + {ENV_FILE} (local ports and generated database passwords)')
    else:
        report.append(f'  = {ENV_FILE} (exists, kept)')
    compose = os.path.join(root, COMPOSE_FILE)
    if os.path.exists(compose):
        report.append(f'  = {COMPOSE_FILE} (exists, kept)')
    else:
        with open(compose, 'w', encoding='utf-8') as fh:
            fh.write(COMPOSE)
        report.append(f'  + {COMPOSE_FILE} (EzyPlatform + MySQL)')
    gitignore = os.path.join(root, '.gitignore')
    current = open(gitignore, encoding='utf-8').read() if os.path.exists(gitignore) else ''
    if ENV_FILE not in current.split():
        with open(gitignore, 'a', encoding='utf-8') as fh:
            fh.write(('' if not current or current.endswith('\n') else '\n') + ENV_FILE + '\n')
        report.append(f'  ~ .gitignore (+ {ENV_FILE})')
    return env


def urls(env):
    return f"http://127.0.0.1:{env['EZY_ADMIN_PORT']}", f"http://127.0.0.1:{env['EZY_WEB_PORT']}"


def http_status(url):
    """HTTP status of a HEAD request, 0 when nothing answers."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code
    except OSError:
        return 0


def wait_for(url, ok, timeout=START_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ok(http_status(url)):
            return True
        time.sleep(5)
    return False


def start(root, env):
    """docker compose up -d, then wait for the admin; True when it answers."""
    print('  $ docker compose up -d   (first run downloads the images, a few minutes)', flush=True)
    if subprocess.call(['docker', 'compose', 'up', '-d'], cwd=root) != 0:
        print('  x docker compose up failed; see the output above')
        return False
    admin, web = urls(env)
    print(f'  waiting for the admin at {admin} ...', flush=True)
    # the admin redirects to /setup-admin until the first super admin exists, so any status < 500 is up
    if not wait_for(admin + '/login', lambda code: 0 < code < 500):
        print(f'  x the admin did not answer within {START_TIMEOUT // 60} minutes; '
              'check: docker compose logs ezyplatform')
        return False
    web_ok = lambda code: 200 <= code < 400  # noqa: E731
    if not wait_for(web, web_ok, timeout=90):
        # on the very first boot the website starts before the admin has initialised the
        # database and answers 404 until restarted; one restart fixes it
        print('  first start: restarting EzyPlatform once so the website picks up the new database', flush=True)
        subprocess.call(['docker', 'compose', 'restart', 'ezyplatform'], cwd=root,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_for(web, web_ok, timeout=300):
            print(f'  ! the website at {web} is not answering yet; check: docker compose logs ezyplatform')
    print(f'  ✓ local EzyPlatform is running: admin {admin}  website {web}')
    return True
