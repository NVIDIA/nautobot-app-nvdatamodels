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

from collections import defaultdict
from collections.abc import Mapping
from copy import copy

from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from nautobot.apps.api import (
    BaseModelSerializer,
    NautobotHyperlinkedRelatedField,
    NautobotModelSerializer,
    TaggedModelSerializerMixin,
)
from nautobot.dcim.models import Rack
from rest_framework import serializers as drf_serializers

from nautobot_nvdatamodels import choices, models
from nautobot_nvdatamodels.lpu_c2c import mutations
from nautobot_nvdatamodels.lpu_c2c.types import ProjectionState


class LPUC2CObjectReferenceSerializer(drf_serializers.Serializer):
    """Serialize a stable reference to a Nautobot object."""

    object_type = drf_serializers.CharField()
    id = drf_serializers.UUIDField()
    display = drf_serializers.CharField()


class LPUC2CDiagnosticSerializer(drf_serializers.Serializer):
    """Serialize one projection diagnostic."""

    severity = drf_serializers.ChoiceField(choices=("error", "warning"))
    code = drf_serializers.CharField()
    message = drf_serializers.CharField()
    affected_objects = LPUC2CObjectReferenceSerializer(many=True)


class _LPUC2CEndpointCoordinateSerializer(drf_serializers.Serializer):
    rack_ordinal = drf_serializers.IntegerField(min_value=0)
    tray_slot = drf_serializers.IntegerField(allow_null=True, min_value=1, max_value=16)


class _LPUC2CRackPositionProjectionSerializer(drf_serializers.Serializer):
    position = LPUC2CObjectReferenceSerializer()
    rack = LPUC2CObjectReferenceSerializer(allow_null=True)


class _LPUC2CEndpointProjectionSerializer(drf_serializers.Serializer):
    device = LPUC2CObjectReferenceSerializer()
    domain = LPUC2CObjectReferenceSerializer()
    coordinate = _LPUC2CEndpointCoordinateSerializer(allow_null=True)


class _LPUC2CProjectionSerializer(drf_serializers.Serializer):
    rack_positions = _LPUC2CRackPositionProjectionSerializer(many=True)
    endpoints = _LPUC2CEndpointProjectionSerializer(many=True)


class LPUC2CProjectionEnvelopeSerializer(drf_serializers.Serializer):
    """Validate the complete domain projection response envelope."""

    domain = LPUC2CObjectReferenceSerializer()
    state = drf_serializers.ChoiceField(choices=("ready", "invalid"))
    projection = _LPUC2CProjectionSerializer(allow_null=True)
    diagnostics = LPUC2CDiagnosticSerializer(many=True)

    def validate(self, attrs):
        """Keep readiness and projection presence consistent."""
        projection = attrs["projection"]
        if attrs["state"] == ProjectionState.READY and projection is None:
            raise drf_serializers.ValidationError({"projection": "A ready evaluation requires a projection."})
        if attrs["state"] == ProjectionState.INVALID and projection is not None:
            raise drf_serializers.ValidationError(
                {"projection": "An invalid evaluation cannot expose a partial projection."}
            )
        return attrs


def _evaluation_references(evaluation):
    yield evaluation.domain
    for rack_position in evaluation.rack_positions:
        yield rack_position.position
        if rack_position.rack is not None:
            yield rack_position.rack
    for endpoint in evaluation.endpoints:
        yield endpoint.device
        yield endpoint.domain
    for diagnostic in evaluation.diagnostics:
        yield from diagnostic.affected_objects


def _reference_displays(evaluation):
    ids_by_type = defaultdict(set)
    for reference in _evaluation_references(evaluation):
        ids_by_type[reference.object_type].add(reference.object_id)

    displays = {}
    for object_type, object_ids in ids_by_type.items():
        model = apps.get_model(object_type)
        for object_id, instance in model._default_manager.in_bulk(object_ids).items():
            displays[(object_type, object_id)] = str(instance)
    return displays


