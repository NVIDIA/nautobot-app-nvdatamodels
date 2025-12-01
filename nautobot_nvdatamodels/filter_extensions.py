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
"""Filter extensions."""

from nautobot.apps.filters import FilterExtension, NaturalKeyOrPKMultipleChoiceFilter

from nautobot_nvdatamodels.models import NVLinkDomain, ResourceBlock


class DeviceFilterExtension(FilterExtension):
    """Extends dcim.device filter."""

    model = "dcim.device"

    filterset_fields = {
        "nautobot_nvdatamodels_nvlink_domain": NaturalKeyOrPKMultipleChoiceFilter(
            field_name="nvlink_domain",
            queryset=NVLinkDomain.objects.all(),
            to_field_name="name",
            label="NVLink Domain (name or ID)",
        ),
        "nautobot_nvdatamodels_resource_block": NaturalKeyOrPKMultipleChoiceFilter(
            field_name="resource_block",
            queryset=ResourceBlock.objects.all(),
            to_field_name="name",
            label="Resource Block (name or ID)",
        ),
    }


filter_extensions = [DeviceFilterExtension]
