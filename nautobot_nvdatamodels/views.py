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

from dataclasses import dataclass

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import RequestConfig
from nautobot.apps import views
from nautobot.core.forms import restrict_form_fields
from nautobot.core.utils.requests import normalize_querydict
from nautobot.core.views import generic
from nautobot.dcim.choices import DeviceFaceChoices
from nautobot.dcim.models import Device, Rack
from nautobot.dcim.tables import DeviceTable

from nautobot_nvdatamodels import filters, forms, models, tables
from nautobot_nvdatamodels.api import serializers
from nautobot_nvdatamodels.lpu_c2c import mutations
from nautobot_nvdatamodels.lpu_c2c.evaluator import ProjectionPermissionDenied, evaluate_domain


@dataclass(frozen=True)
class LPUC2CRackPositionRow:
    """Resolved presentation row for one evaluated rack ordinal."""

    ordinal: int
    rack: Rack | None


@dataclass(frozen=True)
class LPUC2CEndpointRow:
    """Resolved presentation row for one evaluated endpoint."""

    device: Device
    coordinate: object
    can_change_domain: bool
    return_url: str

    @property
    def coordinate_display(self):
        """Render a compact, topology-neutral coordinate label."""
        if self.coordinate is None:
            return "Unavailable"
        parts = [f"Rack {self.coordinate.rack_ordinal}"]
        if self.coordinate.tray_slot is not None:
            parts.append(f"Tray {self.coordinate.tray_slot}")
        return " / ".join(parts)


def _add_service_error(form, error):
    """Map service-layer validation errors onto a workflow form."""
    if isinstance(error, ValidationError) and hasattr(error, "message_dict"):
        for field_name, field_errors in error.message_dict.items():
            target = field_name if field_name in form.fields else None
            for field_error in field_errors:
                form.add_error(target, field_error)
        return
    messages_list = getattr(error, "messages", None) or [str(error)]
    for message in messages_list:
        form.add_error(None, message)


def _lpu_c2c_status_name(status):
    return status.name.removeprefix("LPU C2C ")


class NVLinkDomainUIViewSet(views.NautobotUIViewSet):
    """ViewSet for NVLinkDomain views."""

    bulk_update_form_class = forms.NVLinkDomainBulkEditForm
    filterset_class = filters.NVLinkDomainFilterSet
    filterset_form_class = forms.NVLinkDomainFilterForm
    form_class = forms.NVLinkDomainForm
    lookup_field = "pk"
    queryset = models.NVLinkDomain.objects.all()
    serializer_class = serializers.NVLinkDomainSerializer
    table_class = tables.NVLinkDomainTable

    def get_extra_context(self, request, instance):
        """Get extra context for the NVLinkDomain view."""
        devices = Device.objects.restrict(request.user, "view").filter(nvlink_domain=instance)
        device_table = DeviceTable(devices, orderable=False)
        RequestConfig(request, paginate={"per_page": 10}).configure(device_table)
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
            "rack_face": rack_face,
            "racks": racks,
            **super().get_extra_context(request, instance),
        }


class NVLinkDomainAddDevicesView(generic.ObjectEditView):
    """Add devices to an NVLink domain."""

    queryset = models.NVLinkDomain.objects.all()
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

    queryset = models.NVLinkDomain.objects.all()
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


class LPUC2CDomainUIViewSet(views.NautobotUIViewSet):
    """Standard Domain CRUD plus a single live topology projection on detail."""

    filterset_class = filters.LPUC2CDomainFilterSet
    filterset_form_class = forms.LPUC2CDomainFilterForm
    form_class = forms.LPUC2CDomainForm
    lookup_field = "pk"
    queryset = models.LPUC2CDomain.objects.all()
    serializer_class = serializers.LPUC2CDomainSerializer
    table_class = tables.LPUC2CDomainTable

    def get_extra_context(self, request, instance):
        """Resolve one permission-aware evaluation for the Domain detail page."""
        context = super().get_extra_context(request, instance)
        if self.action != "retrieve" or not instance or not instance.pk:
            return context
        try:
            evaluation = evaluate_domain(instance, user=request.user, require_complete_visibility=True)
        except ProjectionPermissionDenied as error:
            raise Http404 from error
        can_change_domain = (
            models.LPUC2CDomain.objects.restrict(request.user, "change").filter(pk=instance.pk).exists()
        )

        position_ids = [projection.position.object_id for projection in evaluation.rack_positions]
        stored_positions = {
            position.pk: position
            for position in models.LPUC2CDomainRackPosition.objects.filter(
                pk__in=position_ids
            ).select_related("rack")
        }
        rack_position_rows = tuple(
            LPUC2CRackPositionRow(
                ordinal=stored_positions[projection.position.object_id].ordinal,
                rack=stored_positions[projection.position.object_id].rack,
            )
            for projection in evaluation.rack_positions
        )
        rack_position_table = tables.LPUC2CRackPositionProjectionTable(rack_position_rows, orderable=False)
        RequestConfig(request, paginate=False).configure(rack_position_table)

        device_ids = [projection.device.object_id for projection in evaluation.endpoints]
        devices = {device.pk: device for device in Device.objects.filter(pk__in=device_ids)}
        endpoint_rows = tuple(
            LPUC2CEndpointRow(
                device=devices[projection.device.object_id],
                coordinate=projection.coordinate,
                can_change_domain=can_change_domain,
                return_url=instance.get_absolute_url(),
            )
            for projection in evaluation.endpoints
        )
        endpoint_table = tables.LPUC2CEndpointProjectionTable(endpoint_rows, orderable=False)
        RequestConfig(request, paginate=False).configure(endpoint_table)
        context.update(
            {
                "evaluation": evaluation,
                "evaluation_state": evaluation.state,
                "rack_position_rows": rack_position_rows,
                "rack_position_table": rack_position_table,
                "endpoint_rows": endpoint_rows,
                "endpoint_table": endpoint_table,
                "diagnostics": evaluation.diagnostics,
                "can_change_domain": can_change_domain,
            }
        )
        return context

    def form_save(self, form, **kwargs):
        """Persist ordinary fields then perform a real Active transition atomically."""
        requested_status = form.cleaned_data["status"]
        requested_active = _lpu_c2c_status_name(requested_status) == "Active"
        current_status = None
        if form.instance.pk:
            current_status = (
                models.LPUC2CDomain.objects.only("status")
                .select_related("status")
                .get(pk=form.instance.pk)
                .status
            )
        entering_active = requested_active and (
            current_status is None or _lpu_c2c_status_name(current_status) != "Active"
        )
        if not entering_active:
            return super().form_save(form, **kwargs)

        if current_status is None:
            statuses = requested_status.__class__.objects.get_for_model(models.LPUC2CDomain)
            current_status = statuses.filter(name="Planned").first() or statuses.get(name="LPU C2C Planned")
        form.instance.status = current_status
        domain = super().form_save(form, **kwargs)
        try:
            domain = mutations.activate_domain(domain)
        except mutations.InvalidTopologyProjection as error:
            detail = "; ".join(diagnostic.message for diagnostic in error.diagnostics)
            raise ValidationError(f"LPU C2C activation failed: {detail}") from error
        form.instance = domain
        return domain


