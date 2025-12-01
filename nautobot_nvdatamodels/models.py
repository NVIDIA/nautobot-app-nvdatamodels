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
"""Models for NVIDIA extensions to Nautobot."""

from django.db import models
from nautobot.apps.models import BaseModel, PrimaryModel, extras_features
from nautobot.core.constants import CHARFIELD_MAX_LENGTH
from nautobot.dcim.models import Device
from nautobot.extras.models import RoleField, StatusField

from nautobot_nvdatamodels import choices


@extras_features("graphql", "statuses", "custom_fields", "locations")
class NVLinkDomain(PrimaryModel):  # pylint: disable=too-many-ancestors
    """NVLink Domain model."""

    name = models.CharField(max_length=100, unique=True)
    status = StatusField()
    role = RoleField(blank=True, null=True)
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="nvlink_domains",
        blank=True,
        null=True,
    )
    location = models.ForeignKey(
        to="dcim.Location",
        on_delete=models.PROTECT,
        related_name="nvlink_domains",
    )
    rack_group = models.ForeignKey(
        to="dcim.RackGroup",
        on_delete=models.PROTECT,
        related_name="nvlink_domains",
        blank=True,
        null=True,
    )
    rack = models.ForeignKey(
        to="dcim.Rack",
        on_delete=models.PROTECT,
        related_name="nvlink_domains",
        blank=True,
        null=True,
    )
    cluster_id = models.CharField(max_length=CHARFIELD_MAX_LENGTH, verbose_name="Cluster ID", blank=True)
    protocol = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH, choices=choices.NVLinkDomainProtocolChoices, blank=True, null=True
    )
    members = models.ManyToManyField(
        to="dcim.Device",
        related_name="nvlink_domain",
        through="NVLinkDomainMembership",
        through_fields=("domain", "member"),
        blank=True,
        verbose_name="Domain Members",
    )
    topology = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH, choices=choices.NVLinkDomainTopologyChoices, blank=True, null=True
    )

    class Meta:
        """Meta class."""

        ordering = ["name"]
        verbose_name = "NVLink Domain"
        verbose_name_plural = "NVLink Domains"

    def __str__(self):
        """Stringify instance."""
        return self.name


@extras_features("graphql")
class NVLinkDomainMembership(BaseModel):
    """Models membership to NVLink Domains."""

    domain = models.ForeignKey(
        NVLinkDomain, on_delete=models.CASCADE, related_name="nvlink_domain_membership"
    )
    member = models.OneToOneField(
        "dcim.Device", on_delete=models.CASCADE, related_name="nvlink_domain_membership"
    )

    class Meta:
        """Metadata."""

        unique_together = ("domain", "member")
        verbose_name = "NVLink Domain Membership"
        verbose_name_plural = "NVLink Domain Memberships"

    def __str__(self) -> str:
        """Stringify instance."""
        return f"{self.member} in {self.domain}"


@extras_features("graphql", "statuses", "custom_fields", "locations")
class ResourceBlock(PrimaryModel):
    """Resource Block model.

    A resource block represents all compute resources (devices) connected to the same switching fabric.
    Devices in a resource block may be divided into multiple clusters, or held in reserve (not assigned to any cluster).

    This model supports both static device assignment and dynamic device assignment via associated Dynamic Groups.
    """

    name = models.CharField(max_length=CHARFIELD_MAX_LENGTH, unique=True)
    status = StatusField()
    protocol = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=choices.ResourceBlockProtocolChoices,
        blank=True,
        null=True,
        verbose_name="Protocol",
    )
    role = RoleField(blank=True, null=True)
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="resource_blocks",
        blank=True,
        null=True,
    )
    location = models.ForeignKey(
        to="dcim.Location",
        on_delete=models.PROTECT,
        related_name="resource_blocks",
        blank=True,
        null=True,
    )
    devices = models.ManyToManyField(
        to="dcim.Device",
        related_name="resource_block",
        through="ResourceBlockMembership",
        through_fields=("resource_block", "device"),
        blank=True,
        verbose_name="Manually Assigned Devices",
    )
    dynamic_group = models.ForeignKey(
        to="extras.DynamicGroup",
        on_delete=models.SET_NULL,
        related_name="resource_blocks",
        blank=True,
        null=True,
        verbose_name="Dynamic Group",
        help_text="Optional Dynamic Group to automatically include devices based on filter criteria",
    )

    class Meta:
        """Meta class."""

        ordering = ["name"]
        verbose_name = "resource block"
        verbose_name_plural = "resource blocks"

    def __str__(self):
        """Stringify instance."""
        return self.name

    def get_devices(self):
        """Get all devices from both static assignment and dynamic group (deduplicated)."""
        device_ids = set()

        device_ids.update(self.devices.values_list("id", flat=True))
        if self.dynamic_group:
            device_ids.update(self.dynamic_group.members.values_list("id", flat=True))
        return Device.objects.filter(id__in=device_ids)

    def get_static_devices(self):
        """Get only manually assigned devices."""
        return self.devices.all()

    def get_dynamic_devices(self):
        """Get only dynamically assigned devices."""
        if self.dynamic_group:
            return self.dynamic_group.members.all()
        return Device.objects.none()

    @property
    def device_count(self):
        """Return the total number of devices (static + dynamic, deduplicated)."""
        return self.get_devices().count()

    @property
    def static_device_count(self):
        """Return the number of manually assigned devices."""
        return self.devices.count()

    @property
    def dynamic_device_count(self):
        """Return the number of dynamically assigned devices."""
        if not self.dynamic_group:
            return 0
        return self.dynamic_group.members.count()

    @property
    def dynamic_devices_queryset(self):
        """Return dynamic devices as a queryset for serializer depth support."""
        return self.get_dynamic_devices()


@extras_features("graphql")
class ResourceBlockMembership(BaseModel):
    """Models manual membership to Resource Blocks - ensures devices can only belong to one resource block."""

    resource_block = models.ForeignKey(
        ResourceBlock, on_delete=models.CASCADE, related_name="resource_block_memberships"
    )
    device = models.OneToOneField(
        "dcim.Device", on_delete=models.CASCADE, related_name="resource_block_membership"
    )

    class Meta:
        """Metadata."""

        verbose_name = "Resource Block Membership"
        verbose_name_plural = "Resource Block Memberships"

    def __str__(self) -> str:
        """Stringify instance."""
        return f"{self.device} in {self.resource_block}"
