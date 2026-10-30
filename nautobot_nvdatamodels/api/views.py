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

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from nautobot.apps.api import ModelViewSet, NautobotModelViewSet, ReadOnlyModelViewSet
from nautobot.core.api.authentication import TokenPermissions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.response import Response

from nautobot_nvdatamodels import filters, models
from nautobot_nvdatamodels.api import serializers
from nautobot_nvdatamodels.lpu_c2c import mutations
from nautobot_nvdatamodels.lpu_c2c.evaluator import (
    ProjectionPermissionDenied,
    evaluate_domain,
)


class LPUC2CDomainChangeTokenPermissions(TokenPermissions):
    """Require Domain change permission for the POST detail operation."""

    perms_map = {
        **TokenPermissions.perms_map,
        "POST": ["%(app_label)s.change_%(model_name)s"],
    }


def _apply_rack_position_operation(domain, data):
    operation = data.get("operation")
    if operation == "append":
        return mutations.append_position(domain, rack=data.get("rack"))
    if operation == "fill":
        position = _position_at_ordinal(domain, data["ordinal"])
        return mutations.fill_position(position, data["rack"])
    if operation == "vacate":
        return mutations.vacate_position(_position_at_ordinal(domain, data["ordinal"]))
    if operation == "remove_and_compact":
        return mutations.remove_and_compact_position(
            _position_at_ordinal(domain, data["ordinal"]), confirmed=data["confirmed"]
        )
    if operation == "insert":
        return mutations.insert_position(
            domain,
            data["ordinal"],
            data.get("rack"),
            confirmed=data["confirmed"],
        )
    if operation == "reorder":
        positions_by_ordinal = {
            position.ordinal: position
            for position in domain.rack_positions.filter(ordinal__in=data["ordering"])
        }
        if set(positions_by_ordinal) != set(data["ordering"]):
            raise ValidationError({"ordering": "Every ordinal must belong to the URL domain."})
        return mutations.reorder_positions(
            domain,
            [positions_by_ordinal[ordinal].pk for ordinal in data["ordering"]],
            confirmed=data["confirmed"],
        )
    raise ValidationError({"operation": "Unsupported rack-position operation."})


def _position_at_ordinal(domain, ordinal):
    try:
        return domain.rack_positions.get(ordinal=ordinal)
    except models.LPUC2CDomainRackPosition.DoesNotExist as error:
        raise ValidationError({"ordinal": "Ordinal does not belong to the URL domain."}) from error


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


class LPUC2CDomainViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """LPU C2C domain viewset."""

    queryset = models.LPUC2CDomain.objects.all()
    serializer_class = serializers.LPUC2CDomainSerializer
    filterset_class = filters.LPUC2CDomainFilterSet

    def get_queryset(self):
        """Lock the domain row while validating and saving an update."""
        queryset = super().get_queryset()
        if self.action in {"update", "partial_update"}:
            return queryset.select_for_update(of=("self",))
        return queryset

    def bulk_update(self, request, *args, **kwargs):
        """Reject bulk updates that could bypass controlled activation."""
        raise MethodNotAllowed(request.method)

    def bulk_partial_update(self, request, *args, **kwargs):
        """Reject bulk partial updates that could bypass controlled activation."""
        raise MethodNotAllowed(request.method)

    def update(self, request, *args, **kwargs):
        """Apply an Active transition atomically through controlled activation."""
        try:
            with transaction.atomic():
                return super().update(request, *args, **kwargs)
        except mutations.InvalidTopologyProjection as error:
            diagnostics = [
                {
                    "severity": diagnostic.severity.value,
                    "code": diagnostic.code,
                    "message": diagnostic.message,
                }
                for diagnostic in error.diagnostics
            ]
            raise ValidationError({"detail": str(error), "diagnostics": diagnostics}) from error
        except mutations.DomainMutationNotAllowed as error:
            raise ValidationError({"detail": str(error)}) from error
        except DjangoValidationError as error:
            detail = error.message_dict if hasattr(error, "message_dict") else {"detail": error.messages}
            raise ValidationError(detail) from error

    def perform_update(self, serializer):
        """Save ordinary fields before delegating an Active status transition."""
        try:
            requested_status = serializer.validated_data.get("status")
            activate = False
            if requested_status is not None and requested_status.name.removeprefix("LPU C2C ") == "Active":
                persisted_status_id, persisted_status_name = (
                    models.LPUC2CDomain.objects.only("status_id")
                    .values_list("status_id", "status__name")
                    .get(pk=serializer.instance.pk)
                )
                activate = persisted_status_name.removeprefix("LPU C2C ") != "Active"
                if activate:
                    serializer.validated_data.pop("status")
                    serializer.instance.status_id = persisted_status_id
            serializer.save()
            if activate:
                serializer.instance = mutations.activate_domain(serializer.instance.pk)
            self._validate_objects(serializer.instance)
        except ObjectDoesNotExist as error:
            raise PermissionDenied() from error

    @action(detail=True, methods=["get"], url_path="topology-projection")
    def topology_projection(self, request, pk=None):
        """Return the derived topology projection."""
        try:
            evaluation = evaluate_domain(
                self.get_object(), user=request.user, require_complete_visibility=True
            )
        except ProjectionPermissionDenied as error:
            raise PermissionDenied(str(error)) from error
        return Response(serializers.serialize_evaluation(evaluation))

    @action(
        detail=True,
        methods=["post"],
        url_path="rack-position-operation",
        permission_classes=[LPUC2CDomainChangeTokenPermissions],
    )
    def rack_position_operation(self, request, pk=None):
        """Apply a lifecycle-safe rack-position operation."""
        domain = get_object_or_404(
            models.LPUC2CDomain.objects.restrict(request.user, "change"),
            pk=pk,
        )
        self.check_object_permissions(request, domain)
        input_serializer = serializers.LPUC2CRackPositionOperationSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        input_serializer.is_valid(raise_exception=True)
        try:
            result = _apply_rack_position_operation(domain, input_serializer.validated_data)
        except (mutations.ConfirmationRequired, mutations.DomainMutationNotAllowed) as error:
            raise ValidationError({"detail": str(error)}) from error
        except DjangoValidationError as error:
            detail = error.message_dict if hasattr(error, "message_dict") else {"detail": error.messages}
            raise ValidationError(detail) from error
        return Response({"id": str(result.pk) if result is not None else None})


