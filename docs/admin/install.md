# Install NVDataModels in Nautobot

Follow the instructions below to install and configure the NVDataModels app within your Nautobot environment.

## Prerequisites

Refer to the [compatibility matrix](compatibility_matrix.md) for supported Nautobot versions and the deprecation policy.

- Nautobot 2.3.0 or higher
- PostgreSQL or MySQL database

## Installation

!!! note

    You can install apps from the [Python Package Index](https://pypi.org/) or locally. See the [Nautobot documentation](https://docs.nautobot.com/projects/core/en/stable/user-guide/administration/installation/app-install/) for more details. The pip package name for NVDataModels is [`nautobot-app-nvdatamodels`](https://pypi.org/project/nautobot-app-nvdatamodels/).

To install the NVDataModels app from the Python Package Index, follow these steps:

1. Install the NVDataModels package using `pip`.

    ```sh
    pip install nautobot-app-nvdatamodels
    ```

1. To ensure NVDataModels is automatically re-installed during future upgrades, create a file named `local_requirements.txt` (if not already existing) in the Nautobot root directory (alongside `requirements.txt`) and list the `nautobot-app-nvdatamodels` package.

    ```sh
    echo nautobot-app-nvdatamodels >> local_requirements.txt
    ```

1. Once installed, the NVDataModels app needs to be enabled in your Nautobot configuration. The following block of code shows the additional configuration required to be added to your `nautobot_config.py` file.

    - Append `"nautobot_nvdatamodels"` to the `PLUGINS` list.
    - Append the `"nautobot_nvdatamodels"` dictionary to the `PLUGINS_CONFIG` dictionary and override any defaults.

    ```python
    PLUGINS = ["nautobot_nvdatamodels"]

    PLUGINS_CONFIG = {
      "nautobot_nvdatamodels": {
        # ADD YOUR SETTINGS HERE
      }
    }
    ```

1. Once the Nautobot configuration is updated, run the following command to apply migrations and clear the cache.

    ```sh
    nautobot-server post_upgrade
    ```

1. Finally, restart the Nautobot services.

    For example, to restart Nautobot, its workers, and its scheduler, run the following command:

    ```sh
    sudo systemctl restart nautobot nautobot-worker nautobot-scheduler
    ```
