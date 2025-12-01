# NVDataModels Nautobot App

## Features

This app provides the tools necessary to model NVIDIA components in Nautobot.

This app provides the following models:

* `NVLinkDomain`
* `NVLinkDomainMembership`
* `ResourceBlock`
* `ResourceBlockMembership`

## Installation

Once the project is mature, installing this app will follow the standard process for installing any Nautobot app:

1. Add `nautobot-app-nvdatamodels` to Nautobot's `pyproject.toml`
1. Add `nautobot_nvdatamodels` to `PLUGINS` in `nautobot_config.py`

Currently, there are no plugin configuration options to add to `PLUGINS_CONFIG` in `nautobot_config.py`.

## Development Environment Setup

### Prerequisites

This project requires Docker, Docker Compose, and `uv`.

On macOS, use [homebrew](https://brew.sh/) to install Docker, Docker Compose, and `uv`:

```sh
brew install --cask docker
brew install docker-compose uv
```

### Setup

1. Clone this project locally.

1. Install dependencies.

    ```sh
    uv sync --all-extras
    ```

1. Build image.

    ```sh
    invoke build
    ```

1. Start containers.

    ```sh
    invoke start
    ```

The first time you start the containers with a fresh database, it will take 1-2 minutes for the Nautobot container to come up. Check progress by tailing the logs:

```sh
invoke logs -f  # <Ctrl-C> to stop
```

To enable automatic linting and formatting on file save, install the [`ruff` VSCode plugin](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff).

Once it's up, access the development server at <http://localhost:8080>.

### Tips

Changes to code will auto-reload the worker for quick iteration. Tail the worker's logs for easier debugging:

```sh
invoke logs -f -s worker  # <Ctrl-C> to stop
```

If you're working with jobs, it's convenient to enable all jobs (which are disabled by default):

```sh
invoke enable-jobs  # Idempotently enables all disabled jobs, if any
```

If you're developing a job and need to re-run it often for testing, consider this approach:

1. Run the job once in the GUI.

1. Copy the `JobResult`'s UUID.

1. Re-run the job with the same parameters from the CLI:

    ```sh
    invoke rerun-job <job-result-uuid>
    ```

This is not only faster than the GUI-only method, but also gives you the option to feed debug output directly into AI agents, if you use an AI-assisted IDE like Cursor.

It's often helpful to populate Nautobot with dummy data for testing:

```sh
invoke cli
nautobot-server generate_test_data
```

See all available commands with:

```sh
invoke --help
```