class LPUC2CDomainRackOperationView(generic.ObjectEditView):
    """Run one explicit lifecycle-safe rack-position operation."""

    queryset = models.LPUC2CDomain.objects.all()
    form = forms.LPUC2CRackOperationForm
    template_name = "nautobot_nvdatamodels/lpuc2cdomain_rack_operation.html"

    def _device(self, request):
        device_id = request.POST.get("device") or request.GET.get("device")
        if not device_id:
            return None
        return get_object_or_404(Device.objects.restrict(request.user, "view"), pk=device_id)

    def _render(self, request, domain, form, device=None):
        return render(
            request,
            self.template_name,
            {
                "domain": domain,
                "device": device,
                "form": form,
                "heading": f"Manage rack positions for {domain}",
                "submit_label": "Apply rack operation",
                "return_url": self.get_return_url(request, domain),
            },
        )

    def get(self, request, *args, **kwargs):
        """Render the bound workflow form."""
        domain = get_object_or_404(self.queryset, pk=kwargs["pk"])
        device = self._device(request)
        form = self.form(domain=domain, device=device)
        restrict_form_fields(form, request.user)
        return self._render(request, domain, form, device)

    def post(self, request, *args, **kwargs):
        """Delegate a valid submission exclusively to the form's service dispatch."""
        domain = get_object_or_404(self.queryset, pk=kwargs["pk"])
        device = self._device(request)
        form = self.form(data=request.POST, domain=domain, device=device)
        restrict_form_fields(form, request.user)
        if form.is_valid():
            try:
                form.save()
            except ObjectDoesNotExist:
                form.add_error(None, "Related objects changed concurrently; retry the operation.")
            except (
                ValidationError,
                mutations.DomainMutationNotAllowed,
                mutations.ConfirmationRequired,
            ) as error:
                _add_service_error(form, error)
            else:
                messages.success(request, f"Updated rack positions for LPU C2C Domain {domain}.")
                return redirect(self.get_return_url(request, domain))
        return self._render(request, domain, form, device)


class LPUC2CEndpointConfigurationView(generic.ObjectEditView):
    """Edit or remove one Device's endpoint exception through its candidate Domain."""

    queryset = models.LPUC2CDomain.objects.all()
    form = forms.LPUC2CEndpointConfigurationForm
    template_name = "nautobot_nvdatamodels/lpuc2cdomain_rack_operation.html"

    def _device_and_form(self, request, *, data=None):
        device = get_object_or_404(Device.objects.restrict(request.user, "view"), pk=self.kwargs["pk"])
        form = self.form(data=data, device=device)
        restrict_form_fields(form, request.user)
        if form.domain is not None:
            get_object_or_404(self.queryset, pk=form.domain.pk)
        if form.rack_position is not None:
            get_object_or_404(
                models.LPUC2CDomainRackPosition.objects.restrict(request.user, "view"),
                pk=form.rack_position.pk,
            )
            if form.rack_position.rack_id:
                get_object_or_404(Rack.objects.restrict(request.user, "view"), pk=form.rack_position.rack_id)
        return device, form

    def _render(self, request, device, form):
        return render(
            request,
            self.template_name,
            {
                "device": device,
                "domain": form.domain,
                "form": form,
                "heading": f"Configure LPU C2C endpoint for {device}",
                "submit_label": "Save endpoint configuration",
                "return_url": self.get_return_url(request, device),
            },
        )

    def get(self, request, *args, **kwargs):
        """Render the Device-first endpoint form."""
        device, form = self._device_and_form(request)
        return self._render(request, device, form)

    def post(self, request, *args, **kwargs):
        """Delegate a valid endpoint edit or removal exclusively to form.save()."""
        device, form = self._device_and_form(request, data=request.POST)
        if form.is_valid():
            try:
                form.save()
            except ObjectDoesNotExist:
                form.add_error(None, "Related objects changed concurrently; retry the operation.")
            except (ValidationError, mutations.DomainMutationNotAllowed) as error:
                _add_service_error(form, error)
            else:
                messages.success(request, f"Updated LPU C2C endpoint configuration for {device}.")
                return redirect(self.get_return_url(request, device))
        return self._render(request, device, form)
