import textwrap
from pathlib import Path

from invoke import Context, Exit, call, task
from packaging.version import Version
from termcolor import cprint

MIN_NODE_VERSION = "22"

DOCKER_PROJECT_NAME = "looplink-interview"
DOCKER_COMPOSE_FILE = "docker-compose.yml"


@task
def docker(c: Context, command):
    if command == "up":
        c.run(f"docker compose -p {DOCKER_PROJECT_NAME} -f {DOCKER_COMPOSE_FILE} up -d")
    elif command == "down":
        c.run(f"docker compose -p {DOCKER_PROJECT_NAME} -f {DOCKER_COMPOSE_FILE} down --remove-orphans")
    elif command == "rebuild":
        c.run(f"docker compose -p {DOCKER_PROJECT_NAME} -f {DOCKER_COMPOSE_FILE} up --build -d")
    elif command == "reset":
        c.run(f"docker compose -p {DOCKER_PROJECT_NAME} -f {DOCKER_COMPOSE_FILE} down --remove-orphans")
        c.run(f"docker compose -p {DOCKER_PROJECT_NAME} -f {DOCKER_COMPOSE_FILE} up --build -d")
    else:
        raise Exit(f"Unknown docker command: {command}", -1)


@task(pre=[call(docker, command="up")])
def up(c: Context):
    pass


@task(pre=[call(docker, command="down")])
def down(c: Context):
    pass


@task
def requirements(c: Context):
    _install_python_requirements(c)
    _install_npm_requirements(c)


def _install_python_requirements(c: Context):
    result = c.run(
        "uv sync --dry-run",
        echo=True,
        pty=True,
    )
    if "no changes" in result.stdout:
        return

    if _confirm("Do you want to apply the changes?", _exit=False):
        c.run(
            "uv sync --compile-bytecode",
            echo=True,
            pty=True,
        )


def _install_npm_requirements(c: Context):
    c.run("npm install", echo=True, pty=True)


@task
def setup_dev_env(c: Context, step=False):
    cprint("\n\n⚙️  Setting up dev environment...", "green")
    if not step and not _confirm(
        textwrap.dedent(
            """
    This will start docker, run DB migrations, and build JS & CSS resources.
    Do you want to continue?
    """
        ),
        _exit=False,
    ):
        cprint("You can also run this one step at a time with the '-s' or '--step' flag", "yellow")
        raise Exit(None, -1)

    cprint("\n✅ Install Python requirements...", "green")
    if not step or _confirm("\tOK?", _exit=False):
        _install_python_requirements(c)

    cprint("\n✅ Start docker...", "green")
    if not step or _confirm("\tOK?", _exit=False):
        docker(c, command="up")

    if not Path(".env").exists():
        _run_with_confirm(c, "✅ Create .env file...", "cp .env.example .env", step)
    else:
        cprint("\n⏩  Skipping .env file creation, file already exists...", "yellow")

    cprint(f"\n✅ Check node version (>{MIN_NODE_VERSION} required)...", "green")
    if not _check_node_version(c):
        cprint(f"Node version should be {MIN_NODE_VERSION} or higher", "red")
        cprint("\nSkipping front end build. Run 'inv npm --install' once you have upgraded node.", "yellow")
    else:
        cprint("\n✅ Install npm requirements and building front end resources...", "green")
        if not step or _confirm("\tOK?", _exit=False):
            npm(c, install=True)
        cprint("\n✅ Run webpack build for js_entry...", "green")
        if not step or _confirm("\tOK?", _exit=False):
            webpack(c)

    _run_with_confirm(c, "✅ Run DB migrations...", "python manage.py migrate", step)

    cprint("\n\n🎉 Success! Your dev environment is now ready. Here are a few tips:", "green")
    cprint("\n1️⃣  Continuously build webpack in another shell with: `inv npm -w` or `npm run watch`", "cyan")
    cprint("\n2️⃣  Run the development server with: `./manage.py runserver`", "cyan")
    cprint("\n3️⃣  Finally, visit http://localhost:8000\n", "cyan")


@task
def npm(c: Context, watch=False, install=False):
    if install:
        _install_npm_requirements(c)
    cmd = "watch" if watch else "build"
    c.run(f"npm run {cmd}", echo=True, pty=True)


@task
def webpack(c: Context):
    c.run("npm run build", echo=True)


def _run_with_confirm(c: Context, message, command, step=False):
    cprint(f"\n{message}", "green")
    if not step or _confirm("\tOK?", _exit=False):
        c.run(command, echo=True, pty=True)
        return True


def _check_node_version(c: Context):
    res = c.run("node -v", echo=True)
    version = res.stdout.strip()
    if version.startswith("v"):
        version = version[1:]
    ver = Version(version)
    return ver >= Version(MIN_NODE_VERSION)


def _confirm(message, _exit=True, exit_message="Done"):
    response = input(f"{message} (y/n): ")
    confirmed = response.lower() == "y"
    if not confirmed and _exit:
        raise Exit(exit_message, -1)
    return confirmed
