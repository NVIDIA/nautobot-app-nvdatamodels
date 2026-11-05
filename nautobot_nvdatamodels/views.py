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
"""Views for nautobot_nvdatamodels."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import RequestConfig
from nautobot.apps import views
from nautobot.apps.config import get_app_settings_or_config
from nautobot.core.utils.requests import normalize_querydict
from nautobot.core.views import generic
from nautobot.dcim.choices import DeviceFaceChoices
from nautobot.dcim.models import Device, Rack
from nautobot.dcim.tables import DeviceTable

from nautobot_nvdatamodels import filters, forms, models, tables
from nautobot_nvdatamodels.api import serializers


class NVLinkDomainUIViewSet(views.NautobotUIViewSet):
    """ViewSet for NVLinkDomain views."""

    bulk_update_form_class = forms.NVLinkDomainBulkEditForm
    filterset_class = filters.NVLinkDomainFilterSet
    filterset_form_class = forms.NVLinkDomainFilterForm
    form_class = forms.NVLinkDomainForm
    lookup_field = "pk"
    queryset = models.NVLinkDomain.objects.select_related("protocol", "topology")
    serializer_class = serializers.NVLinkDomainSerializer
    table_class = tables.NVLinkDomainTable

    def get_extra_context(self, request, instance):
        """Get extra context for the NVLinkDomain view."""
        hidden_statuses = list(
            get_app_settings_or_config("nautobot_nvdatamodels", "hidden_member_statuses") or []
        )
        show_hidden_members = request.GET.get("show_hidden_members", "").lower() in ("true", "1", "yes")
        all_members = Device.objects.restrict(request.user, "view").filter(nvlink_domain=instance)
        hidden_members = all_members.filter(status__name__in=hidden_statuses)
        devices = (
            all_members if show_hidden_members else all_members.exclude(status__name__in=hidden_statuses)
        )
        device_table = tables.NVLinkDomainMemberTable(devices, orderable=False, user=request.user)
        RequestConfig(request, paginate={"per_page": 10}).configure(device_table)
        # The paginator has already counted ``devices``; reuse it rather than issuing a second COUNT(*).
        member_count = device_table.paginator.count
        hidden_member_count = hidden_members.count()
        # Toggle URLs keep any other query parameters (e.g. ``tab``) intact.
        show_params = request.GET.copy()
        show_params["show_hidden_members"] = "true"
        hide_params = request.GET.copy()
        hide_params.pop("show_hidden_members", None)
        show_hidden_url = f"{request.path}?{show_params.urlencode()}"
        hide_hidden_url = f"{request.path}?{hide_params.urlencode()}" if hide_params else request.path
        if request.user.has_perm("nautobot_nvdatamodels.change_nvlinkdomain"):
            device_table.columns.show("pk")

        rack_face = request.GET.get("face", DeviceFaceChoices.FACE_FRONT)
        if rack := getattr(instance, "rack", None):
            racks = [rack]
        elif rack_groups := getattr(instance, "rack_group", None):
            racks = list(Rack.objects.filter(rack_group=rack_groups))
        else:
            racks = []

        return {
            "device_table": device_table,
            "member_count": member_count,
            "hidden_member_count": hidden_member_count,
            "hidden_status_label": ", ".join(hidden_statuses),
            "show_hidden_members": show_hidden_members,
            "show_hidden_url": show_hidden_url,
            "hide_hidden_url": hide_hidden_url,
            "rack_face": rack_face,
            "racks": racks,
            **super().get_extra_context(request, instance),
        }


class NVLinkDomainAddDevicesView(generic.ObjectEditView):
    """Add devices to an NVLink domain."""

    queryset = models.NVLinkDomain.objects.select_related("protocol", "topology")
    form = forms.NVLinkDomainAddDevicesForm
    template_name = "nautobot_nvdatamodels/nvlinkdomain_add_devices.html"

    def get(self, request, *args, **kwargs):
        """Get request to add devices to an NVLink domain."""
        nvlinkdomain = get_object_or_404(self.queryset, pk=kwargs["pk"])
        form = self.form(nvlinkdomain, initial=normalize_querydict(request.GET, form_class=self.form))

        return render(
            request,
            self.template_name,
            {
                "nvlinkdomain": nvlinkdomain,
                "form": form,
                "return_url": reverse(
                    "plugins:nautobot_nvdatamodels:nvlinkdomain", kwargs={"pk": kwargs["pk"]}
                ),
            },
        )

    def post(self, request, *args, **kwargs):
        """Post request to add devices to an NVLink domain."""
        nvlinkdomain = get_object_or_404(self.queryset, pk=kwargs["pk"])
        form = self.form(nvlinkdomain, request.POST)

        if form.is_valid():
            device_pks = form.cleaned_data["devices"]
            with transaction.atomic():
                # Assign the selected Devices to the NVLink Domain
                devices_to_add = Device.objects.filter(pk__in=device_pks)
                nvlinkdomain.members.add(*devices_to_add)

            messages.success(
                request,
                f"Added {len(device_pks)} devices to NVLink Domain {nvlinkdomain}",
            )
            return redirect(nvlinkdomain.get_absolute_url())

        return render(
            request,
            self.template_name,
            {
                "nvlinkdomain": nvlinkdomain,
                "form": form,
                "return_url": nvlinkdomain.get_absolute_url(),
            },
        )


class NVLinkDomainRemoveDevicesView(generic.ObjectEditView):
    """Remove devices from an NVLink domain."""

    queryset = models.NVLinkDomain.objects.select_related("protocol", "topology")
    form = forms.NVLinkDomainRemoveDevicesForm
    template_name = "nautobot_nvdatamodels/object_bulk_remove.html"

    def post(self, request, *args, **kwargs):
        """Post request to remove devices from an NVLink domain."""
        nvlinkdomain = get_object_or_404(self.queryset, pk=kwargs["pk"])

        if "_confirm" in request.POST:
            form = self.form(request.POST)
            if form.is_valid():
                device_pks = form.cleaned_data["pk"]
                with transaction.atomic():
                    # Remove the selected Devices from the NVLink Domain
                    devices_to_remove = Device.objects.filter(pk__in=device_pks)
                    nvlinkdomain.members.remove(*devices_to_remove)

                messages.success(
                    request,
                    f"Removed {len(device_pks)} devices from NVLink Domain {nvlinkdomain}",
                )
                return redirect(nvlinkdomain.get_absolute_url())

        else:
            form = self.form(initial={"pk": request.POST.getlist("pk")})

        selected_objects = Device.objects.filter(pk__in=form.initial["pk"])
        device_table = DeviceTable(selected_objects, orderable=False)
        RequestConfig(request, paginate={"per_page": 10}).configure(device_table)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "parent_obj": nvlinkdomain,
                "parent_obj_type": models.NVLinkDomain._meta.verbose_name,
                "table": device_table,
                "obj_type": Device._meta.verbose_name
                if len(selected_objects) == 1
                else Device._meta.verbose_name_plural,
                "return_url": nvlinkdomain.get_absolute_url(),
            },
        )


class NVLinkDomainMembershipUIViewSet(
    views.ObjectListViewMixin,
    views.ObjectEditViewMixin,
    views.ObjectDestroyViewMixin,
    views.ObjectBulkDestroyViewMixin,
):
    """ViewSet for NVLinkDomainMembership views."""

    action_buttons = ("add",)
    lookup_field = "pk"
    form_class = forms.NVLinkDomainMembershipForm
    filterset_form_class = forms.NVLinkDomainMembershipFilterForm
    queryset = models.NVLinkDomainMembership.objects.all()
    table_class = tables.NVLinkDomainMembershipTable
    filterset_class = filters.NVLinkDomainMembershipFilterSet
    template_name = "nautobot_nvdatamodels/nvlinkdomainmembership_create.html"


class ResourceBlockUIViewSet(views.NautobotUIViewSet):
    """ViewSet for ResourceBlock views."""

    bulk_update_form_class = forms.ResourceBlockBulkEditForm
    filterset_class = filters.ResourceBlockFilterSet
    filterset_form_class = forms.ResourceBlockFilterForm
    form_class = forms.ResourceBlockForm
    lookup_field = "pk"
    queryset = models.ResourceBlock.objects.all()
    serializer_class = serializers.ResourceBlockSerializer
    table_class = tables.ResourceBlockTable

    def get_extra_context(self, request, instance):
        """Get extra context for the ResourceBlock view."""
        context = super().get_extra_context(request, instance)

        if instance:
            static_devices = instance.get_static_devices().restrict(request.user, "view")
            static_device_table = DeviceTable(static_devices, orderable=False, prefix="static-")
            RequestConfig(request, paginate={"per_page": 10}).configure(static_device_table)
            if request.user.has_perm("nautobot_nvdatamodels.change_resourceblock"):
                static_device_table.columns.show("pk")
            context["static_device_table"] = static_device_table

            dynamic_devices = instance.get_dynamic_devices().restrict(request.user, "view")
            dynamic_device_table = DeviceTable(dynamic_devices, orderable=False, prefix="dynamic-")
            RequestConfig(request, paginate={"per_page": 10}).configure(dynamic_device_table)
            context["dynamic_device_table"] = dynamic_device_table

        return context


class ResourceBlockAddDevicesView(generic.ObjectEditView):
    """Add devices to a Resource Block."""

    queryset = models.ResourceBlock.objects.all()
    form = forms.ResourceBlockAddDevicesForm
    template_name = "nautobot_nvdatamodels/resourceblock_add_devices.html"

    def get(self, request, *args, **kwargs):
        """Get request to add devices to a Resource Block."""
        resourceblock = get_object_or_404(self.queryset, pk=kwargs["pk"])
        form = self.form(resourceblock, initial=normalize_querydict(request.GET, form_class=self.form))

        return render(
            request,
            self.template_name,
            {
                "resourceblock": resourceblock,
                "form": form,
                "return_url": reverse(
                    "plugins:nautobot_nvdatamodels:resourceblock", kwargs={"pk": kwargs["pk"]}
                ),
            },
        )

    def post(self, request, *args, **kwargs):
        """Post request to add devices to a Resource Block."""
        resourceblock = get_object_or_404(self.queryset, pk=kwargs["pk"])
        form = self.form(resourceblock, request.POST)

        if form.is_valid():
            device_pks = form.cleaned_data["devices"]
            with transaction.atomic():
                devices_to_add = Device.objects.filter(pk__in=device_pks)
                resourceblock.devices.add(*devices_to_add)

            messages.success(
                request,
                f"Added {len(device_pks)} devices to Resource Block {resourceblock}",
            )
            return redirect(resourceblock.get_absolute_url())

        return render(
            request,
            self.template_name,
            {
                "resourceblock": resourceblock,
                "form": form,
                "return_url": resourceblock.get_absolute_url(),
            },
        )


class ResourceBlockRemoveDevicesView(generic.ObjectEditView):
    """Remove devices from a Resource Block."""

    queryset = models.ResourceBlock.objects.all()
    form = forms.ResourceBlockRemoveDevicesForm
    template_name = "nautobot_nvdatamodels/object_bulk_remove.html"

    def post(self, request, *args, **kwargs):
        """Post request to remove devices from a Resource Block."""
        resourceblock = get_object_or_404(self.queryset, pk=kwargs["pk"])

        if "_confirm" in request.POST:
            form = self.form(request.POST)
            if form.is_valid():
                device_pks = form.cleaned_data["pk"]
                with transaction.atomic():
                    devices_to_remove = Device.objects.filter(pk__in=device_pks)
                    resourceblock.devices.remove(*devices_to_remove)

                messages.success(
                    request,
                    f"Removed {len(device_pks)} devices from Resource Block {resourceblock}",
                )
                return redirect(resourceblock.get_absolute_url())

        else:
            form = self.form(initial={"pk": request.POST.getlist("pk")})

        selected_objects = Device.objects.filter(pk__in=form.initial["pk"])
        device_table = DeviceTable(selected_objects, orderable=False)
        RequestConfig(request, paginate={"per_page": 10}).configure(device_table)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "parent_obj": resourceblock,
                "parent_obj_type": models.ResourceBlock._meta.verbose_name,
                "table": device_table,
                "obj_type": Device._meta.verbose_name
                if len(selected_objects) == 1
                else Device._meta.verbose_name_plural,
                "return_url": resourceblock.get_absolute_url(),
            },
        )


class ResourceBlockMembershipUIViewSet(
    views.ObjectListViewMixin,
    views.ObjectEditViewMixin,
    views.ObjectDestroyViewMixin,
    views.ObjectBulkDestroyViewMixin,
):
    """ViewSet for ResourceBlockMembership views."""

    action_buttons = ("add",)
    lookup_field = "pk"
    form_class = forms.ResourceBlockMembershipForm
    filterset_form_class = forms.ResourceBlockMembershipFilterForm
    queryset = models.ResourceBlockMembership.objects.all()
    table_class = tables.ResourceBlockMembershipTable
    filterset_class = filters.ResourceBlockMembershipFilterSet
    template_name = "nautobot_nvdatamodels/resourceblockmembership_create.html"


class NVLinkDomainProtocolUIViewSet(views.NautobotUIViewSet):
    """Manage NVLink domain protocol entries."""

    queryset = models.NVLinkDomainProtocol.objects.all()
    form_class = forms.NVLinkDomainProtocolForm
    filterset_class = filters.NVLinkDomainProtocolFilterSet
    filterset_form_class = forms.NVLinkDomainProtocolFilterForm
    serializer_class = serializers.NVLinkDomainProtocolSerializer
    table_class = tables.NVLinkDomainProtocolTable


class NVLinkDomainTopologyUIViewSet(views.NautobotUIViewSet):
    """Manage NVLink domain topology entries."""

    queryset = models.NVLinkDomainTopology.objects.all()
    form_class = forms.NVLinkDomainTopologyForm
    filterset_class = filters.NVLinkDomainTopologyFilterSet
    filterset_form_class = forms.NVLinkDomainTopologyFilterForm
    serializer_class = serializers.NVLinkDomainTopologySerializer
    table_class = tables.NVLinkDomainTopologyTable
