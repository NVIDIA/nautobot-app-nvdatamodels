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
"""Signal handlers that fire on various Django model signals."""

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver
from nautobot.apps import nautobot_database_ready
from nautobot.apps.choices import ColorChoices
from nautobot.extras.models import Status

from nautobot_nvdatamodels.models import NVLinkDomain, ResourceBlock

from .choices import NVLinkDomainDefaultStatusChoices


@receiver(nautobot_database_ready, sender=apps.get_app_config("nautobot_nvdatamodels"))
def create_default_nvlink_domain_statuses(**kwargs):
    """Create default statuses for NVLinkDomain objects."""
    content_type = ContentType.objects.get_for_model(NVLinkDomain)
    color_mapping = {
        "Active": ColorChoices.COLOR_GREEN,
        "Healthy": ColorChoices.COLOR_GREEN,
        "Degraded": ColorChoices.COLOR_YELLOW,
        "Planned": ColorChoices.COLOR_GREY,
        "Offline": ColorChoices.COLOR_GREY,
    }
    for status_name, color in NVLinkDomainDefaultStatusChoices.CHOICES:
        status, _ = Status.objects.get_or_create(name=status_name, defaults={"color": color_mapping[color]})
        status.content_types.add(content_type)


@receiver(nautobot_database_ready, sender=apps.get_app_config("nautobot_nvdatamodels"))
def create_default_resource_block_statuses(**kwargs):
    """Create default statuses for ResourceBlock objects."""
    content_type = ContentType.objects.get_for_model(ResourceBlock)
    color_mapping = [
        ("Active", ColorChoices.COLOR_GREEN),
        ("Planned", ColorChoices.COLOR_GREY),
        ("Decommissioned", ColorChoices.COLOR_RED),
    ]

    for status_name, color in color_mapping:
        status, _ = Status.objects.get_or_create(name=status_name, defaults={"color": color})
        status.content_types.add(content_type)
