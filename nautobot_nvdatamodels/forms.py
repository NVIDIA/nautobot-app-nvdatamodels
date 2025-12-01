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
"""Forms for nautobot_nvdatamodels."""

from django import forms
from nautobot.apps.forms import (
    BootstrapMixin,
    NautobotBulkEditForm,
    NautobotFilterForm,
    NautobotModelForm,
    StaticSelect2,
    TagsBulkEditFormMixin,
)
from nautobot.core.forms import ConfirmationForm, TagFilterField, add_blank_choice
from nautobot.core.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField
from nautobot.dcim.form_mixins import LocatableModelFormMixin
from nautobot.dcim.models import Device, Location, Rack, RackGroup
from nautobot.extras.models import DynamicGroup, Role, Status
from nautobot.tenancy.forms import TenancyForm
from nautobot.tenancy.models import Tenant, TenantGroup

from nautobot_nvdatamodels import choices, models


class NVLinkDomainForm(TenancyForm, LocatableModelFormMixin, NautobotModelForm):  # pylint: disable=too-many-ancestors
    """NVLinkDomain creation/edit form."""

    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        query_params={"content_type": "nautobot_nvdatamodels.nvlinkdomain"},
    )
    rack_group = DynamicModelChoiceField(
        queryset=RackGroup.objects.all(),
        query_params={"location": "$location"},
        required=False,
        label="Rack Group",
        help_text="Rack group for NVLink domains that span multiple racks",
    )
    rack = DynamicModelChoiceField(
        queryset=Rack.objects.all(),
        query_params={"location": "$location", "rack_group": "$rack_group"},
        required=False,
        label="Rack",
        help_text="Rack for NVLink domains that occupy a single rack",
    )
    members = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        query_params={
            "nautobot_nvdatamodels_nvlink_domain__isnull": True,
            "location": "$location",
            "rack_group": "$rack_group",
            "rack": "$rack",
        },
        required=False,
        label="Members",
        help_text="Devices that participate to this NVLink domain",
    )
    protocol = forms.ChoiceField(
        choices=add_blank_choice(choices.NVLinkDomainProtocolChoices),
        required=False,
        widget=StaticSelect2(),
    )
    topology = forms.ChoiceField(
        choices=add_blank_choice(choices.NVLinkDomainTopologyChoices),
        required=False,
        widget=StaticSelect2(),
    )
    cluster_id = forms.CharField(required=False, label="Cluster ID", help_text="Cluster identifier")

    class Meta:
        """Meta attributes."""

        model = models.NVLinkDomain
        fields = [
            "name",
            "status",
            "role",
            "tenant_group",
            "tenant",
            "location",
            "members",
            "rack",
            "rack_group",
            "protocol",
            "topology",
            "tags",
            "cluster_id",
        ]


class NVLinkDomainBulkEditForm(TagsBulkEditFormMixin, NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """NVLinkDomain bulk edit form."""

    pk = forms.ModelMultipleChoiceField(
        queryset=models.NVLinkDomain.objects.all(), widget=forms.MultipleHiddenInput
    )
    cluster_id = forms.CharField(required=False)

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "cluster_id",
            "topology",
            "protocol",
        ]


class NVLinkDomainFilterForm(NautobotFilterForm):
    """Filter form to filter searches."""

    model = models.NVLinkDomain
    field_order = [
        "q",
        "name",
        "status",
        "role",
        "tenant_group",
        "tenant",
        "location",
        "rack_group",
        "rack",
        "protocol",
        "cluster_id",
        "members",
        "tags",
    ]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within Name, Protocol, and Cluster ID.",
    )
    name = forms.CharField(required=False, label="Name")

    status = DynamicModelMultipleChoiceField(
        queryset=Status.objects.all(),
        query_params={"content_types": models.NVLinkDomain._meta.label_lower},
        required=False,
        label="Status",
    )

    role = DynamicModelMultipleChoiceField(
        queryset=Role.objects.all(),
        query_params={"content_types": models.NVLinkDomain._meta.label_lower},
        required=False,
        label="Role",
    )

    tenant_group = DynamicModelChoiceField(
        queryset=TenantGroup.objects.all(),
        required=False,
        null_option="None",
        label="Tenant Group",
    )

    tenant = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        query_params={"group": "$tenant_group"},
        required=False,
        label="Tenant",
    )

    location = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Location",
    )

    rack_group = DynamicModelMultipleChoiceField(
        queryset=RackGroup.objects.all(),
        query_params={"location": "$location"},
        required=False,
        label="Rack Group",
    )

    rack = DynamicModelMultipleChoiceField(
        queryset=Rack.objects.all(),
        query_params={"location": "$location", "rack_group": "$rack_group"},
        required=False,
        label="Rack",
    )

    protocol = forms.ChoiceField(
        choices=add_blank_choice(choices.NVLinkDomainProtocolChoices),
        required=False,
        widget=StaticSelect2(),
        label="Protocol",
    )

    cluster_id = forms.CharField(
        required=False,
        label="Cluster ID",
        help_text="Filter by cluster identifier",
    )

    members = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        query_params={"location": "$location", "rack": "$rack"},
        required=False,
        label="Member Devices",
    )

    tags = TagFilterField(model)