def _serialize_object_reference(reference, displays):
    return {
        "object_type": reference.object_type,
        "id": str(reference.object_id),
        "display": displays[(reference.object_type, reference.object_id)],
    }


def _serialize_coordinate(coordinate):
    if coordinate is None:
        return None
    return {
        "rack_ordinal": coordinate.rack_ordinal,
        "tray_slot": coordinate.tray_slot,
    }


def serialize_evaluation(evaluation):
    """Serialize an LPU C2C evaluation as a domain-level response envelope."""
    displays = _reference_displays(evaluation)
    projection = None
    if evaluation.state == ProjectionState.READY:
        projection = {
            "rack_positions": [
                {
                    "position": _serialize_object_reference(rack_position.position, displays),
                    "rack": (
                        _serialize_object_reference(rack_position.rack, displays)
                        if rack_position.rack is not None
                        else None
                    ),
                }
                for rack_position in evaluation.rack_positions
            ],
            "endpoints": [
                {
                    "device": _serialize_object_reference(endpoint.device, displays),
                    "domain": _serialize_object_reference(endpoint.domain, displays),
                    "coordinate": _serialize_coordinate(endpoint.coordinate),
                }
                for endpoint in evaluation.endpoints
            ],
        }
    envelope = {
        "domain": _serialize_object_reference(evaluation.domain, displays),
        "state": evaluation.state.value,
        "projection": projection,
        "diagnostics": [
            {
                "severity": diagnostic.severity.value,
                "code": diagnostic.code,
                "message": diagnostic.message,
                "affected_objects": [
                    _serialize_object_reference(reference, displays)
                    for reference in diagnostic.affected_objects
                ],
            }
            for diagnostic in evaluation.diagnostics
        ],
    }
    serializer = LPUC2CProjectionEnvelopeSerializer(data=envelope)
    serializer.is_valid(raise_exception=True)
    return serializer.data


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


class LPUC2CDomainSerializer(NautobotModelSerializer, TaggedModelSerializerMixin):  # pylint: disable=too-many-ancestors
    """LPU C2C domain serializer."""

    class Meta:
        """Meta attributes."""

        model = models.LPUC2CDomain
        fields = "__all__"

    def validate(self, attrs):
        """Validate a prospective update against persisted lifecycle state before saving."""
        attrs = super().validate(attrs)
        if self.instance is None:
            status = attrs.get("status")
            if (
                status is not None
                and status.name.removeprefix("LPU C2C ") == choices.LPUC2CDefaultStatusChoices.ACTIVE
            ):
                raise drf_serializers.ValidationError(
                    {"status": "Create the domain in Planned or Maintenance before activating it."}
                )
            return attrs

        candidate = copy(self.instance)
        candidate._state = copy(self.instance._state)
        candidate._state.fields_cache = self.instance._state.fields_cache.copy()
        concrete_field_names = {field.name for field in candidate._meta.concrete_fields}
        for field_name, value in attrs.items():
            if field_name in concrete_field_names:
                setattr(candidate, field_name, value)
        try:
            candidate.full_clean()
        except DjangoValidationError as error:
            detail = (
                error.message_dict if hasattr(error, "message_dict") else {"non_field_errors": error.messages}
            )
            raise drf_serializers.ValidationError(detail) from error
        return attrs


class LPUC2CDomainRackPositionSerializer(BaseModelSerializer):
    """LPU C2C domain rack-position serializer."""

    class Meta:
        """Meta attributes."""

        model = models.LPUC2CDomainRackPosition
        fields = "__all__"


class LPUC2CDeviceTypeCompatibilitySerializer(BaseModelSerializer):
    """LPU C2C device-type compatibility serializer."""

    class Meta:
        """Meta attributes."""

        model = models.LPUC2CDeviceTypeCompatibility
        fields = "__all__"