class LPUC2CDomainRackPositionViewSet(ReadOnlyModelViewSet):  # pylint: disable=too-many-ancestors
    """Read-only LPU C2C rack-position viewset."""

    queryset = models.LPUC2CDomainRackPosition.objects.all()
    serializer_class = serializers.LPUC2CDomainRackPositionSerializer
    filterset_class = filters.LPUC2CDomainRackPositionFilterSet


class LPUC2CDeviceTypeCompatibilityViewSet(ModelViewSet):  # pylint: disable=too-many-ancestors
    """LPU C2C device-type compatibility viewset."""

    queryset = models.LPUC2CDeviceTypeCompatibility.objects.all()
    serializer_class = serializers.LPUC2CDeviceTypeCompatibilitySerializer
    filterset_class = filters.LPUC2CDeviceTypeCompatibilityFilterSet


class LPUC2CEndpointConfigurationViewSet(ModelViewSet):  # pylint: disable=too-many-ancestors
    """LPU C2C endpoint-configuration viewset."""

    queryset = models.LPUC2CEndpointConfiguration.objects.all()
    serializer_class = serializers.LPUC2CEndpointConfigurationSerializer
    filterset_class = filters.LPUC2CEndpointConfigurationFilterSet

    @extend_schema(exclude=True)
    def bulk_update(self, request, *args, **kwargs):
        """Reject generic list-level updates."""
        raise MethodNotAllowed(request.method)

    @extend_schema(exclude=True)
    def bulk_partial_update(self, request, *args, **kwargs):
        """Reject generic list-level partial updates."""
        raise MethodNotAllowed(request.method)

    @extend_schema(exclude=True)
    def bulk_destroy(self, request, *args, **kwargs):
        """Reject generic list-level deletes."""
        raise MethodNotAllowed(request.method)

    def update(self, request, *args, **kwargs):
        """Return an intentional empty response when an update removes a no-op record."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                updated_instance = serializer.update(instance, serializer.validated_data)
                serializer.instance = updated_instance
                if updated_instance is not None:
                    self._validate_objects(updated_instance)
        except ObjectDoesNotExist as error:
            raise PermissionDenied() from error
        if updated_instance is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}
        return Response(serializer.data)

    def perform_destroy(self, instance):
        """Delete only through the lifecycle-safe no-op configuration path."""
        try:
            mutations.set_endpoint_configuration(instance.device_id, instance.rack_position_id)
        except mutations.DomainMutationNotAllowed as error:
            raise ValidationError({"detail": str(error)}) from error
        except DjangoValidationError as error:
            detail = error.message_dict if hasattr(error, "message_dict") else {"detail": error.messages}
            raise ValidationError(detail) from error
