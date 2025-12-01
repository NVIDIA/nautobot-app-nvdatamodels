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
"""Menu items."""

from nautobot.apps.ui import NavMenuAddButton, NavMenuGroup, NavMenuItem, NavMenuTab

items = (
    NavMenuItem(
        link="plugins:nautobot_nvdatamodels:nvlinkdomain_list",
        name="NVLink Domains",
        permissions=["nautobot_nvdatamodels.view_nvlinkdomain"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_nvdatamodels:nvlinkdomain_add",
                permissions=["nautobot_nvdatamodels.add_nvlinkdomain"],
            ),
        ),
    ),
    NavMenuItem(
        link="plugins:nautobot_nvdatamodels:resourceblock_list",
        name="Resource Blocks",
        permissions=["nautobot_nvdatamodels.view_resourceblock"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_nvdatamodels:resourceblock_add",
                permissions=["nautobot_nvdatamodels.add_resourceblock"],
            ),
        ),
    ),
)

menu_items = (
    NavMenuTab(
        name="NVIDIA",
        groups=(NavMenuGroup(name="Clustering", items=tuple(items)),),
    ),
)
