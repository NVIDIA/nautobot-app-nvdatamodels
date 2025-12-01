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
"""API serializers for nautobot_nvdatamodels."""

from nautobot.apps.api import (
    BaseModelSerializer,
    NautobotHyperlinkedRelatedField,
    NautobotModelSerializer,
    TaggedModelSerializerMixin,
)

from nautobot_nvdatamodels import models


class NVLinkDomainSerializer(NautobotModelSerializer, TaggedModelSerializerMixin):  # pylint: disable=too-many-ancestors
    """NVLinkDomain Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.NVLinkDomain
        fields = "__all__"


class NVLinkDomainMembershipSerializer(BaseModelSerializer):
    """NVLinkDomainMembership Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.NVLinkDomainMembership
        fields = "__all__"


class ResourceBlockSerializer(NautobotModelSerializer, TaggedModelSerializerMixin):  # pylint: disable=too-many-ancestors
    """ResourceBlock Serializer."""

    devices = NautobotHyperlinkedRelatedField(
        source="get_devices",
        view_name="dcim-api:device-detail",
        many=True,
        read_only=True,
        help_text="All devices in this resource block (both manually assigned and from dynamic group, deduplicated)",
    )
    static_devices = NautobotHyperlinkedRelatedField(
        source="get_static_devices",
        view_name="dcim-api:device-detail",
        many=True,
        read_only=True,
        help_text="Manually assigned devices only",
    )
    dynamic_devices = NautobotHyperlinkedRelatedField(
        source="get_dynamic_devices",
        view_name="dcim-api:device-detail",
        many=True,
        read_only=True,
        help_text="Dynamically assigned devices only",
    )

    class Meta:
        """Meta attributes."""

        model = models.ResourceBlock
        fields = "__all__"


class ResourceBlockMembershipSerializer(BaseModelSerializer):
    """ResourceBlockMembership Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.ResourceBlockMembership
        fields = "__all__"
