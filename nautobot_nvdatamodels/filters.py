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
"""Filtering for nautobot_nvdatamodels."""

from nautobot.apps.filters import NameSearchFilterSet, NaturalKeyOrPKMultipleChoiceFilter, NautobotFilterSet
from nautobot.core.filters import SearchFilter, TreeNodeMultipleChoiceFilter
from nautobot.dcim.filters.mixins import LocatableModelFilterSetMixin
from nautobot.dcim.models import Device, Rack, RackGroup
from nautobot.extras.filters import RoleModelFilterSetMixin, StatusModelFilterSetMixin
from nautobot.tenancy.filters.mixins import TenancyModelFilterSetMixin

from nautobot_nvdatamodels import models


class NVLinkDomainFilterSet(
    NautobotFilterSet,
    LocatableModelFilterSetMixin,
    TenancyModelFilterSetMixin,
    StatusModelFilterSetMixin,
    RoleModelFilterSetMixin,
    NameSearchFilterSet,
):  # pylint: disable=too-many-ancestors
    """Filter for NVLinkDomain."""

    q = SearchFilter(
        filter_predicates={
            "name": "icontains",
            "protocol": "icontains",
            "cluster_id": "icontains",
        },
    )

    rack_group = TreeNodeMultipleChoiceFilter(
        prefers_id=True,
        queryset=RackGroup.objects.all(),
        to_field_name="name",
        label="Rack group (name or ID)",
    )

    rack = NaturalKeyOrPKMultipleChoiceFilter(
        prefers_id=True,
        queryset=Rack.objects.all(),
        to_field_name="name",
        label="Rack (name or ID)",
    )

    members = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=Device.objects.all(),
        to_field_name="name",
        label="Member device (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.NVLinkDomain
        fields = "__all__"


class NVLinkDomainMembershipFilterSet(NautobotFilterSet, NameSearchFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for NVLinkDomainMembership."""

    domain = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.NVLinkDomain.objects.all(),
        to_field_name="name",
        label="Domain (name or ID)",
    )
    member = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=Device.objects.all(),
        to_field_name="name",
        label="Member device (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.NVLinkDomainMembership
        fields = "__all__"


class ResourceBlockFilterSet(
    NautobotFilterSet,
    LocatableModelFilterSetMixin,
    TenancyModelFilterSetMixin,
    StatusModelFilterSetMixin,
    RoleModelFilterSetMixin,
    NameSearchFilterSet,
):  # pylint: disable=too-many-ancestors
    """Filter for ResourceBlock."""

    q = SearchFilter(
        filter_predicates={
            "name": "icontains",
        },
    )

    devices = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=Device.objects.all(),
        to_field_name="name",
        label="Device (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.ResourceBlock
        fields = "__all__"


class ResourceBlockMembershipFilterSet(NautobotFilterSet, NameSearchFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for ResourceBlockMembership."""

    resource_block = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.ResourceBlock.objects.all(),
        to_field_name="name",
        label="Resource Block (name or ID)",
    )
    device = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=Device.objects.all(),
        to_field_name="name",
        label="Device (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.ResourceBlockMembership
        fields = "__all__"
