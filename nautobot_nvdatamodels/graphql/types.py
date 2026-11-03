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
"""Preserve scalar NVLink reference names alongside expanded reference objects."""

import graphene
import graphene_django_optimizer as gql_optimizer
from nautobot.core.graphql.types import OptimizedNautobotObjectType

from nautobot_nvdatamodels import filters, models


def _visible_reference(instance, info, field):
    reference = getattr(instance, field)
    if reference is None:
        return None
    if type(reference).objects.restrict(info.context.user, "view").filter(pk=reference.pk).exists():
        return reference
    return None


class NVLinkDomainProtocolType(OptimizedNautobotObjectType):
    """Configurable NVLink protocol details."""

    class Meta:
        """Model and filtering configuration."""

        model = models.NVLinkDomainProtocol
        fields = "__all__"
        filterset_class = filters.NVLinkDomainProtocolFilterSet


class NVLinkDomainTopologyType(OptimizedNautobotObjectType):
    """Configurable NVLink topology details."""

    class Meta:
        """Model and filtering configuration."""

        model = models.NVLinkDomainTopology
        fields = "__all__"
        filterset_class = filters.NVLinkDomainTopologyFilterSet


class NVLinkDomainType(OptimizedNautobotObjectType):
    """Domain fields with backwards-compatible scalar reference names."""

    topology = graphene.String(description="Topology name, or null when unassigned.")
    protocol = graphene.String(description="Protocol name, or null when unassigned.")
    nvlink_domain_topology = graphene.Field(NVLinkDomainTopologyType)
    nvlink_domain_protocol = graphene.Field(NVLinkDomainProtocolType)

    class Meta:
        """Model and filtering configuration."""

        model = models.NVLinkDomain
        fields = "__all__"
        filterset_class = filters.NVLinkDomainFilterSet

    @gql_optimizer.resolver_hints(select_related="topology", only=("topology__name",))
    def resolve_topology(self, info):
        """Return the same topology identifier as the REST API."""
        return self.topology.name if self.topology_id else None

    @gql_optimizer.resolver_hints(select_related="protocol", only=("protocol__name",))
    def resolve_protocol(self, info):
        """Return the same protocol identifier as the REST API."""
        return self.protocol.name if self.protocol_id else None

    @gql_optimizer.resolver_hints(model_field="topology")
    def resolve_nvlink_domain_topology(self, info):
        """Expand topology details only when the user may view the reference."""
        return _visible_reference(self, info, "topology")

    @gql_optimizer.resolver_hints(model_field="protocol")
    def resolve_nvlink_domain_protocol(self, info):
        """Expand protocol details only when the user may view the reference."""
        return _visible_reference(self, info, "protocol")


graphql_types = [NVLinkDomainProtocolType, NVLinkDomainTopologyType, NVLinkDomainType]