class NVLinkDomainAddDevicesForm(BootstrapMixin, forms.Form):
    """Add devices to an NVLink domain."""

    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        query_params={"content_type": "nautobot_nvdatamodels.nvlinkdomain"},
    )
    rack = DynamicModelChoiceField(
        queryset=Rack.objects.all(),
        required=False,
        null_option="None",
        query_params={
            "location": "$location",
        },
    )
    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        query_params={
            "location": "$location",
            "rack": "$rack",
            "nautobot_nvdatamodels_nvlink_domain": "null",
        },
    )

    class Meta:
        """Meta attributes."""

        fields = [
            "location",
            "rack",
            "devices",
        ]

    def __init__(self, nvlinkdomain, *args, **kwargs):
        self.nvlinkdomain = nvlinkdomain

        super().__init__(*args, **kwargs)

        self.fields["devices"].choices = []

    def clean(self):
        """Clean the form data."""
        super().clean()

        # If the NVLink Domain is assigned to a Location, all Devices must exist within that Location
        if self.nvlinkdomain.location is not None:
            for device in self.cleaned_data.get("devices", []):
                if device.location and self.nvlinkdomain.location not in device.location.ancestors(
                    include_self=True
                ):
                    raise forms.ValidationError(
                        {
                            "devices": f"{device} belongs to a location ({device.location}) that "
                            f"does not fall within this NVLink domain's location ({self.nvlinkdomain.location})."
                        }
                    )


class NVLinkDomainRemoveDevicesForm(ConfirmationForm):
    """Remove devices from an NVLink domain."""

    pk = forms.ModelMultipleChoiceField(queryset=Device.objects.all(), widget=forms.MultipleHiddenInput())


class NVLinkDomainMembershipForm(forms.ModelForm, BootstrapMixin):  # pylint: disable=too-many-ancestors
    """NVLinkDomainMembership creation/edit form."""

    member = DynamicModelChoiceField(queryset=Device.objects.all(), disabled=True, required=True)
    domain = DynamicModelChoiceField(
        queryset=models.NVLinkDomain.objects.all(), required=True, label="NVLink Domain"
    )
    base_fields = [
        "member",
        "domain",
    ]

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        if request:
            if member_uuid := request.GET.get("member"):
                try:
                    member = Device.objects.get(pk=member_uuid)
                    self.fields["member"] = member
                except Device.DoesNotExist:
                    pass

    class Meta:
        """Meta attributes."""

        model = models.NVLinkDomainMembership
        fields = [
            "member",
            "domain",
        ]


class NVLinkDomainMembershipFilterForm(NautobotFilterForm):
    """Filter form to filter searches."""

    member = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label="Member device",
    )
    domain = DynamicModelMultipleChoiceField(
        queryset=models.NVLinkDomain.objects.all(),
        required=False,
        label="NVLink domain",
    )

    model = models.NVLinkDomainMembership
    field_order = [
        "q",
        "member",
        "domain",
    ]


# ResourceBlock Forms


class ResourceBlockForm(TenancyForm, LocatableModelFormMixin, NautobotModelForm):  # pylint: disable=too-many-ancestors
    """ResourceBlock creation/edit form."""

    protocol = forms.ChoiceField(
        choices=add_blank_choice(choices.ResourceBlockProtocolChoices),
        widget=StaticSelect2(),
        required=False,
    )
    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        query_params={"content_type": "nautobot_nvdatamodels.resourceblock"},
        required=False,
    )
    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        query_params={
            "location": "$location",
            "nautobot_nvdatamodels_resource_block__isnull": True,
        },
        required=False,
        label="Devices",
    )
    dynamic_group = DynamicModelChoiceField(
        queryset=DynamicGroup.objects.all(),
        query_params={"content_type": "dcim.device"},
        required=False,
        label="Dynamic Group",
        help_text="Devices from this dynamic group will be combined with any devices assigned above",
    )

    class Meta:
        """Meta attributes."""

        model = models.ResourceBlock
        fields = [
            "name",
            "status",
            "protocol",
            "role",
            "tenant",
            "location",
            "devices",
            "dynamic_group",
            "tags",
        ]


