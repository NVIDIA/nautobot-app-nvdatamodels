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
"""API views for nautobot_nvdatamodels."""

from nautobot.apps.api import ModelViewSet, NautobotModelViewSet

from nautobot_nvdatamodels import filters, models
from nautobot_nvdatamodels.api import serializers


class NVLinkDomainViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """NVLinkDomain viewset."""

    queryset = models.NVLinkDomain.objects.all()
    serializer_class = serializers.NVLinkDomainSerializer
    filterset_class = filters.NVLinkDomainFilterSet

    # Option for modifying the default HTTP methods:
    # http_method_names = ["get", "post", "put", "patch", "delete", "head", "options", "trace"]


class NVLinkDomainMembershipViewSet(ModelViewSet):  # pylint: disable=too-many-ancestors
    """NVLinkDomainMembership viewset."""

    queryset = models.NVLinkDomainMembership.objects.all()
    serializer_class = serializers.NVLinkDomainMembershipSerializer
    filterset_class = filters.NVLinkDomainMembershipFilterSet


class ResourceBlockViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """ResourceBlock viewset."""

    queryset = models.ResourceBlock.objects.all()
    serializer_class = serializers.ResourceBlockSerializer
    filterset_class = filters.ResourceBlockFilterSet

    # Option for modifying the default HTTP methods:
    # http_method_names = ["get", "post", "put", "patch", "delete", "head", "options", "trace"]


class ResourceBlockMembershipViewSet(ModelViewSet):  # pylint: disable=too-many-ancestors
    """ResourceBlockMembership viewset."""

    queryset = models.ResourceBlockMembership.objects.all()
    serializer_class = serializers.ResourceBlockMembershipSerializer
    filterset_class = filters.ResourceBlockMembershipFilterSet
