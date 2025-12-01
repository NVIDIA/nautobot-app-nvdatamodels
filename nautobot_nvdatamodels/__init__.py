#  SPDX-FileCopyrightText: Copyright (c) "2025" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License")
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""App declaration for nautobot_nvdatamodels."""

# Metadata is inherited from Nautobot. If not including Nautobot in the environment, this should be added
import logging
from importlib import metadata

from nautobot.apps import NautobotAppConfig

logger = logging.getLogger(__name__)
__version__ = metadata.version(__name__)


class NautobotNVIDIAConfig(NautobotAppConfig):
    """App configuration for the nautobot_nvdatamodels app."""

    name = "nautobot_nvdatamodels"
    verbose_name = "Nautobot NVIDIA DSX"
    version = __version__
    author = "Austin de Coup-Crank"
    author_email = "adecoupcrank@nvidia.com"
    description = (
        "A Nautobot app that provides tools for modeling NVIDIA DSX products and resources, "
        "such as NVLink domains and GPU clusters."
    )
    base_url = "nvdatamodels"
    required_settings = []
    min_version = "2.3.0"
    max_version = "2.9999"
    default_settings = {}
    caching_config = {}
    docs_view_name = "plugins:nautobot_nvdatamodels:docs"

    def ready(self):
        """Ready checks."""
        super().ready()
        from . import signals  # noqa F401


config = NautobotNVIDIAConfig  # pylint:disable=invalid-name
