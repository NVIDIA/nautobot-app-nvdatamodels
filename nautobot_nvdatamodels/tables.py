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
"""Tables for nautobot_nvdatamodels."""

import django_tables2 as tables
from nautobot.apps.tables import BaseTable, ButtonsColumn, ToggleColumn
from nautobot.core.tables import LinkedCountColumn, TagColumn
from nautobot.extras.tables import RoleTableMixin, StatusTableMixin

from nautobot_nvdatamodels import models


class NVLinkDomainTable(RoleTableMixin, StatusTableMixin, BaseTable):
    # pylint: disable=R0903
    """Table for list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    member_count = LinkedCountColumn(
        viewname="dcim:device_list",
        url_params={"nautobot_nvdatamodels_nvlink_domain": "pk"},
        verbose_name="Members",
        reverse_lookup="nvlink_domain",
    )
    rack = tables.Column(linkify=True)
    rack_group = tables.Column(linkify=True, verbose_name="Rack Group")
    cluster_id = tables.Column()
    protocol = tables.Column()
    tags = TagColumn(url_name="plugins:nautobot_nvdatamodels:nvlinkdomain_list")
    actions = ButtonsColumn(models.NVLinkDomain)

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.NVLinkDomain
        fields = (
            "pk",
            "name",
            "status",
            "role",
            "protocol",
            "topology",
            "rack",
            "rack_group",
            "member_count",
            "cluster_id",
            "tenant",
            "tags",
            "actions",
        )

        default_columns = (
            "pk",
            "name",
            "status",
            "role",
            "topology",
            "rack",
            "rack_group",
            "member_count",
            "cluster_id",
            "actions",
        )


class NVLinkDomainMembershipTable(BaseTable):
    """Table for list view."""

    pk = ToggleColumn()
    domain = tables.Column(linkify=True, verbose_name="NVLink Domain")
    member = tables.Column(linkify=True)
    actions = ButtonsColumn(models.NVLinkDomainMembership, pk_field="pk", buttons=("edit", "delete"))

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.NVLinkDomainMembership
        fields = (
            "pk",
            "domain",
            "member",
        )


class ResourceBlockTable(RoleTableMixin, StatusTableMixin, BaseTable):
    """Table for ResourceBlock list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    device_count = tables.Column(verbose_name="Total Devices")
    static_device_count = tables.TemplateColumn(
        template_code="""
        {% load helpers %}
        {% if record.static_device_count > 0 %}
            <a href="{% url 'dcim:device_list' %}?nautobot_nvdatamodels_resource_block={{ record.pk }}" class="badge">{{ record.static_device_count }}</a>
        {% else %}
            <span class="badge">0</span>
        {% endif %}
        """,
        verbose_name="Static Devices",
        accessor="static_device_count",
    )
    dynamic_device_count = tables.TemplateColumn(
        template_code="""
        {% load helpers %}
        {% if record.dynamic_device_count > 0 %}
            <a href="{% url 'dcim:device_list' %}?dynamic_groups={{ record.dynamic_group.pk }}" class="badge">{{ record.dynamic_device_count }}</a>
        {% else %}
            <span class="badge">0</span>
        {% endif %}
        """,
        verbose_name="Dynamic Devices",
        accessor="dynamic_device_count",
    )
    dynamic_group = tables.Column(linkify=True, verbose_name="Dynamic Group")
    location = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    protocol = tables.Column()
    tags = TagColumn(url_name="plugins:nautobot_nvdatamodels:resourceblock_list")
    actions = ButtonsColumn(models.ResourceBlock)

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.ResourceBlock
        fields = (
            "pk",
            "name",
            "status",
            "role",
            "protocol",
            "location",
            "tenant",
            "device_count",
            "static_device_count",
            "dynamic_device_count",
            "dynamic_group",
            "tags",
            "actions",
        )

        default_columns = (
            "pk",
            "name",
            "status",
            "role",
            "protocol",
            "location",
            "tenant",
            "device_count",
            "static_device_count",
            "dynamic_device_count",
            "dynamic_group",
            "actions",
        )


class ResourceBlockMembershipTable(BaseTable):
    """Table for ResourceBlockMembership list view."""

    pk = ToggleColumn()
    resource_block = tables.Column(linkify=True, verbose_name="Resource Block")
    device = tables.Column(linkify=True)
    actions = ButtonsColumn(models.ResourceBlockMembership, pk_field="pk", buttons=("edit", "delete"))

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.ResourceBlockMembership
        fields = (
            "pk",
            "resource_block",
            "device",
        )