class LPUC2CEndpointConfigurationSerializer(BaseModelSerializer):
    """LPU C2C endpoint-configuration serializer."""

    class Meta:
        """Meta attributes."""

        model = models.LPUC2CEndpointConfiguration
        fields = "__all__"

    def validate(self, attrs):
        """Reject create payloads that would not persist a configuration."""
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get("excluded", False) and attrs.get("tray_slot") is None:
            raise drf_serializers.ValidationError(
                "Endpoint configuration must exclude or override a coordinate."
            )
        return attrs

    @staticmethod
    def _save_through_mutation_service(validated_data, instance=None):
        values = {
            field: validated_data.get(field, getattr(instance, field) if instance is not None else None)
            for field in ("device", "rack_position", "tray_slot")
        }
        values["excluded"] = validated_data.get(
            "excluded", instance.excluded if instance is not None else False
        )
        try:
            return mutations.set_endpoint_configuration(**values)
        except mutations.DomainMutationNotAllowed as error:
            raise drf_serializers.ValidationError({"detail": str(error)}) from error
        except DjangoValidationError as error:
            detail = error.message_dict if hasattr(error, "message_dict") else {"detail": error.messages}
            raise drf_serializers.ValidationError(detail) from error

    def create(self, validated_data):
        """Create only through the lifecycle-safe endpoint mutation."""
        return self._save_through_mutation_service(validated_data)

    def update(self, instance, validated_data):
        """Update only through the lifecycle-safe endpoint mutation."""
        requested_device = validated_data.get("device", instance.device)
        if requested_device.pk != instance.device_id:
            raise drf_serializers.ValidationError(
                {"device": "An endpoint configuration cannot be reassigned to another device."}
            )
        validated_data["device"] = instance.device
        return self._save_through_mutation_service(validated_data, instance=instance)


class LPUC2CRackPositionOperationSerializer(drf_serializers.Serializer):
    """Validate the public rack-position operation payload."""

    ALLOWED_FIELDS_BY_OPERATION = {
        "append": {"operation", "rack"},
        "fill": {"operation", "ordinal", "rack"},
        "vacate": {"operation", "ordinal"},
        "remove_and_compact": {"operation", "ordinal", "confirmed"},
        "insert": {"operation", "ordinal", "rack", "confirmed"},
        "reorder": {"operation", "ordering", "confirmed"},
    }

    operation = drf_serializers.ChoiceField(
        choices=("append", "fill", "vacate", "remove_and_compact", "insert", "reorder")
    )
    ordinal = drf_serializers.IntegerField(min_value=0, required=False)
    rack = drf_serializers.PrimaryKeyRelatedField(
        queryset=Rack.objects.none(), allow_null=True, required=False
    )
    ordering = drf_serializers.ListField(child=drf_serializers.IntegerField(min_value=0), required=False)
    confirmed = drf_serializers.BooleanField(default=False, required=False)

    def __init__(self, *args, **kwargs):
        """Restrict Rack inputs to objects visible to the requesting user."""
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            self.fields["rack"].queryset = Rack.objects.restrict(request.user, "view")

    def to_internal_value(self, data):
        """Reject fields outside the public operation contract."""
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise drf_serializers.ValidationError(
                {field: "Unknown field." for field in sorted(unknown_fields)}
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        """Require the operation-specific fields without exposing position IDs."""
        operation = attrs["operation"]
        errors = {}
        inapplicable_fields = set(self.initial_data) - self.ALLOWED_FIELDS_BY_OPERATION[operation]
        errors.update(
            {field: "This field is not valid for this operation." for field in sorted(inapplicable_fields)}
        )
        if operation in {"fill", "vacate", "remove_and_compact", "insert"} and "ordinal" not in attrs:
            errors["ordinal"] = "This field is required for this operation."
        if operation == "fill" and attrs.get("rack") is None:
            errors["rack"] = "This field is required for this operation."
        if operation == "reorder" and "ordering" not in attrs:
            errors["ordering"] = "This field is required for this operation."
        if errors:
            raise drf_serializers.ValidationError(errors)
        return attrs
