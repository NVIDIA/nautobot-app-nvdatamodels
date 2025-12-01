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
"""Custom template content."""

from nautobot.apps.ui import TemplateExtension


class DeviceNVIDIAContent(TemplateExtension):
    """Extra content for dcim.Device view."""

    model = "dcim.device"

    def right_page(self):
        """Extra content on right panel."""
        return self.render("nautobot_nvdatamodels/device_nvidia.html")


template_extensions = (DeviceNVIDIAContent,)