class ResourceBlockBulkEditForm(TagsBulkEditFormMixin, NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """ResourceBlock bulk edit form."""

    pk = forms.ModelMultipleChoiceField(
        queryset=models.ResourceBlock.objects.all(), widget=forms.MultipleHiddenInput
    )
    protocol = forms.ChoiceField(
        choices=add_blank_choice(choices.ResourceBlockProtocolChoices),
        widget=StaticSelect2(),
        required=False,
    )
    role = DynamicModelChoiceField(
        queryset=Role.objects.all(),
        query_params={"content_types": models.ResourceBlock._meta.label_lower},
        required=False,
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
    )
    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        query_params={"content_type": "nautobot_nvdatamodels.resourceblock"},
        required=False,
    )
    dynamic_group = DynamicModelChoiceField(
        queryset=DynamicGroup.objects.all(),
        query_params={"content_type": "dcim.device"},
        required=False,
    )

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "protocol",
            "role",
            "tenant",
            "location",
            "dynamic_group",
        ]


class ResourceBlockFilterForm(NautobotFilterForm):
    """Filter form to filter searches."""

    model = models.ResourceBlock
    field_order = [
        "q",
        "name",
        "status",
        "role",
        "protocol",
        "location",
        "devices",
        "tags",
    ]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within Name.",
    )
    name = forms.CharField(required=False, label="Name")

    status = DynamicModelMultipleChoiceField(
        queryset=Status.objects.all(),
        query_params={"content_types": models.ResourceBlock._meta.label_lower},
        required=False,
        label="Status",
    )

    role = DynamicModelMultipleChoiceField(
        queryset=Role.objects.all(),
        query_params={"content_types": models.ResourceBlock._meta.label_lower},
        required=False,
        label="Role",
    )

    protocol = forms.ChoiceField(
        choices=add_blank_choice(choices.ResourceBlockProtocolChoices),
        required=False,
        widget=StaticSelect2(),
        label="Protocol",
    )

    location = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Location",
    )

    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        query_params={"location": "$location"},
        required=False,
        label="Devices",
    )

    tags = TagFilterField(model)


class ResourceBlockAddDevicesForm(BootstrapMixin, forms.Form):
    """Add devices to a Resource Block."""

    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        query_params={"content_type": "nautobot_nvdatamodels.resourceblock"},
    )
    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        query_params={
            "location": "$location",
            "nautobot_nvdatamodels_resource_block__isnull": True,
        },
    )

    class Meta:
        """Meta attributes."""

        fields = [
            "location",
            "devices",
        ]

    def __init__(self, resourceblock, *args, **kwargs):
        self.resourceblock = resourceblock

        super().__init__(*args, **kwargs)

        self.fields["devices"].choices = []

    def clean(self):
        """Clean the form data."""
        cleaned_data = super().clean()

        if cleaned_data is None:
            return cleaned_data

        devices = cleaned_data.get("devices", [])

        # If the Resource Block is assigned to a Location, all Devices must exist within that Location
        if self.resourceblock.location is not None:
            for device in devices:
                if device.location and self.resourceblock.location not in device.location.ancestors(
                    include_self=True
                ):
                    raise forms.ValidationError(
                        {
                            "devices": f"{device} belongs to a location ({device.location}) that "
                            f"does not fall within this Resource Block's location ({self.resourceblock.location})."
                        }
                    )


class ResourceBlockRemoveDevicesForm(ConfirmationForm):
    """Remove devices from a Resource Block."""

    pk = forms.ModelMultipleChoiceField(queryset=Device.objects.all(), widget=forms.MultipleHiddenInput())


class ResourceBlockMembershipForm(forms.ModelForm, BootstrapMixin):  # pylint: disable=too-many-ancestors
    """ResourceBlockMembership creation/edit form."""

    device = DynamicModelChoiceField(queryset=Device.objects.all(), disabled=True, required=True)
    resource_block = DynamicModelChoiceField(
        queryset=models.ResourceBlock.objects.all(), required=True, label="Resource Block"
    )
    base_fields = [
        "device",
        "resource_block",
    ]

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        if request:
            if device_uuid := request.GET.get("device"):
                try:
                    device = Device.objects.get(pk=device_uuid)
                    self.fields["device"] = device
                except Device.DoesNotExist:
                    pass

    class Meta:
        """Meta attributes."""

        model = models.ResourceBlockMembership
        fields = [
            "device",
            "resource_block",
        ]


class ResourceBlockMembershipFilterForm(NautobotFilterForm):
    """Filter form to filter searches."""

    device = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label="Member device",
    )
    resource_block = DynamicModelMultipleChoiceField(
        queryset=models.ResourceBlock.objects.all(),
        required=False,
        label="Resource Block",
    )

    model = models.ResourceBlockMembership
    field_order = [
        "q",
        "device",
        "resource_block",
    ]
