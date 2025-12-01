# Development Environment

Set up a local development environment for the Nautobot app using Docker. The environment includes all required services (Nautobot, database, Redis) with source code mounted for live development. Changes to your local files are automatically reflected in the running containers.

## Prerequisites

1. Install uv according to the [uv documentation](https://github.com/astral-sh/uv) for your operating system.

1. Install Docker according to the [Docker documentation](https://docs.docker.com/get-docker/) for your operating system.

1. Optional: Install `direnv` to automatically load environment variables from `.envrc`.

    * `brew install direnv`
    * Add the following to your `~/.zshrc` (adjusting for other shells if needed): `eval "$(direnv hook zsh)"`
    * Prepare your `.envrc` by copying it from an example file if needed: `cp .envrc.example .envrc`
    * Approve direnv for the current directory: `direnv allow`
    * Reload your shell if you just modified your `~/.zshrc`

1. Create your Python virtual environment and install dependencies.

    **Note**: The configuration files are set up for Python 3.12, the version currently used to deploy Nautobot. If you need to install a specific version, try something like `brew install pyenv` then `pyenv install 3.12` first.

    ```shell
    uv sync && source .venv/bin/activate
    ```

1. Install pip if you do not have it yet:

    ```shell
    uv pip install pip
    ```

1. Create a `creds.env` file in `development/`.

1. Continue with the [Docker development environment](#docker-development-environment) steps.

## Docker Development Environment

1. Copy `invoke.mysql.yml` to `invoke.yml` (also ignored by Git).

1. Build the image and start the services.

   ```shell
   uv sync --all-extras
   source .venv/bin/activate
   invoke build
   invoke start
   ```

Access Nautobot at <http://localhost:8080>.

**Managing the environment**:

* `invoke stop` — Stops containers but preserves data and volumes
* `invoke destroy` — Stops and removes all containers and volumes (**warning**: This deletes all data)

With the environment up, you should see these running Docker containers:

```shell
$ docker ps

CONTAINER ID   IMAGE                                             COMMAND                  CREATED       STATUS                 PORTS                                          NAMES
a7afc23a8c23   postgres:13-alpine                                "docker-entrypoint.s…"   3 hours ago   Up 3 hours (healthy)   0.0.0.0:3306->3306/tcp, 0.0.0.0:5432->5432/tcp nautobot-nvdatamodels-db-1
2c6910fedc16   redis:6-alpine                                    "docker-entrypoint.s…"   3 hours ago   Up 3 hours             0.0.0.0:6379->6379/tcp                         nautobot-nvdatamodels-redis-1
bffe7d37afc5   nautobot-app-nvdatamodels/nautobot:2.4.5-py3.12   "sh -c 'watchmedo au…"   4 hours ago   Up 4 hours             8080/tcp                                       nautobot-nvdatamodels-beat-1
18217e9f0860   nautobot-app-nvdatamodels/nautobot:2.4.5-py3.12   "sh -c 'watchmedo au…"   4 hours ago   Up 4 hours (healthy)   8080/tcp                                       nautobot-nvdatamodels-worker-1
dc8e019bb81a   nautobot-app-nvdatamodels/nautobot:2.4.5-py3.12   "/docker-entrypoint.…"   4 hours ago   Up 4 hours (healthy)   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp    nautobot-nvdatamodels-nautobot-1
fb6401814895   nautobot-app-nvdatamodels/nautobot:2.4.5-py3.12   "mkdocs serve -v -a …"   4 hours ago   Up 4 hours             0.0.0.0:8001->8080/tcp, [::]:8001->8080/tcp    nautobot-nvdatamodels-docs-1
```

### Live Development

The project root directory is mounted into Docker containers, enabling live code updates without rebuilding.

**How it works**:

* Source code changes are immediately reflected in running containers
* Django automatically reloads when files are saved (typically a few seconds)
* Example: Edit `tables.py` and save — changes appear in the browser after reload

!!! warning
    Some changes require container rebuilds. Refer to the "To Rebuild or Not To Rebuild" section for details.

!!! note
    You may see connection errors during Django reload. Wait a few seconds for the process to restart.

### Docker Logs

View container logs for debugging:

```bash
invoke logs -f
```

**Options**:

* `-f` — Follow logs in real time
* `-s <service>` — View logs from a specific service (default: `nautobot`)

**Examples**:

```bash
invoke logs -f -s db      # Database logs
invoke logs -f -s worker   # Worker container logs
```

## Visual Studio Code Setup

This project includes configuration for Visual Studio Code to enhance the development experience. The project's `.vscode/settings.json` file contains settings for the Ruff linter and formatter. To use these settings, install the [Ruff VSCode extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff), and restart Visual Studio Code after installation.

The project settings configure the following behaviors:

* Format Python files on save
* Fix auto-fixable problems on save
* Organize imports on save

!!! note
    These settings require the Ruff extension to be installed. Without it, the configured behaviors will not work.

## Editor Configuration

**Trim trailing whitespace**:

* **Cursor (Mac)**: Command+R, Command+X
* **Windsurf (Mac)**: Command+K, Command+X
* **Other editors**: Search keyboard shortcuts for "trim trailing whitespace"

## Testing

Run tests using the following commands:

* **All tests**: `invoke tests`
* **Verbose output**: `invoke tests --verbose`
* **Specific test**: `invoke unittest --label nautobot_nvdatamodels.tests.test_basic.TestVersion --verbose`
* **Coverage report**: `invoke unittest-coverage`

!!! note
    The worker container auto-restarts when code changes are detected. Avoid editing files during active job execution to prevent runtime errors.
