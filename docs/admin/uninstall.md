# Uninstall NVDataModels

Do the following to cleanly remove the NVDataModels app from your Nautobot environment.

1. Roll back NVDataModels-specific database migrations.

   ```sh
   nautobot-server migrate nautobot_nvdatamodels zero
   ```

1. Remove the configuration you added in `nautobot_config.py` from `PLUGINS` and `PLUGINS_CONFIG`.

1. Uninstall the package.

   ```sh
   pip uninstall nautobot-app-nvdatamodels
   ```